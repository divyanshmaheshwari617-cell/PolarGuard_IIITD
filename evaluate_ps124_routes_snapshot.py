"""PS124 observed target-date snapshot evaluation of FINAL saved routes.
Save in the PolarGuard project root, then run python evaluate_ps124_routes_snapshot.py.
No training, model loading, routing or overwriting of existing results.
Not unseen validation: 2021 overlaps the stated model training period.
Snapshot conditions do not represent conditions throughout vessel transit.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import numpy as np

R = 6371.0088


def vectors(latlon):
    a = np.radians(np.asarray(latlon, dtype=float))
    return np.column_stack((np.cos(a[:, 0])*np.cos(a[:, 1]),
                            np.cos(a[:, 0])*np.sin(a[:, 1]), np.sin(a[:, 0])))


def angles(a, b):
    return np.arctan2(np.linalg.norm(np.cross(a, b), axis=-1),
                      np.sum(a*b, axis=-1))


def clean_route(points):
    p = np.asarray(points, dtype=float)
    if p.ndim != 2 or p.shape[1] != 2 or len(p) < 2:
        raise ValueError('Route must contain at least two latitude/longitude points')
    if not np.isfinite(p).all() or (np.abs(p[:, 0]) > 90).any() or (np.abs(p[:, 1]) > 180).any():
        raise ValueError('Invalid route coordinates')
    v = vectors(p)
    p = p[np.r_[True, angles(v[:-1], v[1:]) > 1e-12]]
    if len(p) < 2:
        raise ValueError('Route has zero length')
    if (angles(vectors(p[:-1]), vectors(p[1:])) > np.pi-1e-6).any():
        raise ValueError('Ambiguous near-antipodal segment')
    return p


def sample_route(points, spacing):
    """Midpoints of equal arclength bins; same requested spacing for both routes."""
    if not np.isfinite(spacing) or spacing <= 0:
        raise ValueError('Spacing must be positive')
    p = clean_route(points)
    v = vectors(p)
    arc = angles(v[:-1], v[1:])
    cumulative = np.r_[0., np.cumsum(arc*R)]
    edges = np.r_[np.arange(0., cumulative[-1], spacing), cumulative[-1]]
    weights = np.diff(edges)
    mids = (edges[:-1]+edges[1:])/2
    idx = np.minimum(np.searchsorted(cumulative, mids, side='right')-1, len(arc)-1)
    t = (mids-cumulative[idx])/(arc[idx]*R)
    out = (np.sin((1-t)*arc[idx])[:, None]*v[idx]
           + np.sin(t*arc[idx])[:, None]*v[idx+1])/np.sin(arc[idx])[:, None]
    out /= np.linalg.norm(out, axis=1)[:, None]
    ll = np.column_stack((np.degrees(np.arctan2(out[:, 2], np.hypot(out[:, 0], out[:, 1]))),
                          np.degrees(np.arctan2(out[:, 1], out[:, 0]))))
    return p, ll, weights


def point_to_route_km(points, route):
    """Minimum spherical distance to complete minor great-circle segments."""
    q = vectors(points)
    v = vectors(clean_route(route))
    best = np.full(len(q), np.inf)
    for a, b in zip(v[:-1], v[1:]):
        length = angles(a, b)
        normal = np.cross(a, b)
        normal /= np.linalg.norm(normal)
        d = np.minimum(angles(q, a), angles(q, b))
        proj = q - (q@normal)[:, None]*normal
        norm = np.linalg.norm(proj, axis=1)
        ok = norm > 1e-12
        proj[ok] /= norm[ok, None]
        for candidate in (proj, -proj):
            inside = ok & (angles(a, candidate)+angles(candidate, b) <= length+1e-10)
            d = np.where(inside, np.minimum(d, angles(q, candidate)), d)
        best = np.minimum(best, d)
    return best*R


def score_route(points, spacing, field, xy_transform, iceberg_points):
    route, samples, weights = sample_route(points, spacing)
    x, y = xy_transform.transform(samples[:, 1], samples[:, 0])
    xs, ys = np.asarray(field.x), np.asarray(field.y)
    if len(xs) < 2 or len(ys) < 2:
        raise ValueError('SIC grid too small')
    # Use native projected grid coordinates; out-of-domain points remain missing.
    dx, dy = np.median(np.abs(np.diff(xs))), np.median(np.abs(np.diff(ys)))
    inside = ((x >= xs.min()-dx/2) & (x <= xs.max()+dx/2)
              & (y >= ys.min()-dy/2) & (y <= ys.max()+dy/2))
    import xarray as xr
    sic = np.asarray(field.sel(x=xr.DataArray(x, dims='sample'),
                               y=xr.DataArray(y, dims='sample'), method='nearest'), dtype=float)
    valid = inside & np.isfinite(sic) & (sic >= 0) & (sic <= 1)
    total = weights.sum()
    covered = weights[valid].sum()
    result = {'distance_km': float(total), 'samples': len(samples),
              'sic_valid_distance_pct': float(100*covered/total),
              'actual_mean_sic_pct': float(np.sum(sic[valid]*weights[valid])/covered*100) if covered else np.nan,
              'distance_sic_ge15_pct_of_valid': float(weights[valid & (sic >= .15)].sum()/covered*100) if covered else np.nan,
              'distance_sic_ge80_pct_of_valid': float(weights[valid & (sic >= .80)].sum()/covered*100) if covered else np.nan,
              'min_iceberg_clearance_km': np.nan}
    if len(iceberg_points):
        result['min_iceberg_clearance_km'] = float(point_to_route_km(iceberg_points, route).min())
    return result


def self_test():
    p = np.array([[0., 0.], [0., 2.]])
    _, s, w = sample_route(p, 7.)
    assert abs(w.sum()-R*np.radians(2)) < 1e-8
    assert w.max() <= 7+1e-8 and len(s) == len(w)
    assert abs(point_to_route_km([[1., 1.]], p)[0]-R*np.radians(1)) < 1e-7
    assert point_to_route_km([[0., 1.]], p)[0] < 1e-7
    assert abs(point_to_route_km([[0., 3.]], p)[0]-R*np.radians(1)) < 1e-7
    dateline = [[0., 179.], [0., -179.]]
    assert point_to_route_km([[0., 180.]], dateline)[0] < 1e-7
    _, _, w2 = sample_route(dateline, 1.)
    assert abs(w2.sum()-w.sum()) < 1e-7
    print('PASS: midpoint weights, segment interior/endpoints and dateline checks')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--spacing-km', type=float, default=1.0)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not 0 < args.spacing_km <= 5:
        parser.error('Spacing must be greater than zero and at most 5 km')
    import pandas as pd
    import xarray as xr
    from pyproj import Transformer
    root = args.project_root.resolve()
    frozen = root/'iceberg/outputs/ais_route_validation/ps124_validation_FINAL'
    cases_file = frozen/'selected_cases/ps124_selected_case_definitions.csv'
    sic_file = root/'data/processed/sea_ice_2019_2025.nc'
    iceberg_file = root/'iceberg/data/processed/iceberg_features_environment_ml_ready_2019_2025.csv'
    for path in (cases_file, sic_file, iceberg_file):
        if not path.is_file():
            raise FileNotFoundError(path)
    cases = pd.read_csv(cases_file)
    if len(cases) != 3 or set(cases.horizon_hours) != {24,48,72}:
        raise ValueError('Expected exactly one frozen case per horizon: 24,48,72')
    bergs = pd.read_csv(iceberg_file, parse_dates=['init_date'])
    output = root/'outputs'/('ps124_snapshot_eval_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    output.mkdir(parents=True, exist_ok=False)
    metadata = {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'evaluation': 'Historical 2021 observed target-date snapshot; NOT unseen or voyage safety validation',
        'spacing_km': args.spacing_km,
        'geometry': 'Sphere radius 6371.0088 km; great-circle segments; endpoint connectors included',
        'clearance': 'Minimum spherical distance from observed iceberg points to complete route segments',
        'sic': 'Daily observed SIC; nearest EPSG:3412 cell; midpoint distance-weighted means; missing coverage explicit',
        'limitations': ['No land, bathymetry, vessel capability or transit-time validation',
                       'No iceberg size/uncertainty buffers',
                       'Intraday vessel times compared with daily environmental snapshots',
                       'No provenance audit of original route generation or case selection'],
        'inputs': {}}
    def record(path, hash_file=True):
        metadata['inputs'][str(path)] = {'size_bytes':path.stat().st_size,'mtime_ns':path.stat().st_mtime_ns}
        if hash_file:
            metadata['inputs'][str(path)]['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    record(cases_file)
    record(iceberg_file)
    record(sic_file, False)
    transformer = Transformer.from_crs('EPSG:4326','EPSG:3412',always_xy=True)
    results = []
    def route_file(path):
        record(path)
        df = pd.read_csv(path).rename(columns={'latitude':'lat','longitude':'lon'})
        return clean_route(df[['lat','lon']].to_numpy(float))
    with xr.open_dataset(sic_file) as ds:
        da = ds['sea_ice_concentration'].transpose('time','y','x')
        dates = da.time.values.astype('datetime64[D]')
        for _, case in cases.sort_values('horizon_hours').iterrows():
            h = int(case.horizon_hours)
            row = {'case_id':f'PS124_{h}H','horizon_hours':h,
                   'initialization_date':str(case.initialization_date),
                   'effective_duration_hours':float(case.effective_duration_hours),
                   'evaluation_status':'not_evaluated'}
            try:
                # Deliberately ignore stale segment_file references to the non-FINAL folder.
                ais = route_file(frozen/'selected_cases'/f'ps124_selected_{h}h_actual.csv')
                pg_original = route_file(frozen/'polarguard_results'/f'ps124_polarguard_route_{h}h.csv')
                start = [float(case.start_latitude),float(case.start_longitude)]
                end = [float(case.destination_latitude),float(case.destination_longitude)]
                def distance(a,b):
                    return float(angles(vectors([a])[0],vectors([b])[0])*R)
                if distance(ais[0],start) > .1 or distance(ais[-1],end) > .1:
                    raise ValueError('FINAL AIS endpoints differ from case definition by over 100 m')
                target = np.datetime64(case.initialization_date,'D')+np.timedelta64(h//24,'D')
                if pd.Timestamp(case.requested_end_time).date() != pd.Timestamp(target).date():
                    raise ValueError('Requested end date does not match initialization plus horizon')
                row['target_date'] = str(target)
                ids = np.flatnonzero(dates == target)
                if len(ids) != 1:
                    raise ValueError('Missing or duplicate observed SIC target date')
                field = da.isel(time=int(ids[0])).load()
                row['direct_distance_km'] = distance(start,end)
                row['start_connector_km'] = distance(start,pg_original[0])
                row['end_connector_km'] = distance(pg_original[-1],end)
                pg = np.vstack((start,pg_original,end))
                b = bergs[bergs.init_date.dt.normalize() == pd.Timestamp(case.initialization_date)]
                bp = b[[f'true_lat_{h}h',f'true_lon_{h}h']].to_numpy(float)
                bp = np.unique(bp[np.isfinite(bp).all(axis=1)],axis=0)
                if len(bp) and ((np.abs(bp[:,0])>90).any() or (np.abs(bp[:,1])>180).any()):
                    raise ValueError('Invalid iceberg coordinates')
                row['iceberg_positions'] = len(bp)
                for prefix, route in [('ais',ais),('pg',pg)]:
                    metrics = score_route(route,args.spacing_km,field,transformer,bp)
                    row.update({prefix+'_'+k:v for k,v in metrics.items()})
                if row['pg_distance_km']+1e-6 < row['direct_distance_km']:
                    raise ValueError('Complete route shorter than direct endpoint distance')
                row['distance_saved_pct'] = 100*(1-row['pg_distance_km']/row['ais_distance_km'])
                row['evaluation_status'] = 'complete'
            except Exception as exc:
                row.update(evaluation_status='evaluation_error',reason=f'{type(exc).__name__}: {exc}')
            results.append(row)
            pd.DataFrame(results).to_csv(output/'summary_metrics.csv',index=False)
            (output/'evaluation_metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
            print(f'{row["case_id"]}: {row["evaluation_status"]}',flush=True)
    errors = sum(r['evaluation_status']=='evaluation_error' for r in results)
    print('Results:',output)
    print('Evaluation errors:',errors)
    if errors:
        print('Share the summary including its reason column. Do not exclude failed evaluations.')
        raise SystemExit(1)


if __name__ == '__main__':
    main()
