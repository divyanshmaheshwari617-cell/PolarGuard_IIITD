from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import HistGradientBoostingRegressor


# ============================================================
# PATHS
# ============================================================

TRAIN_FILE = Path(
    "iceberg/data/processed/iceberg_features_train_2019_2023.csv"
)

VALIDATION_FILE = Path(
    "iceberg/data/processed/iceberg_features_validation_2024.csv"
)

MODEL_DIR = Path(
    "iceberg/models"
)

OUTPUT_DIR = Path(
    "iceberg/outputs"
)

MODEL_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

METRICS_FILE = (
    OUTPUT_DIR
    / "trajectory_ml_validation_2024.json"
)

PREDICTIONS_FILE = (
    OUTPUT_DIR
    / "trajectory_ml_validation_predictions_2024.csv"
)


# ============================================================
# CONSTANTS
# ============================================================

EARTH_RADIUS_KM = 6371.0088


# ============================================================
# FEATURES
# ============================================================

FEATURE_COLUMNS = [

    # Current spatial position
    "current_latitude",
    "current_longitude",

    # Recent daily motion
    "vx_tm3_tm2",
    "vy_tm3_tm2",

    "vx_tm2_tm1",
    "vy_tm2_tm1",

    "vx_tm1_t",
    "vy_tm1_t",

    # Speed
    "speed_tm3_tm2",
    "speed_tm2_tm1",
    "speed_tm1_t",

    # Acceleration
    "accel_x_previous",
    "accel_y_previous",

    "accel_x_recent",
    "accel_y_recent",

    # Smoothed recent motion
    "mean_vx_3day",
    "mean_vy_3day",
    "mean_speed_3day",

    # Seasonal cycle
    "doy_sin",
    "doy_cos",
]


# ============================================================
# HELPERS
# ============================================================

def destination_from_displacement(
    lat,
    lon,
    dx_km,
    dy_km
):
    """
    Convert local east/north displacement to
    approximate future latitude/longitude.
    """

    lat = np.asarray(
        lat,
        dtype=float
    )

    lon = np.asarray(
        lon,
        dtype=float
    )

    dx_km = np.asarray(
        dx_km,
        dtype=float
    )

    dy_km = np.asarray(
        dy_km,
        dtype=float
    )

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
        (new_lon + 180.0)
        % 360.0
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
    Great-circle position error.
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

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    dlon = (
        dlon + np.pi
    ) % (
        2.0 * np.pi
    ) - np.pi

    a = (
        np.sin(dlat / 2.0) ** 2
        +
        np.cos(lat1)
        * np.cos(lat2)
        * np.sin(dlon / 2.0) ** 2
    )

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


def calculate_metrics(errors):
    errors = np.asarray(
        errors,
        dtype=float
    )

    return {
        "mean_error_km": float(
            np.mean(errors)
        ),

        "median_error_km": float(
            np.median(errors)
        ),

        "rmse_km": float(
            np.sqrt(
                np.mean(
                    errors ** 2
                )
            )
        ),

        "p90_error_km": float(
            np.percentile(
                errors,
                90
            )
        ),

        "p95_error_km": float(
            np.percentile(
                errors,
                95
            )
        ),

        "within_1km_percent": float(
            np.mean(
                errors <= 1
            ) * 100
        ),

        "within_5km_percent": float(
            np.mean(
                errors <= 5
            ) * 100
        ),

        "within_10km_percent": float(
            np.mean(
                errors <= 10
            ) * 100
        ),

        "within_25km_percent": float(
            np.mean(
                errors <= 25
            ) * 100
        ),

        "within_50km_percent": float(
            np.mean(
                errors <= 50
            ) * 100
        ),
    }


def print_metrics(
    metrics
):
    print(
        f"  Mean error   : "
        f"{metrics['mean_error_km']:.3f} km"
    )

    print(
        f"  Median error : "
        f"{metrics['median_error_km']:.3f} km"
    )

    print(
        f"  RMSE         : "
        f"{metrics['rmse_km']:.3f} km"
    )

    print(
        f"  90th pct     : "
        f"{metrics['p90_error_km']:.3f} km"
    )

    print(
        f"  95th pct     : "
        f"{metrics['p95_error_km']:.3f} km"
    )

    print(
        f"  Within  1 km : "
        f"{metrics['within_1km_percent']:.2f}%"
    )

    print(
        f"  Within  5 km : "
        f"{metrics['within_5km_percent']:.2f}%"
    )

    print(
        f"  Within 10 km : "
        f"{metrics['within_10km_percent']:.2f}%"
    )

    print(
        f"  Within 25 km : "
        f"{metrics['within_25km_percent']:.2f}%"
    )

    print(
        f"  Within 50 km : "
        f"{metrics['within_50km_percent']:.2f}%"
    )


