import xarray as xr

INPUT_FILE = "data/processed/test_2025.nc"
OUTPUT_FILE = "data/processed/upload_test_4days.nc"

ds = xr.open_dataarray(INPUT_FILE)

# Four consecutive days
small = ds.sel(
    time=slice("2025-08-12", "2025-08-15")
)

print("Shape:", small.shape)
print("Dates:", small.time.values)

small.to_netcdf(OUTPUT_FILE)

print()
print("Created:")
print(OUTPUT_FILE)