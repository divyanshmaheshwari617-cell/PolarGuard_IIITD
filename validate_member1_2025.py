from pathlib import Path
import sys
import math

BASE = Path(__file__).resolve().parent

if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

import numpy as np
import pandas as pd
import xarray as xr

from sea_ice_service import predict_sea_ice


# ============================================================
# CONFIGURATION
# ============================================================

DATA_FILE = (
    BASE
    / "data"
    / "processed"
    / "sea_ice_2019_2025.nc"
)

OUTPUT_DIR = (
    BASE
    / "outputs"
    / "member1_2025_validation"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

DETAIL_FILE = (
    OUTPUT_DIR
    / "member1_2025_weekly_validation_details.csv"
)

SUMMARY_FILE = (
    OUTPUT_DIR
    / "member1_2025_annual_summary.csv"
)

MONTHLY_FILE = (
    OUTPUT_DIR
    / "member1_2025_monthly_summary.csv"
)

YEAR = 2025
STEP_DAYS = 7

ICE_THRESHOLD = 0.15

HORIZONS = {
    "24h": 1,
    "48h": 2,
    "72h": 3,
}


# ============================================================
# METRICS
# ============================================================

def compute_metrics(
    predicted,
    actual,
):
    """
    Compare predicted and actual SIC maps.

    Returns:
        MAE
        RMSE
        bias
        correlation
        classification accuracy at 15% SIC
        valid cell count
    """

    predicted = np.asarray(
        predicted,
        dtype=float,
    )

    actual = np.asarray(
        actual,
        dtype=float,
    )

    valid = (
        np.isfinite(predicted)
        &
        np.isfinite(actual)
    )

    if not np.any(valid):
        return {
            "valid_cells": 0,
            "mae": np.nan,
            "rmse": np.nan,
            "bias": np.nan,
            "correlation": np.nan,
            "ice_accuracy_pct": np.nan,
        }

    p = predicted[
        valid
    ]

    a = actual[
        valid
    ]

    error = (
        p
        -
        a
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

    # --------------------------------------------------------
    # CORRELATION
    # --------------------------------------------------------

    if (
        len(p) > 1
        and
        np.std(p) > 0
        and
        np.std(a) > 0
    ):
        correlation = float(
            np.corrcoef(
                p,
                a,
            )[0, 1]
        )
    else:
        correlation = np.nan

    # --------------------------------------------------------
    # ICE / NO-ICE CLASSIFICATION
    # --------------------------------------------------------

    predicted_ice = (
        p
        >=
        ICE_THRESHOLD
    )

    actual_ice = (
        a
        >=
        ICE_THRESHOLD
    )

    ice_accuracy = float(
        np.mean(
            predicted_ice
            ==
            actual_ice
        )
        *
        100.0
    )

    return {
        "valid_cells":
            int(
                len(p)
            ),

        "mae":
            mae,

        "rmse":
            rmse,

        "bias":
            bias,

        "correlation":
            correlation,

        "ice_accuracy_pct":
            ice_accuracy,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 110)
    print("POLARGUARD")
    print("MEMBER 1 - FULL-YEAR 2025 HELD-OUT VALIDATION")
    print("=" * 110)

    print()
    print(
        "Opening historical SIC dataset..."
    )

    ds = xr.open_dataset(
        DATA_FILE
    )

    if (
        "sea_ice_concentration"
        not in ds.data_vars
    ):
        raise RuntimeError(
            "Expected variable "
            "'sea_ice_concentration' "
            "was not found."
        )

    sic_da = ds[
        "sea_ice_concentration"
    ]

    dates = (
        sic_da.time.values
        .astype(
            "datetime64[D]"
        )
    )

    x_coords = np.asarray(
        ds["x"].values
    )

    y_coords = np.asarray(
        ds["y"].values
    )

    # ========================================================
    # DATE LOOKUP
    # ========================================================

    date_to_index = {
        date:
            index
        for index, date in enumerate(
            dates
        )
    }

    first_2025 = np.datetime64(
        "2025-01-04",
        "D",
    )

    last_2025 = np.datetime64(
        "2025-12-28",
        "D",
    )

    initialization_dates = np.arange(
        first_2025,
        last_2025
        +
        np.timedelta64(
            1,
            "D",
        ),
        np.timedelta64(
            STEP_DAYS,
            "D",
        ),
    )

    print(
        "Initialization samples:",
        len(
            initialization_dates
        ),
    )

    print(
        "Sampling interval:",
        f"{STEP_DAYS} days",
    )

    print(
        "Forecast horizons:",
        "24h / 48h / 72h",
    )

    results = []

    # ========================================================
    # VALIDATION LOOP
    # ========================================================

    for sample_number, init_date in enumerate(
        initialization_dates,
        start=1,
    ):

        print()
        print(
            f"[{sample_number}/"
            f"{len(initialization_dates)}] "
            f"Initialization: "
            f"{str(init_date)}"
        )

        required_dates = [
            init_date
            -
            np.timedelta64(
                3,
                "D",
            ),

            init_date
            -
            np.timedelta64(
                2,
                "D",
            ),

            init_date
            -
            np.timedelta64(
                1,
                "D",
            ),

            init_date,

            init_date
            +
            np.timedelta64(
                1,
                "D",
            ),

            init_date
            +
            np.timedelta64(
                2,
                "D",
            ),

            init_date
            +
            np.timedelta64(
                3,
                "D",
            ),
        ]

        missing_dates = [
            date
            for date in required_dates
            if date not in date_to_index
        ]

        if missing_dates:
            print(
                "SKIPPED - missing dates:",
                missing_dates,
            )
            continue

        # ----------------------------------------------------
        # LOAD ONLY REQUIRED MAPS
        # ----------------------------------------------------

        idx_current = date_to_index[
            init_date
        ]

        idx_lag1 = date_to_index[
            init_date
            -
            np.timedelta64(
                1,
                "D",
            )
        ]

        idx_lag2 = date_to_index[
            init_date
            -
            np.timedelta64(
                2,
                "D",
            )
        ]

        idx_lag3 = date_to_index[
            init_date
            -
            np.timedelta64(
                3,
                "D",
            )
        ]

        current = np.asarray(
            sic_da.isel(
                time=idx_current
            ).values,
            dtype=np.float32,
        )

        lag1 = np.asarray(
            sic_da.isel(
                time=idx_lag1
            ).values,
            dtype=np.float32,
        )

        lag2 = np.asarray(
            sic_da.isel(
                time=idx_lag2
            ).values,
            dtype=np.float32,
        )

        lag3 = np.asarray(
            sic_da.isel(
                time=idx_lag3
            ).values,
            dtype=np.float32,
        )

        # ----------------------------------------------------
        # PREDICT ALL THREE HORIZONS
        # ----------------------------------------------------

        forecasts = predict_sea_ice(
            current=current,
            lag1=lag1,
            lag2=lag2,
            lag3=lag3,
            x_coords=x_coords,
            y_coords=y_coords,
            date=init_date,
        )

        # ----------------------------------------------------
        # COMPARE AGAINST ACTUAL FUTURE MAPS
        # ----------------------------------------------------

        for horizon_name, offset_days in (
            HORIZONS.items()
        ):

            target_date = (
                init_date
                +
                np.timedelta64(
                    offset_days,
                    "D",
                )
            )

            target_index = (
                date_to_index[
                    target_date
                ]
            )

            actual = np.asarray(
                sic_da.isel(
                    time=target_index
                ).values,
                dtype=np.float32,
            )

            predicted = np.asarray(
                forecasts[
                    horizon_name
                ],
                dtype=np.float32,
            )

            metrics = compute_metrics(
                predicted,
                actual,
            )

            print(
                f"  {horizon_name}: "
                f"MAE={metrics['mae']:.4f} "
                f"RMSE={metrics['rmse']:.4f} "
                f"Bias={metrics['bias']:+.4f} "
                f"Corr={metrics['correlation']:.4f} "
                f"Accuracy={metrics['ice_accuracy_pct']:.2f}%"
            )

            results.append(
                {
                    "initialization_date":
                        str(
                            init_date
                        ),

                    "target_date":
                        str(
                            target_date
                        ),

                    "month":
                        int(
                            str(
                                target_date
                            )[5:7]
                        ),

                    "horizon":
                        horizon_name,

                    "horizon_hours":
                        int(
                            offset_days
                            *
                            24
                        ),

                    "valid_cells":
                        metrics[
                            "valid_cells"
                        ],

                    "mae":
                        metrics[
                            "mae"
                        ],

                    "rmse":
                        metrics[
                            "rmse"
                        ],

                    "bias":
                        metrics[
                            "bias"
                        ],

                    "correlation":
                        metrics[
                            "correlation"
                        ],

                    "ice_accuracy_pct":
                        metrics[
                            "ice_accuracy_pct"
                        ],
                }
            )

    ds.close()

    # ========================================================
    # SAVE DETAIL RESULTS
    # ========================================================

    results_df = pd.DataFrame(
        results
    )

    if results_df.empty:
        raise RuntimeError(
            "No validation samples were produced."
        )

    results_df.to_csv(
        DETAIL_FILE,
        index=False,
    )

    # ========================================================
    # ANNUAL SUMMARY
    # ========================================================

    annual_summary = (
        results_df
        .groupby(
            [
                "horizon",
                "horizon_hours",
            ],
            as_index=False,
        )
        .agg(
            samples=(
                "initialization_date",
                "count",
            ),

            mean_valid_cells=(
                "valid_cells",
                "mean",
            ),

            mae=(
                "mae",
                "mean",
            ),

            rmse=(
                "rmse",
                "mean",
            ),

            bias=(
                "bias",
                "mean",
            ),

            correlation=(
                "correlation",
                "mean",
            ),

            ice_accuracy_pct=(
                "ice_accuracy_pct",
                "mean",
            ),
        )
        .sort_values(
            "horizon_hours"
        )
        .reset_index(
            drop=True
        )
    )

    annual_summary.to_csv(
        SUMMARY_FILE,
        index=False,
    )

    # ========================================================
    # MONTHLY SUMMARY
    # ========================================================

    monthly_summary = (
        results_df
        .groupby(
            [
                "month",
                "horizon",
                "horizon_hours",
            ],
            as_index=False,
        )
        .agg(
            samples=(
                "initialization_date",
                "count",
            ),

            mae=(
                "mae",
                "mean",
            ),

            rmse=(
                "rmse",
                "mean",
            ),

            bias=(
                "bias",
                "mean",
            ),

            correlation=(
                "correlation",
                "mean",
            ),

            ice_accuracy_pct=(
                "ice_accuracy_pct",
                "mean",
            ),
        )
        .sort_values(
            [
                "month",
                "horizon_hours",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    monthly_summary.to_csv(
        MONTHLY_FILE,
        index=False,
    )

    # ========================================================
    # FINAL CONSOLE SUMMARY
    # ========================================================

    print()
    print("=" * 110)
    print("2025 ANNUAL ACTUAL VS PREDICTED SUMMARY")
    print("=" * 110)

    print()

    display = annual_summary.copy()

    display[
        "mae_pct"
    ] = (
        display["mae"]
        *
        100.0
    )

    display[
        "rmse_pct"
    ] = (
        display["rmse"]
        *
        100.0
    )

    display[
        "bias_pct"
    ] = (
        display["bias"]
        *
        100.0
    )

    print(
        display[
            [
                "horizon",
                "samples",
                "mae_pct",
                "rmse_pct",
                "bias_pct",
                "correlation",
                "ice_accuracy_pct",
            ]
        ]
        .round(4)
        .to_string(
            index=False
        )
    )

    print()
    print("=" * 110)
    print("FILES CREATED")
    print("=" * 110)

    print(
        DETAIL_FILE
    )

    print(
        SUMMARY_FILE
    )

    print(
        MONTHLY_FILE
    )

    print()
    print("=" * 110)
    print(
        "MEMBER 1 2025 HELD-OUT VALIDATION COMPLETE"
    )
    print("=" * 110)


if __name__ == "__main__":
    main()