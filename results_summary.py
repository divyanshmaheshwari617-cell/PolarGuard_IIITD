import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path


OUTPUT_DIR = Path("outputs/final")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# FINAL HELD-OUT 2025 RESULTS
# ============================================================

horizons = ["24h", "48h", "72h"]

within_5 = [
    94.87,
    93.18,
    92.33
]

rmse_improvement = [
    4.56,
    5.73,
    7.04
]

mae = [
    0.008854,
    0.012707,
    0.015287
]

rmse = [
    0.036288,
    0.050063,
    0.059311
]

uncertainty = [
    1.96,
    2.75,
    3.28
]


# ============================================================
# FIGURE 1 — ±5% TOLERANCE
# ============================================================

x = np.arange(len(horizons))

plt.figure(figsize=(9, 6))

bars = plt.bar(
    x,
    within_5,
    width=0.55
)

plt.xticks(
    x,
    horizons,
    fontsize=12
)

plt.ylim(0, 100)

plt.ylabel(
    "Forecasts Within ±5 Percentage Points (%)"
)

plt.xlabel(
    "Forecast Horizon"
)

plt.title(
    "PolarGuard Sea-Ice Forecast Performance\n"
    "Held-Out 2025 Test Set"
)

for bar, value in zip(bars, within_5):

    plt.text(
        bar.get_x() + bar.get_width() / 2,
        value + 1,
        f"{value:.2f}%",
        ha="center",
        fontweight="bold"
    )

plt.tight_layout()

file1 = (
    OUTPUT_DIR /
    "forecast_tolerance.png"
)

plt.savefig(
    file1,
    dpi=250
)

plt.close()

print("Saved:", file1)


# ============================================================
# FIGURE 2 — RMSE IMPROVEMENT
# ============================================================

plt.figure(figsize=(9, 6))

bars = plt.bar(
    x,
    rmse_improvement,
    width=0.55
)

plt.xticks(
    x,
    horizons,
    fontsize=12
)

plt.ylabel(
    "RMSE Improvement vs Persistence (%)"
)

plt.xlabel(
    "Forecast Horizon"
)

plt.title(
    "PolarGuard Improvement Over Persistence Baseline"
)

plt.ylim(
    0,
    max(rmse_improvement) + 2
)

for bar, value in zip(
    bars,
    rmse_improvement
):

    plt.text(
        bar.get_x() + bar.get_width() / 2,
        value + 0.2,
        f"+{value:.2f}%",
        ha="center",
        fontweight="bold"
    )

plt.tight_layout()

file2 = (
    OUTPUT_DIR /
    "rmse_improvement.png"
)

plt.savefig(
    file2,
    dpi=250
)

plt.close()

print("Saved:", file2)


# ============================================================
# FIGURE 3 — UNCERTAINTY
# ============================================================

plt.figure(figsize=(9, 6))

bars = plt.bar(
    x,
    uncertainty,
    width=0.55
)

plt.xticks(
    x,
    horizons,
    fontsize=12
)

plt.ylabel(
    "Mean Validation RMSE Uncertainty\n"
    "(SIC percentage points)"
)

plt.xlabel(
    "Forecast Horizon"
)

plt.title(
    "PolarGuard Forecast Uncertainty\n"
    "Estimated from 2024 Validation Residuals"
)

plt.ylim(
    0,
    max(uncertainty) + 1
)

for bar, value in zip(
    bars,
    uncertainty
):

    plt.text(
        bar.get_x() + bar.get_width() / 2,
        value + 0.1,
        f"{value:.2f}",
        ha="center",
        fontweight="bold"
    )

plt.tight_layout()

file3 = (
    OUTPUT_DIR /
    "forecast_uncertainty_summary.png"
)

plt.savefig(
    file3,
    dpi=250
)

plt.close()

print("Saved:", file3)


# ============================================================
# PRINT FINAL SUMMARY
# ============================================================

print("\n" + "=" * 72)

print(
    "POLARGUARD — FINAL SEA-ICE MODEL RESULTS"
)

print("=" * 72)

for i, horizon in enumerate(horizons):

    print(f"\n{horizon}")

    print(
        f"  MAE                    : "
        f"{mae[i]:.6f}"
    )

    print(
        f"  RMSE                   : "
        f"{rmse[i]:.6f}"
    )

    print(
        f"  Within ±5% SIC         : "
        f"{within_5[i]:.2f}%"
    )

    print(
        f"  RMSE gain vs baseline  : "
        f"+{rmse_improvement[i]:.2f}%"
    )

    print(
        f"  Mean uncertainty       : "
        f"{uncertainty[i]:.2f} percentage points"
    )


print("\n" + "=" * 72)
print("RESULT FIGURES COMPLETE")
print("=" * 72)
