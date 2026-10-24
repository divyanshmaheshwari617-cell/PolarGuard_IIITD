from pathlib import Path
import numpy as np
import pandas as pd


# ============================================================
# PATHS
# ============================================================

VALIDATION_FILE = Path(
    "iceberg/data/processed/iceberg_features_validation_2024.csv"
)

OUTPUT_DIR = Path(
    "iceberg/outputs"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "iceberg_baseline_validation_2024.csv"
)


# ============================================================
# CONSTANTS
# ============================================================

EARTH_RADIUS_KM = 6371.0088


# ============================================================
# HELPERS
# ============================================================

def wrapped_lon_difference(lon2, lon1):
    """
    Longitude difference safely handling ±180°.
    """

    return (
        (lon2 - lon1 + 180.0) % 360.0
    ) - 180.0


def destination_from_displacement(
    lat,
    lon,
    dx_km,
    dy_km
):
    """
    Convert local east/north displacement back to
    approximate latitude/longitude.

    dx_km:
        positive = east

    dy_km:
        positive = north
    """

    lat_rad = np.radians(lat)

    dlat_rad = (
        dy_km
        / EARTH_RADIUS_KM
    )

    new_lat_rad = (
        lat_rad
        + dlat_rad
    )

    mean_lat_rad = (
        lat_rad
        + new_lat_rad
    ) / 2.0

    cos_lat = np.cos(
        mean_lat_rad
    )

    # Avoid numerical problems extremely close to poles
    cos_lat = np.where(
        np.abs(cos_lat) < 1e-8,
        1e-8,
        cos_lat
    )

    dlon_rad = (
        dx_km
        /
        (
            EARTH_RADIUS_KM
            * cos_lat
        )
    )

    new_lon = (
        lon
        + np.degrees(dlon_rad)
    )

    new_lon = (
        (new_lon + 180.0) % 360.0
    ) - 180.0

    new_lat = np.degrees(
        new_lat_rad
    )

    return new_lat, new_lon


def haversine_km(
    lat1,
    lon1,
    lat2,
    lon2
):
    """
    Great-circle distance between two positions.
    """

    lat1 = np.radians(
        np.asarray(lat1, dtype=float)
    )

    lon1 = np.radians(
        np.asarray(lon1, dtype=float)
    )

    lat2 = np.radians(
        np.asarray(lat2, dtype=float)
    )

    lon2 = np.radians(
        np.asarray(lon2, dtype=float)
    )

    dlat = (
        lat2 - lat1
    )

    dlon = (
        lon2 - lon1
    )

    dlon = (
        dlon + np.pi
    ) % (
        2.0 * np.pi
    ) - np.pi

    a = (
        np.sin(
            dlat / 2.0
        ) ** 2
        +
        np.cos(lat1)
        * np.cos(lat2)
        * np.sin(
            dlon / 2.0
        ) ** 2
    )

    # Numerical safety
    a = np.clip(
        a,
        0.0,
        1.0
    )

    c = (
        2.0
        * np.arctan2(
            np.sqrt(a),
            np.sqrt(1.0 - a)
        )
    )

    return (
        EARTH_RADIUS_KM
        * c
    )


def print_metrics(
    name,
    errors
):
    """
    Print useful position-error metrics.
    """

    errors = np.asarray(
        errors,
        dtype=float
    )

    print(f"\n{name}")

    print(
        f"  Mean error   : "
        f"{np.mean(errors):.3f} km"
    )

    print(
        f"  Median error : "
        f"{np.median(errors):.3f} km"
    )

    print(
        f"  RMSE         : "
        f"{np.sqrt(np.mean(errors ** 2)):.3f} km"
    )

    print(
        f"  90th pct     : "
        f"{np.percentile(errors, 90):.3f} km"
    )

    print(
        f"  95th pct     : "
        f"{np.percentile(errors, 95):.3f} km"
    )

    for threshold in [
        1,
        5,
        10,
        25,
        50,
    ]:

        percentage = (
            100.0
            * np.mean(
                errors <= threshold
            )
        )

        print(
            f"  Within {threshold:>2} km : "
            f"{percentage:6.2f}%"
        )


# ============================================================
# LOAD VALIDATION DATA
# ============================================================

print("=" * 75)
print("ICEBERG BASELINE EVALUATION")
print("VALIDATION YEAR: 2024")
print("=" * 75)

df = pd.read_csv(
    VALIDATION_FILE,
    parse_dates=["init_date"]
)

print(
    f"\nValidation samples: "
    f"{len(df):,}"
)

print(
    f"Unique icebergs: "
    f"{df['iceberg_id'].nunique():,}"
)

print(
    f"Date range: "
    f"{df['init_date'].min()} "
    f"to "
    f"{df['init_date'].max()}"
)


# ============================================================
# STORAGE
# ============================================================

results = []


# ============================================================
# EVALUATE EACH HORIZON
# ============================================================

