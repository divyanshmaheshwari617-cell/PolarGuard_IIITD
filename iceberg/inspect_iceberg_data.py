from pathlib import Path
import pandas as pd
import numpy as np

DATA_DIR = Path(
    "iceberg/data/byu/consolidated_database_v8.0 (1)/updated7_consol"
)

files = sorted(DATA_DIR.glob("*.csv"))

print("=" * 70)
print("POLARGUARD — BYU ICEBERG DATABASE INSPECTION")
print("=" * 70)

print(f"\nCSV files found: {len(files)}")

all_stats = []
failed = []

for file in files:
    try:
        df = pd.read_csv(file)

        if len(df) == 0:
            continue

        # Convert YYYYDDD -> datetime
        dates = pd.to_datetime(
            df["date"].astype(str),
            format="%Y%j",
            errors="coerce"
        )

        valid_dates = dates.dropna()

        all_stats.append({
            "iceberg": file.stem,
            "rows": len(df),
            "valid_dates": len(valid_dates),
            "start": valid_dates.min() if len(valid_dates) else pd.NaT,
            "end": valid_dates.max() if len(valid_dates) else pd.NaT,
        })

    except Exception as e:
        failed.append((file.name, str(e)))

stats = pd.DataFrame(all_stats)

print("\n--- DATABASE SUMMARY ---")

print(f"Iceberg files successfully read: {len(stats)}")
print(f"Failed files: {len(failed)}")

if len(stats):

    print(f"Total observations: {stats['rows'].sum():,}")

    print(f"Minimum observations / iceberg: {stats['rows'].min():,}")
    print(f"Median observations / iceberg: {stats['rows'].median():,.0f}")
    print(f"Mean observations / iceberg: {stats['rows'].mean():,.1f}")
    print(f"Maximum observations / iceberg: {stats['rows'].max():,}")

    print("\nDate coverage:")

    print("Earliest:", stats["start"].min())
    print("Latest:  ", stats["end"].max())

    print("\nTop 15 longest iceberg tracks:")

    print(
        stats.sort_values("rows", ascending=False)
        .head(15)
        .to_string(index=False)
    )

print("\n--- COLUMN INSPECTION ---")

column_sets = {}

for file in files:
    try:
        df = pd.read_csv(file, nrows=5)

        cols = tuple(df.columns)

        column_sets[cols] = column_sets.get(cols, 0) + 1

    except Exception:
        pass

for cols, count in column_sets.items():

    print(f"\n{count} files use columns:")

    for col in cols:
        print("   ", col)

print("\n--- SAMPLE FILE ---")

if files:

    sample = pd.read_csv(files[0])

    print("File:", files[0].name)
    print(sample.head(10))

print("\n--- MISSING VALUES ---")

missing_total = {}

for file in files:

    try:

        df = pd.read_csv(file)

        for col in df.columns:

            missing_total[col] = (
                missing_total.get(col, 0)
                + df[col].isna().sum()
            )

    except Exception:
        pass

for col, count in missing_total.items():

    print(f"{col:15s}: {count:,}")

if failed:

    print("\n--- FAILED FILES ---")

    for filename, error in failed[:20]:
        print(filename, "->", error)

print("\n" + "=" * 70)
print("INSPECTION COMPLETE")
print("=" * 70)