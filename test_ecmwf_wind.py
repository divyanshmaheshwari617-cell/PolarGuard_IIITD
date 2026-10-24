from pathlib import Path
from ecmwf.opendata import Client


print("=" * 72)
print("POLARGUARD - ECMWF AUTOMATIC WIND DOWNLOAD TEST")
print("=" * 72)

output_dir = Path("data/environment_cache/ecmwf")
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / "latest_wind.grib2"

print()
print("Connecting to ECMWF Open Data...")
print("Requesting latest available 10 m wind...")
print()

client = Client(
    source="ecmwf",
    model="ifs",
    resol="0p25",
)

client.retrieve(
    type="fc",
    step=0,
    param=["10u", "10v"],
    target=str(output_file),
)

print()
print("=" * 72)
print("DOWNLOAD COMPLETE")
print("=" * 72)

print(f"Saved file : {output_file.resolve()}")
print(f"File exists: {output_file.exists()}")

if output_file.exists():
    size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"File size  : {size_mb:.2f} MB")

print()
print("ECMWF automatic wind download: READY")
print("=" * 72)