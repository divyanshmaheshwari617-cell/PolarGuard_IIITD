from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# PATHS
# ============================================================

BASE = Path(__file__).resolve().parent

INPUT_FILE = (
    BASE
    / "outputs"
    / "member2_v1_validation"
    / "member2_v1_actual_vs_predicted.csv"
)

OUTPUT_DIR = (
    BASE
    / "outputs"
    / "member2_final_evidence"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# OUTPUT FILES
# ============================================================

SUMMARY_FILE = (
    OUTPUT_DIR
    / "2025_test_summary.csv"
)

SAMPLE_FILE = (
    OUTPUT_DIR
    / "2025_actual_vs_predicted_examples.csv"
)

ERROR_BINS_FILE = (
    OUTPUT_DIR
    / "2025_error_distribution.csv"
)


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 85)
    print("POLARGUARD MEMBER 2")
    print("FINAL 2025 ACTUAL VS PREDICTED ANALYSIS")
    print("=" * 85)

    # --------------------------------------------------------
    # LOAD
    # --------------------------------------------------------

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"File not found:\n{INPUT_FILE}"
        )

    df = pd.read_csv(
        INPUT_FILE,
        parse_dates=["init_date"]
    )

    print(
        f"\nTotal prediction rows: "
        f"{len(df):,}"
    )

    # --------------------------------------------------------
    # USE FINAL HELD-OUT TEST ONLY
    # --------------------------------------------------------

    test = df[
        df["split"] == "test"
    ].copy()

    if len(test) == 0:

        raise RuntimeError(
            "No test rows found."
        )

    print(
        f"2025 test prediction rows: "
        f"{len(test):,}"
    )

    print(
        f"Unique test icebergs: "
        f"{test['iceberg_id'].nunique():,}"
    )

    print(
        f"Date range: "
        f"{test['init_date'].min()} "
        f"to "
        f"{test['init_date'].max()}"
    )


    # ========================================================
    # SUMMARY BY HORIZON
    # ========================================================

    summary_rows = []

    for horizon in [24, 48, 72]:

        h = test[
            test["horizon_hours"] == horizon
        ].copy()

        errors = (
            h["position_error_km"]
            .to_numpy(dtype=float)
        )

        baseline_errors = (
            h["baseline_position_error_km"]
            .to_numpy(dtype=float)
        )

        rmse = float(
            np.sqrt(
                np.mean(errors ** 2)
            )
        )

        baseline_rmse = float(
            np.sqrt(
                np.mean(
                    baseline_errors ** 2
                )
            )
        )

        mae = float(
            np.mean(errors)
        )

        median = float(
            np.median(errors)
        )

        p90 = float(
            np.percentile(
                errors,
                90
            )
        )

        p95 = float(
            np.percentile(
                errors,
                95
            )
        )

        within_1 = float(
            100
            * np.mean(
                errors <= 1
            )
        )

        within_5 = float(
            100
            * np.mean(
                errors <= 5
            )
        )

        within_10 = float(
            100
            * np.mean(
                errors <= 10
            )
        )

        improvement = float(
            100
            * (
                baseline_rmse
                - rmse
            )
            / baseline_rmse
        )

        summary_rows.append(
            {
                "horizon_hours":
                    horizon,

                "samples":
                    len(h),

                "rmse_km":
                    rmse,

                "mean_error_km":
                    mae,

                "median_error_km":
                    median,

                "p90_error_km":
                    p90,

                "p95_error_km":
                    p95,

                "within_1km_pct":
                    within_1,

                "within_5km_pct":
                    within_5,

                "within_10km_pct":
                    within_10,

                "baseline_rmse_km":
                    baseline_rmse,

                "improvement_vs_baseline_pct":
                    improvement,
            }
        )

    summary = pd.DataFrame(
        summary_rows
    )

    summary.to_csv(
        SUMMARY_FILE,
        index=False
    )


    # ========================================================
    # ERROR DISTRIBUTION
    # ========================================================

    error_distribution_rows = []

    ranges = [
        ("0-1 km", 0, 1),
        ("1-2 km", 1, 2),
        ("2-5 km", 2, 5),
        ("5-10 km", 5, 10),
        ("10-20 km", 10, 20),
        ("20+ km", 20, np.inf),
    ]

    for horizon in [24, 48, 72]:

        h = test[
            test["horizon_hours"] == horizon
        ]

        errors = h[
            "position_error_km"
        ]

        for (
            label,
            lower,
            upper
        ) in ranges:

            if np.isinf(upper):

                count = int(
                    (
                        errors >= lower
                    ).sum()
                )

            else:

                count = int(
                    (
                        (errors >= lower)
                        &
                        (errors < upper)
                    ).sum()
                )

            percentage = (
                100.0
                * count
                / len(h)
            )

            error_distribution_rows.append(
                {
                    "horizon_hours":
                        horizon,

                    "error_range":
                        label,

                    "count":
                        count,

                    "percentage":
                        percentage,
                }
            )

    error_distribution = pd.DataFrame(
        error_distribution_rows
    )

    error_distribution.to_csv(
        ERROR_BINS_FILE,
        index=False
    )


    # ========================================================
    # REPRESENTATIVE EXAMPLES
    #
    # Select examples near:
    # 25th percentile
    # median
    # 75th percentile
    # 90th percentile
    #
    # This avoids cherry-picking only best predictions.
    # ========================================================

    examples = []

    percentiles = [
        ("good_q25", 0.25),
        ("median_q50", 0.50),
        ("challenging_q75", 0.75),
        ("difficult_q90", 0.90),
    ]

    for horizon in [24, 48, 72]:

        h = test[
            test["horizon_hours"] == horizon
        ].copy()

        h = h.sort_values(
            "position_error_km"
        ).reset_index(drop=True)

        for label, q in percentiles:

            target_error = (
                h[
                    "position_error_km"
                ]
                .quantile(q)
            )

            index = (
                h[
                    "position_error_km"
                ]
                .sub(target_error)
                .abs()
                .idxmin()
            )

            row = h.loc[index]

            examples.append(
                {
                    "category":
                        label,

                    "horizon_hours":
                        horizon,

                    "iceberg_id":
                        row["iceberg_id"],

                    "init_date":
                        row["init_date"],

                    "current_latitude":
                        row[
                            "current_latitude"
                        ],

                    "current_longitude":
                        row[
                            "current_longitude"
                        ],

                    "actual_latitude":
                        row[
                            "actual_latitude"
                        ],

                    "actual_longitude":
                        row[
                            "actual_longitude"
                        ],

                    "predicted_latitude":
                        row[
                            "predicted_latitude"
                        ],

                    "predicted_longitude":
                        row[
                            "predicted_longitude"
                        ],

                    "position_error_km":
                        row[
                            "position_error_km"
                        ],

                    "baseline_error_km":
                        row[
                            "baseline_position_error_km"
                        ],
                }
            )

    examples_df = pd.DataFrame(
        examples
    )

    examples_df.to_csv(
        SAMPLE_FILE,
        index=False
    )


    # ========================================================
    # GRAPH 1:
    # RMSE MODEL VS BASELINE
    # ========================================================

    plot_data = (
        summary[
            [
                "horizon_hours",
                "rmse_km",
                "baseline_rmse_km",
            ]
        ]
        .set_index(
            "horizon_hours"
        )
    )

    plot_data.columns = [
        "PolarGuard V1",
        "3-day Baseline",
    ]

    ax = plot_data.plot(
        kind="bar",
        figsize=(9, 6),
    )

    ax.set_title(
        "2025 Held-Out Test — Position RMSE"
    )

    ax.set_xlabel(
        "Forecast Horizon (hours)"
    )

    ax.set_ylabel(
        "RMSE (km)"
    )

    ax.grid(
        axis="y",
        alpha=0.25
    )

    plt.tight_layout()

    plt.savefig(
        OUTPUT_DIR
        / "2025_rmse_vs_baseline.png",
        dpi=200,
        bbox_inches="tight"
    )

    plt.close()


    # ========================================================
    # GRAPH 2:
    # ERROR DISTRIBUTION BOX PLOT
    # ========================================================

    groups = []

    labels = []

    for horizon in [24, 48, 72]:

        groups.append(
            test.loc[
                test[
                    "horizon_hours"
                ]
                ==
                horizon,
                "position_error_km"
            ].to_numpy()
        )

        labels.append(
            f"{horizon}h"
        )

    fig, ax = plt.subplots(
        figsize=(9, 6)
    )

    ax.boxplot(
    groups,
    tick_labels=labels,
    showfliers=False,
)

    ax.set_title(
        "2025 Held-Out Test — Error Distribution"
    )

    ax.set_xlabel(
        "Forecast Horizon"
    )

    ax.set_ylabel(
        "Position Error (km)"
    )

    ax.grid(
        axis="y",
        alpha=0.25
    )

    plt.tight_layout()

    plt.savefig(
        OUTPUT_DIR
        / "2025_error_boxplot.png",
        dpi=200,
        bbox_inches="tight"
    )

    plt.close()


    # ========================================================
    # GRAPH 3:
    # CDF / PERCENT OF PREDICTIONS WITHIN ERROR
    # ========================================================

    fig, ax = plt.subplots(
        figsize=(9, 6)
    )

    for horizon in [24, 48, 72]:

        errors = np.sort(
            test.loc[
                test[
                    "horizon_hours"
                ]
                ==
                horizon,
                "position_error_km"
            ].to_numpy()
        )

        cumulative = (
            np.arange(
                1,
                len(errors) + 1
            )
            /
            len(errors)
            *
            100
        )

        ax.plot(
            errors,
            cumulative,
            label=f"{horizon}h"
        )

    ax.set_xlim(
        left=0
    )

    ax.set_ylim(
        0,
        100
    )

    ax.set_title(
        "2025 Held-Out Test — Cumulative Position Error"
    )

    ax.set_xlabel(
        "Position Error (km)"
    )

    ax.set_ylabel(
        "Predictions Within Error (%)"
    )

    ax.grid(
        alpha=0.25
    )

    ax.legend()

    plt.tight_layout()

    plt.savefig(
        OUTPUT_DIR
        / "2025_error_cdf.png",
        dpi=200,
        bbox_inches="tight"
    )

    plt.close()


    # ========================================================
    # PRINT SUMMARY
    # ========================================================

    print()
    print("=" * 85)
    print("2025 FINAL TEST SUMMARY")
    print("=" * 85)

    print()

    print(
        summary
        .round(3)
        .to_string(
            index=False
        )
    )


    print()
    print("=" * 85)
    print("REPRESENTATIVE ACTUAL VS PREDICTED EXAMPLES")
    print("=" * 85)

    display_columns = [
        "category",
        "horizon_hours",
        "iceberg_id",
        "actual_latitude",
        "actual_longitude",
        "predicted_latitude",
        "predicted_longitude",
        "position_error_km",
    ]

    print()

    print(
        examples_df[
            display_columns
        ]
        .round(5)
        .to_string(
            index=False
        )
    )


    print()
    print("=" * 85)
    print("FILES CREATED")
    print("=" * 85)

    print(
        f"\nSummary:\n"
        f"{SUMMARY_FILE}"
    )

    print(
        f"\nActual vs Predicted examples:\n"
        f"{SAMPLE_FILE}"
    )

    print(
        f"\nError distribution:\n"
        f"{ERROR_BINS_FILE}"
    )

    print(
        "\nGraphs:"
    )

    print(
        OUTPUT_DIR
        / "2025_rmse_vs_baseline.png"
    )

    print(
        OUTPUT_DIR
        / "2025_error_boxplot.png"
    )

    print(
        OUTPUT_DIR
        / "2025_error_cdf.png"
    )

    print()
    print("=" * 85)
    print("FINAL EVIDENCE ANALYSIS COMPLETE")
    print("=" * 85)


if __name__ == "__main__":

    main()