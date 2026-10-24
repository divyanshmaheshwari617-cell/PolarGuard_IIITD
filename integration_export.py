import json
from pathlib import Path

import numpy as np
import xarray as xr

from sea_ice_service import (
    predict_sea_ice,
    load_uncertainty
)


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FILE = Path("data/processed/test_2025.nc")

OUTPUT_DIR = Path("outputs/integration")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_NETCDF = OUTPUT_DIR / "sea_ice_integration_package.nc"
OUTPUT_JSON = OUTPUT_DIR / "sea_ice_integration_metadata.json"

FORECAST_DATE = np.datetime64("2025-12-28")


# ============================================================
# LOAD SOURCE DATA
# ============================================================

print("=" * 72)
print("POLARGUARD SEA-ICE INTEGRATION EXPORT")
print("=" * 72)

print("\nLoading:", INPUT_FILE)

ds = xr.open_dataarray(INPUT_FILE)

times = ds.time.values.astype("datetime64[D]")

matches = np.where(times == FORECAST_DATE)[0]

if len(matches) == 0:
    ds.close()
    raise ValueError(
        f"Forecast date {FORECAST_DATE} not found."
    )

t = int(matches[0])

if t < 3:
    ds.close()
    raise ValueError(
        "Not enough lag days available."
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


print("\nForecast initialization:", FORECAST_DATE)
print("Grid shape             :", current.shape)


# ============================================================
# RUN FORECAST
# ============================================================

print("\nGenerating forecasts...")

forecasts = predict_sea_ice(
    current=current,
    lag1=lag1,
    lag2=lag2,
    lag3=lag3,
    x_coords=x_coords,
    y_coords=y_coords,
    date=FORECAST_DATE
)

print("Loading uncertainty maps...")

uncertainty = load_uncertainty()


# ============================================================
# TARGET TIMESTAMPS
# ============================================================

target_24h = FORECAST_DATE + np.timedelta64(1, "D")
target_48h = FORECAST_DATE + np.timedelta64(2, "D")
target_72h = FORECAST_DATE + np.timedelta64(3, "D")


# ============================================================
# CREATE INTEGRATION DATASET
# ============================================================

integration_ds = xr.Dataset(
    data_vars={
        "current_sic": (
            ("y", "x"),
            current.astype(np.float32)
        ),

        "forecast_24h": (
            ("y", "x"),
            forecasts["24h"].astype(np.float32)
        ),

        "uncertainty_24h": (
            ("y", "x"),
            uncertainty["24h"].astype(np.float32)
        ),

        "forecast_48h": (
            ("y", "x"),
            forecasts["48h"].astype(np.float32)
        ),

        "uncertainty_48h": (
            ("y", "x"),
            uncertainty["48h"].astype(np.float32)
        ),

        "forecast_72h": (
            ("y", "x"),
            forecasts["72h"].astype(np.float32)
        ),

        "uncertainty_72h": (
            ("y", "x"),
            uncertainty["72h"].astype(np.float32)
        ),
    },

    coords={
        "x": x_coords,
        "y": y_coords,
    }
)


# ============================================================
# VARIABLE ATTRIBUTES
# ============================================================

integration_ds["current_sic"].attrs = {
    "long_name": "Current sea-ice concentration",
    "units": "fraction",
    "valid_min": 0.0,
    "valid_max": 1.0
}

for horizon in ["24h", "48h", "72h"]:

    integration_ds[f"forecast_{horizon}"].attrs = {
        "long_name": f"Forecast sea-ice concentration at +{horizon}",
        "units": "fraction",
        "valid_min": 0.0,
        "valid_max": 1.0
    }

    integration_ds[f"uncertainty_{horizon}"].attrs = {
        "long_name": f"Historical RMSE-based forecast uncertainty at +{horizon}",
        "units": "SIC fraction",
        "description": (
            "Per-grid-cell RMSE derived from 2024 validation residuals. "
            "This is an empirical forecast-error proxy, not a calibrated "
            "confidence interval."
        )
    }


# ============================================================
# GLOBAL METADATA
# ============================================================

integration_ds.attrs = {
    "project": "PolarGuard",
    "module": "Antarctic Sea-Ice Forecasting",

    "forecast_initialization": str(FORECAST_DATE),

    "target_24h": str(target_24h),
    "target_48h": str(target_48h),
    "target_72h": str(target_72h),

    "projection": "EPSG:3412",

    "grid_shape": "332 x 316",

    "sea_ice_units": (
        "Fraction from 0.0 to 1.0, where 1.0 means 100 percent sea-ice concentration"
    ),

    "invalid_cells": "NaN",

    "model": "Hybrid persistence + HistGradientBoosting",

    "hybrid_threshold": 0.002,

    "train_period": "2019-2023",
    "validation_period": "2024",
    "test_period": "2025",

    "dataset": (
        "NOAA/NSIDC Climate Data Record of Passive Microwave "
        "Sea Ice Concentration, Version 6"
    )
}


# ============================================================
# SAVE NETCDF
# ============================================================

encoding = {}

for variable in integration_ds.data_vars:
    encoding[variable] = {
        "zlib": True,
        "complevel": 4,
        "dtype": "float32"
    }

integration_ds.to_netcdf(
    OUTPUT_NETCDF,
    encoding=encoding
)

print("\nSaved NetCDF:")
print(OUTPUT_NETCDF)


# ============================================================
# CREATE JSON METADATA
# ============================================================

metadata = {
    "project": "PolarGuard",

    "module": "Sea-Ice Forecasting",

    "forecast_initialization": str(FORECAST_DATE),

    "forecast_targets": {
        "24h": str(target_24h),
        "48h": str(target_48h),
        "72h": str(target_72h)
    },

    "grid": {
        "rows": int(current.shape[0]),
        "columns": int(current.shape[1]),
        "projection": "EPSG:3412"
    },

    "sic": {
        "range": [0.0, 1.0],
        "meaning": {
            "0.0": "0 percent sea ice",
            "1.0": "100 percent sea ice"
        },
        "invalid_cells": "NaN"
    },

    "model": {
        "type": "Hybrid persistence + HistGradientBoosting",
        "threshold": 0.002,
        "switch_signal": "abs(SIC(t) - SIC(t-3))"
    },

    "variables": {
        "current_sic": "Current observed SIC",
        "forecast_24h": "Forecast SIC at +24 hours",
        "uncertainty_24h": "Historical RMSE uncertainty for +24h",
        "forecast_48h": "Forecast SIC at +48 hours",
        "uncertainty_48h": "Historical RMSE uncertainty for +48h",
        "forecast_72h": "Forecast SIC at +72 hours",
        "uncertainty_72h": "Historical RMSE uncertainty for +72h"
    },

    "final_test_performance_2025": {
        "24h": {
            "mae": 0.008854,
            "rmse": 0.036288,
            "within_5_sic_points_percent": 94.87,
            "rmse_gain_vs_persistence_percent": 4.56
        },

        "48h": {
            "mae": 0.012707,
            "rmse": 0.050063,
            "within_5_sic_points_percent": 93.18,
            "rmse_gain_vs_persistence_percent": 5.73
        },

        "72h": {
            "mae": 0.015287,
            "rmse": 0.059311,
            "within_5_sic_points_percent": 92.33,
            "rmse_gain_vs_persistence_percent": 7.04
        }
    },

    "uncertainty_note": (
        "Uncertainty values are historical per-grid-cell RMSE values "
        "derived from 2024 validation residuals and are not calibrated "
        "95 percent confidence intervals."
    )
}


with open(
    OUTPUT_JSON,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        metadata,
        f,
        indent=4
    )


print("\nSaved metadata JSON:")
print(OUTPUT_JSON)


# ============================================================
# FINAL CHECK
# ============================================================

print("\n" + "=" * 72)
print("INTEGRATION PACKAGE CONTENTS")
print("=" * 72)

for variable in integration_ds.data_vars:

    arr = integration_ds[variable].values

    print(
        f"{variable:22s} "
        f"shape={arr.shape} "
        f"min={np.nanmin(arr):.4f} "
        f"max={np.nanmax(arr):.4f}"
    )


integration_ds.close()
ds.close()


print("\n" + "=" * 72)
print("INTEGRATION EXPORT COMPLETE")
print("=" * 72)