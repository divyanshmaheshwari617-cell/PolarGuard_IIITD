from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "iceberg_features_with_wind_2019_2025.csv"
)

OUTPUT_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "iceberg_features_with_wind_current_2019_2025.csv"
)

CHECKPOINT_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "ocean_current_checkpoint.csv"
)

OCEAN_DIR = (
    BASE_DIR
    / "data"
    / "environment"
    / "ocean_current"
)

BATCH_SIZE = 1000


# ============================================================
# OCEAN FILES
# ============================================================

OCEAN_FILES = {
    2019: OCEAN_DIR / "ocean_current_2019.nc",
    2020: OCEAN_DIR / "ocean_current_2020.nc",
    2021: OCEAN_DIR / "ocean_current_2021.nc",
    2022: OCEAN_DIR / "ocean_current_2022.nc",
    2023: OCEAN_DIR / "ocean_current_2023.nc",
    2024: OCEAN_DIR / "ocean_current_2024.nc",
    2025: OCEAN_DIR / "ocean_current_2025.nc",
}

OCEAN_2019_NORTH = OCEAN_DIR / "ocean_current_2019_north.nc"


# ============================================================
# HELPER
# ============================================================

def separator(title):
    print()
    print("=" * 75)
    print(title)
    print("=" * 75)


def verify_files():
    """Make sure every required file exists before extraction starts."""

    separator("CHECKING INPUT FILES")

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input feature file not found:\n{INPUT_FILE}"
        )

    print(f"Input feature file: OK")
    print(INPUT_FILE)

    for year, path in OCEAN_FILES.items():
        if not path.exists():
            raise FileNotFoundError(
                f"Missing ocean-current file for {year}:\n{path}"
            )

        size_gb = path.stat().st_size / (1024 ** 3)
        print(f"{year}: OK ({size_gb:.2f} GB)")

    if not OCEAN_2019_NORTH.exists():
        raise FileNotFoundError(
            f"Missing 2019 north file:\n{OCEAN_2019_NORTH}"
        )

    size_gb = OCEAN_2019_NORTH.stat().st_size / (1024 ** 3)
    print(f"2019 north strip: OK ({size_gb:.2f} GB)")


def load_dataframe():
    """Load checkpoint if available; otherwise load original feature table."""

    separator("LOADING ICEBERG FEATURE DATA")

    if CHECKPOINT_FILE.exists():
        print("Checkpoint found.")
        print("Resuming previous ocean-current extraction...")

        df = pd.read_csv(
            CHECKPOINT_FILE,
            parse_dates=["init_date"]
        )

    else:
        print("No checkpoint found.")
        print("Starting ocean-current extraction from beginning...")

        df = pd.read_csv(
            INPUT_FILE,
            parse_dates=["init_date"]
        )

        df["ocean_uo"] = np.nan
        df["ocean_vo"] = np.nan

    # In case an older/incomplete checkpoint does not contain the columns
    if "ocean_uo" not in df.columns:
        df["ocean_uo"] = np.nan

    if "ocean_vo" not in df.columns:
        df["ocean_vo"] = np.nan

    print(f"Total samples: {len(df)}")
    print(
        f"Date range: "
        f"{df['init_date'].min().date()} "
        f"to {df['init_date'].max().date()}"
    )

    completed = (
        df["ocean_uo"].notna()
        & df["ocean_vo"].notna()
    ).sum()

    print(f"Already completed: {completed} / {len(df)}")

    return df


def inspect_dataset(ds, label):
    """Print basic dataset information."""

    print()
    print(f"{label}")
    print(f"Variables: {list(ds.data_vars)}")

    if "time" in ds.coords:
        print(
            f"Time: "
            f"{pd.Timestamp(ds.time.values[0]).date()} "
            f"to "
            f"{pd.Timestamp(ds.time.values[-1]).date()}"
        )

    if "latitude" in ds.coords:
        print(
            f"Latitude: "
            f"{float(ds.latitude.min()):.4f} "
            f"to "
            f"{float(ds.latitude.max()):.4f}"
        )

    if "longitude" in ds.coords:
        print(
            f"Longitude: "
            f"{float(ds.longitude.min()):.4f} "
            f"to "
            f"{float(ds.longitude.max()):.4f}"
        )

    if "depth" in ds.coords:
        print(f"Depth(s): {ds.depth.values}")


