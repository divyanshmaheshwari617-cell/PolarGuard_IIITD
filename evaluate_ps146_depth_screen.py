"""PS146 GEBCO screening only; no training or route generation.
50 m great-circle midpoint sampling plus every route vertex.
Not a navigation clearance certification or an exhaustive raster intersection.
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



def lookup(points, lat, lon, grid):
    """Nearest-cell lookup without extrapolating beyond cell-edge domain."""
    dy, dx = np.median(np.diff(lat)), np.median(np.diff(lon))
    inside = ((points[:,0] >= lat[0]-dy/2) & (points[:,0] <= lat[-1]+dy/2)
              & (points[:,1] >= lon[0]-dx/2) & (points[:,1] <= lon[-1]+dx/2))
    def index(axis, values):
        right = np.clip(np.searchsorted(axis, values), 1, len(axis)-1)
        return np.where(abs(values-axis[right-1]) <= abs(values-axis[right]),right-1,right)
    z = np.asarray(grid[index(lat,points[:,0]),index(lon,points[:,1])],float)
    z[~inside] = np.nan
    return z


def score(points, lat, lon, grid):
    p, mid, weights = sample_route(points, .05)
    z = lookup(mid,lat,lon,grid)
    zv = lookup(p,lat,lon,grid)
    valid = np.isfinite(z)
    allz = np.r_[z,zv]
    finite = allz[np.isfinite(allz)]
    negative = finite[finite < 0]
    result = dict(distance_km=float(weights.sum()),
        sampled_valid_distance_pct=float(weights[valid].sum()/weights.sum()*100),
        missing_vertices=int((~np.isfinite(zv)).sum()),
        nonnegative_elevation_samples=int((finite >= 0).sum()),
        nonnegative_elevation_distance_km=float(weights[valid & (z>=0)].sum()),
        shallowest_sampled_water_depth_m=float(-negative.max()) if len(negative) else np.nan,
        maximum_sampled_elevation_m=float(finite.max()) if len(finite) else np.nan)
    for depth in (10,20,50):
        result[f'water_depth_below_{depth}m_distance_km'] = float(weights[valid & (z<0) & (z>-depth)].sum())
    if (finite >= 0).any():
        result['screening_status'] = 'nonnegative_elevation_flag_review_required'
    elif not valid.all() or not np.isfinite(zv).all():
        result['screening_status'] = 'incomplete_coverage'
    else:
        result['screening_status'] = 'no_nonnegative_elevation_at_sampled_locations'
    return result, mid, z


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--self-test',action='store_true')
    args=parser.parse_args()
    if args.self_test:
        lat=lon=np.array([0.,1.,2.])
        grid=np.array([[-100.,-5.,20.],[-50.,np.nan,-10.],[-30.,-40.,-60.]])
        z=lookup(np.array([[0.,0.],[0.,1.],[0.,2.],[1.,1.],[5.,5.]]),lat,lon,grid)
        assert np.allclose(z[:3],[-100,-5,20]) and np.isnan(z[3:]).all()
        _,_,w=sample_route([[0,0],[0,1]],.05)
        assert abs(w.sum()-R*np.pi/180)<1e-8
        print('PASS: depth sign, missing/outside grid handling, route distance')
        return
    import pandas as pd
    import xarray as xr
    root=args.project_root.resolve()
    val=root/'iceberg/outputs/ais_route_validation/ps146_2025_validation'
    casespath=val/'selected_cases/ps146_2025_frozen_case_definitions.csv'
    routingpath=val/'polarguard_results/ps146_2025_ais_vs_polarguard_summary.csv'
    bathy=root/'data/external/bathymetry/gebco_2026_n-60.0_s-75.0_w-57.0_e1.0.nc'
    cases=pd.read_csv(casespath)
    routing=pd.read_csv(routingpath)
    if cases.case_id.duplicated().any() or routing.case_id.duplicated().any():
        raise ValueError('Duplicate case identifiers')
    with xr.open_dataset(bathy) as ds:
        field=ds['elevation'].transpose('lat','lon').sortby('lat').sortby('lon')
        if field.attrs.get('units') != 'm':
            raise ValueError('Expected elevation in metres')
        lat=field.lat.values.copy(); lon=field.lon.values.copy()
        if len(lat)<2 or len(lon)<2 or not (np.diff(lat)>0).all() or not (np.diff(lon)>0).all():
            raise ValueError('Invalid coordinate axes')
        grid=field.values.copy()
    out=root/'outputs'/('ps146_depth_screen_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    out.mkdir(parents=True,exist_ok=False)
    metadata={'created_utc':datetime.now(timezone.utc).isoformat(),
      'method':'50 m great-circle midpoint bins plus all route vertices; nearest GEBCO cell; actual endpoint connections included',
      'interpretation':'Negative elevation is depth below mean sea level; nonnegative elevation is a review flag, not definitive shoreline classification',
      'depth_bands_m':[10,20,50], 'depth_bands_are':'Descriptive only, not vessel safety limits',
      'limitations':['GEBCO screening is not nautical-chart clearance verification',
        '50 m sampling is not 50 m source resolution and may miss small features',
        'No explicit coastline or floating ice-shelf mask',
        'No voyage draft, under-keel requirement, tides, squat or vertical uncertainty allowance',
        '2026 grid used retrospectively for 2025 routes; no claim of availability at route initialization',
        'Missing depths are unknown; sea ice, weather and iceberg safety are not tested here'],
      'inputs':{}}
    def record(path):
        metadata['inputs'][str(path)]={'bytes':path.stat().st_size,
          'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    for path in (casespath,routingpath,bathy): record(path)
    def read_route(path):
        record(path)
        df=pd.read_csv(path).rename(columns={'latitude':'lat','longitude':'lon'})
        return clean_route(df[['lat','lon']].to_numpy(float))
    def distance(a,b): return float(angles(vectors([a])[0],vectors([b])[0])*R)
    rows=[]
    for _,c in cases.iterrows():
        cid=str(c.case_id)
        row={'case_id':cid,'evaluation_status':'not_evaluated','navigation_safety':'not_verified'}
        try:
            match=routing[routing.case_id==cid]
            if len(match)!=1: raise ValueError('Missing routing status')
            flag=str(match.iloc[0]['success']).strip().lower()
            if flag not in ('true','false','1','0','1.0','0.0'): raise ValueError('Unknown routing status')
            if flag in ('false','0','0.0'):
                row.update(evaluation_status='routing_failed',reason=str(match.iloc[0].get('reason','')))
            else:
                ais=read_route(val/'selected_cases'/f'{cid}_actual_ais.csv')
                pg0=read_route(val/'polarguard_results'/f'{cid}_polarguard_route.csv')
                start=[float(c.start_latitude),float(c.start_longitude)]
                end=[float(c.destination_latitude),float(c.destination_longitude)]
                if distance(start,ais[0])>.1 or distance(end,ais[-1])>.1:
                    raise ValueError('AIS endpoint mismatch exceeds 100 m')
                row['start_connector_km']=distance(start,pg0[0])
                row['end_connector_km']=distance(pg0[-1],end)
                pg=np.vstack((start,pg0,end))
                for label,route in [('ais',ais),('pg',pg)]:
                    metrics,mid,z=score(route,lat,lon,grid)
                    row.update({label+'_'+k:v for k,v in metrics.items()})
                    # Save every midpoint for locating flags; vertices also included separately.
                    p=clean_route(route)
                    locations=np.vstack((mid,p)); elev=np.r_[z,lookup(p,lat,lon,grid)]
                    pd.DataFrame({'lat':locations[:,0],'lon':locations[:,1],
                      'elevation_m':elev,'sample_kind':['midpoint']*len(mid)+['vertex']*len(p)}).to_csv(out/f'{cid}_{label}_depth_samples.csv',index=False)
                row['distance_saved_pct']=100*(1-row['pg_distance_km']/row['ais_distance_km'])
                row['evaluation_status']='complete'
        except Exception as exc:
            row.update(evaluation_status='evaluation_error',reason=f'{type(exc).__name__}: {exc}')
        rows.append(row)
        pd.DataFrame(rows).to_csv(out/'summary_metrics.csv',index=False)
        (out/'evaluation_metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
        print(cid+': '+row['evaluation_status'],flush=True)
    errors=sum(r['evaluation_status']=='evaluation_error' for r in rows)
    print('Results:',out)
    print('Evaluation errors:',errors)
    print('Depth screening only. No route is certified safe by this script.')
    if errors: raise SystemExit(1)

if __name__=='__main__':
    main()
