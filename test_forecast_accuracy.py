import numpy as np
import xarray as xr

from sea_ice_service import predict_sea_ice


# ============================================================
# CONFIGURATION
# ============================================================

TEST_FILE = "data/processed/test_2025.nc"

# Forecast starts from this date.
# Therefore:
# 24h actual = 2025-12-29
# 48h actual = 2025-12-30
# 72h actual = 2025-12-31
FORECAST_DATE = np.datetime64("2025-12-28")


# ============================================================
# LOAD TEST DATA
# ============================================================

print("=" * 70)
print("POLARGUARD HISTORICAL FORECAST ACCURACY TEST")
print("=" * 70)

print("\nLoading:", TEST_FILE)

ds = xr.open_dataarray(TEST_FILE)

times = ds.time.values.astype("datetime64[D]")


# ============================================================
# FIND FORECAST INITIALIZATION DATE
# ============================================================

indices = np.where(times == FORECAST_DATE)[0]

if len(indices) == 0:
    ds.close()
    raise ValueError(
        f"Forecast date {FORECAST_DATE} not found in test dataset."
    )

t = int(indices[0])

# We need 3 previous days and 3 future days.
if t < 3:
    ds.close()
    raise ValueError(
        "Not enough previous days available for lag features."
    )

if t + 3 >= len(ds.time):
    ds.close()
    raise ValueError(
        "Not enough future observations available for 72h evaluation."
    )


# ============================================================
# PREPARE MODEL INPUTS
# ============================================================

current = ds.values[t]
lag1 = ds.values[t - 1]
lag2 = ds.values[t - 2]
lag3 = ds.values[t - 3]

x_coords = ds.x.values
y_coords = ds.y.values


print("\nForecast initialization :", FORECAST_DATE)
print("Current SIC             :", times[t])
print("Lag 1                   :", times[t - 1])
print("Lag 2                   :", times[t - 2])
print("Lag 3                   :", times[t - 3])

print("\nInput map shape:", current.shape)


# ============================================================
# GENERATE FORECASTS
# ============================================================

print("\nGenerating PolarGuard forecasts...")

forecasts = predict_sea_ice(
    current=current,
    lag1=lag1,
    lag2=lag2,
    lag3=lag3,
    x_coords=x_coords,
    y_coords=y_coords,
    date=FORECAST_DATE
)

print("Forecast generation complete.")


# ============================================================
# EVALUATE FORECASTS
# ============================================================

horizons = {
    "24h": 1,
    "48h": 2,
    "72h": 3
}


print("\n" + "=" * 70)
print("FORECAST RESULTS")
print("=" * 70)


for horizon, offset in horizons.items():

    prediction = forecasts[horizon]

    # Real observed SIC after 1, 2, or 3 days
    actual = ds.values[t + offset]

    actual_date = times[t + offset]

    # Only compare cells where both prediction
    # and observation are valid.
    valid = (
        np.isfinite(prediction)
        & np.isfinite(actual)
    )

    pred = prediction[valid]
    obs = actual[valid]

    if len(pred) == 0:
        print(f"\n{horizon}: No valid cells.")
        continue

    # --------------------------------------------------------
    # Errors
    # --------------------------------------------------------

    absolute_error = np.abs(pred - obs)

    mae = np.mean(absolute_error)

    rmse = np.sqrt(
        np.mean((pred - obs) ** 2)
    )

    # --------------------------------------------------------
    # Tolerance metrics
    # --------------------------------------------------------

    within_1 = (
        np.mean(absolute_error <= 0.01)
        * 100
    )

    within_5 = (
        np.mean(absolute_error <= 0.05)
        * 100
    )

    within_10 = (
        np.mean(absolute_error <= 0.10)
        * 100
    )

    # --------------------------------------------------------
    # Persistence baseline
    # --------------------------------------------------------

    persistence = current[valid]

    persistence_mae = np.mean(
        np.abs(persistence - obs)
    )

    persistence_rmse = np.sqrt(
        np.mean((persistence - obs) ** 2)
    )

    rmse_improvement = (
        (
            persistence_rmse - rmse
        )
        / persistence_rmse
        * 100
    )

    # --------------------------------------------------------
    # PRINT RESULTS
    # --------------------------------------------------------

    print(f"\n{horizon} FORECAST")
    print("-" * 50)

    print(
        f"Target date              : {actual_date}"
    )

    print(
        f"Valid grid cells         : {len(pred):,}"
    )

    print(
        f"MAE                      : {mae:.6f}"
    )

    print(
        f"RMSE                     : {rmse:.6f}"
    )

    print(
        f"Within ±1 SIC point      : {within_1:.2f}%"
    )

    print(
        f"Within ±5 SIC points     : {within_5:.2f}%"
    )

    print(
        f"Within ±10 SIC points    : {within_10:.2f}%"
    )

    print(
        f"Persistence MAE          : {persistence_mae:.6f}"
    )

    print(
        f"Persistence RMSE         : {persistence_rmse:.6f}"
    )

    print(
        f"RMSE improvement         : {rmse_improvement:+.2f}%"
    )


# ============================================================
# FINISH
# ============================================================

ds.close()

print("\n" + "=" * 70)
print("HISTORICAL FORECAST TEST COMPLETE")
print("=" * 70)