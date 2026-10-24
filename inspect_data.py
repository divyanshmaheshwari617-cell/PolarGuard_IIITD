from pathlib import Path
import xarray as xr
import matplotlib.pyplot as plt
import numpy as np

files = sorted(Path("data/raw").glob("*.nc"))

if not files:
    raise FileNotFoundError("No .nc files found in data/raw")

file_path = files[0]

print("Opening:", file_path)

ds = xr.open_dataset(file_path)

sic = ds["cdr_seaice_conc"].isel(time=0)

print("\nSea-Ice Concentration Variable")
print(sic)

print("\nStatistics")
print("Minimum:", float(sic.min(skipna=True)))
print("Maximum:", float(sic.max(skipna=True)))
print("Mean:", float(sic.mean(skipna=True)))
print("NaN count:", int(np.isnan(sic.values).sum()))

plt.figure(figsize=(8, 8))

sic.plot(
    x="x",
    y="y",
    vmin=0,
    vmax=1,
    cmap="Blues"
)

plt.title("Antarctic Sea-Ice Concentration — 2024-01-01")
plt.xlabel("X coordinate (meters)")
plt.ylabel("Y coordinate (meters)")

plt.tight_layout()
plt.show()