# ============================================================
# LOAD DATA
# ============================================================

print("=" * 75)
print("ICEBERG TRAJECTORY ML TRAINING")
print("=" * 75)

train = pd.read_csv(
    TRAIN_FILE,
    parse_dates=["init_date"]
)

validation = pd.read_csv(
    VALIDATION_FILE,
    parse_dates=["init_date"]
)

print(
    f"\nTraining samples: "
    f"{len(train):,}"
)

print(
    f"Validation samples: "
    f"{len(validation):,}"
)

print(
    f"Features: "
    f"{len(FEATURE_COLUMNS)}"
)


# ============================================================
# CHECK MISSING DATA
# ============================================================

train_missing = (
    train[FEATURE_COLUMNS]
    .isna()
    .sum()
    .sum()
)

validation_missing = (
    validation[FEATURE_COLUMNS]
    .isna()
    .sum()
    .sum()
)

print(
    f"\nTraining feature NaNs: "
    f"{train_missing:,}"
)

print(
    f"Validation feature NaNs: "
    f"{validation_missing:,}"
)

if (
    train_missing > 0
    or validation_missing > 0
):
    raise ValueError(
        "Missing values found in model features."
    )


# ============================================================
# MODEL INPUTS
# ============================================================

X_train = train[
    FEATURE_COLUMNS
].to_numpy(
    dtype=np.float32
)

X_validation = validation[
    FEATURE_COLUMNS
].to_numpy(
    dtype=np.float32
)


# ============================================================
# TRAIN MODELS
#
# Six regressors:
#
# 24h dx
# 24h dy
# 48h dx
# 48h dy
# 72h dx
# 72h dy
# ============================================================

all_metrics = {}

prediction_output = validation[
    [
        "iceberg_id",
        "init_date",
        "current_latitude",
        "current_longitude",
    ]
].copy()


