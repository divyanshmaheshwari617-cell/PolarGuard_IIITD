from pathlib import Path
import xarray as xr

DATA_FILE = Path("data/processed/sea_ice_2019_2025.nc")
OUT_DIR = Path("data/processed")

if not DATA_FILE.exists():
    raise FileNotFoundError("Combined dataset not found.")

print("=" * 70)
print("POLARGUARD — TRAIN / VALIDATION / TEST SPLIT")
print("=" * 70)

sic = xr.open_dataarray(DATA_FILE)

# ------------------------------------------------------------
# CHRONOLOGICAL SPLIT
# ------------------------------------------------------------

train = sic.sel(
    time=slice("2019-01-01", "2023-12-31")
)

validation = sic.sel(
    time=slice("2024-01-01", "2024-12-31")
)

test = sic.sel(
    time=slice("2025-01-01", "2025-12-31")
)

print("\nTRAIN")
print("Shape:", train.shape)
print("Start:", train.time.values[0])
print("End  :", train.time.values[-1])

print("\nVALIDATION")
print("Shape:", validation.shape)
print("Start:", validation.time.values[0])
print("End  :", validation.time.values[-1])

print("\nTEST")
print("Shape:", test.shape)
print("Start:", test.time.values[0])
print("End  :", test.time.values[-1])

# ------------------------------------------------------------
# SAVE
# ------------------------------------------------------------

train_file = OUT_DIR / "train_2019_2023.nc"
validation_file = OUT_DIR / "validation_2024.nc"
test_file = OUT_DIR / "test_2025.nc"

train.to_netcdf(train_file)
validation.to_netcdf(validation_file)
test.to_netcdf(test_file)

print("\n" + "=" * 70)
print("SPLIT COMPLETE")
print("=" * 70)

print("Train saved      :", train_file)
print("Validation saved :", validation_file)
print("Test saved       :", test_file)