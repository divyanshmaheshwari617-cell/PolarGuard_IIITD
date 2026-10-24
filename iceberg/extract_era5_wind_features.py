import pandas as pd
import xarray as xr
import numpy as np
from pathlib import Path


# ============================================================
# CONFIG
# ============================================================

BATCH_SIZE = 1000

PROJECT_ROOT = Path(__file__).resolve().parent.parent

FEATURE_FILE = (
    PROJECT_ROOT
    / "iceberg"
    / "data"
    / "processed"
    / "iceberg_trajectory_features_2019_2025.csv"
)

ERA5_FILE_1 = (
    PROJECT_ROOT
    / "iceberg"
    / "data"
    / "environment"
    / "era5_environment.nc"
)

ERA5_FILE_2 = (
    PROJECT_ROOT
    / "iceberg"
    / "data"
    / "environment"
    / "era5_2023_2025.nc"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "iceberg"
    / "data"
    / "processed"
    / "iceberg_features_with_wind_2019_2025.csv"
)

CHECKPOINT_FILE = (
    PROJECT_ROOT
    / "iceberg"
    / "data"
    / "processed"
    / "era5_wind_checkpoint.csv"
)


print("=" * 75)
print("POLARGUARD - BATCHED ERA5 WIND FEATURE EXTRACTION")
print("=" * 75)


# ============================================================
# CHECK FILES
# ============================================================

for path in [FEATURE_FILE, ERA5_FILE_1, ERA5_FILE_2]:
    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found:\n{path}"
        )


# ============================================================
# LOAD OR RESUME DATA
# ============================================================

if CHECKPOINT_FILE.exists():

    print("\nCheckpoint found.")
    print("Resuming previous extraction...")

    df = pd.read_csv(CHECKPOINT_FILE)

else:

    print("\nNo checkpoint found.")
    print("Starting fresh extraction...")

    df = pd.read_csv(FEATURE_FILE)

    df["wind_u10"] = np.nan
    df["wind_v10"] = np.nan


df["init_date"] = pd.to_datetime(df["init_date"])

df = df.sort_values(
    ["init_date", "iceberg_id"]
).reset_index(drop=True)


print("\nTotal samples:", len(df))

print(
    "Date range:",
    df["init_date"].min(),
    "to",
    df["init_date"].max()
)


# ============================================================
# OPEN ERA5
# ============================================================

print("\nOpening ERA5 2019-2022...")

ds1 = xr.open_dataset(ERA5_FILE_1)

print(
    "ERA5 #1:",
    ds1.valid_time.values[0],
    "to",
    ds1.valid_time.values[-1]
)


print("\nOpening ERA5 2023-2025...")

ds2 = xr.open_dataset(ERA5_FILE_2)

print(
    "ERA5 #2:",
    ds2.valid_time.values[0],
    "to",
    ds2.valid_time.values[-1]
)


# ============================================================
# VALIDATE DATASETS
# ============================================================

for name, ds in [
    ("ERA5 2019-2022", ds1),
    ("ERA5 2023-2025", ds2),
]:

    for variable in [
        "u10",
        "v10",
        "valid_time",
        "latitude",
        "longitude",
    ]:

        if (
            variable not in ds.data_vars
            and variable not in ds.coords
        ):
            raise ValueError(
                f"{name}: missing {variable}"
            )


# ============================================================
# BATCH EXTRACTION FUNCTION
# ============================================================

