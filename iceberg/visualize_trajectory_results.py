from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# PATHS
# ============================================================

PREDICTIONS_FILE = Path(
    "iceberg/outputs/trajectory_ml_validation_predictions_2024.csv"
)

BASELINE_FILE = Path(
    "iceberg/outputs/iceberg_baseline_validation_2024.csv"
)

OUTPUT_DIR = Path(
    "iceberg/outputs/plots"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# LOAD DATA
# ============================================================

print("=" * 75)
print("ICEBERG TRAJECTORY VISUALIZATION")
print("=" * 75)

pred = pd.read_csv(
    PREDICTIONS_FILE,
    parse_dates=["init_date"]
)

baseline = pd.read_csv(
    BASELINE_FILE,
    parse_dates=["init_date"]
)

print(f"\nPrediction rows: {len(pred):,}")
print(f"Baseline rows: {len(baseline):,}")
print(
    f"Unique icebergs in predictions: "
    f"{pred['iceberg_id'].nunique():,}"
)


# ============================================================
# 1. RMSE COMPARISON GRAPH
# ============================================================

horizons = [24, 48, 72]

baseline_rmse = [
    4.572,
    8.108,
    12.087,
]

ml_rmse = [
    np.sqrt(
        np.mean(
            pred["error_km_24h"] ** 2
        )
    ),
    np.sqrt(
        np.mean(
            pred["error_km_48h"] ** 2
        )
    ),
    np.sqrt(
        np.mean(
            pred["error_km_72h"] ** 2
        )
    ),
]

x = np.arange(
    len(horizons)
)

width = 0.35

plt.figure(
    figsize=(9, 6)
)

plt.bar(
    x - width / 2,
    baseline_rmse,
    width,
    label="3-day mean velocity baseline"
)

plt.bar(
    x + width / 2,
    ml_rmse,
    width,
    label="Trajectory ML"
)

plt.xticks(
    x,
    [
        "24h",
        "48h",
        "72h",
    ]
)

plt.ylabel(
    "Position RMSE (km)"
)

plt.xlabel(
    "Forecast horizon"
)

plt.title(
    "Iceberg Trajectory Forecast RMSE"
)

plt.legend()

plt.tight_layout()

rmse_file = (
    OUTPUT_DIR
    / "trajectory_rmse_comparison.png"
)

plt.savefig(
    rmse_file,
    dpi=200
)

plt.close()


# ============================================================
# 2. RMSE IMPROVEMENT GRAPH
# ============================================================

improvements = []

for base, model in zip(
    baseline_rmse,
    ml_rmse
):

    improvement = (
        (base - model)
        / base
        * 100.0
    )

    improvements.append(
        improvement
    )


plt.figure(
    figsize=(9, 6)
)

plt.bar(
    [
        "24h",
        "48h",
        "72h",
    ],
    improvements
)

plt.ylabel(
    "RMSE improvement over baseline (%)"
)

plt.xlabel(
    "Forecast horizon"
)

plt.title(
    "Iceberg ML Improvement Over Kinematic Baseline"
)

plt.tight_layout()

improvement_file = (
    OUTPUT_DIR
    / "trajectory_rmse_improvement.png"
)

plt.savefig(
    improvement_file,
    dpi=200
)

plt.close()


# ============================================================
# 3. ERROR DISTRIBUTION GRAPH
# ============================================================

plt.figure(
    figsize=(9, 6)
)

plt.boxplot(
    [
        pred["error_km_24h"],
        pred["error_km_48h"],
        pred["error_km_72h"],
    ],
    tick_labels=[
        "24h",
        "48h",
        "72h",
    ],
    showfliers=False
)

plt.ylabel(
    "Position error (km)"
)

plt.xlabel(
    "Forecast horizon"
)

plt.title(
    "Iceberg Trajectory Position Error Distribution"
)

plt.tight_layout()

error_distribution_file = (
    OUTPUT_DIR
    / "trajectory_error_distribution.png"
)

plt.savefig(
    error_distribution_file,
    dpi=200
)

plt.close()


# ============================================================
# 4. WITHIN-5-KM GRAPH
# ============================================================

within_5 = [
    100.0
    * np.mean(
        pred["error_km_24h"]
        <= 5.0
    ),
    100.0
    * np.mean(
        pred["error_km_48h"]
        <= 5.0
    ),
    100.0
    * np.mean(
        pred["error_km_72h"]
        <= 5.0
    ),
]


plt.figure(
    figsize=(9, 6)
)

plt.bar(
    [
        "24h",
        "48h",
        "72h",
    ],
    within_5
)

plt.ylim(
    0,
    100
)

plt.ylabel(
    "Forecasts within 5 km (%)"
)

plt.xlabel(
    "Forecast horizon"
)

plt.title(
    "Iceberg Forecasts Within 5 km of Observed Position"
)

plt.tight_layout()

within5_file = (
    OUTPUT_DIR
    / "trajectory_within_5km.png"
)

plt.savefig(
    within5_file,
    dpi=200
)

plt.close()


# ============================================================
# 5. SELECT GOOD EXAMPLE ICEBERG
# ============================================================

# Find an iceberg with many validation predictions

counts = (
    pred["iceberg_id"]
    .value_counts()
)

candidate_ids = counts[
    counts >= 20
].index.tolist()

if len(candidate_ids) == 0:
    candidate_ids = (
        counts.index.tolist()
    )

selected_id = (
    candidate_ids[0]
)

iceberg_data = pred[
    pred["iceberg_id"]
    == selected_id
].copy()

iceberg_data = (
    iceberg_data
    .sort_values(
        "init_date"
    )
    .reset_index(
        drop=True
    )
)


# Limit plot to make it readable

iceberg_data = (
    iceberg_data
    .head(30)
)


print(
    f"\nSelected iceberg for "
    f"trajectory example: {selected_id}"
)

print(
    f"Example points: "
    f"{len(iceberg_data)}"
)


# ============================================================
# 6. 24H ACTUAL VS PREDICTED TRAJECTORY
# ============================================================

plt.figure(
    figsize=(9, 7)
)

plt.plot(
    iceberg_data[
        "true_lon_24h"
    ],
    iceberg_data[
        "true_lat_24h"
    ],
    marker="o",
    label="Observed position"
)

plt.plot(
    iceberg_data[
        "pred_lon_24h"
    ],
    iceberg_data[
        "pred_lat_24h"
    ],
    marker="x",
    label="ML predicted position"
)

plt.xlabel(
    "Longitude"
)

plt.ylabel(
    "Latitude"
)

plt.title(
    f"Iceberg {selected_id}: "
    "24h Observed vs Predicted Trajectory"
)

plt.legend()

plt.grid(
    alpha=0.3
)

plt.tight_layout()

trajectory_24_file = (
    OUTPUT_DIR
    / f"{selected_id}_trajectory_24h.png"
)

plt.savefig(
    trajectory_24_file,
    dpi=200
)

plt.close()


# ============================================================
# 7. 48H ACTUAL VS PREDICTED
# ============================================================

plt.figure(
    figsize=(9, 7)
)

plt.plot(
    iceberg_data[
        "true_lon_48h"
    ],
    iceberg_data[
        "true_lat_48h"
    ],
    marker="o",
    label="Observed position"
)

plt.plot(
    iceberg_data[
        "pred_lon_48h"
    ],
    iceberg_data[
        "pred_lat_48h"
    ],
    marker="x",
    label="ML predicted position"
)

plt.xlabel(
    "Longitude"
)

plt.ylabel(
    "Latitude"
)

plt.title(
    f"Iceberg {selected_id}: "
    "48h Observed vs Predicted Trajectory"
)

plt.legend()

plt.grid(
    alpha=0.3
)

plt.tight_layout()

trajectory_48_file = (
    OUTPUT_DIR
    / f"{selected_id}_trajectory_48h.png"
)

plt.savefig(
    trajectory_48_file,
    dpi=200
)

plt.close()


# ============================================================
# 8. 72H ACTUAL VS PREDICTED
# ============================================================

plt.figure(
    figsize=(9, 7)
)

plt.plot(
    iceberg_data[
        "true_lon_72h"
    ],
    iceberg_data[
        "true_lat_72h"
    ],
    marker="o",
    label="Observed position"
)

plt.plot(
    iceberg_data[
        "pred_lon_72h"
    ],
    iceberg_data[
        "pred_lat_72h"
    ],
    marker="x",
    label="ML predicted position"
)

plt.xlabel(
    "Longitude"
)

plt.ylabel(
    "Latitude"
)

plt.title(
    f"Iceberg {selected_id}: "
    "72h Observed vs Predicted Trajectory"
)

plt.legend()

plt.grid(
    alpha=0.3
)

plt.tight_layout()

trajectory_72_file = (
    OUTPUT_DIR
    / f"{selected_id}_trajectory_72h.png"
)

plt.savefig(
    trajectory_72_file,
    dpi=200
)

plt.close()


# ============================================================
# 9. ERROR OVER TIME
# ============================================================

plt.figure(
    figsize=(11, 6)
)

plt.plot(
    iceberg_data[
        "init_date"
    ],
    iceberg_data[
        "error_km_24h"
    ],
    marker="o",
    label="24h"
)

plt.plot(
    iceberg_data[
        "init_date"
    ],
    iceberg_data[
        "error_km_48h"
    ],
    marker="o",
    label="48h"
)

plt.plot(
    iceberg_data[
        "init_date"
    ],
    iceberg_data[
        "error_km_72h"
    ],
    marker="o",
    label="72h"
)

plt.ylabel(
    "Position error (km)"
)

plt.xlabel(
    "Initialization date"
)

plt.title(
    f"Iceberg {selected_id}: "
    "Forecast Error Over Time"
)

plt.legend()

plt.xticks(
    rotation=45
)

plt.tight_layout()

error_time_file = (
    OUTPUT_DIR
    / f"{selected_id}_error_over_time.png"
)

plt.savefig(
    error_time_file,
    dpi=200
)

plt.close()


# ============================================================
# SUMMARY
# ============================================================

print("\n" + "=" * 75)
print("VISUALIZATION SUMMARY")
print("=" * 75)

print("\nML RMSE values:")

for horizon, value in zip(
    horizons,
    ml_rmse
):
    print(
        f"{horizon}h : "
        f"{value:.3f} km"
    )


print("\nRMSE improvements:")

for horizon, value in zip(
    horizons,
    improvements
):
    print(
        f"{horizon}h : "
        f"{value:+.2f}%"
    )


print("\nWithin 5 km:")

for horizon, value in zip(
    horizons,
    within_5
):
    print(
        f"{horizon}h : "
        f"{value:.2f}%"
    )


print("\nFiles saved:")

for file_path in [
    rmse_file,
    improvement_file,
    error_distribution_file,
    within5_file,
    trajectory_24_file,
    trajectory_48_file,
    trajectory_72_file,
    error_time_file,
]:
    print(file_path)


print("\n" + "=" * 75)
print("VISUALIZATION COMPLETE")
print("=" * 75)