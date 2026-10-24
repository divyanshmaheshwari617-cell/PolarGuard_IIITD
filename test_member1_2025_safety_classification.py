from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent

if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt

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
    / "safety_classification"
)

FIGURE_DIR = (
    OUTPUT_DIR
    / "figures"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

FIGURE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

SUMMARY_FILE = (
    OUTPUT_DIR
    / "sic_safety_classification_summary.csv"
)

DAILY_FILE = (
    OUTPUT_DIR
    / "sic_safety_classification_daily.csv"
)


# ============================================================
# SETTINGS
# ============================================================

UNSAFE_SIC_THRESHOLD = 0.80

HORIZONS = {
    "24h": 1,
    "48h": 2,
    "72h": 3,
}


# ============================================================
# METRIC HELPERS
# ============================================================

def safe_divide(
    numerator,
    denominator,
):

    if denominator == 0:
        return np.nan

    return (
        numerator
        /
        denominator
    )


def calculate_classification_metrics(
    predicted,
    actual,
):
    """
    Unsafe class:
        SIC >= 0.80

    Safe class:
        SIC < 0.80

    Positive class = UNSAFE.
    """

    valid = (
        np.isfinite(predicted)
        &
        np.isfinite(actual)
    )

    if valid.sum() == 0:
        return None

    pred = predicted[
        valid
    ]

    truth = actual[
        valid
    ]

    predicted_unsafe = (
        pred
        >=
        UNSAFE_SIC_THRESHOLD
    )

    actual_unsafe = (
        truth
        >=
        UNSAFE_SIC_THRESHOLD
    )

    # --------------------------------------------------------
    # CONFUSION MATRIX
    # --------------------------------------------------------

    true_unsafe = int(
        np.sum(
            predicted_unsafe
            &
            actual_unsafe
        )
    )

    false_unsafe = int(
        np.sum(
            predicted_unsafe
            &
            ~actual_unsafe
        )
    )

    false_safe = int(
        np.sum(
            ~predicted_unsafe
            &
            actual_unsafe
        )
    )

    true_safe = int(
        np.sum(
            ~predicted_unsafe
            &
            ~actual_unsafe
        )
    )

    total = (
        true_unsafe
        +
        false_unsafe
        +
        false_safe
        +
        true_safe
    )

    # --------------------------------------------------------
    # STANDARD METRICS
    # --------------------------------------------------------

    accuracy = safe_divide(
        true_unsafe
        +
        true_safe,
        total,
    )

    unsafe_precision = safe_divide(
        true_unsafe,
        true_unsafe
        +
        false_unsafe,
    )

    unsafe_recall = safe_divide(
        true_unsafe,
        true_unsafe
        +
        false_safe,
    )

    if (
        np.isfinite(
            unsafe_precision
        )
        and
        np.isfinite(
            unsafe_recall
        )
        and
        (
            unsafe_precision
            +
            unsafe_recall
        )
        >
        0
    ):

        unsafe_f1 = (
            2.0
            *
            unsafe_precision
            *
            unsafe_recall
            /
            (
                unsafe_precision
                +
                unsafe_recall
            )
        )

    else:

        unsafe_f1 = np.nan

    specificity = safe_divide(
        true_safe,
        true_safe
        +
        false_unsafe,
    )

    # --------------------------------------------------------
    # SAFETY-CRITICAL METRICS
    # --------------------------------------------------------

    #
    # False-safe rate:
    #
    # Of all ACTUAL unsafe cells,
    # how many did PolarGuard incorrectly
    # classify as safe?
    #
    false_safe_rate = safe_divide(
        false_safe,
        actual_unsafe.sum(),
    )

    #
    # False-unsafe rate:
    #
    # Of all ACTUAL safe cells,
    # how many were classified unsafe?
    #
    false_unsafe_rate = safe_divide(
        false_unsafe,
        (~actual_unsafe).sum(),
    )

    actual_unsafe_rate = float(
        np.mean(
            actual_unsafe
        )
    )

    predicted_unsafe_rate = float(
        np.mean(
            predicted_unsafe
        )
    )

    return {
        "valid_cells":
            int(
                valid.sum()
            ),

        "true_unsafe":
            true_unsafe,

        "false_unsafe":
            false_unsafe,

        "false_safe":
            false_safe,

        "true_safe":
            true_safe,

        "accuracy":
            float(
                accuracy
            ),

        "unsafe_precision":
            float(
                unsafe_precision
            ),

        "unsafe_recall":
            float(
                unsafe_recall
            ),

        "unsafe_f1":
            float(
                unsafe_f1
            ),

        "specificity":
            float(
                specificity
            ),

        "false_safe_rate":
            float(
                false_safe_rate
            ),

        "false_unsafe_rate":
            float(
                false_unsafe_rate
            ),

        "actual_unsafe_rate":
            actual_unsafe_rate,

        "predicted_unsafe_rate":
            predicted_unsafe_rate,
    }


# ============================================================
# PLOT CONFUSION MATRIX
# ============================================================

def plot_confusion_matrix(
    horizon,
    row,
):

    matrix = np.array(
        [
            [
                row[
                    "true_safe"
                ],
                row[
                    "false_unsafe"
                ],
            ],
            [
                row[
                    "false_safe"
                ],
                row[
                    "true_unsafe"
                ],
            ],
        ],
        dtype=float,
    )

    fig, ax = plt.subplots(
        figsize=(6.5, 5.5)
    )

    image = ax.imshow(
        matrix
    )

    ax.set_xticks(
        [
            0,
            1,
        ]
    )

    ax.set_yticks(
        [
            0,
            1,
        ]
    )

    ax.set_xticklabels(
        [
            "Predicted Safe",
            "Predicted Unsafe",
        ]
    )

    ax.set_yticklabels(
        [
            "Actual Safe",
            "Actual Unsafe",
        ]
    )

    ax.set_title(
        f"2025 SIC Safety Confusion Matrix — +{horizon}"
    )

    for i in range(
        matrix.shape[
            0
        ]
    ):

        for j in range(
            matrix.shape[
                1
            ]
        ):

            ax.text(
                j,
                i,
                f"{int(matrix[i, j]):,}",
                ha="center",
                va="center",
            )

    fig.colorbar(
        image,
        ax=ax,
        label="Grid-cell count",
    )

    fig.tight_layout()

    output_file = (
        FIGURE_DIR
        /
        f"confusion_matrix_{horizon}.png"
    )

    fig.savefig(
        output_file,
        dpi=220,
        bbox_inches="tight",
    )

    plt.close(
        fig
    )

    print(
        "Saved:",
        output_file,
    )


# ============================================================
# PLOT SAFETY METRICS
# ============================================================

def plot_safety_metrics(
    summary,
):

    data = summary.sort_values(
        "horizon_hours"
    ).copy()

    labels = [
        f"+{int(value)}h"
        for value in data[
            "horizon_hours"
        ]
    ]

    recall = (
        data[
            "unsafe_recall"
        ]
        .to_numpy(dtype=float)
        *
        100.0
    )

    precision = (
        data[
            "unsafe_precision"
        ]
        .to_numpy(dtype=float)
        *
        100.0
    )

    f1 = (
        data[
            "unsafe_f1"
        ]
        .to_numpy(dtype=float)
        *
        100.0
    )

    x = np.arange(
        len(data)
    )

    width = 0.25

    fig, ax = plt.subplots(
        figsize=(9, 5.8)
    )

    ax.bar(
        x - width,
        precision,
        width,
        label="Unsafe Precision",
    )

    ax.bar(
        x,
        recall,
        width,
        label="Unsafe Recall",
    )

    ax.bar(
        x + width,
        f1,
        width,
        label="Unsafe F1",
    )

    ax.set_xticks(
        x
    )

    ax.set_xticklabels(
        labels
    )

    ax.set_ylim(
        0,
        100,
    )

    ax.set_ylabel(
        "Score (%)"
    )

    ax.set_xlabel(
        "Forecast Horizon"
    )

    ax.set_title(
        "PolarGuard Dangerous-Ice Classification — 2025"
    )

    ax.legend()

    ax.grid(
        axis="y",
        alpha=0.25,
    )

    fig.tight_layout()

    output_file = (
        FIGURE_DIR
        /
        "01_unsafe_precision_recall_f1.png"
    )

    fig.savefig(
        output_file,
        dpi=220,
        bbox_inches="tight",
    )

    plt.close(
        fig
    )

    print(
        "Saved:",
        output_file,
    )


# ============================================================
# FALSE-SAFE RATE PLOT
# ============================================================

def plot_false_safe_rate(
    summary,
):

    data = summary.sort_values(
        "horizon_hours"
    ).copy()

    labels = [
        f"+{int(value)}h"
        for value in data[
            "horizon_hours"
        ]
    ]

    values = (
        data[
            "false_safe_rate"
        ]
        .to_numpy(dtype=float)
        *
        100.0
    )

    fig, ax = plt.subplots(
        figsize=(8, 5.5)
    )

    x = np.arange(
        len(data)
    )

    bars = ax.bar(
        x,
        values,
    )

    ax.set_xticks(
        x
    )

    ax.set_xticklabels(
        labels
    )

    ax.set_ylabel(
        "False-Safe Rate (%)"
    )

    ax.set_xlabel(
        "Forecast Horizon"
    )

    ax.set_title(
        "Safety-Critical False-Safe Rate — 2025"
    )

    ax.grid(
        axis="y",
        alpha=0.25,
    )

    for bar, value in zip(
        bars,
        values,
    ):

        ax.text(
            bar.get_x()
            +
            bar.get_width() / 2,
            value + 0.25,
            f"{value:.2f}%",
            ha="center",
            va="bottom",
        )

    fig.tight_layout()

    output_file = (
        FIGURE_DIR
        /
        "02_false_safe_rate.png"
    )

    fig.savefig(
        output_file,
        dpi=220,
        bbox_inches="tight",
    )

    plt.close(
        fig
    )

    print(
        "Saved:",
        output_file,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 110)
    print("POLARGUARD")
    print("FULL-YEAR 2025 SIC SAFETY CLASSIFICATION")
    print("=" * 110)

    print()
    print(
        "Unsafe SIC threshold:",
        f"{UNSAFE_SIC_THRESHOLD * 100:.1f}%"
    )

    if not TEST_FILE.exists():

        raise FileNotFoundError(
            f"Missing test dataset: {TEST_FILE}"
        )

    ds = xr.open_dataset(
        TEST_FILE
    )

    sic = ds[
        "sea_ice_concentration"
    ]

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
    # FULL-YEAR TEST
    # ========================================================

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

            metrics = (
                calculate_classification_metrics(
                    predicted=predicted,
                    actual=actual,
                )
            )

            if metrics is None:
                continue

            row = {
                "initialization_date":
                    str(
                        initialization_date
                    ),

                "target_date":
                    str(
                        times[
                            index + offset
                        ]
                    ),

                "month":
                    str(
                        times[
                            index + offset
                        ]
                    )[:7],

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

    daily_df = pd.DataFrame(
        daily_rows
    )

    if daily_df.empty:

        raise RuntimeError(
            "No safety-classification results generated."
        )

    daily_df.to_csv(
        DAILY_FILE,
        index=False,
    )

    # ========================================================
    # IMPORTANT:
    # AGGREGATE CONFUSION COUNTS FIRST
    # ========================================================
    #
    # We sum TP/FP/FN/TN across all test dates and then
    # calculate the final metrics.
    #
    # This is preferable to simply averaging daily recall.
    #
    # ========================================================

    summary_rows = []

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

        true_unsafe = int(
            subset[
                "true_unsafe"
            ].sum()
        )

        false_unsafe = int(
            subset[
                "false_unsafe"
            ].sum()
        )

        false_safe = int(
            subset[
                "false_safe"
            ].sum()
        )

        true_safe = int(
            subset[
                "true_safe"
            ].sum()
        )

        total = (
            true_unsafe
            +
            false_unsafe
            +
            false_safe
            +
            true_safe
        )

        accuracy = safe_divide(
            true_unsafe
            +
            true_safe,
            total,
        )

        precision = safe_divide(
            true_unsafe,
            true_unsafe
            +
            false_unsafe,
        )

        recall = safe_divide(
            true_unsafe,
            true_unsafe
            +
            false_safe,
        )

        if (
            np.isfinite(
                precision
            )
            and
            np.isfinite(
                recall
            )
            and
            (
                precision
                +
                recall
            )
            >
            0
        ):

            f1 = (
                2.0
                *
                precision
                *
                recall
                /
                (
                    precision
                    +
                    recall
                )
            )

        else:

            f1 = np.nan

        specificity = safe_divide(
            true_safe,
            true_safe
            +
            false_unsafe,
        )

        false_safe_rate = safe_divide(
            false_safe,
            true_unsafe
            +
            false_safe,
        )

        false_unsafe_rate = safe_divide(
            false_unsafe,
            true_safe
            +
            false_unsafe,
        )

        actual_unsafe_rate = safe_divide(
            true_unsafe
            +
            false_safe,
            total,
        )

        predicted_unsafe_rate = safe_divide(
            true_unsafe
            +
            false_unsafe,
            total,
        )

        summary_rows.append(
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
                    len(
                        subset
                    ),

                "valid_cells":
                    total,

                "true_unsafe":
                    true_unsafe,

                "false_unsafe":
                    false_unsafe,

                "false_safe":
                    false_safe,

                "true_safe":
                    true_safe,

                "accuracy":
                    accuracy,

                "unsafe_precision":
                    precision,

                "unsafe_recall":
                    recall,

                "unsafe_f1":
                    f1,

                "specificity":
                    specificity,

                "false_safe_rate":
                    false_safe_rate,

                "false_unsafe_rate":
                    false_unsafe_rate,

                "actual_unsafe_rate":
                    actual_unsafe_rate,

                "predicted_unsafe_rate":
                    predicted_unsafe_rate,
            }
        )

    summary_df = pd.DataFrame(
        summary_rows
    )

    summary_df.to_csv(
        SUMMARY_FILE,
        index=False,
    )

    # ========================================================
    # PRINT RESULTS
    # ========================================================

    print()
    print("=" * 110)
    print("2025 DANGEROUS-ICE CLASSIFICATION RESULTS")
    print("=" * 110)
    print()

    display = summary_df.copy()

    percentage_columns = [
        "accuracy",
        "unsafe_precision",
        "unsafe_recall",
        "unsafe_f1",
        "specificity",
        "false_safe_rate",
        "false_unsafe_rate",
        "actual_unsafe_rate",
        "predicted_unsafe_rate",
    ]

    for column in percentage_columns:

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
            "accuracy":
                "accuracy_pct",

            "unsafe_precision":
                "unsafe_precision_pct",

            "unsafe_recall":
                "unsafe_recall_pct",

            "unsafe_f1":
                "unsafe_f1_pct",

            "specificity":
                "specificity_pct",

            "false_safe_rate":
                "false_safe_rate_pct",

            "false_unsafe_rate":
                "false_unsafe_rate_pct",

            "actual_unsafe_rate":
                "actual_unsafe_rate_pct",

            "predicted_unsafe_rate":
                "predicted_unsafe_rate_pct",
        }
    )

    print(
        display[
            [
                "horizon",
                "test_initializations",
                "true_unsafe",
                "false_safe",
                "false_unsafe",
                "true_safe",
                "unsafe_precision_pct",
                "unsafe_recall_pct",
                "unsafe_f1_pct",
                "false_safe_rate_pct",
                "accuracy_pct",
            ]
        ]
        .round(
            3
        )
        .to_string(
            index=False
        )
    )

    # ========================================================
    # FIGURES
    # ========================================================

    print()
    print("=" * 110)
    print("CREATING FIGURES")
    print("=" * 110)

    plot_safety_metrics(
        summary_df
    )

    plot_false_safe_rate(
        summary_df
    )

    for _, row in (
        summary_df.iterrows()
    ):

        plot_confusion_matrix(
            horizon=row[
                "horizon"
            ],
            row=row,
        )

    print()
    print("=" * 110)
    print("FILES CREATED")
    print("=" * 110)

    print(
        SUMMARY_FILE
    )

    print(
        DAILY_FILE
    )

    for file in sorted(
        FIGURE_DIR.glob(
            "*.png"
        )
    ):

        print(
            file
        )

    print()
    print("=" * 110)
    print(
        "2025 SIC SAFETY CLASSIFICATION COMPLETE"
    )
    print("=" * 110)

    ds.close()


if __name__ == "__main__":
    main()