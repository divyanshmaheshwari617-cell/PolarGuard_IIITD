"""Frozen PolarGuard forecasts versus Bootstrap 2025, by ice concentration region.
Save in the PolarGuard project root, then run: python evaluate_bootstrap_ice_regions.py
Optional quick check: python evaluate_bootstrap_ice_regions.py --days 3
No fitting, model saving, or changes to the existing service. Results are
cross-product agreement, not independent ground truth or navigation validation.
"""
from pathlib import Path
from functools import lru_cache
from datetime import datetime
import argparse
import csv
import json
import os
import sys
import numpy as np
import xarray as xr


def clean_fraction(values):
    a = np.asarray(values, dtype=np.float64)
    return np.where(np.isfinite(a) & (a >= 0) & (a <= 1), a, np.nan)


REGIONS = {
    'all_ocean': 'All mutually valid ocean cells',
    'observed_ice_ge15': 'Reference concentration >= 0.15',
    'observed_ice_15_to80': 'Reference concentration >= 0.15 and < 0.80',
    'observed_dense_ge80': 'Reference concentration >= 0.80',
    'ice_union_ge15': 'Reference OR model OR persistence concentration >= 0.15',
}


def region_masks(reference, prediction, persistence):
    return {
        'all_ocean': np.ones(reference.shape, dtype=bool),
        'observed_ice_ge15': reference >= 0.15,
        'observed_ice_15_to80': (reference >= 0.15) & (reference < 0.80),
        'observed_dense_ge80': reference >= 0.80,
        'ice_union_ge15': (reference >= 0.15) | (prediction >= 0.15) | (persistence >= 0.15),
    }


def error_sums(prediction, reference, persistence):
    mask = np.isfinite(prediction) & np.isfinite(reference) & np.isfinite(persistence)
    error = prediction[mask].astype(np.float64) - reference[mask]
    baseline_error = persistence[mask].astype(np.float64) - reference[mask]
    return np.array([mask.sum(), np.abs(error).sum(), np.square(error).sum(),
                     error.sum(), np.abs(baseline_error).sum(),
                     np.square(baseline_error).sum()], dtype=np.float64)