for horizon in [
    24,
    48,
    72,
]:

    print("\n" + "=" * 75)
    print(
        f"{horizon} HOUR FORECAST"
    )
    print("=" * 75)

    days = (
        horizon / 24.0
    )


    # ========================================================
    # TRUE FUTURE POSITION
    # ========================================================

    true_lat = df[
        f"true_lat_{horizon}h"
    ].to_numpy(
        dtype=float
    )

    true_lon = df[
        f"true_lon_{horizon}h"
    ].to_numpy(
        dtype=float
    )


    # ========================================================
    # BASELINE 1:
    # PERSISTENCE
    #
    # Predict no movement.
    # ========================================================

    persistence_lat = df[
        "current_latitude"
    ].to_numpy(
        dtype=float
    )

    persistence_lon = df[
        "current_longitude"
    ].to_numpy(
        dtype=float
    )

    persistence_error = (
        haversine_km(
            persistence_lat,
            persistence_lon,
            true_lat,
            true_lon
        )
    )


    # ========================================================
    # BASELINE 2:
    # LAST-VELOCITY EXTRAPOLATION
    #
    # Continue t-1 -> t velocity.
    # ========================================================

    recent_vx = df[
        "vx_tm1_t"
    ].to_numpy(
        dtype=float
    )

    recent_vy = df[
        "vy_tm1_t"
    ].to_numpy(
        dtype=float
    )

    cv_dx = (
        recent_vx
        * days
    )

    cv_dy = (
        recent_vy
        * days
    )

    cv_lat, cv_lon = (
        destination_from_displacement(
            df[
                "current_latitude"
            ].to_numpy(
                dtype=float
            ),
            df[
                "current_longitude"
            ].to_numpy(
                dtype=float
            ),
            cv_dx,
            cv_dy
        )
    )

    constant_velocity_error = (
        haversine_km(
            cv_lat,
            cv_lon,
            true_lat,
            true_lon
        )
    )


    # ========================================================
    # BASELINE 3:
    # 3-DAY MEAN VELOCITY
    #
    # Often more stable than last-day velocity.
    # ========================================================

    mean_vx = df[
        "mean_vx_3day"
    ].to_numpy(
        dtype=float
    )

    mean_vy = df[
        "mean_vy_3day"
    ].to_numpy(
        dtype=float
    )

    mean_dx = (
        mean_vx
        * days
    )

    mean_dy = (
        mean_vy
        * days
    )

    mean_lat, mean_lon = (
        destination_from_displacement(
            df[
                "current_latitude"
            ].to_numpy(
                dtype=float
            ),
            df[
                "current_longitude"
            ].to_numpy(
                dtype=float
            ),
            mean_dx,
            mean_dy
        )
    )

    mean_velocity_error = (
        haversine_km(
            mean_lat,
            mean_lon,
            true_lat,
            true_lon
        )
    )


    # ========================================================
    # PRINT METRICS
    # ========================================================

    print_metrics(
        "Persistence baseline",
        persistence_error
    )

    print_metrics(
        "Last-velocity baseline",
        constant_velocity_error
    )

    print_metrics(
        "3-day mean-velocity baseline",
        mean_velocity_error
    )


    # ========================================================
    # COMPARE BEST BASELINE
    # ========================================================

    persistence_rmse = (
        np.sqrt(
            np.mean(
                persistence_error ** 2
            )
        )
    )

    cv_rmse = (
        np.sqrt(
            np.mean(
                constant_velocity_error ** 2
            )
        )
    )

    mean_velocity_rmse = (
        np.sqrt(
            np.mean(
                mean_velocity_error ** 2
            )
        )
    )

    baseline_rmses = {
        "persistence": persistence_rmse,
        "last_velocity": cv_rmse,
        "mean_3day_velocity": (
            mean_velocity_rmse
        ),
    }

    best_name = min(
        baseline_rmses,
        key=baseline_rmses.get
    )

    best_rmse = (
        baseline_rmses[
            best_name
        ]
    )

    print(
        "\nBest RMSE baseline:"
    )

    print(
        f"  {best_name}"
        f" = {best_rmse:.3f} km"
    )


    # ========================================================
    # STORE PER-SAMPLE RESULTS
    # ========================================================

    horizon_results = pd.DataFrame(
        {
            "iceberg_id": (
                df["iceberg_id"]
            ),
            "init_date": (
                df["init_date"]
            ),
            "horizon_hours": horizon,
            "true_latitude": true_lat,
            "true_longitude": true_lon,

            "persistence_latitude": (
                persistence_lat
            ),
            "persistence_longitude": (
                persistence_lon
            ),
            "persistence_error_km": (
                persistence_error
            ),

            "last_velocity_latitude": (
                cv_lat
            ),
            "last_velocity_longitude": (
                cv_lon
            ),
            "last_velocity_error_km": (
                constant_velocity_error
            ),

            "mean_velocity_latitude": (
                mean_lat
            ),
            "mean_velocity_longitude": (
                mean_lon
            ),
            "mean_velocity_error_km": (
                mean_velocity_error
            ),
        }
    )

    results.append(
        horizon_results
    )


# ============================================================
# SAVE RESULTS
# ============================================================

all_results = pd.concat(
    results,
    ignore_index=True
)

all_results.to_csv(
    OUTPUT_FILE,
    index=False
)


print("\n" + "=" * 75)
print("BASELINE EVALUATION COMPLETE")
print("=" * 75)

print(
    f"\nSaved results:"
)

print(
    OUTPUT_FILE
)

print(
    "\nIMPORTANT:"
)

print(
    "These results use ONLY the 2024 validation set."
)

print(
    "The 2025 held-out test set remains untouched."
)