import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parent

FILE = (
    BASE / "data" / "processed" /
    "iceberg_features_with_wind_current_2019_2025.csv"
)

OUT = (
    BASE / "outputs" /
    "missing_ocean_current_analysis.csv"
)

OUT.parent.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(FILE, parse_dates=["init_date"])

missing = df[
    df["ocean_uo"].isna() |
    df["ocean_vo"].isna()
].copy()

missing["year"] = missing["init_date"].dt.year

print("=" * 75)
print("MISSING OCEAN CURRENT ANALYSIS")
print("=" * 75)

print("\nTotal rows:", len(df))
print("Missing rows:", len(missing))
print(f"Missing percentage: {100 * len(missing) / len(df):.2f}%")

print("\nMissing by year:")
print(missing.groupby("year").size())

print("\nLatitude statistics:")
print(missing["current_latitude"].describe())

print("\nLongitude statistics:")
print(missing["current_longitude"].describe())

print("\nMissing by iceberg (top 20):")
print(
    missing["iceberg_id"]
    .value_counts()
    .head(20)
)

print("\nSample missing positions:")
print(
    missing[
        [
            "iceberg_id",
            "init_date",
            "current_latitude",
            "current_longitude"
        ]
    ].head(30).to_string(index=False)
)

missing.to_csv(OUT, index=False)

print("\nSaved:")
print(OUT)

print("\n" + "=" * 75)
print("ANALYSIS COMPLETE")
print("=" * 75)