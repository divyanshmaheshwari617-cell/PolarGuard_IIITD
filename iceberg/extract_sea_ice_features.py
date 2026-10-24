from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

try:
    from pyproj import Transformer
except ImportError:
    raise ImportError(
        "\npyproj is not installed.\n"
        "Run:\n"
        "pip install pyproj\n"
    )


# ============================================================
# PATHS
# ============================================================

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent

INPUT_FILE = (
    BASE
    / "data"
    / "processed"
    / "iceberg_features_with_wind_current_recovered_2019_2025.csv"
)

SEA_ICE_FILE = (
    ROOT
    / "data"
    / "processed"
    / "sea_ice_2019_2025.nc"
)

OUTPUT_FILE = (
    BASE
    / "data"
    / "processed"
    / "iceberg_features_environment_2019_2025.csv"
)

CHECKPOINT_FILE = (
    BASE
    / "data"
    / "processed"
    / "sea_ice_extraction_checkpoint.csv"
)

BATCH_SIZE = 2000


# ============================================================
# HELPERS
# ============================================================

def separator(title):
    print()
    print("=" * 75)
    print(title)
    print("=" * 75)


def haversine_km(lat1, lon1, lat2, lon2):
    """
    Haversine great-circle distance.
    """
    R = 6371.0088

    lat1 = np.radians(lat1)
    lon1 = np.radians(lon1)
    lat2 = np.radians(lat2)
    lon2 = np.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        np.sin(dlat / 2.0) ** 2
        + np.cos(lat1)
        * np.cos(lat2)
        * np.sin(dlon / 2.0) ** 2
    )

    return 2 * R * np.arcsin(np.sqrt(a))


def nearest_indices(grid, values):
    """
    Return nearest grid index for every requested coordinate.

    Works for ascending or descending grids.
    """
    grid = np.asarray(grid, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)

    # Small grids: x=316, y=332.
    # Batched calculation is safe and simple.
    distances = np.abs(
        values[:, None] - grid[None, :]
    )

    return np.argmin(distances, axis=1)


# ============================================================
# MAIN
# ============================================================

