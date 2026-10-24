from pathlib import Path
import xarray as xr

DATA_DIR = Path("data/aggregate")
OUT_DIR = Path("data/processed")

OUT_DIR.mkdir(parents=True, exist_ok=True)

files = sorted(DATA_DIR.glob("*.nc"))

if not files:
    raise FileNotFoundError("No aggregate .nc files found.")

print("=" * 70)
print("POLARGUARD — FULL SEA-ICE PREPROCESSING")
print("=" * 70)

print(f"\nAggregate files found: {len(files)}")

datasets = []

for i, file_path in enumerate(files, start=1):

    print(
        f"[{i}/{len(files)}] "
        f"Reading {file_path.name}"
    )

    ds = xr.open_dataset(file_path)

    # Extract Sea-Ice Concentration
    sic = ds["cdr_seaice_conc"]

    # Keep only physically valid SIC
    sic = sic.where(
        (sic >= 0.0) &
        (sic <= 1.0)
    )

    # Load before closing source file
    sic = sic.load()

    datasets.append(sic)

    ds.close()


print("\nCombining all years...")

sea_ice = xr.concat(
    datasets,
    dim="time"
)

# Ensure chronological order
sea_ice = sea_ice.sortby("time")

sea_ice.name = "sea_ice_concentration"

print("\n" + "=" * 70)
print("COMBINED DATASET")
print("=" * 70)

print("Shape:", sea_ice.shape)

print(
    "Start:",
    sea_ice.time.values[0]
)

print(
    "End:",
    sea_ice.time.values[-1]
)

print(
    "Total days:",
    sea_ice.sizes["time"]
)

print("\nStatistics:")

print(
    "Minimum:",
    float(sea_ice.min(skipna=True))
)

print(
    "Maximum:",
    float(sea_ice.max(skipna=True))
)

print(
    "Mean:",
    float(sea_ice.mean(skipna=True))
)


# ------------------------------------------------------------
# CHECK FOR DUPLICATE DATES
# ------------------------------------------------------------

time_index = sea_ice.get_index("time")

duplicates = time_index.duplicated().sum()

print(
    "\nDuplicate dates:",
    duplicates
)


# ------------------------------------------------------------
# CHECK FOR MISSING DAYS
# ------------------------------------------------------------

expected_time = xr.date_range(
    start=str(time_index[0].date()),
    end=str(time_index[-1].date()),
    freq="D"
)

missing_days = len(expected_time) - len(time_index)

print(
    "Expected days:",
    len(expected_time)
)

print(
    "Actual days:",
    len(time_index)
)

print(
    "Missing days:",
    missing_days
)


# ------------------------------------------------------------
# SAVE
# ------------------------------------------------------------

output_file = (
    OUT_DIR /
    "sea_ice_2019_2025.nc"
)

print("\nSaving processed dataset...")

sea_ice.to_netcdf(
    output_file
)

print("\n" + "=" * 70)
print("PREPROCESSING COMPLETE")
print("=" * 70)

print(
    "Saved:",
    output_file
)