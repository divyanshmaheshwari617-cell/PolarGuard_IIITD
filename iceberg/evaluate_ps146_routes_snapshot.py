"""Read-only evaluation of saved PS146 routes; writes only a new output folder.

Run from the PolarGuard project root:
    python evaluate_ps146_routes_snapshot.py
Optional: --spacing-km 0.5, --case-id PS146_2025_24H_C4, --self-test

Observed SIC and iceberg positions are a TARGET-DATE SNAPSHOT, not a
time-aligned voyage simulation. No route generation, model loading or fitting.
Sea-ice sampling does not prove land avoidance or navigability. Icebergs are
points (no size or position uncertainty buffer). Segments are great-circle arcs.
"""
from pathlib import Path
import argparse
import hashlib
import json
from datetime import datetime, timezone
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
    parser.add_argument('--spacing-km', type=float, default=1.)
    parser.add_argument('--case-id')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not 0 < args.spacing_km <= 5:
        parser.error('--spacing-km must be greater than zero and at most 5')
    import pandas as pd
    import xarray as xr
    from pyproj import Transformer
    root = args.project_root.resolve()
    val = root/'iceberg/outputs/ais_route_validation/ps146_2025_validation'
    paths = {'cases': val/'selected_cases/ps146_2025_frozen_case_definitions.csv',
             'routing': val/'polarguard_results/ps146_2025_ais_vs_polarguard_summary.csv',
             'icebergs': root/'iceberg/data/processed/iceberg_features_environment_ml_ready_2019_2025.csv',
             'sic': root/'data/processed/test_2025.nc'}
    for p in paths.values():
        if not p.is_file():
            raise FileNotFoundError(p)
    cases = pd.read_csv(paths['cases'])
    routing = pd.read_csv(paths['routing'])
    bergs = pd.read_csv(paths['icebergs'], parse_dates=['init_date'])
    if cases.case_id.duplicated().any() or routing.case_id.duplicated().any():
        raise ValueError('Duplicate case identifiers in input summaries')
    if args.case_id:
        cases = cases[cases.case_id == args.case_id]
        if cases.empty:
            raise ValueError('Requested case not found')
    out = root/'outputs'/('ps146_snapshot_eval_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    out.mkdir(parents=True, exist_ok=False)
    metadata = {'created_utc': datetime.now(timezone.utc).isoformat(), 'spacing_km': args.spacing_km,
                'evaluation': 'Observed target-date snapshot; NOT time-aligned voyage safety validation',
                'geometry': 'Sphere radius 6371.0088 km; great-circle segments; exact point-to-segment iceberg clearance',
                'sic': 'Nearest EPSG:3412 grid cell; 0..1 only; distance-weighted midpoint samples; missing coverage reported',
                'limitations': ['No land, depth, vessel capability or transit-time verification',
                                'Icebergs are observed point locations without size/uncertainty buffers',
                                'Case selection and route generation provenance not audited'],
                'inputs': {k: {'path': str(p), 'size_bytes': p.stat().st_size,
                               'mtime_ns': p.stat().st_mtime_ns} for k,p in paths.items()}}
    for k in ('cases', 'routing', 'icebergs'):
        metadata['inputs'][k]['sha256'] = hashlib.sha256(paths[k].read_bytes()).hexdigest()
    (out/'evaluation_metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    transform = Transformer.from_crs('EPSG:4326', 'EPSG:3412', always_xy=True)
    results = []
    with xr.open_dataset(paths['sic']) as ds:
        da = ds['sea_ice_concentration'].transpose('time','y','x')
        for _, c in cases.iterrows():
            cid = str(c.case_id)
            row = {'case_id': cid, 'horizon_hours': int(c.horizon_hours),
                   'target_date': str(c.target_date), 'evaluation_status': 'not_evaluated'}
            match = routing[routing.case_id == cid]
            try:
                if match.empty:
                    raise ValueError('Missing routing result')
                flag = str(match.iloc[0]['success']).strip().lower()
                if flag not in ('true','false','1','0','1.0','0.0'):
                    raise ValueError('Unrecognized routing success value')
                row['routing_success'] = flag in ('true','1','1.0')
                if not row['routing_success']:
                    row.update(evaluation_status='routing_failed', reason=str(match.iloc[0].get('reason','')))
                else:
                    aispath = Path(str(c.route_file))
                    if not aispath.is_file():
                        aispath = val/'selected_cases'/f'{cid}_actual_ais.csv'
                    ais = pd.read_csv(aispath)[['lat','lon']].to_numpy(float)
                    pg = pd.read_csv(val/'polarguard_results'/f'{cid}_polarguard_route.csv')[['latitude','longitude']].to_numpy(float)
                    start = [float(c.start_latitude),float(c.start_longitude)]
                    end = [float(c.destination_latitude),float(c.destination_longitude)]
                    if angles(vectors([ais[0]])[0],vectors([start])[0])*R > .1 or angles(vectors([ais[-1]])[0],vectors([end])[0])*R > .1:
                        raise ValueError('AIS endpoints differ from case endpoints by over 100 m')
                    pg = np.vstack((start,pg,end))
                    target = np.datetime64(c.target_date,'D')
                    if target != np.datetime64(c.initialization_date,'D')+np.timedelta64(int(c.horizon_hours),'h'):
                        raise ValueError('Target date and forecast horizon disagree')
                    dates = da.time.values.astype('datetime64[D]')
                    ids = np.flatnonzero(dates == target)
                    if len(ids) != 1:
                        raise ValueError('Missing or duplicate target SIC date')
                    field = da.isel(time=int(ids[0])).load()
                    b = bergs[bergs.init_date.dt.normalize() == pd.Timestamp(c.initialization_date)]
                    bp = b[[f'true_lat_{int(c.horizon_hours)}h',f'true_lon_{int(c.horizon_hours)}h']].to_numpy(float)
                    bp = np.unique(bp[np.isfinite(bp).all(axis=1)],axis=0)
                    if len(bp) and ((np.abs(bp[:,0])>90).any() or (np.abs(bp[:,1])>180).any()):
                        raise ValueError('Invalid iceberg coordinates')
                    row['iceberg_positions'] = len(bp)
                    for prefix, route in [('ais',ais),('pg',pg)]:
                        metrics = score_route(route,args.spacing_km,field,transform,bp)
                        row.update({prefix+'_'+k:v for k,v in metrics.items()})
                    row['distance_saved_pct'] = 100*(1-row['pg_distance_km']/row['ais_distance_km'])
                    row['evaluation_status'] = 'complete'
            except Exception as exc:
                row.update(evaluation_status='evaluation_error',reason=f'{type(exc).__name__}: {exc}')
            results.append(row)
            pd.DataFrame(results).to_csv(out/'summary_metrics.csv',index=False)
            print(f'{cid}: {row["evaluation_status"]}',flush=True)
    print('\nResults:',out)
    errors = sum(r['evaluation_status']=='evaluation_error' for r in results)
    print('Evaluation errors:',errors,'(see reason column; do not silently exclude these cases)')
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
