from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd

from sklearn.linear_model import Ridge


# ============================================================
# PATHS
# ============================================================

BASE = Path(__file__).resolve().parent

DATA_FILE = (
    BASE
    / "data"
    / "processed"
    / "iceberg_features_environment_ml_ready_2019_2025.csv"
)

MODEL_DIR = (
    BASE
    / "models"
    / "residual_v2"
)

OUTPUT_DIR = (
    BASE
    / "outputs"
    / "member2_v2"
)

MODEL_DIR.mkdir(
    parents=True,
    exist_ok=True
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# SETTINGS
# ============================================================

HORIZONS = [24, 48, 72]

EARTH_RADIUS_KM = 6371.0088

# IMPORTANT:
# 2025 remains completely locked.
RUN_FINAL_TEST_2025 = False


# ============================================================
# PHYSICS-INFORMED BASELINE FEATURES
# ============================================================
#
# These describe:
#
# 1. recent observed iceberg drift
# 2. ocean-current forcing
# 3. wind forcing
# 4. sea-ice concentration
#
# We deliberately keep this baseline small and interpretable.
# ============================================================

BASELINE_FEATURES = [

    # Recent iceberg motion
    "mean_vx_3day",
    "mean_vy_3day",

    # Most recent motion
    "vx_tm1_t",
    "vy_tm1_t",

    # Ocean forcing
    "ocean_uo",
    "ocean_vo",

    # Wind forcing
    "wind_u10",
    "wind_v10",

    # Sea-ice state
    "sea_ice_sic_filled",
]


# ============================================================
# DESTINATION FROM DISPLACEMENT
# ============================================================

def destination_from_displacement(
    lat,
    lon,
    dx,
    dy,
):

    lat = np.asarray(
        lat,
        dtype=float
    )

    lon = np.asarray(
        lon,
        dtype=float
    )

    dx = np.asarray(
        dx,
        dtype=float
    )

    dy = np.asarray(
        dy,
        dtype=float
    )

    lat_rad = np.radians(
        lat
    )

    pred_lat = (
        lat
        +
        np.degrees(
            dy / EARTH_RADIUS_KM
        )
    )

    cos_lat = np.cos(
        lat_rad
    )

    cos_lat = np.where(
        np.abs(cos_lat) < 1e-8,
        1e-8,
        cos_lat
    )

    pred_lon = (
        lon
        +
        np.degrees(
            dx
            /
            (
                EARTH_RADIUS_KM
                *
                cos_lat
            )
        )
    )

    pred_lon = (
        (pred_lon + 180.0)
        % 360.0
    ) - 180.0

    return pred_lat, pred_lon


# ============================================================
# HAVERSINE
# ============================================================

def haversine_km(
    lat1,
    lon1,
    lat2,
    lon2,
):

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
        *
        np.cos(lat2)
        *
        np.sin(dlon / 2.0) ** 2
    )

    a = np.clip(
        a,
        0.0,
        1.0
    )

    return (
        2.0
        *
        EARTH_RADIUS_KM
        *
        np.arcsin(
            np.sqrt(a)
        )
    )


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(errors):

    errors = np.asarray(
        errors,
        dtype=float
    )

    return {

        "samples":
            int(len(errors)),

        "mean_error_km":
            float(
                np.mean(errors)
            ),

        "median_error_km":
            float(
                np.median(errors)
            ),

        "rmse_km":
            float(
                np.sqrt(
                    np.mean(
                        errors ** 2
                    )
                )
            ),

        "within_5km_pct":
            float(
                100.0
                *
                np.mean(
                    errors <= 5.0
                )
            ),
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("POLARGUARD MEMBER 2 V2")
    print("PHYSICS-INFORMED DRIFT BASELINE")
    print("=" * 80)

    # --------------------------------------------------------
    # LOAD DATA
    # --------------------------------------------------------

    if not DATA_FILE.exists():

        raise FileNotFoundError(
            f"Dataset not found:\n{DATA_FILE}"
        )

    df = pd.read_csv(
        DATA_FILE,
        parse_dates=["init_date"]
    )

    print(
        f"\nTotal rows: {len(df):,}"
    )

    print("\nSplit sizes:")

    print(
        df["data_split"]
        .value_counts()
    )


    # ========================================================
    # KEEP 2025 LOCKED
    # ========================================================

    train = df[
        df["data_split"] == "train"
    ].copy()

    validation = df[
        df["data_split"] == "validation"
    ].copy()

    test = df[
        df["data_split"] == "test"
    ].copy()

    print(
        f"\nTraining rows:   {len(train):,}"
    )

    print(
        f"Validation rows: {len(validation):,}"
    )

    print(
        f"Locked test rows:{len(test):,}"
    )

    if not RUN_FINAL_TEST_2025:

        print(
            "\n2025 TEST SET REMAINS LOCKED."
        )


    # ========================================================
    # DATA QUALITY
    # ========================================================

    required = (
        BASELINE_FEATURES.copy()
    )

    for horizon in HORIZONS:

        required.extend(
            [
                f"target_dx_{horizon}h",
                f"target_dy_{horizon}h",
                f"true_lat_{horizon}h",
                f"true_lon_{horizon}h",
            ]
        )

    missing_columns = [
        col
        for col in required
        if col not in df.columns
    ]

    if missing_columns:

        raise ValueError(
            "Missing columns:\n"
            +
            "\n".join(
                missing_columns
            )
        )

    print(
        "\nRequired columns: PASS"
    )


    # ========================================================
    # BASELINE TRAINING
    # ========================================================

    X_train = train[
        BASELINE_FEATURES
    ]

    X_val = validation[
        BASELINE_FEATURES
    ]

    results = []

    prediction_output = validation[
        [
            "iceberg_id",
            "init_date",
            "current_latitude",
            "current_longitude",
        ]
    ].copy()


    for horizon in HORIZONS:

        print()
        print("=" * 70)

        print(
            f"{horizon}H PHYSICS-INFORMED BASELINE"
        )

        print("=" * 70)


        # ====================================================
        # TARGETS
        # ====================================================

        y_dx_train = train[
            f"target_dx_{horizon}h"
        ]

        y_dy_train = train[
            f"target_dy_{horizon}h"
        ]


        # ====================================================
        # SIMPLE INTERPRETABLE DRIFT MODEL
        # ====================================================
        #
        # Ridge is used here instead of a complex nonlinear ML
        # model so that this remains a simple, interpretable
        # drift baseline.
        #
        # This is NOT the residual ML model.
        # ====================================================

        baseline_dx_model = Ridge(
            alpha=1.0
        )

        baseline_dy_model = Ridge(
            alpha=1.0
        )


        baseline_dx_model.fit(
            X_train,
            y_dx_train
        )

        baseline_dy_model.fit(
            X_train,
            y_dy_train
        )


        # ====================================================
        # SAVE BASELINE MODELS
        # ====================================================

        dx_model_file = (
            MODEL_DIR
            /
            f"physics_baseline_{horizon}h_dx.joblib"
        )

        dy_model_file = (
            MODEL_DIR
            /
            f"physics_baseline_{horizon}h_dy.joblib"
        )

        joblib.dump(
            baseline_dx_model,
            dx_model_file
        )

        joblib.dump(
            baseline_dy_model,
            dy_model_file
        )


        # ====================================================
        # VALIDATION PREDICTION
        # ====================================================

        baseline_dx = (
            baseline_dx_model.predict(
                X_val
            )
        )

        baseline_dy = (
            baseline_dy_model.predict(
                X_val
            )
        )


        # ====================================================
        # CONVERT TO LAT/LON
        # ====================================================

        pred_lat, pred_lon = (
            destination_from_displacement(

                validation[
                    "current_latitude"
                ],

                validation[
                    "current_longitude"
                ],

                baseline_dx,

                baseline_dy,
            )
        )


        # ====================================================
        # ACTUAL POSITIONS
        # ====================================================

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


        # ====================================================
        # ERROR
        # ====================================================

        errors = haversine_km(
            pred_lat,
            pred_lon,
            true_lat,
            true_lon
        )

        metrics = calculate_metrics(
            errors
        )


        # ====================================================
        # SAVE PREDICTIONS
        # ====================================================

        prediction_output[
            f"baseline_dx_{horizon}h"
        ] = baseline_dx

        prediction_output[
            f"baseline_dy_{horizon}h"
        ] = baseline_dy

        prediction_output[
            f"baseline_lat_{horizon}h"
        ] = pred_lat

        prediction_output[
            f"baseline_lon_{horizon}h"
        ] = pred_lon

        prediction_output[
            f"true_lat_{horizon}h"
        ] = true_lat

        prediction_output[
            f"true_lon_{horizon}h"
        ] = true_lon

        prediction_output[
            f"error_km_{horizon}h"
        ] = errors


        # ====================================================
        # COEFFICIENTS
        # ====================================================

        print(
            "\nLearned drift coefficients:"
        )

        for feature, coefficient in zip(
            BASELINE_FEATURES,
            baseline_dx_model.coef_
        ):

            print(
                f"DX  {feature:25s} "
                f"{coefficient:+.6f}"
            )

        print()

        for feature, coefficient in zip(
            BASELINE_FEATURES,
            baseline_dy_model.coef_
        ):

            print(
                f"DY  {feature:25s} "
                f"{coefficient:+.6f}"
            )


        # ====================================================
        # RESULTS
        # ====================================================

        print()

        print(
            f"Validation RMSE       : "
            f"{metrics['rmse_km']:.3f} km"
        )

        print(
            f"Mean error            : "
            f"{metrics['mean_error_km']:.3f} km"
        )

        print(
            f"Median error          : "
            f"{metrics['median_error_km']:.3f} km"
        )

        print(
            f"Within 5 km           : "
            f"{metrics['within_5km_pct']:.2f}%"
        )


        results.append(
            {

                "horizon_hours":
                    horizon,

                "samples":
                    metrics["samples"],

                "rmse_km":
                    metrics["rmse_km"],

                "mean_error_km":
                    metrics["mean_error_km"],

                "median_error_km":
                    metrics["median_error_km"],

                "within_5km_pct":
                    metrics["within_5km_pct"],
            }
        )


    # ========================================================
    # SAVE RESULTS
    # ========================================================

    results_df = pd.DataFrame(
        results
    )

    metrics_file = (
        OUTPUT_DIR
        /
        "physics_baseline_validation_2024.csv"
    )

    prediction_file = (
        OUTPUT_DIR
        /
        "physics_baseline_predictions_2024.csv"
    )

    results_df.to_csv(
        metrics_file,
        index=False
    )

    prediction_output.to_csv(
        prediction_file,
        index=False
    )


    # ========================================================
    # SAVE CONFIGURATION
    # ========================================================

    config = {

        "name":
            "PolarGuard Member 2 V2 physics-informed baseline",

        "training_period":
            "2019-2023",

        "validation_period":
            "2024",

        "test_period":
            "2025 LOCKED",

        "baseline_model":
            "Ridge",

        "features":
            BASELINE_FEATURES,

        "forecast_horizons_hours":
            HORIZONS,
    }

    config_file = (
        OUTPUT_DIR
        /
        "physics_baseline_config.json"
    )

    with open(
        config_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            config,
            f,
            indent=2
        )


    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print()
    print("=" * 80)
    print("PHYSICS-INFORMED BASELINE SUMMARY")
    print("=" * 80)

    print()

    print(
        results_df
        .round(3)
        .to_string(
            index=False
        )
    )

    print()
    print("Saved:")
    print(metrics_file)
    print(prediction_file)
    print(config_file)

    print()
    print(
        "2025 TEST SET WAS NOT USED."
    )

    print()
    print("=" * 80)
    print("BASELINE BUILD COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()