from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# PATHS
# ============================================================

BASE = Path(__file__).resolve().parent

V1_METRICS_FILE = (
    BASE
    / "outputs"
    / "member2_v1_validation"
    / "member2_v1_metrics.csv"
)

V2_METRICS_FILE = (
    BASE
    / "outputs"
    / "member2_v2"
    / "member2_v2_validation_2024.csv"
)

PHYSICS_BASELINE_FILE = (
    BASE
    / "outputs"
    / "member2_v2"
    / "physics_baseline_validation_2024.csv"
)

OUTPUT_DIR = (
    BASE
    / "outputs"
    / "member2_model_comparison"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# OUTPUT FILES
# ============================================================

COMPARISON_CSV = (
    OUTPUT_DIR
    / "member2_2024_model_comparison.csv"
)

RMSE_PLOT = (
    OUTPUT_DIR
    / "member2_2024_rmse_comparison.png"
)

WITHIN5_PLOT = (
    OUTPUT_DIR
    / "member2_2024_within5km_comparison.png"
)


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("POLARGUARD MEMBER 2 MODEL COMPARISON")
    print("VALIDATION YEAR: 2024")
    print("=" * 80)

    # --------------------------------------------------------
    # CHECK FILES
    # --------------------------------------------------------

    required_files = [
        V1_METRICS_FILE,
        V2_METRICS_FILE,
        PHYSICS_BASELINE_FILE,
    ]

    for file_path in required_files:

        if not file_path.exists():

            raise FileNotFoundError(
                f"Missing required file:\n{file_path}"
            )

    print("\nAll required result files found.")

    # --------------------------------------------------------
    # LOAD V1 RESULTS
    # --------------------------------------------------------

    v1 = pd.read_csv(
        V1_METRICS_FILE
    )

    v1 = v1[
        v1["split"] == "validation"
    ].copy()

    v1 = v1[
        [
            "horizon_hours",
            "rmse_km",
            "within_5km_pct",
            "baseline_rmse_km",
        ]
    ].rename(
        columns={
            "rmse_km":
                "v1_direct_ml_rmse_km",

            "within_5km_pct":
                "v1_within_5km_pct",

            "baseline_rmse_km":
                "mean_velocity_baseline_rmse_km",
        }
    )

    # --------------------------------------------------------
    # LOAD PHYSICS BASELINE RESULTS
    # --------------------------------------------------------

    physics = pd.read_csv(
        PHYSICS_BASELINE_FILE
    )

    physics = physics[
        [
            "horizon_hours",
            "rmse_km",
            "within_5km_pct",
        ]
    ].rename(
        columns={
            "rmse_km":
                "physics_baseline_rmse_km",

            "within_5km_pct":
                "physics_within_5km_pct",
        }
    )

    # --------------------------------------------------------
    # LOAD V2 RESULTS
    # --------------------------------------------------------

    v2 = pd.read_csv(
        V2_METRICS_FILE
    )

    v2 = v2[
        [
            "horizon_hours",
            "v2_residual_rmse_km",
            "v2_within_5km_pct",
        ]
    ]

    # --------------------------------------------------------
    # MERGE
    # --------------------------------------------------------

    comparison = (
        v1
        .merge(
            physics,
            on="horizon_hours",
            how="inner",
        )
        .merge(
            v2,
            on="horizon_hours",
            how="inner",
        )
    )

    # --------------------------------------------------------
    # WINNER
    # --------------------------------------------------------

    rmse_columns = {

        "3-day mean velocity":
            "mean_velocity_baseline_rmse_km",

        "Physics-informed baseline":
            "physics_baseline_rmse_km",

        "V1 Direct ML":
            "v1_direct_ml_rmse_km",

        "V2 Residual ML":
            "v2_residual_rmse_km",
    }

    winners = []

    for _, row in comparison.iterrows():

        scores = {

            model_name:
                float(
                    row[column_name]
                )

            for (
                model_name,
                column_name
            ) in rmse_columns.items()
        }

        winner = min(
            scores,
            key=scores.get
        )

        winners.append(
            winner
        )

    comparison[
        "best_model"
    ] = winners

    # --------------------------------------------------------
    # V2 VS V1 DIFFERENCE
    # --------------------------------------------------------

    comparison[
        "v2_minus_v1_rmse_km"
    ] = (
        comparison[
            "v2_residual_rmse_km"
        ]
        -
        comparison[
            "v1_direct_ml_rmse_km"
        ]
    )

    comparison[
        "v2_vs_v1_percent_change"
    ] = (
        (
            comparison[
                "v2_residual_rmse_km"
            ]
            -
            comparison[
                "v1_direct_ml_rmse_km"
            ]
        )
        /
        comparison[
            "v1_direct_ml_rmse_km"
        ]
        *
        100.0
    )

    # --------------------------------------------------------
    # SAVE TABLE
    # --------------------------------------------------------

    comparison.to_csv(
        COMPARISON_CSV,
        index=False
    )

    # ========================================================
    # RMSE GRAPH
    # ========================================================

    plot_data = comparison[
        [
            "horizon_hours",
            "mean_velocity_baseline_rmse_km",
            "physics_baseline_rmse_km",
            "v1_direct_ml_rmse_km",
            "v2_residual_rmse_km",
        ]
    ].copy()

    plot_data = plot_data.set_index(
        "horizon_hours"
    )

    plot_data.columns = [
        "3-day Mean Velocity",
        "Physics-Informed Baseline",
        "V1 Direct ML",
        "V2 Residual ML",
    ]

    ax = plot_data.plot(
        kind="bar",
        figsize=(11, 6),
    )

    ax.set_title(
        "PolarGuard Member 2 — 2024 Validation RMSE"
    )

    ax.set_xlabel(
        "Forecast Horizon (hours)"
    )

    ax.set_ylabel(
        "Position RMSE (km)"
    )

    ax.grid(
        axis="y",
        alpha=0.25
    )

    plt.tight_layout()

    plt.savefig(
        RMSE_PLOT,
        dpi=180,
        bbox_inches="tight"
    )

    plt.close()

    # ========================================================
    # WITHIN 5 KM GRAPH
    # ========================================================

    within_data = comparison[
        [
            "horizon_hours",
            "physics_within_5km_pct",
            "v1_within_5km_pct",
            "v2_within_5km_pct",
        ]
    ].copy()

    within_data = within_data.set_index(
        "horizon_hours"
    )

    within_data.columns = [
        "Physics-Informed Baseline",
        "V1 Direct ML",
        "V2 Residual ML",
    ]

    ax = within_data.plot(
        kind="bar",
        figsize=(11, 6),
    )

    ax.set_title(
        "PolarGuard Member 2 — Predictions Within 5 km"
    )

    ax.set_xlabel(
        "Forecast Horizon (hours)"
    )

    ax.set_ylabel(
        "Predictions Within 5 km (%)"
    )

    ax.grid(
        axis="y",
        alpha=0.25
    )

    plt.tight_layout()

    plt.savefig(
        WITHIN5_PLOT,
        dpi=180,
        bbox_inches="tight"
    )

    plt.close()

    # ========================================================
    # PRINT RESULT
    # ========================================================

    print()
    print("=" * 80)
    print("2024 VALIDATION COMPARISON")
    print("=" * 80)

    display_columns = [

        "horizon_hours",

        "mean_velocity_baseline_rmse_km",

        "physics_baseline_rmse_km",

        "v1_direct_ml_rmse_km",

        "v2_residual_rmse_km",

        "best_model",

        "v2_vs_v1_percent_change",
    ]

    print()

    print(
        comparison[
            display_columns
        ]
        .round(3)
        .to_string(
            index=False
        )
    )

    print()
    print("=" * 80)
    print("MODEL SELECTION")
    print("=" * 80)

    for _, row in comparison.iterrows():

        print(
            f"{int(row['horizon_hours'])}h -> "
            f"{row['best_model']}"
        )

    print()
    print("Saved comparison table:")
    print(COMPARISON_CSV)

    print()
    print("Saved RMSE graph:")
    print(RMSE_PLOT)

    print()
    print("Saved Within-5-km graph:")
    print(WITHIN5_PLOT)

    print()
    print("=" * 80)
    print("COMPARISON COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()