def extract_batches(
    dataset,
    mask,
    label
):

    global df

    print("\n" + "=" * 75)
    print(label)
    print("=" * 75)

    indices = df.index[mask].to_numpy()

    # Only process rows where wind has not already been extracted
    missing_mask = (
        df.loc[indices, "wind_u10"].isna()
        |
        df.loc[indices, "wind_v10"].isna()
    )

    remaining_indices = indices[
        missing_mask.to_numpy()
    ]

    total_remaining = len(
        remaining_indices
    )

    print(
        "Rows still needing wind:",
        total_remaining
    )

    if total_remaining == 0:

        print(
            "This section is already complete."
        )

        return


    number_of_batches = int(
        np.ceil(
            total_remaining
            /
            BATCH_SIZE
        )
    )


    print(
        "Batch size:",
        BATCH_SIZE
    )

    print(
        "Number of batches:",
        number_of_batches
    )


    for batch_number in range(
        number_of_batches
    ):

        start = (
            batch_number
            *
            BATCH_SIZE
        )

        end = min(
            start + BATCH_SIZE,
            total_remaining
        )

        batch_indices = (
            remaining_indices[
                start:end
            ]
        )

        batch = df.loc[
            batch_indices
        ]


        print(
            f"\nBatch "
            f"{batch_number + 1}"
            f"/{number_of_batches}"
            f" | rows {start + 1}-{end}"
        )


        # ----------------------------------------------------
        # Query time
        #
        # BYU provides daily observation date,
        # not reliable exact observation hour.
        #
        # Use 12 UTC consistently.
        # ----------------------------------------------------

        query_times = (
            batch["init_date"]
            +
            pd.Timedelta(hours=12)
        ).values.astype(
            "datetime64[ns]"
        )


        query_latitudes = (
            batch[
                "current_latitude"
            ]
            .astype(float)
            .values
        )


        query_longitudes = (
            batch[
                "current_longitude"
            ]
            .astype(float)
            .values
        )


        # Normalize to [-180, 180)
        query_longitudes = (
            (
                query_longitudes
                +
                180.0
            )
            %
            360.0
        ) - 180.0


        # ----------------------------------------------------
        # ERA5 nearest-neighbor lookup
        # ----------------------------------------------------

        selected = dataset[
            ["u10", "v10"]
        ].sel(

            valid_time=xr.DataArray(
                query_times,
                dims="points"
            ),

            latitude=xr.DataArray(
                query_latitudes,
                dims="points"
            ),

            longitude=xr.DataArray(
                query_longitudes,
                dims="points"
            ),

            method="nearest",
        )


        u_values = (
            selected["u10"]
            .values
            .astype(np.float32)
        )


        v_values = (
            selected["v10"]
            .values
            .astype(np.float32)
        )


        df.loc[
            batch_indices,
            "wind_u10"
        ] = u_values


        df.loc[
            batch_indices,
            "wind_v10"
        ] = v_values


        # ----------------------------------------------------
        # SAVE CHECKPOINT AFTER EVERY BATCH
        # ----------------------------------------------------

        df.to_csv(
            CHECKPOINT_FILE,
            index=False
        )


        completed_total = int(
            df[
                [
                    "wind_u10",
                    "wind_v10",
                ]
            ]
            .notna()
            .all(axis=1)
            .sum()
        )


        print(
            "Batch complete."
        )

        print(
            "Overall completed:",
            completed_total,
            "/",
            len(df)
        )

        print(
            "Checkpoint saved."
        )


# ============================================================
# YEAR MASKS
# ============================================================

mask_2019_2022 = (
    (df["init_date"] >= "2019-01-01")
    &
    (df["init_date"] <= "2022-12-31")
)


mask_2023_2025 = (
    (df["init_date"] >= "2023-01-01")
    &
    (df["init_date"] <= "2025-12-31")
)


print(
    "\n2019-2022 samples:",
    int(mask_2019_2022.sum())
)

print(
    "2023-2025 samples:",
    int(mask_2023_2025.sum())
)


# ============================================================
# EXTRACT 2019-2022
# ============================================================

extract_batches(
    ds1,
    mask_2019_2022,
    "ERA5 EXTRACTION 2019-2022"
)


# ============================================================
# EXTRACT 2023-2025
# ============================================================

extract_batches(
    ds2,
    mask_2023_2025,
    "ERA5 EXTRACTION 2023-2025"
)


# ============================================================
# WIND SPEED
# ============================================================

df["wind_speed_10m"] = np.sqrt(
    df["wind_u10"] ** 2
    +
    df["wind_v10"] ** 2
).astype(np.float32)


# ============================================================
# QUALITY CHECK
# ============================================================

print("\n" + "=" * 75)
print("FINAL WIND FEATURE QUALITY CHECK")
print("=" * 75)


missing_u = int(
    df["wind_u10"]
    .isna()
    .sum()
)

missing_v = int(
    df["wind_v10"]
    .isna()
    .sum()
)


print(
    "\nTotal samples:",
    len(df)
)

print(
    "Missing u10:",
    missing_u
)

print(
    "Missing v10:",
    missing_v
)


print(
    "\nu10 statistics:"
)

print(
    df["wind_u10"]
    .describe()
)


print(
    "\nv10 statistics:"
)

print(
    df["wind_v10"]
    .describe()
)


print(
    "\nWind speed statistics:"
)

print(
    df["wind_speed_10m"]
    .describe()
)


# ============================================================
# YEAR CHECK
# ============================================================

df["_year"] = (
    df["init_date"]
    .dt.year
)


print(
    "\nSamples by year:"
)

print(
    df.groupby("_year")
    .size()
)


print(
    "\nMissing wind by year:"
)

print(
    df.groupby("_year")[
        [
            "wind_u10",
            "wind_v10",
        ]
    ]
    .apply(
        lambda x:
        x.isna().sum()
    )
)


df.drop(
    columns=["_year"],
    inplace=True
)


# ============================================================
# SAVE FINAL FILE
# ============================================================

df.to_csv(
    OUTPUT_FILE,
    index=False
)


print(
    "\nFinal dataset saved:"
)

print(
    OUTPUT_FILE
)


# ============================================================
# REMOVE CHECKPOINT ONLY AFTER SUCCESS
# ============================================================

if (
    missing_u == 0
    and
    missing_v == 0
):

    if CHECKPOINT_FILE.exists():

        CHECKPOINT_FILE.unlink()

        print(
            "\nCheckpoint removed "
            "because extraction completed successfully."
        )


ds1.close()
ds2.close()


print("\n" + "=" * 75)
print("ERA5 WIND EXTRACTION COMPLETE")
print("=" * 75)