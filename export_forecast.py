from pathlib import Path
import json
import numpy as np
import xarray as xr


FORECAST_FILE = Path("outputs/sea_ice_forecast_demo.nc")
UNCERTAINTY_FILE = Path("outputs/sea_ice_uncertainty.nc")

OUTPUT_DIR = Path("outputs/final")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


print("=" * 70)
print("POLARGUARD — FINAL SEA-ICE EXPORT")
print("=" * 70)


# ============================================================
# LOAD
# ============================================================

forecast = xr.open_dataset(FORECAST_FILE)
uncertainty = xr.open_dataset(UNCERTAINTY_FILE)


# ============================================================
# BUILD FINAL DATASET
# ============================================================

final = xr.Dataset(
    coords={
        "y": forecast.y,
        "x": forecast.x
    }
)


final["current_sic"] = forecast["current_sic"]


for horizon in ["24h", "48h", "72h"]:

    final[f"forecast_{horizon}"] = (
        forecast[f"forecast_{horizon}"]
    )

    final[f"uncertainty_{horizon}"] = (
        uncertainty[f"uncertainty_rmse_{horizon}"]
    )


# ============================================================
# METADATA
# ============================================================

final.attrs["system"] = "PolarGuard"

final.attrs["product"] = (
    "Antarctic Sea-Ice Concentration Forecast"
)

final.attrs["forecast_method"] = (
    "Hybrid Persistence + HistGradientBoosting"
)

final.attrs["sic_units"] = (
    "fraction from 0.0 to 1.0"
)

final.attrs["forecast_horizons"] = (
    "24h, 48h, 72h"
)

final.attrs["uncertainty_method"] = (
    "Per-grid-cell RMSE from 2024 validation residuals"
)

final.attrs["hybrid_threshold"] = 0.002


# ============================================================
# SAVE NETCDF
# ============================================================

netcdf_file = (
    OUTPUT_DIR /
    "sea_ice_forecast_final.nc"
)

final.to_netcdf(netcdf_file)

print("\nSaved NetCDF:")
print(netcdf_file)


# ============================================================
# SUMMARY JSON
# ============================================================

summary = {

    "system": "PolarGuard",

    "module": "Sea-Ice Forecasting",

    "variable": "Sea-Ice Concentration",

    "units": "fraction",

    "range": [0.0, 1.0],

    "forecast_horizons": [
        "24h",
        "48h",
        "72h"
    ],

    "method": (
        "Hybrid Persistence + "
        "HistGradientBoosting"
    ),

    "hybrid_threshold": 0.002,

    "training_period": "2019-2023",

    "validation_period": "2024",

    "test_period": "2025",

    "test_metrics": {

        "24h": {
            "mae": 0.008854,
            "rmse": 0.036288,
            "persistence_rmse": 0.038023,
            "rmse_improvement_percent": 4.56
        },

        "48h": {
            "mae": 0.012707,
            "rmse": 0.050063,
            "persistence_rmse": 0.053105,
            "rmse_improvement_percent": 5.73
        },

        "72h": {
            "mae": 0.015287,
            "rmse": 0.059311,
            "persistence_rmse": 0.063799,
            "rmse_improvement_percent": 7.04
        }
    },

    "mean_validation_uncertainty": {
        "24h": 0.019594,
        "48h": 0.027492,
        "72h": 0.032782
    }
}


json_file = (
    OUTPUT_DIR /
    "sea_ice_forecast_summary.json"
)


with open(
    json_file,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        summary,
        f,
        indent=4
    )


print("\nSaved JSON:")
print(json_file)


# ============================================================
# VERIFY
# ============================================================

print("\nFinal variables:")

for variable in final.data_vars:

    values = final[variable].values

    print(
        f"{variable:25s}",
        f"shape={values.shape}",
        f"min={np.nanmin(values):.4f}",
        f"max={np.nanmax(values):.4f}"
    )


forecast.close()
uncertainty.close()
final.close()


print("\n" + "=" * 70)
print("FINAL EXPORT COMPLETE")
print("=" * 70)