def main():

    separator("POLARGUARD SEA-ICE FEATURE EXTRACTION")

    # --------------------------------------------------------
    # File checks
    # --------------------------------------------------------

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found:\n{INPUT_FILE}"
        )

    if not SEA_ICE_FILE.exists():
        raise FileNotFoundError(
            f"Sea-ice file not found:\n{SEA_ICE_FILE}"
        )

    print("\nIceberg input:")
    print(INPUT_FILE)

    print("\nSea-ice dataset:")
    print(SEA_ICE_FILE)

    # --------------------------------------------------------
    # Load iceberg table / checkpoint
    # --------------------------------------------------------

    separator("LOADING ICEBERG DATA")

    if CHECKPOINT_FILE.exists():

        print("Checkpoint found.")
        print("Resuming previous extraction...")

        df = pd.read_csv(
            CHECKPOINT_FILE,
            parse_dates=["init_date"]
        )

    else:

        print("No checkpoint found.")
        print("Starting new extraction...")

        df = pd.read_csv(
            INPUT_FILE,
            parse_dates=["init_date"]
        )

    print(f"Rows: {len(df)}")

    print(
        "Date range:",
        df["init_date"].min().date(),
        "to",
        df["init_date"].max().date()
    )

    # --------------------------------------------------------
    # Create output columns
    # --------------------------------------------------------

    if "sea_ice_sic" not in df.columns:
        df["sea_ice_sic"] = np.nan

    if "sea_ice_x" not in df.columns:
        df["sea_ice_x"] = np.nan

    if "sea_ice_y" not in df.columns:
        df["sea_ice_y"] = np.nan

    if "sea_ice_grid_distance_km" not in df.columns:
        df["sea_ice_grid_distance_km"] = np.nan

    # --------------------------------------------------------
    # Open sea-ice dataset
    # --------------------------------------------------------

    separator("OPENING SEA-ICE DATASET")

    ds = xr.open_dataset(SEA_ICE_FILE)

    required = [
        "sea_ice_concentration",
        "time",
        "x",
        "y",
    ]

    for item in required:
        if item not in ds:
            ds.close()
            raise ValueError(
                f"Required sea-ice item missing: {item}"
            )

    sic = ds["sea_ice_concentration"]

    x_grid = ds["x"].values.astype(np.float64)
    y_grid = ds["y"].values.astype(np.float64)

    times = pd.to_datetime(ds["time"].values)

    print(f"Sea-ice time steps: {len(times)}")

    print(
        "Sea-ice dates:",
        times.min().date(),
        "to",
        times.max().date()
    )

    print(
        f"x range: {x_grid.min():.0f} "
        f"to {x_grid.max():.0f} m"
    )

    print(
        f"y range: {y_grid.min():.0f} "
        f"to {y_grid.max():.0f} m"
    )

    # --------------------------------------------------------
    # Date -> integer index
    # --------------------------------------------------------

    time_lookup = {
        pd.Timestamp(t).normalize(): i
        for i, t in enumerate(times)
    }

    # --------------------------------------------------------
    # Coordinate transformer
    #
    # WGS84 lat/lon -> Antarctic Polar Stereographic
    # --------------------------------------------------------

    transformer = Transformer.from_crs(
        "EPSG:4326",
        "EPSG:3412",
        always_xy=True
    )

    separator("TRANSFORMING ICEBERG COORDINATES")

    lon = df["current_longitude"].to_numpy(
        dtype=np.float64
    )

    lat = df["current_latitude"].to_numpy(
        dtype=np.float64
    )

    iceberg_x, iceberg_y = transformer.transform(
        lon,
        lat
    )

    iceberg_x = np.asarray(
        iceberg_x,
        dtype=np.float64
    )

    iceberg_y = np.asarray(
        iceberg_y,
        dtype=np.float64
    )

    print(
        f"Transformed x range: "
        f"{np.nanmin(iceberg_x):.0f} "
        f"to {np.nanmax(iceberg_x):.0f}"
    )

    print(
        f"Transformed y range: "
        f"{np.nanmin(iceberg_y):.0f} "
        f"to {np.nanmax(iceberg_y):.0f}"
    )

    # --------------------------------------------------------
    # Find rows still requiring extraction
    # --------------------------------------------------------

    # We use sea_ice_x as the progress indicator because SIC itself
    # is allowed to legitimately be NaN for a masked cell.
    pending = df.index[
        df["sea_ice_x"].isna()
    ].to_numpy()

    print()
    print(f"Rows needing extraction: {len(pending)}")

    total_batches = int(
        np.ceil(len(pending) / BATCH_SIZE)
    )

    print(f"Batch size: {BATCH_SIZE}")
    print(f"Number of batches: {total_batches}")

    # --------------------------------------------------------
    # BATCH EXTRACTION
    # --------------------------------------------------------

    separator("SEA-ICE EXTRACTION")

    for batch_number, start in enumerate(
        range(0, len(pending), BATCH_SIZE),
        start=1
    ):

        end = min(
            start + BATCH_SIZE,
            len(pending)
        )

        batch_indices = pending[start:end]

        print()
        print(
            f"Batch {batch_number}/{total_batches} "
            f"| rows {start + 1}-{end}"
        )

        bx = iceberg_x[batch_indices]
        by = iceberg_y[batch_indices]

        # Nearest x/y grid cells
        x_indices = nearest_indices(
            x_grid,
            bx
        )

        y_indices = nearest_indices(
            y_grid,
            by
        )

        # Date indices
        batch_dates = (
            pd.to_datetime(
                df.loc[
                    batch_indices,
                    "init_date"
                ]
            )
            .dt.normalize()
        )

        time_indices = []

        for date in batch_dates:

            if date not in time_lookup:
                ds.close()

                raise ValueError(
                    f"Date {date.date()} "
                    f"not found in sea-ice dataset."
                )

            time_indices.append(
                time_lookup[date]
            )

        time_indices = np.asarray(
            time_indices,
            dtype=int
        )

        # ----------------------------------------------------
        # Vectorized point extraction
        # ----------------------------------------------------

        selected = sic.isel(
            time=xr.DataArray(
                time_indices,
                dims="points"
            ),
            y=xr.DataArray(
                y_indices,
                dims="points"
            ),
            x=xr.DataArray(
                x_indices,
                dims="points"
            ),
        )

        sic_values = (
            selected
            .load()
            .values
            .astype(np.float64)
            .reshape(-1)
        )

        selected_x = x_grid[x_indices]
        selected_y = y_grid[y_indices]

        # ----------------------------------------------------
        # Calculate approximate grid-cell distance
        #
        # Since both coordinates are in metres in the same
        # projection, Euclidean distance is suitable here as a
        # grid-selection diagnostic.
        # ----------------------------------------------------

        grid_distance_km = (
            np.sqrt(
                (bx - selected_x) ** 2
                + (by - selected_y) ** 2
            )
            / 1000.0
        )

        # ----------------------------------------------------
        # Save values
        # ----------------------------------------------------

        df.loc[
            batch_indices,
            "sea_ice_sic"
        ] = sic_values

        df.loc[
            batch_indices,
            "sea_ice_x"
        ] = selected_x

        df.loc[
            batch_indices,
            "sea_ice_y"
        ] = selected_y

        df.loc[
            batch_indices,
            "sea_ice_grid_distance_km"
        ] = grid_distance_km

        processed = (
            df["sea_ice_x"].notna()
        ).sum()

        valid_sic = (
            df["sea_ice_sic"].notna()
        ).sum()

        print("Batch complete.")

        print(
            f"Coordinates processed: "
            f"{processed}/{len(df)}"
        )

        print(
            f"Valid SIC so far: "
            f"{valid_sic}/{processed}"
        )

        # Save checkpoint after every batch
        df.to_csv(
            CHECKPOINT_FILE,
            index=False
        )

        print("Checkpoint saved.")

    ds.close()

    # ========================================================
    # QUALITY CHECK
    # ========================================================

    separator("FINAL SEA-ICE FEATURE QUALITY CHECK")

    total = len(df)

    missing_sic = int(
        df["sea_ice_sic"].isna().sum()
    )

    valid_sic = total - missing_sic

    print(f"\nTotal rows: {total}")

    print(
        f"Valid sea-ice SIC: "
        f"{valid_sic}"
    )

    print(
        f"Missing sea-ice SIC: "
        f"{missing_sic}"
    )

    print(
        f"Valid percentage: "
        f"{100 * valid_sic / total:.2f}%"
    )

    print("\nSIC statistics:")

    print(
        df["sea_ice_sic"].describe()
    )

    print("\nGrid-distance statistics (km):")

    print(
        df[
            "sea_ice_grid_distance_km"
        ].describe()
    )

    # --------------------------------------------------------
    # SIC ranges
    # --------------------------------------------------------

    finite_sic = df.loc[
        df["sea_ice_sic"].notna(),
        "sea_ice_sic"
    ]

    if len(finite_sic) > 0:

        print()
        print(
            f"Minimum finite SIC: "
            f"{finite_sic.min():.6f}"
        )

        print(
            f"Maximum finite SIC: "
            f"{finite_sic.max():.6f}"
        )

        # Safety diagnostic.
        # Our processed Member-1 SIC is expected to be 0-1.
        if finite_sic.max() > 1.01:

            print()
            print(
                "WARNING: SIC values exceed 1.0."
            )

            print(
                "Do NOT train yet. "
                "We need to inspect SIC scaling."
            )

    # --------------------------------------------------------
    # Missing by year
    # --------------------------------------------------------

    df["_year"] = (
        pd.to_datetime(df["init_date"])
        .dt.year
    )

    print("\nSamples by year:")

    print(
        df.groupby("_year").size()
    )

    print("\nMissing SIC by year:")

    print(
        df.groupby("_year")[
            "sea_ice_sic"
        ].apply(
            lambda x: x.isna().sum()
        )
    )

    print("\nTop icebergs with missing SIC:")

    missing_rows = df[
        df["sea_ice_sic"].isna()
    ]

    if len(missing_rows) > 0:

        print(
            missing_rows[
                "iceberg_id"
            ]
            .value_counts()
            .head(20)
        )

    else:
        print("None")

    # --------------------------------------------------------
    # Environment feature summary
    # --------------------------------------------------------

    separator("ENVIRONMENT FEATURE SUMMARY")

    environmental_columns = [
        "wind_u10",
        "wind_v10",
        "ocean_uo",
        "ocean_vo",
        "ocean_speed",
        "sea_ice_sic",
    ]

    for column in environmental_columns:

        if column in df.columns:

            missing = int(
                df[column].isna().sum()
            )

            print(
                f"{column:20s} "
                f"missing = {missing}"
            )

    # Remove temporary year
    df = df.drop(
        columns=["_year"]
    )

    # --------------------------------------------------------
    # Save final table
    # --------------------------------------------------------

    df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print()
    print("Final environmental feature table saved:")
    print(OUTPUT_FILE)

    # Only remove checkpoint when coordinate extraction itself
    # has finished. SIC NaNs may be legitimate masked cells.
    if df["sea_ice_x"].notna().all():

        if CHECKPOINT_FILE.exists():
            CHECKPOINT_FILE.unlink()

        print()
        print(
            "Extraction checkpoint removed."
        )

    separator("SEA-ICE EXTRACTION COMPLETE")


if __name__ == "__main__":
    main()