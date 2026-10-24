# ============================================================
# POLARGUARD MEMBER 2 V1 VALIDATION
#
# Purpose:
#   Evaluate the current frozen environment-v1 Member 2 model.
#
# Outputs:
#   1. Actual vs Predicted positions
#   2. Train / Validation / Test metrics
#   3. Baseline comparison
#   4. Generalization gap table
#   5. CSV files
#   6. RMSE comparison plot
#
# IMPORTANT:
#   RUN_FINAL_TEST_2025 = False by default.
#
#   Keep it False while we are still developing Member 2 V2.
#   Turn it True only when we are ready for the FINAL locked
#   comparison.
# ============================================================

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

import matplotlib.pyplot as plt


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
    / "environment"
)

OUTPUT_DIR = (
    BASE
    / "outputs"
    / "member2_v1_validation"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
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


# ------------------------------------------------------------
# IMPORTANT
#
# Keep FALSE while developing / comparing new architectures.
#
# Change to True only when V1 and V2 are frozen and you want
# the final 2025 held-out test.
# ------------------------------------------------------------

RUN_FINAL_TEST_2025 = False


# ============================================================
# EXACT 26 FEATURES USED BY FINAL MEMBER 2
# ============================================================

FEATURE_COLUMNS = [

    # --------------------------------------------------------
    # Current position
    # --------------------------------------------------------

    "current_latitude",
    "current_longitude",

    # --------------------------------------------------------
    # Recent displacement / velocity
    # --------------------------------------------------------

    "vx_tm3_tm2",
    "vy_tm3_tm2",

    "vx_tm2_tm1",
    "vy_tm2_tm1",

    "vx_tm1_t",
    "vy_tm1_t",

    # --------------------------------------------------------
    # Speed
    # --------------------------------------------------------

    "speed_tm3_tm2",
    "speed_tm2_tm1",
    "speed_tm1_t",

    # --------------------------------------------------------
    # Acceleration
    # --------------------------------------------------------

    "accel_x_previous",
    "accel_y_previous",

    "accel_x_recent",
    "accel_y_recent",

    # --------------------------------------------------------
    # 3-day motion
    # --------------------------------------------------------

    "mean_vx_3day",
    "mean_vy_3day",
    "mean_speed_3day",

    # --------------------------------------------------------
    # Seasonality
    # --------------------------------------------------------

    "doy_sin",
    "doy_cos",

    # --------------------------------------------------------
    # ERA5 wind
    # --------------------------------------------------------

    "wind_u10",
    "wind_v10",

    # --------------------------------------------------------
    # GLORYS ocean current
    # --------------------------------------------------------

    "ocean_uo",
    "ocean_vo",

    # --------------------------------------------------------
    # Sea ice
    # --------------------------------------------------------

    "sea_ice_sic_filled",
    "sea_ice_available",
]


# ============================================================
# GEOGRAPHIC HELPERS
# ============================================================

def destination_from_displacement(
    lat,
    lon,
    dx_km,
    dy_km,
):
    """
    Convert east/north displacement in kilometres
    into approximate future latitude / longitude.

    This follows the deployed Member 2 service logic.
    """

    lat = np.asarray(
        lat,
        dtype=float,
    )

    lon = np.asarray(
        lon,
        dtype=float,
    )

    dx_km = np.asarray(
        dx_km,
        dtype=float,
    )

    dy_km = np.asarray(
        dy_km,
        dtype=float,
    )

    lat_rad = np.radians(
        lat
    )

    # --------------------------------------------------------
    # Latitude
    # --------------------------------------------------------

    future_lat = (
        lat
        +
        np.degrees(
            dy_km
            /
            EARTH_RADIUS_KM
        )
    )

    # --------------------------------------------------------
    # Longitude
    # --------------------------------------------------------

    cos_lat = np.cos(
        lat_rad
    )

    cos_lat = np.where(
        np.abs(cos_lat) < 1e-8,
        1e-8,
        cos_lat,
    )

    future_lon = (
        lon
        +
        np.degrees(
            dx_km
            /
            (
                EARTH_RADIUS_KM
                *
                cos_lat
            )
        )
    )

    # Normalize longitude to [-180, +180]

    future_lon = (
        (
            future_lon
            + 180.0
        )
        % 360.0
    ) - 180.0

    return (
        future_lat,
        future_lon,
    )


# ============================================================
# HAVERSINE DISTANCE
# ============================================================

def haversine_km(
    lat1,
    lon1,
    lat2,
    lon2,
):
    """
    Great-circle geographic distance in kilometres.
    """

    lat1 = np.radians(
        np.asarray(
            lat1,
            dtype=float,
        )
    )

    lon1 = np.radians(
        np.asarray(
            lon1,
            dtype=float,
        )
    )

    lat2 = np.radians(
        np.asarray(
            lat2,
            dtype=float,
        )
    )

    lon2 = np.radians(
        np.asarray(
            lon2,
            dtype=float,
        )
    )

    dlat = (
        lat2
        - lat1
    )

    dlon = (
        lon2
        - lon1
    )

    # Handle the +/-180 degree dateline

    dlon = (
        dlon
        + np.pi
    ) % (
        2.0
        * np.pi
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
        1.0,
    )

    c = (
        2.0
        *
        np.arctan2(
            np.sqrt(a),
            np.sqrt(
                1.0 - a
            ),
        )
    )

    return (
        EARTH_RADIUS_KM
        * c
    )


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(
    errors,
):
    """
    Calculate trajectory-position error metrics.
    """

    errors = np.asarray(
        errors,
        dtype=float,
    )

    return {

        "samples":
            int(
                len(errors)
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

        "rmse_km":
            float(
                np.sqrt(
                    np.mean(
                        errors ** 2
                    )
                )
            ),

        "p90_error_km":
            float(
                np.percentile(
                    errors,
                    90,
                )
            ),

        "p95_error_km":
            float(
                np.percentile(
                    errors,
                    95,
                )
            ),

        "within_1km_pct":
            float(
                100.0
                *
                np.mean(
                    errors <= 1.0
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

        "within_10km_pct":
            float(
                100.0
                *
                np.mean(
                    errors <= 10.0
                )
            ),

        "within_25km_pct":
            float(
                100.0
                *
                np.mean(
                    errors <= 25.0
                )
            ),
    }


# ============================================================
# MODEL LOADING
# ============================================================

def load_models():
    """
    Load the frozen Member 2 environment-v1 models.

    Six models:
        24h dx
        24h dy

        48h dx
        48h dy

        72h dx
        72h dy
    """

    models = {}

    for horizon in HORIZONS:

        dx_file = (
            MODEL_DIR
            /
            f"iceberg_environment_{horizon}h_dx.joblib"
        )

        dy_file = (
            MODEL_DIR
            /
            f"iceberg_environment_{horizon}h_dy.joblib"
        )

        if not dx_file.exists():

            raise FileNotFoundError(
                f"Missing DX model:\n{dx_file}"
            )

        if not dy_file.exists():

            raise FileNotFoundError(
                f"Missing DY model:\n{dy_file}"
            )

        models[
            horizon
        ] = {

            "dx":
                joblib.load(
                    dx_file
                ),

            "dy":
                joblib.load(
                    dy_file
                ),
        }

    return models


# ============================================================
# DATA QUALITY CHECK
# ============================================================

def validate_dataset(
    df,
):
    """
    Ensure all required columns exist before evaluation.
    """

    required_columns = list(
        FEATURE_COLUMNS
    )

    required_columns += [

        "iceberg_id",
        "init_date",
        "data_split",

        "current_latitude",
        "current_longitude",
    ]

    for horizon in HORIZONS:

        required_columns.extend(
            [
                f"target_dx_{horizon}h",
                f"target_dy_{horizon}h",

                f"true_lat_{horizon}h",
                f"true_lon_{horizon}h",
            ]
        )

    missing = [

        column

        for column in required_columns

        if column not in df.columns
    ]

    if missing:

        raise ValueError(
            "Dataset is missing required columns:\n"
            +
            "\n".join(
                missing
            )
        )

    feature_nan_count = int(
        df[
            FEATURE_COLUMNS
        ]
        .isna()
        .sum()
        .sum()
    )

    if feature_nan_count > 0:

        raise ValueError(
            f"Found {feature_nan_count:,} "
            "missing values in model features."
        )


# ============================================================
# EVALUATE ONE DATA SPLIT
# ============================================================

def evaluate_split(
    df,
    split_name,
    models,
):
    """
    Evaluate one split:
        train
        validation
        test

    Returns:
        summary rows
        per-sample prediction rows
        baseline rows
    """

    subset = df[
        df["data_split"]
        ==
        split_name
    ].copy()

    if len(subset) == 0:

        print(
            f"\nNo rows found for split: "
            f"{split_name}"
        )

        return (
            [],
            [],
            [],
        )

    print()
    print("=" * 80)

    print(
        f"EVALUATING: "
        f"{split_name.upper()}"
    )

    print("=" * 80)

    print(
        f"Samples: "
        f"{len(subset):,}"
    )

    print(
        f"Unique icebergs: "
        f"{subset['iceberg_id'].nunique():,}"
    )

    X = subset[
        FEATURE_COLUMNS
    ]

    summary_rows = []

    prediction_rows = []

    baseline_rows = []

    for horizon in HORIZONS:

        print()
        print(
            "-" * 70
        )

        print(
            f"{split_name.upper()} "
            f"{horizon}H"
        )

        print(
            "-" * 70
        )

        # ----------------------------------------------------
        # LOAD FROZEN HORIZON MODELS
        # ----------------------------------------------------

        model_dx = (
            models[
                horizon
            ]["dx"]
        )

        model_dy = (
            models[
                horizon
            ]["dy"]
        )

        # ----------------------------------------------------
        # DIRECT ML PREDICTION
        # ----------------------------------------------------

        pred_dx = (
            model_dx.predict(
                X
            )
        )

        pred_dy = (
            model_dy.predict(
                X
            )
        )

        # ----------------------------------------------------
        # PREDICTED FUTURE POSITION
        # ----------------------------------------------------

        pred_lat, pred_lon = (
            destination_from_displacement(

                subset[
                    "current_latitude"
                ].to_numpy(),

                subset[
                    "current_longitude"
                ].to_numpy(),

                pred_dx,

                pred_dy,
            )
        )

        # ----------------------------------------------------
        # ACTUAL FUTURE POSITION
        # ----------------------------------------------------

        true_lat = (
            subset[
                f"true_lat_{horizon}h"
            ]
            .to_numpy(
                dtype=float
            )
        )

        true_lon = (
            subset[
                f"true_lon_{horizon}h"
            ]
            .to_numpy(
                dtype=float
            )
        )

        # ----------------------------------------------------
        # GEOGRAPHIC POSITION ERROR
        # ----------------------------------------------------

        position_error = (
            haversine_km(
                pred_lat,
                pred_lon,
                true_lat,
                true_lon,
            )
        )

        metrics = (
            calculate_metrics(
                position_error
            )
        )

        # ----------------------------------------------------
        # DX / DY DISPLACEMENT ERROR
        # ----------------------------------------------------

        true_dx = (
            subset[
                f"target_dx_{horizon}h"
            ]
            .to_numpy(
                dtype=float
            )
        )

        true_dy = (
            subset[
                f"target_dy_{horizon}h"
            ]
            .to_numpy(
                dtype=float
            )
        )

        dx_rmse = float(
            np.sqrt(
                np.mean(
                    (
                        pred_dx
                        - true_dx
                    ) ** 2
                )
            )
        )

        dy_rmse = float(
            np.sqrt(
                np.mean(
                    (
                        pred_dy
                        - true_dy
                    ) ** 2
                )
            )
        )

        # ----------------------------------------------------
        # 3-DAY MEAN VELOCITY BASELINE
        # ----------------------------------------------------

        days = (
            horizon
            / 24.0
        )

        baseline_dx = (
            subset[
                "mean_vx_3day"
            ]
            .to_numpy(
                dtype=float
            )
            *
            days
        )

        baseline_dy = (
            subset[
                "mean_vy_3day"
            ]
            .to_numpy(
                dtype=float
            )
            *
            days
        )

        baseline_lat, baseline_lon = (
            destination_from_displacement(

                subset[
                    "current_latitude"
                ].to_numpy(),

                subset[
                    "current_longitude"
                ].to_numpy(),

                baseline_dx,

                baseline_dy,
            )
        )

        baseline_error = (
            haversine_km(
                baseline_lat,
                baseline_lon,
                true_lat,
                true_lon,
            )
        )

        baseline_metrics = (
            calculate_metrics(
                baseline_error
            )
        )

        # ----------------------------------------------------
        # IMPROVEMENT OVER BASELINE
        # ----------------------------------------------------

        baseline_rmse = (
            baseline_metrics[
                "rmse_km"
            ]
        )

        ml_rmse = (
            metrics[
                "rmse_km"
            ]
        )

        if baseline_rmse > 0:

            improvement_pct = (
                (
                    baseline_rmse
                    -
                    ml_rmse
                )
                /
                baseline_rmse
                *
                100.0
            )

        else:

            improvement_pct = (
                np.nan
            )

        # ----------------------------------------------------
        # SUMMARY ROW
        # ----------------------------------------------------

        summary_rows.append(
            {

                "split":
                    split_name,

                "horizon_hours":
                    horizon,

                "samples":
                    metrics[
                        "samples"
                    ],

                "mean_error_km":
                    metrics[
                        "mean_error_km"
                    ],

                "median_error_km":
                    metrics[
                        "median_error_km"
                    ],

                "rmse_km":
                    metrics[
                        "rmse_km"
                    ],

                "p90_error_km":
                    metrics[
                        "p90_error_km"
                    ],

                "p95_error_km":
                    metrics[
                        "p95_error_km"
                    ],

                "within_1km_pct":
                    metrics[
                        "within_1km_pct"
                    ],

                "within_5km_pct":
                    metrics[
                        "within_5km_pct"
                    ],

                "within_10km_pct":
                    metrics[
                        "within_10km_pct"
                    ],

                "within_25km_pct":
                    metrics[
                        "within_25km_pct"
                    ],

                "dx_rmse_km":
                    dx_rmse,

                "dy_rmse_km":
                    dy_rmse,

                "baseline_rmse_km":
                    baseline_rmse,

                "rmse_improvement_vs_baseline_pct":
                    improvement_pct,
            }
        )

        # ----------------------------------------------------
        # BASELINE SUMMARY
        # ----------------------------------------------------

        baseline_rows.append(
            {

                "split":
                    split_name,

                "horizon_hours":
                    horizon,

                "ml_rmse_km":
                    ml_rmse,

                "mean_velocity_baseline_rmse_km":
                    baseline_rmse,

                "ml_improvement_pct":
                    improvement_pct,
            }
        )

        # ----------------------------------------------------
        # PER-SAMPLE ACTUAL VS PREDICTED
        # ----------------------------------------------------

        for i in range(
            len(subset)
        ):

            row = subset.iloc[
                i
            ]

            prediction_rows.append(
                {

                    "split":
                        split_name,

                    "iceberg_id":
                        row[
                            "iceberg_id"
                        ],

                    "init_date":
                        row[
                            "init_date"
                        ],

                    "horizon_hours":
                        horizon,

                    "current_latitude":
                        float(
                            row[
                                "current_latitude"
                            ]
                        ),

                    "current_longitude":
                        float(
                            row[
                                "current_longitude"
                            ]
                        ),

                    "actual_latitude":
                        float(
                            true_lat[
                                i
                            ]
                        ),

                    "actual_longitude":
                        float(
                            true_lon[
                                i
                            ]
                        ),

                    "predicted_latitude":
                        float(
                            pred_lat[
                                i
                            ]
                        ),

                    "predicted_longitude":
                        float(
                            pred_lon[
                                i
                            ]
                        ),

                    "actual_dx_km":
                        float(
                            true_dx[
                                i
                            ]
                        ),

                    "actual_dy_km":
                        float(
                            true_dy[
                                i
                            ]
                        ),

                    "predicted_dx_km":
                        float(
                            pred_dx[
                                i
                            ]
                        ),

                    "predicted_dy_km":
                        float(
                            pred_dy[
                                i
                            ]
                        ),

                    "position_error_km":
                        float(
                            position_error[
                                i
                            ]
                        ),

                    "baseline_position_error_km":
                        float(
                            baseline_error[
                                i
                            ]
                        ),
                }
            )

        # ----------------------------------------------------
        # PRINT RESULTS
        # ----------------------------------------------------

        print(
            f"ML RMSE             : "
            f"{metrics['rmse_km']:.3f} km"
        )

        print(
            f"Mean error          : "
            f"{metrics['mean_error_km']:.3f} km"
        )

        print(
            f"Median error        : "
            f"{metrics['median_error_km']:.3f} km"
        )

        print(
            f"Within 5 km         : "
            f"{metrics['within_5km_pct']:.2f}%"
        )

        print(
            f"3-day baseline RMSE : "
            f"{baseline_rmse:.3f} km"
        )

        print(
            f"RMSE improvement    : "
            f"{improvement_pct:+.2f}%"
        )

    return (
        summary_rows,
        prediction_rows,
        baseline_rows,
    )


# ============================================================
# GENERALIZATION TABLE
# ============================================================

def build_generalization_table(
    summary_df,
):
    """
    Create Train vs Validation vs Test RMSE table.
    """

    rows = []

    for horizon in HORIZONS:

        horizon_data = (
            summary_df[
                summary_df[
                    "horizon_hours"
                ]
                ==
                horizon
            ]
        )

        def get_rmse(
            split_name,
        ):

            values = (
                horizon_data[
                    horizon_data[
                        "split"
                    ]
                    ==
                    split_name
                ][
                    "rmse_km"
                ]
            )

            if len(values) == 0:

                return np.nan

            return float(
                values.iloc[
                    0
                ]
            )

        train_rmse = (
            get_rmse(
                "train"
            )
        )

        validation_rmse = (
            get_rmse(
                "validation"
            )
        )

        test_rmse = (
            get_rmse(
                "test"
            )
        )

        validation_gap = (
            validation_rmse
            -
            train_rmse
            if (
                np.isfinite(
                    validation_rmse
                )
                and
                np.isfinite(
                    train_rmse
                )
            )
            else np.nan
        )

        test_gap = (
            test_rmse
            -
            train_rmse
            if (
                np.isfinite(
                    test_rmse
                )
                and
                np.isfinite(
                    train_rmse
                )
            )
            else np.nan
        )

        rows.append(
            {

                "horizon_hours":
                    horizon,

                "train_rmse_km":
                    train_rmse,

                "validation_rmse_km":
                    validation_rmse,

                "test_rmse_km":
                    test_rmse,

                "validation_minus_train_gap_km":
                    validation_gap,

                "test_minus_train_gap_km":
                    test_gap,
            }
        )

    return pd.DataFrame(
        rows
    )


# ============================================================
# PLOT
# ============================================================

def save_rmse_plot(
    summary_df,
):
    """
    Save Train / Validation / Test RMSE comparison.
    """

    pivot = (
        summary_df
        .pivot(
            index="horizon_hours",
            columns="split",
            values="rmse_km",
        )
    )

    wanted_columns = [
        column
        for column in [
            "train",
            "validation",
            "test",
        ]
        if column in pivot.columns
    ]

    pivot = pivot[
        wanted_columns
    ]

    ax = pivot.plot(
        kind="bar",
        figsize=(
            10,
            6,
        ),
    )

    ax.set_title(
        "PolarGuard Member 2 V1 — RMSE Generalization"
    )

    ax.set_xlabel(
        "Forecast Horizon (hours)"
    )

    ax.set_ylabel(
        "Position RMSE (km)"
    )

    ax.grid(
        axis="y",
        alpha=0.25,
    )

    plt.tight_layout()

    output_file = (
        OUTPUT_DIR
        /
        "member2_v1_rmse_generalization.png"
    )

    plt.savefig(
        output_file,
        dpi=180,
        bbox_inches="tight",
    )

    plt.close()

    return output_file


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 80)
    print("POLARGUARD MEMBER 2 V1 VALIDATION")
    print("=" * 80)

    # --------------------------------------------------------
    # CHECK DATA
    # --------------------------------------------------------

    if not DATA_FILE.exists():

        raise FileNotFoundError(
            "Member 2 environment dataset not found:\n"
            f"{DATA_FILE}"
        )

    print(
        "\nDataset:"
    )

    print(
        DATA_FILE
    )

    # --------------------------------------------------------
    # LOAD DATASET
    # --------------------------------------------------------

    df = pd.read_csv(
        DATA_FILE,
        parse_dates=[
            "init_date",
        ],
    )

    print(
        f"\nTotal rows: "
        f"{len(df):,}"
    )

    print(
        "\nSplit sizes:"
    )

    print(
        df[
            "data_split"
        ]
        .value_counts()
    )

    # --------------------------------------------------------
    # QUALITY CHECK
    # --------------------------------------------------------

    validate_dataset(
        df
    )

    print(
        "\nDataset quality check: PASS"
    )

    print(
        f"Features used: "
        f"{len(FEATURE_COLUMNS)}"
    )

    # --------------------------------------------------------
    # LOAD MODELS
    # --------------------------------------------------------

    models = (
        load_models()
    )

    print(
        "\nFrozen Member 2 models loaded successfully."
    )

    print(
        "Model family: "
        "HistGradientBoostingRegressor"
    )

    print(
        "Architecture: "
        "Direct dx/dy trajectory prediction"
    )

    # --------------------------------------------------------
    # CHOOSE SPLITS
    # --------------------------------------------------------

    splits_to_run = [
        "train",
        "validation",
    ]

    if RUN_FINAL_TEST_2025:

        splits_to_run.append(
            "test"
        )

        print()
        print(
            "WARNING:"
        )

        print(
            "2025 FINAL TEST IS ENABLED."
        )

        print(
            "Do not use these results for model tuning."
        )

    else:

        print()
        print(
            "2025 final test remains LOCKED."
        )

        print(
            "Set RUN_FINAL_TEST_2025 = True "
            "only for the final evaluation."
        )

    # --------------------------------------------------------
    # RUN EVALUATION
    # --------------------------------------------------------

    all_summary = []

    all_predictions = []

    all_baselines = []

    for split_name in splits_to_run:

        (
            summary_rows,
            prediction_rows,
            baseline_rows,
        ) = evaluate_split(
            df=df,
            split_name=split_name,
            models=models,
        )

        all_summary.extend(
            summary_rows
        )

        all_predictions.extend(
            prediction_rows
        )

        all_baselines.extend(
            baseline_rows
        )

    # --------------------------------------------------------
    # CREATE TABLES
    # --------------------------------------------------------

    summary_df = pd.DataFrame(
        all_summary
    )

    predictions_df = pd.DataFrame(
        all_predictions
    )

    baseline_df = pd.DataFrame(
        all_baselines
    )

    generalization_df = (
        build_generalization_table(
            summary_df
        )
    )

    # --------------------------------------------------------
    # SAVE RESULTS
    # --------------------------------------------------------

    summary_file = (
        OUTPUT_DIR
        /
        "member2_v1_metrics.csv"
    )

    prediction_file = (
        OUTPUT_DIR
        /
        "member2_v1_actual_vs_predicted.csv"
    )

    baseline_file = (
        OUTPUT_DIR
        /
        "member2_v1_baseline_comparison.csv"
    )

    generalization_file = (
        OUTPUT_DIR
        /
        "member2_v1_generalization_matrix.csv"
    )

    summary_df.to_csv(
        summary_file,
        index=False,
    )

    predictions_df.to_csv(
        prediction_file,
        index=False,
    )

    baseline_df.to_csv(
        baseline_file,
        index=False,
    )

    generalization_df.to_csv(
        generalization_file,
        index=False,
    )

    # --------------------------------------------------------
    # SAVE TEST-ONLY ACTUAL VS PREDICTED
    # --------------------------------------------------------

    if RUN_FINAL_TEST_2025:

        test_predictions = (
            predictions_df[
                predictions_df[
                    "split"
                ]
                ==
                "test"
            ]
            .copy()
        )

        test_file = (
            OUTPUT_DIR
            /
            "member2_v1_2025_test_actual_vs_predicted.csv"
        )

        test_predictions.to_csv(
            test_file,
            index=False,
        )

    # --------------------------------------------------------
    # SAVE GRAPH
    # --------------------------------------------------------

    plot_file = (
        save_rmse_plot(
            summary_df
        )
    )

    # --------------------------------------------------------
    # PRINT SUMMARY
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("MEMBER 2 V1 METRICS")
    print("=" * 80)

    display_columns = [

        "split",
        "horizon_hours",
        "samples",
        "rmse_km",
        "mean_error_km",
        "median_error_km",
        "within_5km_pct",
        "baseline_rmse_km",
        "rmse_improvement_vs_baseline_pct",
    ]

    print()

    print(
        summary_df[
            display_columns
        ]
        .round(
            3
        )
        .to_string(
            index=False
        )
    )

    print()
    print("=" * 80)
    print("GENERALIZATION MATRIX")
    print("=" * 80)

    print()

    print(
        generalization_df
        .round(
            3
        )
        .to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # FILE LOCATIONS
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("OUTPUT FILES")
    print("=" * 80)

    print(
        f"\nMetrics:\n"
        f"{summary_file}"
    )

    print(
        f"\nActual vs Predicted:\n"
        f"{prediction_file}"
    )

    print(
        f"\nBaseline Comparison:\n"
        f"{baseline_file}"
    )

    print(
        f"\nGeneralization Matrix:\n"
        f"{generalization_file}"
    )

    print(
        f"\nRMSE Plot:\n"
        f"{plot_file}"
    )

    print()
    print("=" * 80)
    print("MEMBER 2 V1 VALIDATION COMPLETE")
    print("=" * 80)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()