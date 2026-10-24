from pathlib import Path
import re
import urllib.request
from urllib.parse import urljoin

# ============================================================
# POLARGUARD — NSIDC ANTARCTIC SEA-ICE DOWNLOADER
# Dataset: NOAA/NSIDC CDR Sea Ice Concentration V6
# Region: Southern Hemisphere
# ============================================================

BASE_URL = "https://noaadata.apps.nsidc.org/NOAA/G02202_V6/south/daily/"

# 2024 is already downloaded, so skip it
YEARS = [2019, 2020, 2021, 2022, 2023, 2025]

OUT_DIR = Path("data/raw")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def get_nc_files(year):
    """
    Read the official NSIDC directory for a year
    and return all actual .nc filenames.
    """

    year_url = f"{BASE_URL}{year}/"

    print("\n" + "=" * 60)
    print(f"Reading NSIDC directory for {year}")
    print("=" * 60)

    try:
        with urllib.request.urlopen(year_url) as response:
            html = response.read().decode("utf-8")

        files = sorted(
            set(
                re.findall(
                    r'href="([^"]+\.nc)"',
                    html
                )
            )
        )

        return year_url, files

    except Exception as e:
        print(f"ERROR reading directory for {year}:")
        print(e)

        return year_url, []


total_downloaded = 0
total_skipped = 0
total_failed = 0


for year in YEARS:

    year_url, files = get_nc_files(year)

    print(f"Found {len(files)} NetCDF files for {year}.")

    if len(files) == 0:
        print(f"No files found for {year}. Skipping year.")
        continue

    for i, filename in enumerate(files, start=1):

        destination = OUT_DIR / filename

        # ----------------------------------------------------
        # Skip if file is already present
        # ----------------------------------------------------
        if destination.exists():

            print(
                f"[{year}] "
                f"[{i}/{len(files)}] "
                f"SKIP: {filename}"
            )

            total_skipped += 1
            continue

        file_url = urljoin(
            year_url,
            filename
        )

        # ----------------------------------------------------
        # Download
        # ----------------------------------------------------
        try:

            print(
                f"[{year}] "
                f"[{i}/{len(files)}] "
                f"Downloading: {filename}"
            )

            urllib.request.urlretrieve(
                file_url,
                destination
            )

            total_downloaded += 1

        except Exception as e:

            print(
                f"[{year}] "
                f"[{i}/{len(files)}] "
                f"FAILED: {filename}"
            )

            print("Reason:", e)

            total_failed += 1


# ============================================================
# FINAL SUMMARY
# ============================================================

print("\n" + "=" * 60)
print("POLARGUARD DOWNLOAD SUMMARY")
print("=" * 60)

all_files = sorted(
    OUT_DIR.glob("*.nc")
)

print(f"New files downloaded : {total_downloaded}")
print(f"Existing files skipped: {total_skipped}")
print(f"Failed downloads       : {total_failed}")
print(f"Total .nc files now    : {len(all_files)}")

print("\nSaved inside:")
print(OUT_DIR.resolve())

print("\nDownload process complete.")