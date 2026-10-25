from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import HistGradientBoostingRegressor


# ============================================================
# PATHS
# ============================================================

BASE = Path(__file__).resolve().parent

DATA_FILE = (
    BASE / "data" / "processed" /
    "iceberg_features_environment_ml_ready_2019_2025.csv"
)

MODEL_DIR = BASE / "models" / "environment"

OUTPUT_DIR = BASE / "outputs"

MODEL_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# FEATURES
# ============================================================

TRAJECTORY_FEATURES = [
    "current_latitude",
    "current_longitude",

    "vx_tm3_tm2",
    "vy_tm3_tm2",

    "vx_tm2_tm1",
    "vy_tm2_tm1",

    "vx_tm1_t",
    "vy_tm1_t",

    "speed_tm3_tm2",
    "speed_tm2_tm1",
    "speed_tm1_t",

    "accel_x_previous",
    "accel_y_previous",

    "accel_x_recent",
    "accel_y_recent",

    "mean_vx_3day",
    "mean_vy_3day",
    "mean_speed_3day",

    "doy_sin",
    "doy_cos",
]


ENVIRONMENT_FEATURES = [
    "wind_u10",
    "wind_v10",

    "ocean_uo",
    "ocean_vo",

    "sea_ice_sic_filled",
    "sea_ice_available",
]


FEATURES = (
    TRAJECTORY_FEATURES
    + ENVIRONMENT_FEATURES
)


# ============================================================
# TARGETS
# ============================================================

HORIZONS = [24, 48, 72]


# ============================================================
# TRAJECTORY MATH
# ============================================================

EARTH_RADIUS_KM = 6371.0088


def destination_from_displacement(
    lat,
    lon,
    dx_km,
    dy_km
):
    """
    Convert local east/north displacement into future lat/lon.

    This matches the local Cartesian target representation used
    during feature generation.
    """

    lat = np.asarray(lat, dtype=np.float64)
    lon = np.asarray(lon, dtype=np.float64)

    dx_km = np.asarray(dx_km, dtype=np.float64)
    dy_km = np.asarray(dy_km, dtype=np.float64)

    lat_rad = np.radians(lat)

    predicted_lat = (
        lat
        + np.degrees(
            dy_km / EARTH_RADIUS_KM
        )
    )

    cos_lat = np.cos(lat_rad)

    cos_lat = np.where(
        np.abs(cos_lat) < 1e-8,
        1e-8,
        cos_lat
    )

    predicted_lon = (
        lon
        + np.degrees(
            dx_km /
            (EARTH_RADIUS_KM * cos_lat)
        )
    )

    predicted_lon = (
        (predicted_lon + 180.0) % 360.0
    ) - 180.0

    return predicted_lat, predicted_lon


