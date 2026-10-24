from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# PATHS
# ============================================================

BASE = Path(__file__).resolve().parent

INPUT_DIR = (
    BASE
    / "iceberg"
    / "outputs"
    / "model_testing_2025"
)

OVERALL_FILE = (
    INPUT_DIR
    / "sic_2025_metrics.csv"
)

MONTHLY_FILE = (
    INPUT_DIR
    / "sic_2025_monthly_metrics.csv"
)

OUTPUT_DIR = (
    INPUT_DIR
    / "figures"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

DPI = 220


# ============================================================
# HELPERS
# ============================================================

def save_figure(
    fig,
    filename,
):
    output_file = (
        OUTPUT_DIR
        /
        filename
    )

    fig.savefig(
        output_file,
        dpi=DPI,
        bbox_inches="tight",
    )

    plt.close(fig)

    print(
        "Saved:",
        output_file,
    )


def horizon_labels(
    df,
):
    return [
        f"+{int(value)}h"
        for value in df[
            "horizon_hours"
        ]
    ]


# ============================================================
# FIGURE 1
# POLARGUARD RMSE BY HORIZON
# ============================================================

def plot_rmse_by_horizon(
    overall,
):
    data = overall.sort_values(
        "horizon_hours"
    ).copy()

    labels = horizon_labels(data)

    rmse = (
        data["rmse"]
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
        rmse,
    )

    ax.set_xticks(x)

    ax.set_xticklabels(
        labels
    )

    ax.set_ylabel(
        "RMSE (SIC percentage points)"
    )

    ax.set_xlabel(
        "Forecast Horizon"
    )

    ax.set_title(
        "PolarGuard Full-Year 2025 SIC Forecast RMSE"
    )

    ax.grid(
        axis="y",
        alpha=0.25,
    )

    for bar, value in zip(
        bars,
        rmse,
    ):
        ax.text(
            bar.get_x()
            +
            bar.get_width() / 2,
            value + 0.12,
            f"{value:.2f}",
            ha="center",
            va="bottom",
        )

    fig.tight_layout()

    save_figure(
        fig,
        "01_rmse_by_horizon.png",
    )


# ============================================================
# FIGURE 2
# POLARGUARD VS PERSISTENCE RMSE
# ============================================================

def plot_rmse_vs_persistence(
    overall,
):
    data = overall.sort_values(
        "horizon_hours"
    ).copy()

    labels = horizon_labels(data)

    pg_rmse = (
        data["rmse"]
        .to_numpy(dtype=float)
        *
        100.0
    )

    persistence_rmse = (
        data[
            "persistence_rmse"
        ]
        .to_numpy(dtype=float)
        *
        100.0
    )

    x = np.arange(
        len(data)
    )

    width = 0.36

    fig, ax = plt.subplots(
        figsize=(9, 5.8)
    )

    ax.bar(
        x - width / 2,
        pg_rmse,
        width,
        label="PolarGuard",
    )

    ax.bar(
        x + width / 2,
        persistence_rmse,
        width,
        label="Persistence Baseline",
    )

    ax.set_xticks(x)

    ax.set_xticklabels(
        labels
    )

    ax.set_ylabel(
        "RMSE (SIC percentage points)"
    )

    ax.set_xlabel(
        "Forecast Horizon"
    )

    ax.set_title(
        "PolarGuard vs Persistence Baseline — 2025 RMSE"
    )

    ax.legend()

    ax.grid(
        axis="y",
        alpha=0.25,
    )

    fig.tight_layout()

    save_figure(
        fig,
        "02_rmse_vs_persistence.png",
    )


# ============================================================
# FIGURE 3
# R2 BY HORIZON
# ============================================================

def plot_r2_by_horizon(
    overall,
):
    data = overall.sort_values(
        "horizon_hours"
    ).copy()

    labels = horizon_labels(data)

    values = data[
        "r2"
    ].to_numpy(dtype=float)

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

    ax.set_xticks(x)

    ax.set_xticklabels(
        labels
    )

    ax.set_ylabel(
        "R²"
    )

    ax.set_xlabel(
        "Forecast Horizon"
    )

    ax.set_title(
        "PolarGuard Full-Year 2025 SIC Forecast R²"
    )

    ax.set_ylim(
        0.94,
        1.0,
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
            value + 0.001,
            f"{value:.4f}",
            ha="center",
            va="bottom",
        )

    fig.tight_layout()

    save_figure(
        fig,
        "03_r2_by_horizon.png",
    )


# ============================================================
# FIGURE 4
# ACTUAL VS PREDICTED MEAN SIC
# ============================================================

def plot_actual_vs_predicted_mean_sic(
    overall,
):
    data = overall.sort_values(
        "horizon_hours"
    ).copy()

    labels = horizon_labels(data)

    actual = (
        data[
            "actual_mean_sic"
        ]
        .to_numpy(dtype=float)
        *
        100.0
    )

    predicted = (
        data[
            "predicted_mean_sic"
        ]
        .to_numpy(dtype=float)
        *
        100.0
    )

    x = np.arange(
        len(data)
    )

    width = 0.36

    fig, ax = plt.subplots(
        figsize=(9, 5.8)
    )

    ax.bar(
        x - width / 2,
        actual,
        width,
        label="Actual 2025 SIC",
    )

    ax.bar(
        x + width / 2,
        predicted,
        width,
        label="PolarGuard Predicted SIC",
    )

    ax.set_xticks(x)

    ax.set_xticklabels(
        labels
    )

    ax.set_ylabel(
        "Mean SIC (%)"
    )

    ax.set_xlabel(
        "Forecast Horizon"
    )

    ax.set_title(
        "Actual vs Predicted Mean Sea-Ice Concentration — 2025"
    )

    ax.legend()

    ax.grid(
        axis="y",
        alpha=0.25,
    )

    fig.tight_layout()

    save_figure(
        fig,
        "04_actual_vs_predicted_mean_sic.png",
    )


# ============================================================
# FIGURE 5
# BIAS BY HORIZON
# ============================================================

def plot_bias_by_horizon(
    overall,
):
    data = overall.sort_values(
        "horizon_hours"
    ).copy()

    labels = horizon_labels(data)

    bias = (
        data[
            "bias"
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
        bias,
    )

    ax.axhline(
        0.0,
        linewidth=1.2,
    )

    ax.set_xticks(x)

    ax.set_xticklabels(
        labels
    )

    ax.set_ylabel(
        "Bias (SIC percentage points)"
    )

    ax.set_xlabel(
        "Forecast Horizon"
    )

    ax.set_title(
        "PolarGuard Forecast Bias — Full-Year 2025"
    )

    ax.grid(
        axis="y",
        alpha=0.25,
    )

    for bar, value in zip(
        bars,
        bias,
    ):
        ax.text(
            bar.get_x()
            +
            bar.get_width() / 2,
            value - 0.01
            if value < 0
            else value + 0.01,
            f"{value:.3f}",
            ha="center",
            va="top"
            if value < 0
            else "bottom",
        )

    fig.tight_layout()

    save_figure(
        fig,
        "05_bias_by_horizon.png",
    )


# ============================================================
# FIGURE 6
# MONTHLY MAE
# ============================================================

def plot_monthly_mae(
    monthly,
):
    fig, ax = plt.subplots(
        figsize=(12, 6)
    )

    for horizon in [
        "24h",
        "48h",
        "72h",
    ]:
        data = monthly[
            monthly[
                "horizon"
            ]
            ==
            horizon
        ].sort_values(
            "month"
        )

        ax.plot(
            data["month"],
            data["mae"] * 100.0,
            marker="o",
            label=f"+{horizon}",
        )

    ax.set_ylabel(
        "MAE (SIC percentage points)"
    )

    ax.set_xlabel(
        "Month"
    )

    ax.set_title(
        "Monthly Sea-Ice Forecast MAE — 2025"
    )

    ax.tick_params(
        axis="x",
        rotation=45,
    )

    ax.legend()

    ax.grid(
        alpha=0.25,
    )

    fig.tight_layout()

    save_figure(
        fig,
        "06_monthly_mae_2025.png",
    )


# ============================================================
# FIGURE 7
# MONTHLY RMSE
# ============================================================

def plot_monthly_rmse(
    monthly,
):
    fig, ax = plt.subplots(
        figsize=(12, 6)
    )

    for horizon in [
        "24h",
        "48h",
        "72h",
    ]:
        data = monthly[
            monthly[
                "horizon"
            ]
            ==
            horizon
        ].sort_values(
            "month"
        )

        ax.plot(
            data["month"],
            data["rmse"] * 100.0,
            marker="o",
            label=f"+{horizon}",
        )

    ax.set_ylabel(
        "RMSE (SIC percentage points)"
    )

    ax.set_xlabel(
        "Month"
    )

    ax.set_title(
        "Monthly Sea-Ice Forecast RMSE — 2025"
    )

    ax.tick_params(
        axis="x",
        rotation=45,
    )

    ax.legend()

    ax.grid(
        alpha=0.25,
    )

    fig.tight_layout()

    save_figure(
        fig,
        "07_monthly_rmse_2025.png",
    )


# ============================================================
# FIGURE 8
# MONTHLY ACTUAL VS PREDICTED SIC
# ============================================================

def plot_monthly_actual_vs_predicted(
    monthly,
):
    fig, ax = plt.subplots(
        figsize=(12, 6)
    )

    for horizon in [
        "24h",
        "48h",
        "72h",
    ]:
        data = monthly[
            monthly[
                "horizon"
            ]
            ==
            horizon
        ].sort_values(
            "month"
        )

        ax.plot(
            data["month"],
            data[
                "actual_mean_sic"
            ] * 100.0,
            linestyle="--",
            alpha=0.6,
        )

        ax.plot(
            data["month"],
            data[
                "predicted_mean_sic"
            ] * 100.0,
            marker="o",
            label=f"Predicted +{horizon}",
        )

    ax.set_ylabel(
        "Mean SIC (%)"
    )

    ax.set_xlabel(
        "Month"
    )

    ax.set_title(
        "Monthly Actual vs PolarGuard Predicted SIC — 2025"
    )

    ax.tick_params(
        axis="x",
        rotation=45,
    )

    ax.legend()

    ax.grid(
        alpha=0.25,
    )

    fig.tight_layout()

    save_figure(
        fig,
        "08_monthly_actual_vs_predicted_sic.png",
    )


# ============================================================
# FIGURE 9
# RMSE IMPROVEMENT VS PERSISTENCE
# ============================================================

def plot_rmse_improvement(
    overall,
):
    data = overall.sort_values(
        "horizon_hours"
    ).copy()

    labels = horizon_labels(data)

    improvement = (
        data[
            "rmse_improvement_vs_persistence_pct"
        ]
        .to_numpy(dtype=float)
    )

    fig, ax = plt.subplots(
        figsize=(8, 5.5)
    )

    x = np.arange(
        len(data)
    )

    bars = ax.bar(
        x,
        improvement,
    )

    ax.axhline(
        0.0,
        linewidth=1.2,
    )

    ax.set_xticks(x)

    ax.set_xticklabels(
        labels
    )

    ax.set_ylabel(
        "RMSE Improvement vs Persistence (%)"
    )

    ax.set_xlabel(
        "Forecast Horizon"
    )

    ax.set_title(
        "PolarGuard Improvement over Persistence Baseline"
    )

    ax.grid(
        axis="y",
        alpha=0.25,
    )

    for bar, value in zip(
        bars,
        improvement,
    ):
        ax.text(
            bar.get_x()
            +
            bar.get_width() / 2,
            value + 0.15,
            f"{value:.2f}%",
            ha="center",
            va="bottom",
        )

    fig.tight_layout()

    save_figure(
        fig,
        "09_rmse_improvement_vs_persistence.png",
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 100)
    print("POLARGUARD")
    print("2025 MEMBER-1 TESTING VISUALIZATION")
    print("=" * 100)

    if not OVERALL_FILE.exists():

        raise FileNotFoundError(
            f"Missing overall metrics file: "
            f"{OVERALL_FILE}"
        )

    if not MONTHLY_FILE.exists():

        raise FileNotFoundError(
            f"Missing monthly metrics file: "
            f"{MONTHLY_FILE}"
        )

    overall = pd.read_csv(
        OVERALL_FILE
    )

    monthly = pd.read_csv(
        MONTHLY_FILE
    )

    print()
    print(
        "Overall rows:",
        len(overall),
    )

    print(
        "Monthly rows:",
        len(monthly),
    )

    print()

    plot_rmse_by_horizon(
        overall
    )

    plot_rmse_vs_persistence(
        overall
    )

    plot_r2_by_horizon(
        overall
    )

    plot_actual_vs_predicted_mean_sic(
        overall
    )

    plot_bias_by_horizon(
        overall
    )

    plot_monthly_mae(
        monthly
    )

    plot_monthly_rmse(
        monthly
    )

    plot_monthly_actual_vs_predicted(
        monthly
    )

    plot_rmse_improvement(
        overall
    )

    print()
    print("=" * 100)
    print("FIGURES CREATED")
    print("=" * 100)

    for file in sorted(
        OUTPUT_DIR.glob(
            "*.png"
        )
    ):
        print(
            file
        )

    print()
    print("=" * 100)
    print(
        "2025 MEMBER-1 TESTING VISUALIZATION COMPLETE"
    )
    print("=" * 100)


if __name__ == "__main__":
    main()