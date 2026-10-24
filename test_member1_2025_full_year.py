from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent

if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

import numpy as np
import pandas as pd
import xarray as xr

from sklearn.metrics import r2_score

from sea_ice_service import predict_sea_ice


# ============================================================
# PATHS
# ============================================================

TEST_FILE = (
    BASE
    / "data"
    / "processed"
    / "test_2025.nc"
)

OUTPUT_DIR = (
    BASE
    / "iceberg"
    / "outputs"
    / "model_testing_2025"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

OVERALL_FILE = (
    OUTPUT_DIR
    / "sic_2025_metrics.csv"
)

DAILY_FILE = (
    OUTPUT_DIR
    / "sic_2025_daily_metrics.csv"
)

MONTHLY_FILE = (
    OUTPUT_DIR
    / "sic_2025_monthly_metrics.csv"
)


# ============================================================
# SETTINGS
# ============================================================

HORIZONS = {
    "24h": 1,
    "48h": 2,
    "72h": 3,
}


# ============================================================
# HELPERS
# ============================================================

def calculate_metrics(
    predicted,
    actual,
    current,
):
    """
    Calculate PolarGuard forecast metrics and persistence baseline.
    """

    valid = (
        np.isfinite(predicted)
        &
        np.isfinite(actual)
    )

    if valid.sum() == 0:
        return None

    pred = predicted[valid].astype(float)
    truth = actual[valid].astype(float)

    error = (
        pred
        -
        truth
    )

    mae = float(
        np.mean(
            np.abs(error)
        )
    )

    rmse = float(
        np.sqrt(
            np.mean(
                error ** 2
            )
        )
    )

    bias = float(
        np.mean(
            error
        )
    )

    actual_mean = float(
        np.mean(
            truth
        )
    )

    predicted_mean = float(
        np.mean(
            pred
        )
    )

    if len(pred) > 1:

        try:

            r2 = float(
                r2_score(
                    truth,
                    pred,
                )
            )

        except Exception:

            r2 = np.nan

    else:

        r2 = np.nan

    # --------------------------------------------------------
    # PERSISTENCE BASELINE
    # --------------------------------------------------------
    #
    # Persistence means:
    #
    # future SIC = current SIC
    #
    # --------------------------------------------------------

    persistence_valid = (
        np.isfinite(current)
        &
        np.isfinite(actual)
    )

    if persistence_valid.sum() > 0:

        persistence_pred = (
            current[
                persistence_valid
            ].astype(float)
        )

        persistence_truth = (
            actual[
                persistence_valid
            ].astype(float)
        )

        persistence_error = (
            persistence_pred
            -
            persistence_truth
        )

        persistence_mae = float(
            np.mean(
                np.abs(
                    persistence_error
                )
            )
        )

        persistence_rmse = float(
            np.sqrt(
                np.mean(
                    persistence_error ** 2
                )
            )
        )

    else:

        persistence_mae = np.nan
        persistence_rmse = np.nan

    # --------------------------------------------------------
    # IMPROVEMENT VS PERSISTENCE
    # --------------------------------------------------------

    if (
        np.isfinite(
            persistence_mae
        )
        and
        persistence_mae > 0
    ):

        mae_improvement_pct = (
            (
                persistence_mae
                -
                mae
            )
            /
            persistence_mae
            *
            100.0
        )

    else:

        mae_improvement_pct = np.nan

    if (
        np.isfinite(
            persistence_rmse
        )
        and
        persistence_rmse > 0
    ):

        rmse_improvement_pct = (
            (
                persistence_rmse
                -
                rmse
            )
            /
            persistence_rmse
            *
            100.0
        )

    else:

        rmse_improvement_pct = np.nan

    return {
        "valid_cells":
            int(
                valid.sum()
            ),

        "actual_mean_sic":
            actual_mean,

        "predicted_mean_sic":
            predicted_mean,

        "mae":
            mae,

        "rmse":
            rmse,

        "bias":
            bias,

        "r2":
            r2,

        "persistence_mae":
            persistence_mae,

        "persistence_rmse":
            persistence_rmse,

        "mae_improvement_vs_persistence_pct":
            mae_improvement_pct,

        "rmse_improvement_vs_persistence_pct":
            rmse_improvement_pct,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 110)
    print("POLARGUARD")
    print("FULL-YEAR 2025 MEMBER-1 SEA-ICE TEST")
    print("=" * 110)

    if not TEST_FILE.exists():

        raise FileNotFoundError(
            f"Test dataset not found: {TEST_FILE}"
        )

    # ========================================================
    # LOAD TEST DATA
    # ========================================================

    ds = xr.open_dataset(
        TEST_FILE
    )

    if (
        "sea_ice_concentration"
        not in ds.data_vars
    ):

        raise RuntimeError(
            "Expected variable "
            "'sea_ice_concentration' "
            "not found in test_2025.nc"
        )

    sic = ds[
        "sea_ice_concentration"
    ]

    print()
    print(
        "Dataset shape:",
        sic.shape,
    )

    print(
        "Start:",
        sic.time.values[
            0
        ],
    )

    print(
        "End:",
        sic.time.values[
            -1
        ],
    )

    times = (
        sic.time.values
        .astype(
            "datetime64[D]"
        )
    )

    x_coords = np.asarray(
        sic.x.values
    )

    y_coords = np.asarray(
        sic.y.values
    )

    daily_rows = []

    # ========================================================
    # DAILY FULL-YEAR TEST
    # ========================================================

    # Need:
    # t-3 history
    # and t+3 future for 72h
    #
    # Therefore:
    # first valid initialization = index 3
    # last valid initialization = len - 4

    for index in range(
        3,
        len(times) - 3,
    ):

        initialization_date = (
            times[
                index
            ]
        )

        current = np.asarray(
            sic.isel(
                time=index
            ).values,
            dtype=np.float32,
        )

        lag1 = np.asarray(
            sic.isel(
                time=index - 1
            ).values,
            dtype=np.float32,
        )

        lag2 = np.asarray(
            sic.isel(
                time=index - 2
            ).values,
            dtype=np.float32,
        )

        lag3 = np.asarray(
            sic.isel(
                time=index - 3
            ).values,
            dtype=np.float32,
        )

        forecasts = predict_sea_ice(
            current=current,
            lag1=lag1,
            lag2=lag2,
            lag3=lag3,
            x_coords=x_coords,
            y_coords=y_coords,
            date=initialization_date,
        )

        # ====================================================
        # EACH HORIZON
        # ====================================================

        for horizon, offset in (
            HORIZONS.items()
        ):

            actual = np.asarray(
                sic.isel(
                    time=index + offset
                ).values,
                dtype=np.float32,
            )

            predicted = np.asarray(
                forecasts[
                    horizon
                ],
                dtype=np.float32,
            )

            metrics = calculate_metrics(
                predicted=predicted,
                actual=actual,
                current=current,
            )

            if metrics is None:
                continue

            target_date = (
                times[
                    index + offset
                ]
            )

            row = {
                "initialization_date":
                    str(
                        initialization_date
                    ),

                "target_date":
                    str(
                        target_date
                    ),

                "month":
                    str(
                        target_date
                    )[
                        :7
                    ],

                "horizon":
                    horizon,

                "horizon_hours":
                    int(
                        offset
                        *
                        24
                    ),
            }

            row.update(
                metrics
            )

            daily_rows.append(
                row
            )

        if (
            index % 25
            ==
            0
        ):

            print(
                f"Processed initialization "
                f"{index}/{len(times) - 1}: "
                f"{initialization_date}"
            )

    # ========================================================
    # DAILY DATAFRAME
    # ========================================================

    daily_df = pd.DataFrame(
        daily_rows
    )

    if daily_df.empty:

        raise RuntimeError(
            "No valid 2025 test results were generated."
        )

    daily_df.to_csv(
        DAILY_FILE,
        index=False,
    )

    # ========================================================
    # OVERALL AGGREGATE
    # ========================================================

    overall_rows = []

    for horizon in [
        "24h",
        "48h",
        "72h",
    ]:

        subset = daily_df[
            daily_df[
                "horizon"
            ]
            ==
            horizon
        ].copy()

        if subset.empty:
            continue

        overall_rows.append(
            {
                "horizon":
                    horizon,

                "horizon_hours":
                    int(
                        subset[
                            "horizon_hours"
                        ].iloc[
                            0
                        ]
                    ),

                "test_initializations":
                    int(
                        len(
                            subset
                        )
                    ),

                "mean_valid_cells":
                    float(
                        subset[
                            "valid_cells"
                        ].mean()
                    ),

                "actual_mean_sic":
                    float(
                        subset[
                            "actual_mean_sic"
                        ].mean()
                    ),

                "predicted_mean_sic":
                    float(
                        subset[
                            "predicted_mean_sic"
                        ].mean()
                    ),

                "mae":
                    float(
                        subset[
                            "mae"
                        ].mean()
                    ),

                "rmse":
                    float(
                        subset[
                            "rmse"
                        ].mean()
                    ),

                "bias":
                    float(
                        subset[
                            "bias"
                        ].mean()
                    ),

                "r2":
                    float(
                        subset[
                            "r2"
                        ].mean()
                    ),

                "persistence_mae":
                    float(
                        subset[
                            "persistence_mae"
                        ].mean()
                    ),

                "persistence_rmse":
                    float(
                        subset[
                            "persistence_rmse"
                        ].mean()
                    ),

                "mae_improvement_vs_persistence_pct":
                    float(
                        subset[
                            "mae_improvement_vs_persistence_pct"
                        ].mean()
                    ),

                "rmse_improvement_vs_persistence_pct":
                    float(
                        subset[
                            "rmse_improvement_vs_persistence_pct"
                        ].mean()
                    ),
            }
        )

    overall_df = pd.DataFrame(
        overall_rows
    )

    overall_df.to_csv(
        OVERALL_FILE,
        index=False,
    )

    # ========================================================
    # MONTHLY AGGREGATE
    # ========================================================

    monthly_rows = []

    grouped = daily_df.groupby(
        [
            "month",
            "horizon",
            "horizon_hours",
        ],
        dropna=False,
    )

    for (
        month,
        horizon,
        horizon_hours,
    ), group in grouped:

        monthly_rows.append(
            {
                "month":
                    month,

                "horizon":
                    horizon,

                "horizon_hours":
                    int(
                        horizon_hours
                    ),

                "test_initializations":
                    int(
                        len(
                            group
                        )
                    ),

                "actual_mean_sic":
                    float(
                        group[
                            "actual_mean_sic"
                        ].mean()
                    ),

                "predicted_mean_sic":
                    float(
                        group[
                            "predicted_mean_sic"
                        ].mean()
                    ),

                "mae":
                    float(
                        group[
                            "mae"
                        ].mean()
                    ),

                "rmse":
                    float(
                        group[
                            "rmse"
                        ].mean()
                    ),

                "bias":
                    float(
                        group[
                            "bias"
                        ].mean()
                    ),

                "r2":
                    float(
                        group[
                            "r2"
                        ].mean()
                    ),

                "persistence_mae":
                    float(
                        group[
                            "persistence_mae"
                        ].mean()
                    ),

                "persistence_rmse":
                    float(
                        group[
                            "persistence_rmse"
                        ].mean()
                    ),

                "mae_improvement_vs_persistence_pct":
                    float(
                        group[
                            "mae_improvement_vs_persistence_pct"
                        ].mean()
                    ),

                "rmse_improvement_vs_persistence_pct":
                    float(
                        group[
                            "rmse_improvement_vs_persistence_pct"
                        ].mean()
                    ),
            }
        )

    monthly_df = pd.DataFrame(
        monthly_rows
    )

    monthly_df = monthly_df.sort_values(
        [
            "month",
            "horizon_hours",
        ]
    )

    monthly_df.to_csv(
        MONTHLY_FILE,
        index=False,
    )

    # ========================================================
    # DISPLAY FINAL RESULTS
    # ========================================================

    print()
    print("=" * 110)
    print("FULL-YEAR 2025 SIC TEST RESULTS")
    print("=" * 110)
    print()

    display = overall_df.copy()

    for column in [
        "actual_mean_sic",
        "predicted_mean_sic",
        "mae",
        "rmse",
        "bias",
        "persistence_mae",
        "persistence_rmse",
    ]:

        display[
            column
        ] = (
            display[
                column
            ]
            *
            100.0
        )

    display = display.rename(
        columns={
            "actual_mean_sic":
                "actual_mean_sic_pct",

            "predicted_mean_sic":
                "predicted_mean_sic_pct",

            "mae":
                "mae_sic_points",

            "rmse":
                "rmse_sic_points",

            "bias":
                "bias_sic_points",

            "persistence_mae":
                "persistence_mae_sic_points",

            "persistence_rmse":
                "persistence_rmse_sic_points",
        }
    )

    print(
        display[
            [
                "horizon",
                "test_initializations",
                "actual_mean_sic_pct",
                "predicted_mean_sic_pct",
                "mae_sic_points",
                "rmse_sic_points",
                "bias_sic_points",
                "r2",
                "persistence_mae_sic_points",
                "persistence_rmse_sic_points",
                "mae_improvement_vs_persistence_pct",
                "rmse_improvement_vs_persistence_pct",
            ]
        ]
        .round(
            4
        )
        .to_string(
            index=False
        )
    )

    print()
    print("=" * 110)
    print("FILES CREATED")
    print("=" * 110)

    print(
        OVERALL_FILE
    )

    print(
        DAILY_FILE
    )

    print(
        MONTHLY_FILE
    )

    print()
    print("=" * 110)
    print(
        "FULL-YEAR 2025 MEMBER-1 TEST COMPLETE"
    )
    print("=" * 110)

    ds.close()


if __name__ == "__main__":
    main()