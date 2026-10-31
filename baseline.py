from pathlib import Path
import xarray as xr
import numpy as np

DATA_DIR = Path("data/processed")

FILES = {
    "Validation 2024": DATA_DIR / "validation_2024.nc",
    "Test 2025": DATA_DIR / "test_2025.nc",
}

HORIZONS = {
    "24h": 1,
    "48h": 2,
    "72h": 3,
}


def calculate_metrics(pred, true):
    pred = pred.values
    true = true.values

    valid = np.isfinite(pred) & np.isfinite(true)

    pred = pred[valid]
    true = true[valid]

    mae = np.mean(np.abs(pred - true))
    rmse = np.sqrt(np.mean((pred - true) ** 2))

    return mae, rmse, valid.sum()


print("=" * 70)
print("POLARGUARD — OFFICIAL PERSISTENCE BASELINE")
print("=" * 70)

for dataset_name, file_path in FILES.items():

    if not file_path.exists():
        raise FileNotFoundError(f"Missing: {file_path}")

    sic = xr.open_dataarray(file_path)

    print("\n" + "=" * 70)
    print(dataset_name)
    print("=" * 70)

    print("Shape:", sic.shape)
    print("Start:", sic.time.values[0])
    print("End  :", sic.time.values[-1])

    for horizon_name, days_ahead in HORIZONS.items():

        # Persistence prediction:
        # current sea-ice map is used as future prediction
        pred = sic.isel(
            time=slice(0, -days_ahead)
        )

        true = sic.isel(
            time=slice(days_ahead, None)
        )

        # Align by sample index, not calendar date
        pred = pred.assign_coords(
            time=np.arange(pred.sizes["time"])
        )

        true = true.assign_coords(
            time=np.arange(true.sizes["time"])
        )

        mae, rmse, count = calculate_metrics(
            pred,
            true
        )

        print(f"\n{horizon_name}")
        print(f"MAE  : {mae:.6f}")
        print(f"RMSE : {rmse:.6f}")
        print(f"Valid comparisons: {count:,}")

    sic.close()

print("\n" + "=" * 70)
print("BASELINE COMPLETE")
print("=" * 70)
