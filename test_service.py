import numpy as np
import xarray as xr

from sea_ice_service import (
    predict_sea_ice,
    load_uncertainty
)


TEST_FILE = "data/processed/test_2025.nc"

ds = xr.open_dataarray(TEST_FILE)

# Use Dec 28, 2025 as demo initialization
date = np.datetime64("2025-12-28")

times = ds.time.values.astype(
    "datetime64[D]"
)

indices = np.where(
    times == date
)[0]

if len(indices) == 0:
    raise ValueError(
        "Date not found"
    )

t = int(indices[0])

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
    date=date
)

uncertainty = load_uncertainty()


print("=" * 65)
print("POLARGUARD SEA-ICE SERVICE TEST")
print("=" * 65)

for horizon in [
    "24h",
    "48h",
    "72h"
]:

    forecast = forecasts[horizon]

    print(f"\n{horizon}")

    print(
        "Forecast shape:",
        forecast.shape
    )

    print(
        "Forecast min:",
        np.nanmin(forecast)
    )

    print(
        "Forecast max:",
        np.nanmax(forecast)
    )

    print(
        "Uncertainty shape:",
        uncertainty[horizon].shape
    )


ds.close()

print("\n" + "=" * 65)
print("SERVICE TEST COMPLETE")
print("=" * 65)