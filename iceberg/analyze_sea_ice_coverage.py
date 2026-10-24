from pathlib import Path
import pandas as pd
import numpy as np

BASE = Path(__file__).resolve().parent

FILE = (
    BASE / "data" / "processed" /
    "iceberg_features_environment_2019_2025.csv"
)

df = pd.read_csv(FILE, parse_dates=["init_date"])

print("=" * 75)
print("POLARGUARD SEA-ICE COVERAGE ANALYSIS")
print("=" * 75)

# ------------------------------------------------------------
# Distance analysis
# ------------------------------------------------------------

print("\nSEA-ICE GRID DISTANCE")

for threshold in [15, 20, 25, 30, 50, 100]:
    count = (
        df["sea_ice_grid_distance_km"] > threshold
    ).sum()

    print(
        f"> {threshold:3d} km : "
        f"{count:6d} "
        f"({100 * count / len(df):.3f}%)"
    )

# ------------------------------------------------------------
# Missing SIC
# ------------------------------------------------------------

missing = df[df["sea_ice_sic"].isna()].copy()

print("\n" + "=" * 75)
print("MISSING SIC")
print("=" * 75)

print("\nMissing rows:", len(missing))

print("\nMissing latitude:")
print(missing["current_latitude"].describe())

print("\nMissing longitude:")
print(missing["current_longitude"].describe())

print("\nGrid distance for missing rows:")
print(missing["sea_ice_grid_distance_km"].describe())

print("\nTop missing icebergs:")
print(
    missing["iceberg_id"]
    .value_counts()
    .head(20)
)

# ------------------------------------------------------------
# Check whether large-distance points have valid SIC
# ------------------------------------------------------------

print("\n" + "=" * 75)
print("LARGE GRID-DISTANCE ROWS")
print("=" * 75)

for threshold in [25, 50, 100]:

    subset = df[
        df["sea_ice_grid_distance_km"] > threshold
    ]

    print(f"\nDistance > {threshold} km")
    print("Rows:", len(subset))

    if len(subset) > 0:

        print(
            "Missing SIC:",
            subset["sea_ice_sic"].isna().sum()
        )

        print(
            "Latitude range:",
            subset["current_latitude"].min(),
            "to",
            subset["current_latitude"].max()
        )

# ------------------------------------------------------------
# Missing by split
# ------------------------------------------------------------

df["year"] = df["init_date"].dt.year

print("\n" + "=" * 75)
print("MISSING BY DATA SPLIT")
print("=" * 75)

train = df[df["year"] <= 2023]
val = df[df["year"] == 2024]
test = df[df["year"] == 2025]

for name, part in [
    ("TRAIN 2019-2023", train),
    ("VALIDATION 2024", val),
    ("TEST 2025", test),
]:

    missing_count = part["sea_ice_sic"].isna().sum()

    print(
        f"{name:20s}: "
        f"{missing_count:5d}/{len(part):5d} "
        f"({100 * missing_count / len(part):.2f}%)"
    )

print("\n" + "=" * 75)
print("ANALYSIS COMPLETE")
print("=" * 75)