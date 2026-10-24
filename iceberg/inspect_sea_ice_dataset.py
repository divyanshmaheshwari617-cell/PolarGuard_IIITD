from pathlib import Path
import xarray as xr

BASE = Path(__file__).resolve().parent.parent

FILE = (
    BASE
    / "data"
    / "processed"
    / "sea_ice_2019_2025.nc"
)

print("=" * 75)
print("POLARGUARD SEA-ICE DATASET INSPECTION")
print("=" * 75)

print("\nFile:")
print(FILE)

ds = xr.open_dataset(FILE)

print("\nDATASET:")
print(ds)

print("\nDIMENSIONS:")
for name, size in ds.sizes.items():
    print(f"{name}: {size}")

print("\nCOORDINATES:")
for name in ds.coords:
    print()
    print(name)
    print(ds[name])

print("\nDATA VARIABLES:")
for name in ds.data_vars:
    print()
    print(f"Variable: {name}")
    print(ds[name])

print("\nATTRIBUTES:")
for key, value in ds.attrs.items():
    print(f"{key}: {value}")

ds.close()

print("\n" + "=" * 75)
print("INSPECTION COMPLETE")
print("=" * 75)