for horizon in [
    24,
    48,
    72,
]:

    print("\n" + "=" * 75)
    print(
        f"TRAINING {horizon}H MODEL"
    )
    print("=" * 75)

    y_dx_train = train[
        f"target_dx_{horizon}h"
    ].to_numpy(
        dtype=np.float32
    )

    y_dy_train = train[
        f"target_dy_{horizon}h"
    ].to_numpy(
        dtype=np.float32
    )


    # --------------------------------------------------------
    # X-DIRECTION MODEL
    # --------------------------------------------------------

    model_dx = (
        HistGradientBoostingRegressor(
            learning_rate=0.06,
            max_iter=250,
            max_leaf_nodes=31,
            min_samples_leaf=30,
            l2_regularization=0.2,
            random_state=42,
        )
    )

    print(
        f"\nTraining {horizon}h "
        f"east-west model..."
    )

    model_dx.fit(
        X_train,
        y_dx_train
    )


    # --------------------------------------------------------
    # Y-DIRECTION MODEL
    # --------------------------------------------------------

    model_dy = (
        HistGradientBoostingRegressor(
            learning_rate=0.06,
            max_iter=250,
            max_leaf_nodes=31,
            min_samples_leaf=30,
            l2_regularization=0.2,
            random_state=42,
        )
    )

    print(
        f"Training {horizon}h "
        f"north-south model..."
    )

    model_dy.fit(
        X_train,
        y_dy_train
    )


    # --------------------------------------------------------
    # SAVE MODELS
    # --------------------------------------------------------

    dx_model_file = (
        MODEL_DIR
        / f"iceberg_model_{horizon}h_dx.joblib"
    )

    dy_model_file = (
        MODEL_DIR
        / f"iceberg_model_{horizon}h_dy.joblib"
    )

    joblib.dump(
        model_dx,
        dx_model_file
    )

    joblib.dump(
        model_dy,
        dy_model_file
    )


    # --------------------------------------------------------
    # VALIDATION PREDICTIONS
    # --------------------------------------------------------

    pred_dx = model_dx.predict(
        X_validation
    )

    pred_dy = model_dy.predict(
        X_validation
    )


    pred_lat, pred_lon = (
        destination_from_displacement(
            validation[
                "current_latitude"
            ].to_numpy(),
            validation[
                "current_longitude"
            ].to_numpy(),
            pred_dx,
            pred_dy
        )
    )


    true_lat = validation[
        f"true_lat_{horizon}h"
    ].to_numpy(
        dtype=float
    )

    true_lon = validation[
        f"true_lon_{horizon}h"
    ].to_numpy(
        dtype=float
    )


    error = haversine_km(
        pred_lat,
        pred_lon,
        true_lat,
        true_lon
    )


    # --------------------------------------------------------
    # METRICS
    # --------------------------------------------------------

    metrics = calculate_metrics(
        error
    )

    all_metrics[
        f"{horizon}h"
    ] = metrics

    print(
        f"\n{horizon}h validation results:"
    )

    print_metrics(
        metrics
    )


    # --------------------------------------------------------
    # COMPARE WITH BEST BASELINE
    # --------------------------------------------------------

    baseline_rmse = {
        24: 4.572,
        48: 8.108,
        72: 12.087,
    }[horizon]


    improvement = (
        (
            baseline_rmse
            - metrics["rmse_km"]
        )
        / baseline_rmse
        * 100.0
    )


    print(
        "\nCompared with 3-day "
        "mean-velocity baseline:"
    )

    print(
        f"  Baseline RMSE : "
        f"{baseline_rmse:.3f} km"
    )

    print(
        f"  ML RMSE       : "
        f"{metrics['rmse_km']:.3f} km"
    )

    print(
        f"  Improvement   : "
        f"{improvement:+.2f}%"
    )


    all_metrics[
        f"{horizon}h"
    ][
        "baseline_rmse_km"
    ] = baseline_rmse

    all_metrics[
        f"{horizon}h"
    ][
        "rmse_improvement_percent"
    ] = float(
        improvement
    )


    # --------------------------------------------------------
    # SAVE PREDICTIONS
    # --------------------------------------------------------

    prediction_output[
        f"pred_dx_{horizon}h"
    ] = pred_dx

    prediction_output[
        f"pred_dy_{horizon}h"
    ] = pred_dy

    prediction_output[
        f"pred_lat_{horizon}h"
    ] = pred_lat

    prediction_output[
        f"pred_lon_{horizon}h"
    ] = pred_lon

    prediction_output[
        f"true_lat_{horizon}h"
    ] = true_lat

    prediction_output[
        f"true_lon_{horizon}h"
    ] = true_lon

    prediction_output[
        f"error_km_{horizon}h"
    ] = error


# ============================================================
# SAVE METRICS
# ============================================================

with open(
    METRICS_FILE,
    "w"
) as f:

    json.dump(
        all_metrics,
        f,
        indent=2
    )


prediction_output.to_csv(
    PREDICTIONS_FILE,
    index=False
)


# ============================================================
# FINAL SUMMARY
# ============================================================

print("\n" + "=" * 75)
print("TRAJECTORY ML VALIDATION SUMMARY")
print("=" * 75)

for horizon in [
    24,
    48,
    72,
]:

    result = all_metrics[
        f"{horizon}h"
    ]

    print(
        f"\n{horizon}h:"
    )

    print(
        f"  RMSE        : "
        f"{result['rmse_km']:.3f} km"
    )

    print(
        f"  Mean error  : "
        f"{result['mean_error_km']:.3f} km"
    )

    print(
        f"  Within 5 km : "
        f"{result['within_5km_percent']:.2f}%"
    )

    print(
        f"  RMSE gain   : "
        f"{result['rmse_improvement_percent']:+.2f}%"
    )


print("\nModels saved in:")
print(MODEL_DIR)

print("\nMetrics saved:")
print(METRICS_FILE)

print("\nPredictions saved:")
print(PREDICTIONS_FILE)

print(
    "\n2025 TEST SET HAS NOT BEEN USED."
)

print("=" * 75)
print("TRAINING COMPLETE")
print("=" * 75)