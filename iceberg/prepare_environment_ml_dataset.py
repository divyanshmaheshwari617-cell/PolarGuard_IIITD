from pathlib import Path
import numpy as np
import pandas as pd


BASE = Path(__file__).resolve().parent

INPUT = (
    BASE / "data" / "processed" /
    "iceberg_features_environment_2019_2025.csv"
)

OUTPUT = (
    BASE / "data" / "processed" /
    "iceberg_features_environment_ml_ready_2019_2025.csv"
)


def main():

    print("=" * 75)
    print("POLARGUARD ENVIRONMENT ML DATASET PREPARATION")
    print("=" * 75)

    df = pd.read_csv(INPUT, parse_dates=["init_date"])

    print("\nTotal rows:", len(df))

    # --------------------------------------------------------
    # DATA SPLIT LABEL
    # --------------------------------------------------------

    year = df["init_date"].dt.year

    df["data_split"] = np.where(
        year <= 2023,
        "train",
        np.where(
            year == 2024,
            "validation",
            "test"
        )
    )

    print("\nSplit sizes:")
    print(df["data_split"].value_counts())

    # --------------------------------------------------------
    # SEA-ICE AVAILABILITY FLAG
    # --------------------------------------------------------

    df["sea_ice_available"] = (
        df["sea_ice_sic"].notna()
    ).astype(np.int8)

    print("\nSea-ice availability:")
    print(df["sea_ice_available"].value_counts())

    # --------------------------------------------------------
    # TRAINING-ONLY SIC MEDIAN
    #
    # IMPORTANT:
    # Do not use validation/test information for imputation.
    # --------------------------------------------------------

    train_mask = df["data_split"] == "train"

    training_sic = df.loc[
        train_mask & df["sea_ice_sic"].notna(),
        "sea_ice_sic"
    ]

    training_median = float(training_sic.median())

    print(
        f"\nTraining-only SIC median: "
        f"{training_median:.6f}"
    )

    # --------------------------------------------------------
    # IMPUTE MISSING SIC
    # --------------------------------------------------------

    missing_before = int(
        df["sea_ice_sic"].isna().sum()
    )

    df["sea_ice_sic_filled"] = (
        df["sea_ice_sic"]
        .fillna(training_median)
    )

    missing_after = int(
        df["sea_ice_sic_filled"].isna().sum()
    )

    print(
        f"\nMissing original SIC: "
        f"{missing_before}"
    )

    print(
        f"Missing filled SIC: "
        f"{missing_after}"
    )

    # --------------------------------------------------------
    # OCEAN CURRENT QUALITY FEATURE
    # --------------------------------------------------------

    # Original direct GLORYS extraction = 0
    # Nearby valid-cell recovery = 1
    if "ocean_recovered" in df.columns:

        df["ocean_recovered"] = (
            df["ocean_recovered"]
            .astype(str)
            .str.lower()
            .map({
                "true": 1,
                "false": 0,
                "1": 1,
                "0": 0
            })
            .fillna(0)
            .astype(np.int8)
        )

    # --------------------------------------------------------
    # QUALITY CHECK
    # --------------------------------------------------------

    print()
    print("=" * 75)
    print("FINAL QUALITY CHECK")
    print("=" * 75)

    print("\nEnvironmental features:")

    columns = [
        "wind_u10",
        "wind_v10",
        "ocean_uo",
        "ocean_vo",
        "ocean_speed",
        "sea_ice_sic_filled",
        "sea_ice_available",
    ]

    for col in columns:

        if col not in df.columns:
            print(f"{col:25s} MISSING COLUMN")
            continue

        print(
            f"{col:25s} "
            f"NaN={df[col].isna().sum()}"
        )

    print("\nSIC availability by split:")

    print(
        df.groupby("data_split")[
            "sea_ice_available"
        ].agg(
            total="count",
            available="sum"
        )
    )

    print("\nFilled SIC statistics:")

    print(
        df["sea_ice_sic_filled"].describe()
    )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    df.to_csv(
        OUTPUT,
        index=False
    )

    print("\nSaved:")
    print(OUTPUT)

    print()
    print("=" * 75)
    print("ML DATASET PREPARATION COMPLETE")
    print("=" * 75)


if __name__ == "__main__":
    main()