def normalize_longitudes(lon):
    """
    Convert longitude to [-180, 180).
    Example:
        180 -> -180
        190 -> -170
    """
    lon = np.asarray(lon, dtype=np.float64)
    return ((lon + 180.0) % 360.0) - 180.0


def extract_from_dataset(
    df,
    dataset,
    row_indices,
    label
):
    """
    Extract nearest GLORYS12 uo/vo values for selected dataframe rows.

    Processing is batched and checkpointed.
    """

    row_indices = np.asarray(row_indices, dtype=int)

    if len(row_indices) == 0:
        print(f"\n{label}: no rows.")
        return df

    # Only process rows still missing ocean-current values
    missing_mask = (
        df.loc[row_indices, "ocean_uo"].isna()
        | df.loc[row_indices, "ocean_vo"].isna()
    )

    pending_indices = row_indices[missing_mask.to_numpy()]

    separator(label)

    print(f"Rows in this group: {len(row_indices)}")
    print(f"Rows still needing current: {len(pending_indices)}")
    print(f"Batch size: {BATCH_SIZE}")

    if len(pending_indices) == 0:
        print("Nothing to extract for this group.")
        return df

    number_batches = int(
        np.ceil(len(pending_indices) / BATCH_SIZE)
    )

    print(f"Number of batches: {number_batches}")

    for batch_number, start in enumerate(
        range(0, len(pending_indices), BATCH_SIZE),
        start=1
    ):

        end = min(
            start + BATCH_SIZE,
            len(pending_indices)
        )

        batch_indices = pending_indices[start:end]

        print()
        print(
            f"Batch {batch_number}/{number_batches} "
            f"| rows {start + 1}-{end}"
        )

        batch = df.loc[batch_indices]

        # GLORYS daily mean timestamps are at 00:00.
        query_times = pd.to_datetime(
            batch["init_date"]
        ).values.astype("datetime64[ns]")

        query_lats = (
            batch["current_latitude"]
            .to_numpy(dtype=np.float64)
        )

        query_lons = normalize_longitudes(
            batch["current_longitude"]
            .to_numpy(dtype=np.float64)
        )

        # Vectorized nearest-neighbour lookup
        selected = dataset.sel(
            time=xr.DataArray(
                query_times,
                dims="points"
            ),
            latitude=xr.DataArray(
                query_lats,
                dims="points"
            ),
            longitude=xr.DataArray(
                query_lons,
                dims="points"
            ),
            method="nearest"
        )

        # Dataset contains only one shallow depth layer.
        # Remove it if still present.
        if "depth" in selected.dims:
            selected = selected.squeeze(
                "depth",
                drop=True
            )

        u_values = (
            selected["uo"]
            .load()
            .values
            .astype(np.float32)
            .reshape(-1)
        )

        v_values = (
            selected["vo"]
            .load()
            .values
            .astype(np.float32)
            .reshape(-1)
        )

        df.loc[
            batch_indices,
            "ocean_uo"
        ] = u_values

        df.loc[
            batch_indices,
            "ocean_vo"
        ] = v_values

        completed = (
            df["ocean_uo"].notna()
            & df["ocean_vo"].notna()
        ).sum()

        print("Batch complete.")
        print(
            f"Overall completed: "
            f"{completed} / {len(df)}"
        )

        # Save after EVERY batch
        df.to_csv(
            CHECKPOINT_FILE,
            index=False
        )

        print("Checkpoint saved.")

    return df