def metrics(s):
    n, ae, se, bias, bae, bse = s
    if n == 0:
        return {'valid_cell_pairs': 0, 'mae': '', 'rmse': '', 'bias': '',
                'persistence_mae': '', 'persistence_rmse': '', 'rmse_improvement_percent': ''}
    rmse, baseline_rmse = np.sqrt(se / n), np.sqrt(bse / n)
    return {'valid_cell_pairs': int(n), 'mae': ae / n, 'rmse': rmse,
            'bias': bias / n, 'persistence_mae': bae / n,
            'persistence_rmse': baseline_rmse,
            'rmse_improvement_percent': (100 * (1 - rmse / baseline_rmse)
                                         if baseline_rmse > 0 else '')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--days', type=int, default=365, help='First N target days of 2025 (default 365).')
    args = parser.parse_args()
    if not 1 <= args.days <= 365:
        parser.error('--days must be between 1 and 365')
    root = args.project_root.resolve()
    source = root / 'data/processed/sea_ice_2019_2025.nc'
    references = root / 'data/external/bootstrap_2025'
    if not (root / 'sea_ice_service.py').is_file():
        raise FileNotFoundError('Save this script in the project root next to sea_ice_service.py.')
    os.chdir(root)  # Existing service uses paths relative to the working directory.
    sys.path.insert(0, str(root))
    start = np.datetime64('2025-01-01', 'D')
    end = start + np.timedelta64(args.days - 1, 'D')
    days = np.arange(start, end + np.timedelta64(1, 'D'), dtype='datetime64[D]')

    def ref_path(day):
        stamp = str(day).replace('-', '')
        return references / ('NSIDC0079_SEAICE_PS_S25km_' + stamp + '_v4.0.nc')

    missing = [str(ref_path(d)) for d in days if not ref_path(d).is_file()]
    if missing:
        raise FileNotFoundError('Missing daily files: ' + '\n'.join(missing[:10]))

    with xr.open_dataset(source) as cdr:
        source_days = cdr.time.values.astype('datetime64[D]')
        if len(set(source_days)) != len(source_days):
            raise ValueError('Duplicate dates in original input dataset.')
        indices = {d: i for i, d in enumerate(source_days)}
        first_init = start - np.timedelta64(3, 'D')
        last_init = end - np.timedelta64(1, 'D')
        required = np.arange(first_init - np.timedelta64(3, 'D'),
                             last_init + np.timedelta64(1, 'D'), dtype='datetime64[D]')
        if any(d not in indices for d in required):
            raise ValueError('Original inputs lack one or more required initialization/lag dates.')
        xs, ys = cdr.x.values, cdr.y.values

        @lru_cache(maxsize=8)
        def inputs(day):
            a = cdr['sea_ice_concentration'].isel(time=indices[day]).transpose('y', 'x').values
            finite = a[np.isfinite(a)]
            if finite.size == 0 or finite.min() < 0 or finite.max() > 1:
                raise ValueError('Original CDR inputs must already use 0-1 fractions with NaN masks; '
                                 'inspect preprocessing before continuing. Date: ' + str(day))
            return np.asarray(a).copy()

        def read_reference(day):
            with xr.open_dataset(ref_path(day)) as ds:
                if ds.sizes.get('time') != 1 or ds.time.values.astype('datetime64[D]')[0] != day:
                    raise ValueError('Reference date mismatch: ' + str(day))
                if not (np.array_equal(ds.x.values, xs) and np.array_equal(ds.y.values, ys)):
                    raise ValueError('Grid coordinates differ: explicit alignment is required. No regridding applied.')
                if 'F17_ICECON' not in ds:
                    raise ValueError('Expected F17_ICECON variable missing: ' + str(day))
                a = ds['F17_ICECON']
                if not np.isclose(float(a.encoding.get('scale_factor', np.nan)), 0.001):
                    raise ValueError('Unexpected packing scale; inspect reference before evaluation.')
                # Xarray has already applied 0.001. Land/missing become 1.2/1.1.
                return clean_fraction(a.isel(time=0).transpose('y', 'x').values)

        print('Checking all selected reference files and grid coordinates...', flush=True)
        for day in days:
            ref = read_reference(day)
            if not np.isfinite(ref).any():
                raise ValueError('No valid reference concentration on ' + str(day))
        read_reference = lru_cache(maxsize=8)(read_reference)
        inputs(first_init)
        from sea_ice_service import predict_sea_ice

        out = root / 'outputs' / ('bootstrap_ice_regions_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        out.mkdir(parents=True, exist_ok=False)
        metadata = {
            'status': 'running', 'target_start': str(start), 'target_end': str(end),
            'input_source': str(source), 'reference_folder': str(references),
            'method': 'Existing frozen hybrid predict_sea_ice; original CDR inputs and four daily lags/current.',
            'reference': 'NSIDC-0079 V4, daily Antarctic F17_ICECON; decoded once; valid range 0-1.',
            'scoring': 'Equal weight per valid grid-cell/date pair; identical model and persistence masks.',
            'limitations': 'CDR and Bootstrap are related products. Cross-product agreement is not independent '
                           'ground truth, training-split verification, or navigation safety validation. '
                           'All valid ocean cells included; open water can dominate aggregate metrics.',
            'units': 'Concentration fraction; multiply MAE/RMSE/bias by 100 for percentage points.',
            'models_modified': False,
            'regions': REGIONS,
            'region_notes': 'Groups overlap: do not add them together. 15% and 80% are diagnostic '
                            'concentration cutoffs, not vessel safety thresholds. The 15-80% band '
                            'is not a geometric ice-edge measurement. Reference-conditioned '
                            'groups can favor persistence in some conditions; inspect the union '
                            'group too. Every comparison uses a common valid mask for both methods.',
        }
        meta_file = out / 'evaluation_info.json'
        meta_file.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
        horizons = {'24h': 1, '48h': 2, '72h': 3}
        totals = {(h, region): np.zeros(6) for h in horizons for region in REGIONS}
        counts = {h: 0 for h in horizons}
        nonempty = {(h, region): 0 for h in horizons for region in REGIONS}
        init_days = np.arange(first_init, last_init + np.timedelta64(1, 'D'), dtype='datetime64[D]')
        fields = ['initialization_date', 'target_date', 'horizon', 'region'] + list(metrics(np.ones(6)))
        print('Writing results to: ' + str(out), flush=True)
        with (out / 'daily_region_metrics.csv').open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for i, day in enumerate(init_days, 1):
                current, lag1, lag2, lag3 = [inputs(day - np.timedelta64(k, 'D')) for k in range(4)]
                if not (np.isfinite(current) & np.isfinite(lag1) & np.isfinite(lag2) & np.isfinite(lag3)).any():
                    raise ValueError('No valid four-day inputs on ' + str(day))
                predictions = predict_sea_ice(current=current, lag1=lag1, lag2=lag2, lag3=lag3,
                                              x_coords=xs, y_coords=ys, date=day)
                for horizon, offset in horizons.items():
                    target = day + np.timedelta64(offset, 'D')
                    if not start <= target <= end:
                        continue
                    pred = np.asarray(predictions[horizon])
                    if pred.shape != current.shape:
                        raise ValueError('Prediction grid shape mismatch.')
                    pred = clean_fraction(pred)
                    reference = read_reference(target)
                    for region, mask in region_masks(reference, pred, current).items():
                        sums = error_sums(pred, np.where(mask, reference, np.nan), current)
                        row = {'initialization_date': str(day), 'target_date': str(target),
                               'horizon': horizon, 'region': region}
                        row.update(metrics(sums))
                        writer.writerow(row)
                        totals[horizon, region] += sums
                        nonempty[horizon, region] += int(sums[0] > 0)
                    counts[horizon] += 1
                handle.flush()
                print(f'[{i}/{len(init_days)}] Initialization {day} complete', flush=True)
        with (out / 'summary_region_metrics.csv').open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=['horizon', 'region', 'target_days',
                                                        'days_with_valid_cells'] + list(metrics(np.ones(6))))
            writer.writeheader()
            for horizon in horizons:
                if counts[horizon] != args.days:
                    raise ValueError('Unexpected number of scored target days.')
                for region in REGIONS:
                    m = metrics(totals[horizon, region])
                    writer.writerow({'horizon': horizon, 'region': region,
                                     'target_days': counts[horizon],
                                     'days_with_valid_cells': nonempty[horizon, region], **m})
                    if m['valid_cell_pairs']:
                        print(f"{horizon} | {region}: MAE={m['mae']:.6f}, RMSE={m['rmse']:.6f}, "
                              f"persistence RMSE={m['persistence_rmse']:.6f}")
                    else:
                        print(f'{horizon} | {region}: no valid cells')
        metadata['status'] = 'complete'
        meta_file.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
        print('COMPLETE. Share summary_region_metrics.csv and daily_region_metrics.csv from: ' + str(out))


if __name__ == '__main__':
    main()
