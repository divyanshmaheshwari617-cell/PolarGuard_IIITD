from pathlib import Path
import re
import urllib.request
from urllib.parse import urljoin

BASE_URL = "https://noaadata.apps.nsidc.org/NOAA/G02202_V6/south/aggregate/"

YEARS = [2019, 2020, 2021, 2022, 2023, 2024, 2025]

OUT_DIR = Path("data/aggregate")
OUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("POLARGUARD — YEARLY SEA-ICE DOWNLOADER")
print("=" * 60)

print("\nReading official NSIDC aggregate directory...")

with urllib.request.urlopen(BASE_URL) as response:
    html = response.read().decode("utf-8")

# Get every .nc file listed in the directory
all_files = sorted(
    set(re.findall(r'href="([^"]+\.nc)"', html))
)

print(f"Total aggregate NetCDF files found: {len(all_files)}")

selected_files = []

for filename in all_files:
    for year in YEARS:
        # Yearly aggregate filenames contain start/end dates
        # such as YYYY0101-YYYY1231
        if str(year) in filename:
            selected_files.append(filename)
            break

selected_files = sorted(set(selected_files))

print("\nFiles selected for 2019–2025:")

for filename in selected_files:
    print(filename)

print(f"\nSelected: {len(selected_files)} files")

for i, filename in enumerate(selected_files, start=1):

    destination = OUT_DIR / filename

    if destination.exists():
        print(
            f"[{i}/{len(selected_files)}] "
            f"SKIP: {filename}"
        )
        continue

    url = urljoin(BASE_URL, filename)

    try:
        print(
            f"[{i}/{len(selected_files)}] "
            f"Downloading: {filename}"
        )

        urllib.request.urlretrieve(
            url,
            destination
        )

        print("   Done")

    except Exception as e:
        print(f"   FAILED: {e}")

print("\n" + "=" * 60)
print("DOWNLOAD FINISHED")
print("=" * 60)

files = list(OUT_DIR.glob("*.nc"))

print(f"Files downloaded: {len(files)}")
print("Location:", OUT_DIR.resolve())
