import numpy as np
import xarray as xr

from sea_ice_service import predict_sea_ice


TEST_FILE = "data/processed/test_2025.nc"

TEST_DATES = [
    np.datetime64("2025-02-15"),
    np.datetime64("2025-05-15"),
    np.datetime64("2025-08-15"),
    np.datetime64("2025-11-15"),
]

HORIZONS = {
    "24h": 1,
    "48h": 2,
    "72h": 3,
}


ds = xr.open_dataarray(TEST_FILE)

times = ds.time.values.astype("datetime64[D]")

print("=" * 75)
print("POLARGUARD MULTI-DATE FORECAST TEST")
print("=" * 75)


for forecast_date in TEST_DATES:

    indices = np.where(times == forecast_date)[0]

    if len(indices) == 0:
        print(f"\nDate not found: {forecast_date}")
        continue

    t = int(indices[0])

    if t < 3 or t + 3 >= len(times):
        print(f"\nSkipping {forecast_date}: insufficient lag/future data")
        continue

    current = ds.values[t]
    lag1 = ds.values[t - 1]
    lag2 = ds.values[t - 2]
    lag3 = ds.values[t - 3]

    forecasts = predict_sea_ice(
        current=current,
        lag1=lag1,
        lag2=lag2,
        lag3=lag3,
        x_coords=ds.x.values,
        y_coords=ds.y.values,
        date=forecast_date
    )

    print("\n" + "=" * 75)
    print(f"FORECAST INITIALIZATION: {forecast_date}")
    print("=" * 75)

    for horizon, offset in HORIZONS.items():

        prediction = forecasts[horizon]
        actual = ds.values[t + offset]

        valid = (
            np.isfinite(prediction)
            & np.isfinite(actual)
        )

        pred = prediction[valid]
        obs = actual[valid]

        absolute_error = np.abs(pred - obs)

        mae = np.mean(absolute_error)

        rmse = np.sqrt(
            np.mean((pred - obs) ** 2)
        )

        within_5 = (
            np.mean(absolute_error <= 0.05)
            * 100
        )

        persistence = current[valid]

        persistence_rmse = np.sqrt(
            np.mean((persistence - obs) ** 2)
        )

        improvement = (
            (persistence_rmse - rmse)
            / persistence_rmse
            * 100
        )

        print(f"\n{horizon}")
        print(f"Target date          : {times[t + offset]}")
        print(f"Valid cells          : {len(pred):,}")
        print(f"MAE                  : {mae:.6f}")
        print(f"RMSE                 : {rmse:.6f}")
        print(f"Within ±5 SIC points : {within_5:.2f}%")
        print(f"Persistence RMSE     : {persistence_rmse:.6f}")
        print(f"RMSE improvement     : {improvement:+.2f}%")


ds.close()

print("\n" + "=" * 75)
print("MULTI-DATE TEST COMPLETE")
print("=" * 75)