import json
from pathlib import Path
from datetime import datetime

from iceberg_service import predict_iceberg_trajectory


# ============================================================
# OUTPUT DIRECTORY
# ============================================================

OUTPUT_DIR = Path("iceberg/outputs/integration")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "iceberg_forecast_demo.json"


# ============================================================
# DEMO INPUT
#
# Same example used in iceberg_service.py
# Four consecutive daily iceberg positions:
# t-3, t-2, t-1, t
# ============================================================

ICEBERG_ID = "a23a"

INITIALIZATION_DATE = "2019-01-04"

lat_tm3 = -75.75435
lon_tm3 = -41.10950

lat_tm2 = -75.69135
lon_tm2 = -41.09485

lat_tm1 = -75.63525
lon_tm1 = -41.08170

current_latitude = -75.61100
current_longitude = -41.07600


# ============================================================
# DATE → DAY OF YEAR
# ============================================================

init_date = datetime.strptime(
    INITIALIZATION_DATE,
    "%Y-%m-%d"
)

day_of_year = init_date.timetuple().tm_yday


# ============================================================
# RUN TRAJECTORY SERVICE
# ============================================================

print("=" * 75)
print("POLARGUARD ICEBERG INTEGRATION EXPORT")
print("=" * 75)

print(f"\nIceberg: {ICEBERG_ID}")
print(f"Initialization date: {INITIALIZATION_DATE}")

result = predict_iceberg_trajectory(
    lat_tm3=lat_tm3,
    lon_tm3=lon_tm3,

    lat_tm2=lat_tm2,
    lon_tm2=lon_tm2,

    lat_tm1=lat_tm1,
    lon_tm1=lon_tm1,

    current_latitude=current_latitude,
    current_longitude=current_longitude,

    day_of_year=day_of_year
)


# ============================================================
# BUILD INTEGRATION PACKAGE
# ============================================================

integration_package = {
    "module": "PolarGuard Iceberg Trajectory Forecast",

    "version": "trajectory-only-v1",

    "iceberg_id": ICEBERG_ID,

    "initialization_date": INITIALIZATION_DATE,

    "input": {
        "history_days": 4,

        "positions": {
            "t_minus_3": {
                "latitude": lat_tm3,
                "longitude": lon_tm3
            },

            "t_minus_2": {
                "latitude": lat_tm2,
                "longitude": lon_tm2
            },

            "t_minus_1": {
                "latitude": lat_tm1,
                "longitude": lon_tm1
            },

            "current": {
                "latitude": current_latitude,
                "longitude": current_longitude
            }
        }
    },

    "current_position": result["current_position"],

    "forecast": result["forecast"],

    "forecast_horizons_hours": [
        24,
        48,
        72
    ],

    "coordinate_system": {
        "latitude": "degrees_north",
        "longitude": "degrees_east"
    },

    "model": result["model"],

    "environment": {
        "included": False,
        "note": (
            "Environmental features will be added "
            "after final environmental-data integration."
        )
    },

    "uncertainty": {
        "included": False,
        "note": (
            "Final uncertainty will be calculated "
            "after final model selection."
        )
    }
}


# ============================================================
# SAVE JSON
# ============================================================

with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        integration_package,
        f,
        indent=2
    )


# ============================================================
# DISPLAY RESULTS
# ============================================================

print("\nCurrent position:")

print(
    f"Latitude  : "
    f"{current_latitude:.6f}"
)

print(
    f"Longitude : "
    f"{current_longitude:.6f}"
)


for horizon in [
    "24h",
    "48h",
    "72h"
]:

    forecast = result[
        "forecast"
    ][horizon]

    print(
        f"\n{horizon} forecast:"
    )

    print(
        f"  Latitude  : "
        f"{forecast['latitude']:.6f}"
    )

    print(
        f"  Longitude : "
        f"{forecast['longitude']:.6f}"
    )

    print(
        f"  Movement  : "
        f"{forecast['displacement_distance_km']:.3f} km"
    )


# ============================================================
# FINAL
# ============================================================

print("\n" + "=" * 75)
print("INTEGRATION EXPORT COMPLETE")
print("=" * 75)

print(
    f"\nJSON saved to:\n{OUTPUT_FILE}"
)

print(
    "\nThis is the trajectory-only integration package."
)

print(
    "2025 held-out test data was NOT used."
)