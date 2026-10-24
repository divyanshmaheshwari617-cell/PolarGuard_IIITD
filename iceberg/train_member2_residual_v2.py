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
    BASE
    / "data"
    / "processed"
    / "iceberg_features_environment_ml_ready_2019_2025.csv"
)

BASELINE_MODEL_DIR = (
    BASE
    / "models"
    / "residual_v2"
)

RESIDUAL_MODEL_DIR = (
    BASE
    / "models"
    / "residual_v2"
)

OUTPUT_DIR = (
    BASE
    / "outputs"
    / "member2_v2"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

RESIDUAL_MODEL_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# SETTINGS
# ============================================================

EARTH_RADIUS_KM = 6371.0088

HORIZONS = [
    24,
    48,
    72,
]

# Keep final test locked.
RUN_FINAL_TEST_2025 = False


# ============================================================
# BASELINE FEATURES
# ============================================================

BASELINE_FEATURES = [

    "mean_vx_3day",
    "mean_vy_3day",

    "vx_tm1_t",
    "vy_tm1_t",

    "ocean_uo",
    "ocean_vo",

    "wind_u10",
    "wind_v10",

    "sea_ice_sic_filled",
]


# ============================================================
# FULL 26-FEATURE RESIDUAL MODEL
# ============================================================

FEATURE_COLUMNS = [

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

    "wind_u10",
    "wind_v10",

    "ocean_uo",
    "ocean_vo",

    "sea_ice_sic_filled",
    "sea_ice_available",
]


# ============================================================
# GEOGRAPHIC HELPERS
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

    return (
        pred_lat,
        pred_lon
    )


def haversine_km(
    lat1,
    lon1,
    lat2,
    lon2,
):

    lat1 = np.radians(
        np.asarray(
            lat1,
            dtype=float
        )
    )

    lon1 = np.radians(
        np.asarray(
            lon1,
            dtype=float
        )
    )

    lat2 = np.radians(
        np.asarray(
            lat2,
            dtype=float
        )
    )

    lon2 = np.radians(
        np.asarray(
            lon2,
            dtype=float
        )
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

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
        *
        np.cos(lat2)
        *
        np.sin(
            dlon / 2.0
        ) ** 2
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

def calculate_metrics(
    errors
):

    errors = np.asarray(
        errors,
        dtype=float
    )

    return {

        "samples":
            int(
                len(errors)
            ),

        "rmse_km":
            float(
                np.sqrt(
                    np.mean(
                        errors ** 2
                    )
                )
            ),

        "mean_error_km":
            float(
                np.mean(
                    errors
                )
            ),

        "median_error_km":
            float(
                np.median(
                    errors
                )
            ),

        "p90_error_km":
            float(
                np.percentile(
                    errors,
                    90
                )
            ),

        "p95_error_km":
            float(
                np.percentile(
                    errors,
                    95
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
    print("PHYSICS-INFORMED + ML RESIDUAL")
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
        parse_dates=[
            "init_date"
        ]
    )

    train = df[
        df["data_split"]
        ==
        "train"
    ].copy()

    validation = df[
        df["data_split"]
        ==
        "validation"
    ].copy()

    test = df[
        df["data_split"]
        ==
        "test"
    ].copy()

    print(
        f"\nTraining rows: "
        f"{len(train):,}"
    )

    print(
        f"Validation rows: "
        f"{len(validation):,}"
    )

    print(
        f"Locked test rows: "
        f"{len(test):,}"
    )

    print(
        "\n2025 TEST SET REMAINS LOCKED."
    )


    # ========================================================
    # FEATURE MATRICES
    # ========================================================

    X_train_residual = train[
        FEATURE_COLUMNS
    ]

    X_val_residual = validation[
        FEATURE_COLUMNS
    ]

    X_train_baseline = train[
        BASELINE_FEATURES
    ]

    X_val_baseline = validation[
        BASELINE_FEATURES
    ]


    # ========================================================
    # OUTPUT TABLE
    # ========================================================

    prediction_output = validation[
        [
            "iceberg_id",
            "init_date",
            "current_latitude",
            "current_longitude",
        ]
    ].copy()

    results = []


    # ========================================================
    # EACH HORIZON
    # ========================================================

    for horizon in HORIZONS:

        print()
        print("=" * 75)

        print(
            f"{horizon}H RESIDUAL MODEL"
        )

        print("=" * 75)


        # ====================================================
        # LOAD PHYSICS-INFORMED BASELINE
        # ====================================================

        baseline_dx_file = (
            BASELINE_MODEL_DIR
            /
            f"physics_baseline_{horizon}h_dx.joblib"
        )

        baseline_dy_file = (
            BASELINE_MODEL_DIR
            /
            f"physics_baseline_{horizon}h_dy.joblib"
        )

        if not baseline_dx_file.exists():

            raise FileNotFoundError(
                baseline_dx_file
            )

        if not baseline_dy_file.exists():

            raise FileNotFoundError(
                baseline_dy_file
            )

        baseline_dx_model = (
            joblib.load(
                baseline_dx_file
            )
        )

        baseline_dy_model = (
            joblib.load(
                baseline_dy_file
            )
        )


        # ====================================================
        # BASELINE PREDICTION — TRAIN
        # ====================================================

        train_baseline_dx = (
            baseline_dx_model.predict(
                X_train_baseline
            )
        )

        train_baseline_dy = (
            baseline_dy_model.predict(
                X_train_baseline
            )
        )


        # ====================================================
        # ACTUAL TRAIN TARGETS
        # ====================================================

        actual_dx_train = train[
            f"target_dx_{horizon}h"
        ].to_numpy(
            dtype=float
        )

        actual_dy_train = train[
            f"target_dy_{horizon}h"
        ].to_numpy(
            dtype=float
        )


        # ====================================================
        # RESIDUAL TARGETS
        #
        # residual = actual - baseline
        # ====================================================

        residual_dx_train = (
            actual_dx_train
            -
            train_baseline_dx
        )

        residual_dy_train = (
            actual_dy_train
            -
            train_baseline_dy
        )


        print(
            "\nResidual target statistics:"
        )

        print(
            f"DX mean={np.mean(residual_dx_train):+.4f} km "
            f"std={np.std(residual_dx_train):.4f} km"
        )

        print(
            f"DY mean={np.mean(residual_dy_train):+.4f} km "
            f"std={np.std(residual_dy_train):.4f} km"
        )


        # ====================================================
        # TRAIN ML RESIDUAL MODELS
        # ====================================================

        residual_dx_model = (
            HistGradientBoostingRegressor(

                learning_rate=0.06,

                max_iter=250,

                max_leaf_nodes=31,

                min_samples_leaf=30,

                l2_regularization=0.2,

                random_state=42,
            )
        )

        residual_dy_model = (
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
            "\nTraining residual X model..."
        )

        residual_dx_model.fit(
            X_train_residual,
            residual_dx_train
        )

        print(
            "Training residual Y model..."
        )

        residual_dy_model.fit(
            X_train_residual,
            residual_dy_train
        )


        # ====================================================
        # SAVE RESIDUAL MODELS
        # ====================================================

        residual_dx_file = (
            RESIDUAL_MODEL_DIR
            /
            f"residual_v2_{horizon}h_dx.joblib"
        )

        residual_dy_file = (
            RESIDUAL_MODEL_DIR
            /
            f"residual_v2_{horizon}h_dy.joblib"
        )

        joblib.dump(
            residual_dx_model,
            residual_dx_file
        )

        joblib.dump(
            residual_dy_model,
            residual_dy_file
        )


        # ====================================================
        # VALIDATION BASELINE
        # ====================================================

        val_baseline_dx = (
            baseline_dx_model.predict(
                X_val_baseline
            )
        )

        val_baseline_dy = (
            baseline_dy_model.predict(
                X_val_baseline
            )
        )


        # ====================================================
        # ML PREDICTED RESIDUAL
        # ====================================================

        pred_residual_dx = (
            residual_dx_model.predict(
                X_val_residual
            )
        )

        pred_residual_dy = (
            residual_dy_model.predict(
                X_val_residual
            )
        )


        # ====================================================
        # FINAL V2 DISPLACEMENT
        #
        # FINAL = BASELINE + ML RESIDUAL
        # ====================================================

        final_dx = (
            val_baseline_dx
            +
            pred_residual_dx
        )

        final_dy = (
            val_baseline_dy
            +
            pred_residual_dy
        )


        # ====================================================
        # FUTURE LAT / LON
        # ====================================================

        pred_lat, pred_lon = (
            destination_from_displacement(

                validation[
                    "current_latitude"
                ],

                validation[
                    "current_longitude"
                ],

                final_dx,

                final_dy,
            )
        )


        # ====================================================
        # TRUE FUTURE POSITION
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
        # POSITION ERROR
        # ====================================================

        errors = (
            haversine_km(
                pred_lat,
                pred_lon,
                true_lat,
                true_lon
            )
        )

        metrics = (
            calculate_metrics(
                errors
            )
        )


        # ====================================================
        # BASELINE ERROR FOR COMPARISON
        # ====================================================

        baseline_lat, baseline_lon = (
            destination_from_displacement(

                validation[
                    "current_latitude"
                ],

                validation[
                    "current_longitude"
                ],

                val_baseline_dx,

                val_baseline_dy,
            )
        )

        baseline_errors = (
            haversine_km(
                baseline_lat,
                baseline_lon,
                true_lat,
                true_lon
            )
        )

        baseline_metrics = (
            calculate_metrics(
                baseline_errors
            )
        )


        # ====================================================
        # KNOWN V1 VALIDATION RMSE
        # ====================================================

        v1_rmse_lookup = {

            24: 3.974,

            48: 6.521,

            72: 9.403,
        }

        v1_rmse = (
            v1_rmse_lookup[
                horizon
            ]
        )


        # ====================================================
        # IMPROVEMENT
        # ====================================================

        baseline_rmse = (
            baseline_metrics[
                "rmse_km"
            ]
        )

        v2_rmse = (
            metrics[
                "rmse_km"
            ]
        )

        improvement_vs_baseline = (
            (
                baseline_rmse
                -
                v2_rmse
            )
            /
            baseline_rmse
            *
            100.0
        )

        improvement_vs_v1 = (
            (
                v1_rmse
                -
                v2_rmse
            )
            /
            v1_rmse
            *
            100.0
        )


        # ====================================================
        # PRINT
        # ====================================================

        print()

        print(
            f"Physics baseline RMSE : "
            f"{baseline_rmse:.3f} km"
        )

        print(
            f"V1 direct ML RMSE     : "
            f"{v1_rmse:.3f} km"
        )

        print(
            f"V2 residual RMSE      : "
            f"{v2_rmse:.3f} km"
        )

        print(
            f"V2 mean error         : "
            f"{metrics['mean_error_km']:.3f} km"
        )

        print(
            f"V2 median error       : "
            f"{metrics['median_error_km']:.3f} km"
        )

        print(
            f"V2 within 5 km        : "
            f"{metrics['within_5km_pct']:.2f}%"
        )

        print(
            f"Improvement vs baseline: "
            f"{improvement_vs_baseline:+.2f}%"
        )

        print(
            f"Improvement vs V1      : "
            f"{improvement_vs_v1:+.2f}%"
        )


        # ====================================================
        # SAVE VALIDATION PREDICTIONS
        # ====================================================

        prediction_output[
            f"baseline_dx_{horizon}h"
        ] = val_baseline_dx

        prediction_output[
            f"baseline_dy_{horizon}h"
        ] = val_baseline_dy

        prediction_output[
            f"ml_residual_dx_{horizon}h"
        ] = pred_residual_dx

        prediction_output[
            f"ml_residual_dy_{horizon}h"
        ] = pred_residual_dy

        prediction_output[
            f"final_dx_{horizon}h"
        ] = final_dx

        prediction_output[
            f"final_dy_{horizon}h"
        ] = final_dy

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
        ] = errors


        # ====================================================
        # STORE SUMMARY
        # ====================================================

        results.append(
            {

                "horizon_hours":
                    horizon,

                "samples":
                    metrics[
                        "samples"
                    ],

                "physics_baseline_rmse_km":
                    baseline_rmse,

                "v1_direct_ml_rmse_km":
                    v1_rmse,

                "v2_residual_rmse_km":
                    v2_rmse,

                "v2_mean_error_km":
                    metrics[
                        "mean_error_km"
                    ],

                "v2_median_error_km":
                    metrics[
                        "median_error_km"
                    ],

                "v2_within_5km_pct":
                    metrics[
                        "within_5km_pct"
                    ],

                "v2_improvement_vs_baseline_pct":
                    improvement_vs_baseline,

                "v2_improvement_vs_v1_pct":
                    improvement_vs_v1,
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
        "member2_v2_validation_2024.csv"
    )

    predictions_file = (
        OUTPUT_DIR
        /
        "member2_v2_predictions_2024.csv"
    )

    results_df.to_csv(
        metrics_file,
        index=False
    )

    prediction_output.to_csv(
        predictions_file,
        index=False
    )


    # ========================================================
    # SAVE METADATA
    # ========================================================

    metadata = {

        "architecture":
            "physics-informed baseline + ML residual",

        "baseline":
            "Ridge physics-informed drift baseline",

        "residual_model":
            "HistGradientBoostingRegressor",

        "residual_formula":
            "actual displacement - baseline displacement",

        "final_formula":
            "baseline displacement + predicted residual",

        "training_period":
            "2019-2023",

        "validation_period":
            "2024",

        "test_period":
            "2025 LOCKED",

        "features":
            FEATURE_COLUMNS,
    }

    metadata_file = (
        OUTPUT_DIR
        /
        "member2_v2_metadata.json"
    )

    with open(
        metadata_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            metadata,
            f,
            indent=2
        )


    # ========================================================
    # FINAL TABLE
    # ========================================================

    print()
    print("=" * 80)
    print("MEMBER 2 V2 VALIDATION SUMMARY")
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

    print(
        "Saved:"
    )

    print(
        metrics_file
    )

    print(
        predictions_file
    )

    print(
        metadata_file
    )

    print()

    print(
        "2025 TEST SET WAS NOT USED."
    )

    print()

    print("=" * 80)
    print("MEMBER 2 V2 TRAINING COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()