def haversine_km(
    lat1,
    lon1,
    lat2,
    lon2
):
    lat1 = np.radians(
        np.asarray(lat1, dtype=np.float64)
    )

    lon1 = np.radians(
        np.asarray(lon1, dtype=np.float64)
    )

    lat2 = np.radians(
        np.asarray(lat2, dtype=np.float64)
    )

    lon2 = np.radians(
        np.asarray(lon2, dtype=np.float64)
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        np.sin(dlat / 2.0) ** 2
        + np.cos(lat1)
        * np.cos(lat2)
        * np.sin(dlon / 2.0) ** 2
    )

    a = np.clip(a, 0.0, 1.0)

    return (
        2.0
        * EARTH_RADIUS_KM
        * np.arcsin(np.sqrt(a))
    )


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(errors):

    errors = np.asarray(
        errors,
        dtype=np.float64
    )

    return {
        "mean_km": float(
            np.mean(errors)
        ),

        "median_km": float(
            np.median(errors)
        ),

        "rmse_km": float(
            np.sqrt(
                np.mean(errors ** 2)
            )
        ),

        "p90_km": float(
            np.percentile(errors, 90)
        ),

        "p95_km": float(
            np.percentile(errors, 95)
        ),

        "within_1km_pct": float(
            100 * np.mean(errors <= 1)
        ),

        "within_5km_pct": float(
            100 * np.mean(errors <= 5)
        ),

        "within_10km_pct": float(
            100 * np.mean(errors <= 10)
        ),

        "within_25km_pct": float(
            100 * np.mean(errors <= 25)
        ),

        "within_50km_pct": float(
            100 * np.mean(errors <= 50)
        ),
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 78)
    print("POLARGUARD ENVIRONMENT-ENHANCED ICEBERG MODEL")
    print("=" * 78)

    # --------------------------------------------------------
    # Load data
    # --------------------------------------------------------

    df = pd.read_csv(
        DATA_FILE,
        parse_dates=["init_date"]
    )

    print(f"\nTotal rows: {len(df)}")

    # --------------------------------------------------------
    # Explicit chronological split
    #
    # 2025 IS NOT USED HERE.
    # --------------------------------------------------------

    train = df[
        df["data_split"] == "train"
    ].copy()

    val = df[
        df["data_split"] == "validation"
    ].copy()

    locked_test = df[
        df["data_split"] == "test"
    ]

    print(f"Training rows:   {len(train)}")
    print(f"Validation rows: {len(val)}")
    print(
        f"Locked test rows: {len(locked_test)} "
        "(NOT EVALUATED)"
    )

    if len(train) != 84493:
        raise ValueError(
            f"Unexpected training size: {len(train)}"
        )

    if len(val) != 13490:
        raise ValueError(
            f"Unexpected validation size: {len(val)}"
        )

    # --------------------------------------------------------
    # Feature validation
    # --------------------------------------------------------

    missing_columns = [
        col for col in FEATURES
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing features: {missing_columns}"
        )

    print(
        f"\nNumber of model features: "
        f"{len(FEATURES)}"
    )

    print("\nFeatures:")

    for i, feature in enumerate(
        FEATURES,
        start=1
    ):
        print(f"{i:2d}. {feature}")

    train_nan = int(
        train[FEATURES]
        .isna()
        .sum()
        .sum()
    )

    val_nan = int(
        val[FEATURES]
        .isna()
        .sum()
        .sum()
    )

    print(f"\nTraining feature NaNs: {train_nan}")
    print(f"Validation feature NaNs: {val_nan}")

    if train_nan != 0 or val_nan != 0:
        raise ValueError(
            "NaNs found in model features."
        )

    X_train = train[FEATURES]
    X_val = val[FEATURES]

    # --------------------------------------------------------
    # Existing trajectory-only benchmark
    # --------------------------------------------------------

    baseline_rmse = {
        24: 4.005,
        48: 6.645,
        72: 9.530,
    }

    all_metrics = {}

    prediction_output = val[
        [
            "iceberg_id",
            "init_date",
            "current_latitude",
            "current_longitude",
        ]
    ].copy()

    # --------------------------------------------------------
    # Train each horizon
    # --------------------------------------------------------

    for horizon in HORIZONS:

        print()
        print("=" * 78)
        print(
            f"TRAINING {horizon}H "
            f"ENVIRONMENT MODEL"
        )
        print("=" * 78)

        dx_target = f"target_dx_{horizon}h"
        dy_target = f"target_dy_{horizon}h"

        true_lat_col = f"true_lat_{horizon}h"
        true_lon_col = f"true_lon_{horizon}h"

        y_dx = train[dx_target]
        y_dy = train[dy_target]

        # ----------------------------------------------------
        # Same HGB configuration as trajectory-only model
        #
        # This makes the comparison fair:
        # only the feature set changes.
        # ----------------------------------------------------

        model_dx = HistGradientBoostingRegressor(
            learning_rate=0.06,
            max_iter=250,
            max_leaf_nodes=31,
            min_samples_leaf=30,
            l2_regularization=0.2,
            random_state=42,
        )

        model_dy = HistGradientBoostingRegressor(
            learning_rate=0.06,
            max_iter=250,
            max_leaf_nodes=31,
            min_samples_leaf=30,
            l2_regularization=0.2,
            random_state=42,
        )

        print("Training dx model...")
        model_dx.fit(
            X_train,
            y_dx
        )

        print("Training dy model...")
        model_dy.fit(
            X_train,
            y_dy
        )

        # ----------------------------------------------------
        # Save models
        # ----------------------------------------------------

        dx_path = (
            MODEL_DIR /
            f"iceberg_environment_{horizon}h_dx.joblib"
        )

        dy_path = (
            MODEL_DIR /
            f"iceberg_environment_{horizon}h_dy.joblib"
        )

        joblib.dump(
            model_dx,
            dx_path
        )

        joblib.dump(
            model_dy,
            dy_path
        )

        print("Models saved.")

        # ----------------------------------------------------
        # 2024 validation prediction
        # ----------------------------------------------------

        pred_dx = model_dx.predict(X_val)
        pred_dy = model_dy.predict(X_val)

        pred_lat, pred_lon = (
            destination_from_displacement(
                val["current_latitude"].to_numpy(),
                val["current_longitude"].to_numpy(),
                pred_dx,
                pred_dy,
            )
        )

        errors = haversine_km(
            pred_lat,
            pred_lon,
            val[true_lat_col].to_numpy(),
            val[true_lon_col].to_numpy(),
        )

        metrics = calculate_metrics(errors)

        previous_rmse = baseline_rmse[horizon]

        improvement = (
            100.0
            * (
                previous_rmse
                - metrics["rmse_km"]
            )
            / previous_rmse
        )

        metrics[
            "trajectory_only_rmse_km"
        ] = previous_rmse

        metrics[
            "rmse_improvement_vs_trajectory_only_pct"
        ] = float(improvement)

        all_metrics[
            f"{horizon}h"
        ] = metrics

        # ----------------------------------------------------
        # Store predictions
        # ----------------------------------------------------

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
            f"error_km_{horizon}h"
        ] = errors

        # ----------------------------------------------------
        # Print results
        # ----------------------------------------------------

        print()
        print(f"{horizon}H VALIDATION RESULTS")
        print("-" * 50)

        print(
            f"Mean error:   "
            f"{metrics['mean_km']:.3f} km"
        )

        print(
            f"Median error: "
            f"{metrics['median_km']:.3f} km"
        )

        print(
            f"RMSE:         "
            f"{metrics['rmse_km']:.3f} km"
        )

        print(
            f"P90:          "
            f"{metrics['p90_km']:.3f} km"
        )

        print(
            f"P95:          "
            f"{metrics['p95_km']:.3f} km"
        )

        print(
            f"Within 1 km:  "
            f"{metrics['within_1km_pct']:.2f}%"
        )

        print(
            f"Within 5 km:  "
            f"{metrics['within_5km_pct']:.2f}%"
        )

        print(
            f"Within 10 km: "
            f"{metrics['within_10km_pct']:.2f}%"
        )

        print()
        print(
            f"Trajectory-only RMSE: "
            f"{previous_rmse:.3f} km"
        )

        print(
            f"Environment RMSE:      "
            f"{metrics['rmse_km']:.3f} km"
        )

        print(
            f"Improvement:           "
            f"{improvement:+.2f}%"
        )

    # ========================================================
    # SAVE RESULTS
    # ========================================================

    metrics_file = (
        OUTPUT_DIR /
        "iceberg_environment_validation_2024.json"
    )

    with open(
        metrics_file,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            all_metrics,
            f,
            indent=2
        )

    predictions_file = (
        OUTPUT_DIR /
        "iceberg_environment_predictions_2024.csv"
    )

    prediction_output.to_csv(
        predictions_file,
        index=False
    )

    # --------------------------------------------------------
    # Final comparison
    # --------------------------------------------------------

    print()
    print("=" * 78)
    print("FINAL 2024 VALIDATION COMPARISON")
    print("=" * 78)

    print()
    print(
        f"{'Horizon':<10}"
        f"{'Trajectory':>14}"
        f"{'Environment':>14}"
        f"{'Change':>12}"
    )

    print("-" * 50)

    for horizon in HORIZONS:

        m = all_metrics[
            f"{horizon}h"
        ]

        print(
            f"{str(horizon) + 'h':<10}"
            f"{m['trajectory_only_rmse_km']:>12.3f} km"
            f"{m['rmse_km']:>12.3f} km"
            f"{m['rmse_improvement_vs_trajectory_only_pct']:>+10.2f}%"
        )

    print()
    print("Metrics saved:")
    print(metrics_file)

    print()
    print("Predictions saved:")
    print(predictions_file)

    print()
    print(
        "2025 TEST SET WAS NOT EVALUATED."
    )

    print()
    print("=" * 78)
    print("ENVIRONMENT MODEL TRAINING COMPLETE")
    print("=" * 78)


if __name__ == "__main__":
    main()
