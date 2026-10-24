from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.ensemble import HistGradientBoostingRegressor
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

OUTPUT_DIR = (
    BASE
    / "outputs"
    / "member2_backtesting"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# IMPORTANT SETTINGS
# ============================================================

EARTH_RADIUS_KM = 6371.0088

HORIZONS = [
    24,
    48,
    72,
]


# ------------------------------------------------------------
# CHRONOLOGICAL BACKTESTS
#
# 2025 IS INTENTIONALLY NOT INCLUDED.
# ------------------------------------------------------------

BACKTEST_YEARS = [
    2022,
    2023,
    2024,
]


# ============================================================
# V1 DIRECT-ML FEATURES
# Exact 26-feature Member 2 feature set
# ============================================================

FULL_FEATURES = [

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
# PHYSICS-INFORMED / KINEMATIC BASELINE FEATURES
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
# MODEL FACTORY
# ============================================================

def make_hist_gradient_boosting():

    return HistGradientBoostingRegressor(

        learning_rate=0.06,

        max_iter=250,

        max_leaf_nodes=31,

        min_samples_leaf=30,

        l2_regularization=0.2,

        random_state=42,
    )


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
        dtype=float,
    )

    lon = np.asarray(
        lon,
        dtype=float,
    )

    dx = np.asarray(
        dx,
        dtype=float,
    )

    dy = np.asarray(
        dy,
        dtype=float,
    )

    lat_rad = np.radians(
        lat
    )

    pred_lat = (
        lat
        +
        np.degrees(
            dy
            /
            EARTH_RADIUS_KM
        )
    )

    cos_lat = np.cos(
        lat_rad
    )

    cos_lat = np.where(
        np.abs(cos_lat) < 1e-8,
        1e-8,
        cos_lat,
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
        (
            pred_lon
            + 180.0
        )
        % 360.0
    ) - 180.0

    return (
        pred_lat,
        pred_lon,
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
        *
        c
    )


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(
    errors,
):

    errors = np.asarray(
        errors,
        dtype=float,
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
# CONVERT DISPLACEMENT TO POSITION ERROR
# ============================================================

def displacement_error(
    data,
    pred_dx,
    pred_dy,
    horizon,
):

    pred_lat, pred_lon = (
        destination_from_displacement(

            data[
                "current_latitude"
            ].to_numpy(),

            data[
                "current_longitude"
            ].to_numpy(),

            pred_dx,

            pred_dy,
        )
    )

    true_lat = (
        data[
            f"true_lat_{horizon}h"
        ]
        .to_numpy(
            dtype=float
        )
    )

    true_lon = (
        data[
            f"true_lon_{horizon}h"
        ]
        .to_numpy(
            dtype=float
        )
    )

    errors = (
        haversine_km(
            pred_lat,
            pred_lon,
            true_lat,
            true_lon,
        )
    )

    return (
        errors,
        pred_lat,
        pred_lon,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 90)
    print("POLARGUARD MEMBER 2")
    print("CHRONOLOGICAL OUT-OF-SAMPLE BACKTEST")
    print("=" * 90)

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
        ],
    )

    df[
        "year"
    ] = (
        df[
            "init_date"
        ]
        .dt.year
    )

    print(
        f"\nTotal rows: "
        f"{len(df):,}"
    )

    print(
        "\nRows by year:"
    )

    print(
        df[
            "year"
        ]
        .value_counts()
        .sort_index()
    )

    # --------------------------------------------------------
    # HARD SAFETY CHECK
    # --------------------------------------------------------

    if 2025 in BACKTEST_YEARS:

        raise RuntimeError(
            "2025 MUST NOT be used during backtesting."
        )

    print()
    print(
        "2025 FINAL TEST SET IS NOT USED."
    )

    print(
        "Backtest years:",
        BACKTEST_YEARS,
    )

    # --------------------------------------------------------
    # DATA QUALITY
    # --------------------------------------------------------

    required_columns = (
        FULL_FEATURES
        +
        BASELINE_FEATURES
        +
        [
            "iceberg_id",
            "init_date",
            "year",
        ]
    )

    for horizon in HORIZONS:

        required_columns.extend(
            [
                f"target_dx_{horizon}h",
                f"target_dy_{horizon}h",
                f"true_lat_{horizon}h",
                f"true_lon_{horizon}h",
            ]
        )

    missing_columns = [

        column

        for column in set(
            required_columns
        )

        if column not in df.columns
    ]

    if missing_columns:

        raise ValueError(
            "Missing required columns:\n"
            +
            "\n".join(
                sorted(
                    missing_columns
                )
            )
        )

    print(
        "\nDataset quality check: PASS"
    )


    # ========================================================
    # STORAGE
    # ========================================================

    results = []

    prediction_rows = []


    # ========================================================
    # EACH UNSEEN YEAR
    # ========================================================

    for evaluation_year in BACKTEST_YEARS:

        print()
        print("=" * 90)

        print(
            f"UNSEEN YEAR: "
            f"{evaluation_year}"
        )

        print("=" * 90)


        # ----------------------------------------------------
        # STRICT CHRONOLOGICAL SPLIT
        #
        # Training = everything BEFORE evaluation year
        #
        # Evaluation = exactly that year
        # ----------------------------------------------------

        train = df[
            df[
                "year"
            ]
            <
            evaluation_year
        ].copy()

        evaluation = df[
            df[
                "year"
            ]
            ==
            evaluation_year
        ].copy()


        # ----------------------------------------------------
        # NEVER ALLOW 2025 INTO TRAINING
        # ----------------------------------------------------

        train = train[
            train[
                "year"
            ]
            <
            2025
        ].copy()


        if len(train) == 0:

            raise RuntimeError(
                f"No training data available "
                f"before {evaluation_year}."
            )

        if len(evaluation) == 0:

            raise RuntimeError(
                f"No evaluation data found "
                f"for {evaluation_year}."
            )


        print(
            f"\nTrain period: "
            f"{int(train['year'].min())}"
            f"–"
            f"{int(train['year'].max())}"
        )

        print(
            f"Training rows: "
            f"{len(train):,}"
        )

        print(
            f"Training icebergs: "
            f"{train['iceberg_id'].nunique():,}"
        )

        print(
            f"\nUnseen evaluation year: "
            f"{evaluation_year}"
        )

        print(
            f"Evaluation rows: "
            f"{len(evaluation):,}"
        )

        print(
            f"Evaluation icebergs: "
            f"{evaluation['iceberg_id'].nunique():,}"
        )


        # ====================================================
        # FEATURE MATRICES
        # ====================================================

        X_train_full = train[
            FULL_FEATURES
        ]

        X_eval_full = evaluation[
            FULL_FEATURES
        ]

        X_train_baseline = train[
            BASELINE_FEATURES
        ]

        X_eval_baseline = evaluation[
            BASELINE_FEATURES
        ]


        # ====================================================
        # HORIZONS
        # ====================================================

        for horizon in HORIZONS:

            print()
            print(
                "-" * 80
            )

            print(
                f"{evaluation_year} "
                f"| {horizon}H"
            )

            print(
                "-" * 80
            )


            # =================================================
            # ACTUAL TARGETS
            # =================================================

            y_dx_train = (
                train[
                    f"target_dx_{horizon}h"
                ]
                .to_numpy(
                    dtype=float
                )
            )

            y_dy_train = (
                train[
                    f"target_dy_{horizon}h"
                ]
                .to_numpy(
                    dtype=float
                )
            )


            # =================================================
            # MODEL A:
            # 3-DAY MEAN VELOCITY BASELINE
            # =================================================

            days = (
                horizon
                / 24.0
            )

            mean_velocity_dx = (
                evaluation[
                    "mean_vx_3day"
                ]
                .to_numpy(
                    dtype=float
                )
                *
                days
            )

            mean_velocity_dy = (
                evaluation[
                    "mean_vy_3day"
                ]
                .to_numpy(
                    dtype=float
                )
                *
                days
            )

            (
                mean_velocity_errors,
                _,
                _,
            ) = displacement_error(

                evaluation,

                mean_velocity_dx,

                mean_velocity_dy,

                horizon,
            )

            mean_velocity_metrics = (
                calculate_metrics(
                    mean_velocity_errors
                )
            )


            # =================================================
            # MODEL B:
            # PHYSICS-INFORMED RIDGE BASELINE
            # =================================================

            physics_dx_model = Ridge(
                alpha=1.0
            )

            physics_dy_model = Ridge(
                alpha=1.0
            )

            physics_dx_model.fit(
                X_train_baseline,
                y_dx_train,
            )

            physics_dy_model.fit(
                X_train_baseline,
                y_dy_train,
            )

            train_physics_dx = (
                physics_dx_model.predict(
                    X_train_baseline
                )
            )

            train_physics_dy = (
                physics_dy_model.predict(
                    X_train_baseline
                )
            )

            eval_physics_dx = (
                physics_dx_model.predict(
                    X_eval_baseline
                )
            )

            eval_physics_dy = (
                physics_dy_model.predict(
                    X_eval_baseline
                )
            )

            (
                physics_errors,
                _,
                _,
            ) = displacement_error(

                evaluation,

                eval_physics_dx,

                eval_physics_dy,

                horizon,
            )

            physics_metrics = (
                calculate_metrics(
                    physics_errors
                )
            )


            # =================================================
            # MODEL C:
            # V1 DIRECT HISTGRADIENTBOOSTING
            # =================================================

            v1_dx_model = (
                make_hist_gradient_boosting()
            )

            v1_dy_model = (
                make_hist_gradient_boosting()
            )

            v1_dx_model.fit(
                X_train_full,
                y_dx_train,
            )

            v1_dy_model.fit(
                X_train_full,
                y_dy_train,
            )

            v1_dx = (
                v1_dx_model.predict(
                    X_eval_full
                )
            )

            v1_dy = (
                v1_dy_model.predict(
                    X_eval_full
                )
            )

            (
                v1_errors,
                v1_lat,
                v1_lon,
            ) = displacement_error(

                evaluation,

                v1_dx,

                v1_dy,

                horizon,
            )

            v1_metrics = (
                calculate_metrics(
                    v1_errors
                )
            )


            # =================================================
            # MODEL D:
            # PHYSICS-INFORMED + ML RESIDUAL
            # =================================================

            residual_dx_train = (
                y_dx_train
                -
                train_physics_dx
            )

            residual_dy_train = (
                y_dy_train
                -
                train_physics_dy
            )

            residual_dx_model = (
                make_hist_gradient_boosting()
            )

            residual_dy_model = (
                make_hist_gradient_boosting()
            )

            residual_dx_model.fit(
                X_train_full,
                residual_dx_train,
            )

            residual_dy_model.fit(
                X_train_full,
                residual_dy_train,
            )

            predicted_residual_dx = (
                residual_dx_model.predict(
                    X_eval_full
                )
            )

            predicted_residual_dy = (
                residual_dy_model.predict(
                    X_eval_full
                )
            )

            v2_dx = (
                eval_physics_dx
                +
                predicted_residual_dx
            )

            v2_dy = (
                eval_physics_dy
                +
                predicted_residual_dy
            )

            (
                v2_errors,
                v2_lat,
                v2_lon,
            ) = displacement_error(

                evaluation,

                v2_dx,

                v2_dy,

                horizon,
            )

            v2_metrics = (
                calculate_metrics(
                    v2_errors
                )
            )


            # =================================================
            # DETERMINE WINNER
            # =================================================

            model_rmses = {

                "3-day mean velocity":
                    mean_velocity_metrics[
                        "rmse_km"
                    ],

                "Physics-informed baseline":
                    physics_metrics[
                        "rmse_km"
                    ],

                "V1 Direct ML":
                    v1_metrics[
                        "rmse_km"
                    ],

                "V2 Residual ML":
                    v2_metrics[
                        "rmse_km"
                    ],
            }

            winner = min(
                model_rmses,
                key=model_rmses.get,
            )


            # =================================================
            # V2 VS V1
            # =================================================

            v2_vs_v1_pct = (
                (
                    v1_metrics[
                        "rmse_km"
                    ]
                    -
                    v2_metrics[
                        "rmse_km"
                    ]
                )
                /
                v1_metrics[
                    "rmse_km"
                ]
                *
                100.0
            )


            # =================================================
            # STORE SUMMARY
            # =================================================

            results.append(
                {

                    "evaluation_year":
                        evaluation_year,

                    "training_end_year":
                        evaluation_year
                        - 1,

                    "horizon_hours":
                        horizon,

                    "training_samples":
                        len(train),

                    "evaluation_samples":
                        len(evaluation),

                    "evaluation_icebergs":
                        evaluation[
                            "iceberg_id"
                        ].nunique(),

                    "mean_velocity_rmse_km":
                        mean_velocity_metrics[
                            "rmse_km"
                        ],

                    "physics_baseline_rmse_km":
                        physics_metrics[
                            "rmse_km"
                        ],

                    "v1_direct_ml_rmse_km":
                        v1_metrics[
                            "rmse_km"
                        ],

                    "v2_residual_ml_rmse_km":
                        v2_metrics[
                            "rmse_km"
                        ],

                    "v1_mean_error_km":
                        v1_metrics[
                            "mean_error_km"
                        ],

                    "v2_mean_error_km":
                        v2_metrics[
                            "mean_error_km"
                        ],

                    "v1_median_error_km":
                        v1_metrics[
                            "median_error_km"
                        ],

                    "v2_median_error_km":
                        v2_metrics[
                            "median_error_km"
                        ],

                    "v1_within_5km_pct":
                        v1_metrics[
                            "within_5km_pct"
                        ],

                    "v2_within_5km_pct":
                        v2_metrics[
                            "within_5km_pct"
                        ],

                    "v2_improvement_vs_v1_pct":
                        v2_vs_v1_pct,

                    "best_model":
                        winner,
                }
            )


            # =================================================
            # ACTUAL VS PREDICTED SAMPLE OUTPUT
            # =================================================

            true_lat = (
                evaluation[
                    f"true_lat_{horizon}h"
                ]
                .to_numpy(
                    dtype=float
                )
            )

            true_lon = (
                evaluation[
                    f"true_lon_{horizon}h"
                ]
                .to_numpy(
                    dtype=float
                )
            )

            for i in range(
                len(evaluation)
            ):

                row = evaluation.iloc[
                    i
                ]

                prediction_rows.append(
                    {

                        "evaluation_year":
                            evaluation_year,

                        "horizon_hours":
                            horizon,

                        "iceberg_id":
                            row[
                                "iceberg_id"
                            ],

                        "init_date":
                            row[
                                "init_date"
                            ],

                        "actual_latitude":
                            true_lat[
                                i
                            ],

                        "actual_longitude":
                            true_lon[
                                i
                            ],

                        "v1_predicted_latitude":
                            v1_lat[
                                i
                            ],

                        "v1_predicted_longitude":
                            v1_lon[
                                i
                            ],

                        "v1_error_km":
                            v1_errors[
                                i
                            ],

                        "v2_predicted_latitude":
                            v2_lat[
                                i
                            ],

                        "v2_predicted_longitude":
                            v2_lon[
                                i
                            ],

                        "v2_error_km":
                            v2_errors[
                                i
                            ],
                    }
                )


            # =================================================
            # PRINT
            # =================================================

            print(
                f"3-day baseline  : "
                f"{mean_velocity_metrics['rmse_km']:.3f} km"
            )

            print(
                f"Physics baseline: "
                f"{physics_metrics['rmse_km']:.3f} km"
            )

            print(
                f"V1 Direct ML    : "
                f"{v1_metrics['rmse_km']:.3f} km"
            )

            print(
                f"V2 Residual ML  : "
                f"{v2_metrics['rmse_km']:.3f} km"
            )

            print(
                f"Winner          : "
                f"{winner}"
            )

            print(
                f"V2 improvement vs V1: "
                f"{v2_vs_v1_pct:+.2f}%"
            )


    # ========================================================
    # DATAFRAMES
    # ========================================================

    results_df = pd.DataFrame(
        results
    )

    predictions_df = pd.DataFrame(
        prediction_rows
    )


    # ========================================================
    # SAVE RAW RESULTS
    # ========================================================

    summary_file = (
        OUTPUT_DIR
        /
        "member2_chronological_backtest.csv"
    )

    predictions_file = (
        OUTPUT_DIR
        /
        "member2_backtest_actual_vs_predicted.csv"
    )

    results_df.to_csv(
        summary_file,
        index=False,
    )

    predictions_df.to_csv(
        predictions_file,
        index=False,
    )


    # ========================================================
    # OVERALL MODEL SUMMARY
    # ========================================================

    overall = (
        results_df
        .groupby(
            "horizon_hours"
        )
        .agg(

            backtests=(
                "evaluation_year",
                "count"
            ),

            mean_v1_rmse_km=(
                "v1_direct_ml_rmse_km",
                "mean"
            ),

            mean_v2_rmse_km=(
                "v2_residual_ml_rmse_km",
                "mean"
            ),

            mean_physics_rmse_km=(
                "physics_baseline_rmse_km",
                "mean"
            ),

            mean_3day_rmse_km=(
                "mean_velocity_rmse_km",
                "mean"
            ),

            mean_v1_within5_pct=(
                "v1_within_5km_pct",
                "mean"
            ),

            mean_v2_within5_pct=(
                "v2_within_5km_pct",
                "mean"
            ),
        )
        .reset_index()
    )

    overall_file = (
        OUTPUT_DIR
        /
        "member2_backtest_overall_summary.csv"
    )

    overall.to_csv(
        overall_file,
        index=False,
    )


    # ========================================================
    # WIN COUNTS
    # ========================================================

    win_counts = (
        results_df[
            "best_model"
        ]
        .value_counts()
        .rename_axis(
            "model"
        )
        .reset_index(
            name="wins"
        )
    )

    win_file = (
        OUTPUT_DIR
        /
        "member2_backtest_win_counts.csv"
    )

    win_counts.to_csv(
        win_file,
        index=False,
    )


    # ========================================================
    # RMSE PLOT
    # ========================================================

    plot_table = (
        results_df[
            [
                "evaluation_year",
                "horizon_hours",
                "v1_direct_ml_rmse_km",
                "v2_residual_ml_rmse_km",
            ]
        ]
        .copy()
    )

    for horizon in HORIZONS:

        horizon_data = (
            plot_table[
                plot_table[
                    "horizon_hours"
                ]
                ==
                horizon
            ]
            .set_index(
                "evaluation_year"
            )
        )

        plot_data = horizon_data[
            [
                "v1_direct_ml_rmse_km",
                "v2_residual_ml_rmse_km",
            ]
        ].copy()

        plot_data.columns = [
            "V1 Direct ML",
            "V2 Residual ML",
        ]

        ax = plot_data.plot(
            kind="bar",
            figsize=(
                9,
                6,
            ),
        )

        ax.set_title(
            f"Member 2 {horizon}h "
            "Chronological Backtest"
        )

        ax.set_xlabel(
            "Unseen Evaluation Year"
        )

        ax.set_ylabel(
            "Position RMSE (km)"
        )

        ax.grid(
            axis="y",
            alpha=0.25,
        )

        plt.tight_layout()

        plot_file = (
            OUTPUT_DIR
            /
            f"member2_backtest_{horizon}h_rmse.png"
        )

        plt.savefig(
            plot_file,
            dpi=180,
            bbox_inches="tight",
        )

        plt.close()


    # ========================================================
    # FINAL PRINT
    # ========================================================

    print()
    print("=" * 90)
    print("CHRONOLOGICAL BACKTEST RESULTS")
    print("=" * 90)

    display_columns = [

        "evaluation_year",

        "horizon_hours",

        "mean_velocity_rmse_km",

        "physics_baseline_rmse_km",

        "v1_direct_ml_rmse_km",

        "v2_residual_ml_rmse_km",

        "v2_improvement_vs_v1_pct",

        "best_model",
    ]

    print()

    print(
        results_df[
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
    print("=" * 90)
    print("AVERAGE ACROSS UNSEEN YEARS")
    print("=" * 90)

    print()

    print(
        overall
        .round(
            3
        )
        .to_string(
            index=False
        )
    )

    print()
    print("=" * 90)
    print("MODEL WIN COUNTS")
    print("=" * 90)

    print()

    print(
        win_counts
        .to_string(
            index=False
        )
    )

    print()
    print("=" * 90)
    print("OUTPUTS")
    print("=" * 90)

    print(
        f"\nBacktest summary:\n"
        f"{summary_file}"
    )

    print(
        f"\nActual vs Predicted:\n"
        f"{predictions_file}"
    )

    print(
        f"\nOverall summary:\n"
        f"{overall_file}"
    )

    print(
        f"\nWin counts:\n"
        f"{win_file}"
    )

    print()

    print(
        "IMPORTANT: 2025 WAS NEVER USED."
    )

    print()
    print("=" * 90)
    print("BACKTEST COMPLETE")
    print("=" * 90)


if __name__ == "__main__":

    main()