def main():

    separator("POLARGUARD GLORYS12 OCEAN-CURRENT EXTRACTION")

    verify_files()

    df = load_dataframe()

    # --------------------------------------------------------
    # Basic validation
    # --------------------------------------------------------

    required_columns = [
        "init_date",
        "current_latitude",
        "current_longitude",
        "wind_u10",
        "wind_v10",
    ]

    missing_columns = [
        c for c in required_columns
        if c not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    df["init_date"] = pd.to_datetime(
        df["init_date"]
    )

    df["_year"] = df["init_date"].dt.year

    unexpected_years = sorted(
        set(df["_year"].unique())
        - set(range(2019, 2026))
    )

    if unexpected_years:
        raise ValueError(
            f"Unexpected years found: {unexpected_years}"
        )

    # --------------------------------------------------------
    # 2019 SOUTH
    #
    # Original 2019 file:
    # -80 to -50 latitude
    # --------------------------------------------------------

    ds_2019_south = xr.open_dataset(
        OCEAN_FILES[2019]
    )

    inspect_dataset(
        ds_2019_south,
        "2019 SOUTH DATASET"
    )

    mask_2019_south = (
        (df["_year"] == 2019)
        & (df["current_latitude"] <= -50.0)
    )

    idx_2019_south = df.index[
        mask_2019_south
    ].to_numpy()

    df = extract_from_dataset(
        df,
        ds_2019_south,
        idx_2019_south,
        "OCEAN CURRENT EXTRACTION 2019 SOUTH"
    )

    ds_2019_south.close()

    # --------------------------------------------------------
    # 2019 NORTH
    #
    # Supplementary strip:
    # -50 to -42.25 latitude
    # --------------------------------------------------------

    ds_2019_north = xr.open_dataset(
        OCEAN_2019_NORTH
    )

    inspect_dataset(
        ds_2019_north,
        "2019 NORTH DATASET"
    )

    mask_2019_north = (
        (df["_year"] == 2019)
        & (df["current_latitude"] > -50.0)
    )

    idx_2019_north = df.index[
        mask_2019_north
    ].to_numpy()

    df = extract_from_dataset(
        df,
        ds_2019_north,
        idx_2019_north,
        "OCEAN CURRENT EXTRACTION 2019 NORTH"
    )

    ds_2019_north.close()

    # --------------------------------------------------------
    # 2020-2025
    # --------------------------------------------------------

    for year in range(2020, 2026):

        path = OCEAN_FILES[year]

        ds = xr.open_dataset(path)

        inspect_dataset(
            ds,
            f"{year} DATASET"
        )

        mask_year = (
            df["_year"] == year
        )

        idx_year = df.index[
            mask_year
        ].to_numpy()

        df = extract_from_dataset(
            df,
            ds,
            idx_year,
            f"OCEAN CURRENT EXTRACTION {year}"
        )

        ds.close()

    # --------------------------------------------------------
    # DERIVED CURRENT SPEED
    # --------------------------------------------------------

    df["ocean_speed"] = np.sqrt(
        df["ocean_uo"] ** 2
        + df["ocean_vo"] ** 2
    )

    # --------------------------------------------------------
    # FINAL QUALITY CHECK
    # --------------------------------------------------------

    separator("FINAL OCEAN-CURRENT FEATURE QUALITY CHECK")

    print(f"\nTotal samples: {len(df)}")

    missing_u = int(
        df["ocean_uo"].isna().sum()
    )

    missing_v = int(
        df["ocean_vo"].isna().sum()
    )

    print(f"Missing ocean_uo: {missing_u}")
    print(f"Missing ocean_vo: {missing_v}")

    print("\nocean_uo statistics:")
    print(df["ocean_uo"].describe())

    print("\nocean_vo statistics:")
    print(df["ocean_vo"].describe())

    print("\nOcean speed statistics:")
    print(df["ocean_speed"].describe())

    print("\nSamples by year:")
    print(
        df.groupby("_year").size()
    )

    print("\nMissing ocean current by year:")

    missing_by_year = (
        df.groupby("_year")[
            ["ocean_uo", "ocean_vo"]
        ]
        .apply(lambda x: x.isna().sum())
    )

    print(missing_by_year)

    # --------------------------------------------------------
    # SAVE FINAL DATASET
    # --------------------------------------------------------

    df = df.drop(
        columns=["_year"]
    )

    df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print("\nFinal dataset saved:")
    print(OUTPUT_FILE)

    # --------------------------------------------------------
    # Remove checkpoint ONLY if absolutely every row succeeded
    # --------------------------------------------------------

    if missing_u == 0 and missing_v == 0:

        if CHECKPOINT_FILE.exists():
            CHECKPOINT_FILE.unlink()

        print(
            "\nCheckpoint removed because "
            "extraction completed successfully."
        )

    else:
        print()
        print(
            "WARNING: Some ocean-current values are missing."
        )
        print(
            "Checkpoint has been kept."
        )
        print(
            "Do NOT train the environmental model yet."
        )
        print(
            "We will inspect these missing locations first."
        )

    separator("GLORYS12 OCEAN-CURRENT EXTRACTION COMPLETE")


if __name__ == "__main__":
    main()