from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import numpy as np
import requests
import xarray as xr


# ============================================================
# POLARGUARD
# NEAR-REAL-TIME ANTARCTIC SATELLITE DATA SERVICE
# ============================================================
#
# Dataset:
# G10016 Version 4
# Near-Real-Time NOAA/NSIDC Climate Data Record
# of Passive Microwave Sea Ice Concentration
#
# IMPORTANT:
# - This is NEAR-REAL-TIME satellite-derived data.
# - It is NOT a literal live satellite stream.
# - Southern Hemisphere only.
# - No model retraining happens here.
# - Invalid/masked SIC remains NaN.
# ============================================================


DATASET_ID = "G10016"
DATASET_VERSION = "4"

BASE_URL = (
    "https://noaadata.apps.nsidc.org/"
    "NOAA/G10016_V4/south/daily/"
)

CACHE_DIR = Path(
    "data/satellite_cache/g10016_v4"
)

REFERENCE_GRID_FILE = Path(
    "data/processed/sea_ice_2019_2025.nc"
)

EXPECTED_SHAPE = (332, 316)

REQUEST_TIMEOUT = 60


# Example:
# sic_pss25_20260901_am2_icdr_v04r00.nc
FILE_PATTERN = re.compile(
    r"^sic_pss25_(\d{8})_.*_icdr_v04r\d+\.nc$",
    re.IGNORECASE,
)


# ============================================================
# GENERAL HELPERS
# ============================================================

def _today_utc():
    return datetime.now(
        timezone.utc
    ).date()


def _http_get_text(url):
    """
    Download a directory-listing page.
    """

    response = requests.get(
        url,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    return response.text


# ============================================================
# READ NSIDC DIRECTORY
# ============================================================

def list_year_files(year):
    """
    Read the official NSIDC HTTPS directory for one year
    and return available Antarctic daily NetCDF files.
    """

    year = int(year)

    year_url = urljoin(
        BASE_URL,
        f"{year}/",
    )

    print()
    print(
        f"Checking NSIDC archive: {year_url}"
    )

    try:
        html = _http_get_text(
            year_url
        )

    except requests.HTTPError as exc:

        print(
            f"Could not access {year}: {exc}"
        )

        return []

    # Simple nginx directory listings contain href="filename".
    hrefs = re.findall(
        r'href=["\']([^"\']+)["\']',
        html,
        flags=re.IGNORECASE,
    )

    files = []

    for href in hrefs:

        filename = href.split("/")[-1]

        match = FILE_PATTERN.match(
            filename
        )

        if match is None:
            continue

        try:
            observation_date = (
                datetime.strptime(
                    match.group(1),
                    "%Y%m%d",
                ).date()
            )

        except ValueError:
            continue

        files.append(
            {
                "date": observation_date,
                "filename": filename,
                "url": urljoin(
                    year_url,
                    filename,
                ),
            }
        )

    # Remove duplicate filenames if directory HTML repeats links.
    unique = {}

    for item in files:
        unique[item["filename"]] = item

    files = sorted(
        unique.values(),
        key=lambda x: x["date"],
    )

    print(
        f"Found {len(files)} Antarctic "
        f"daily files for {year}."
    )

    return files


# ============================================================
# FIND RECENT FILES
# ============================================================

def discover_recent_files():
    """
    Inspect current and previous year.

    Looking at previous year also makes the service work
    safely around January.
    """

    today = _today_utc()

    years = [
        today.year - 1,
        today.year,
    ]

    all_files = []

    for year in years:

        all_files.extend(
            list_year_files(year)
        )

    if not all_files:

        raise RuntimeError(
            "No Antarctic G10016 V4 daily NetCDF "
            "files were found in the NSIDC archive."
        )

    # If more than one revision/file exists for a date,
    # keep the lexicographically latest filename.
    by_date = {}

    for item in all_files:

        date = item["date"]

        if date not in by_date:

            by_date[date] = item

        else:

            if (
                item["filename"]
                > by_date[date]["filename"]
            ):
                by_date[date] = item

    files = sorted(
        by_date.values(),
        key=lambda x: x["date"],
    )

    print()
    print(
        "Latest Antarctic observation available:",
        files[-1]["date"],
    )

    return files


# ============================================================
# FIND FOUR CONSECUTIVE DAYS
# ============================================================

def find_latest_four_consecutive(files):
    """
    Find latest sequence:

        t-3
        t-2
        t-1
        t/current

    All four observations must exist.
    """

    by_date = {
        item["date"]: item
        for item in files
    }

    available_dates = sorted(
        by_date.keys(),
        reverse=True,
    )

    for current_date in available_dates:

        required_dates = [
            current_date
            - timedelta(days=3),

            current_date
            - timedelta(days=2),

            current_date
            - timedelta(days=1),

            current_date,
        ]

        if all(
            date in by_date
            for date in required_dates
        ):

            selected = [
                by_date[date]
                for date in required_dates
            ]

            print()
            print(
                "Latest four consecutive "
                "Antarctic observations:"
            )

            for item in selected:

                print(
                    f"  {item['date']}  "
                    f"{item['filename']}"
                )

            return selected

    raise RuntimeError(
        "Could not find four consecutive "
        "G10016 Antarctic daily observations."
    )


# ============================================================
# DOWNLOAD
# ============================================================

def download_file(
    item,
    cache_dir=CACHE_DIR,
):
    """
    Download one NetCDF file.

    Existing cached files are reused.
    """

    cache_dir = Path(
        cache_dir
    )

    cache_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination = (
        cache_dir
        / item["filename"]
    )

    if (
        destination.exists()
        and destination.stat().st_size > 0
    ):

        print(
            "Using cached:",
            destination,
        )

        return destination

    print(
        "Downloading:",
        item["filename"],
    )

    temporary = destination.with_suffix(
        destination.suffix + ".part"
    )

    with requests.get(
        item["url"],
        stream=True,
        timeout=REQUEST_TIMEOUT,
    ) as response:

        response.raise_for_status()

        with open(
            temporary,
            "wb",
        ) as file:

            for chunk in response.iter_content(
                chunk_size=1024 * 1024
            ):

                if chunk:
                    file.write(chunk)

    if (
        not temporary.exists()
        or temporary.stat().st_size == 0
    ):

        raise RuntimeError(
            f"Download produced an empty file: "
            f"{item['filename']}"
        )

    temporary.replace(
        destination
    )

    return destination


def download_selected_files(
    selected,
    cache_dir=CACHE_DIR,
):

    paths = []

    for item in selected:

        path = download_file(
            item,
            cache_dir=cache_dir,
        )

        paths.append(path)

    return paths


# ============================================================
# NETCDF SIC READER
# ============================================================

def _find_sic_variable(ds):
    """
    Select the sea-ice concentration variable.
    """

    preferred_names = [
        "cdr_seaice_conc",
        "seaice_conc_cdr",
        "sea_ice_concentration",
        "sic",
    ]

    for name in preferred_names:

        if name in ds.data_vars:
            return ds[name]

    # Helpful error for debugging if NSIDC changes format.
    variables = list(
        ds.data_vars
    )

    raise ValueError(
        "Could not find the sea-ice concentration "
        "variable. NetCDF variables found: "
        f"{variables}"
    )


def load_daily_sic(file_path):
    """
    Load and standardize one G10016 Antarctic daily map.

    Output:
        sic : (332, 316), float32, range 0..1
        x   : (316,)
        y   : (332,)
    """

    with xr.open_dataset(
        file_path
    ) as ds:

        da = _find_sic_variable(
            ds
        )

        da = da.squeeze(
            drop=True
        )

        if (
            "y" not in da.dims
            or "x" not in da.dims
        ):

            raise ValueError(
                f"Unexpected SIC dimensions in "
                f"{file_path}: {da.dims}"
            )

        da = da.transpose(
            "y",
            "x",
        )

        sic = np.asarray(
            da.values,
            dtype=np.float32,
        )

        if (
            "x" not in ds.coords
            or "y" not in ds.coords
        ):

            raise ValueError(
                "NetCDF file does not contain "
                "x and y coordinates."
            )

        x = np.asarray(
            ds["x"].values,
            dtype=np.float64,
        )

        y = np.asarray(
            ds["y"].values,
            dtype=np.float64,
        )

    # --------------------------------------------------------
    # SIC normalization
    # --------------------------------------------------------

    finite = np.isfinite(
        sic
    )

    if not finite.any():

        raise ValueError(
            f"No valid SIC values found in {file_path}"
        )

    maximum = float(
        np.nanmax(sic)
    )

    # Normally xarray applies NetCDF scale_factor
    # automatically. This is only a safety fallback.
    if (
        maximum > 1.5
        and maximum <= 100.0
    ):

        sic = (
            sic / 100.0
        ).astype(
            np.float32
        )

    # IMPORTANT:
    # ocean/missing/flag values outside valid SIC
    # must remain masked, never changed to zero.
    invalid = (
        (~np.isfinite(sic))
        | (sic < 0.0)
        | (sic > 1.0)
    )

    sic = sic.astype(
        np.float32
    )

    sic[invalid] = np.nan

    # --------------------------------------------------------
    # Shape validation
    # --------------------------------------------------------

    if sic.shape != EXPECTED_SHAPE:

        raise ValueError(
            f"Unexpected satellite grid shape "
            f"{sic.shape}. PolarGuard expects "
            f"{EXPECTED_SHAPE}."
        )

    if x.shape != (
        EXPECTED_SHAPE[1],
    ):

        raise ValueError(
            f"Unexpected X coordinate shape: "
            f"{x.shape}"
        )

    if y.shape != (
        EXPECTED_SHAPE[0],
    ):

        raise ValueError(
            f"Unexpected Y coordinate shape: "
            f"{y.shape}"
        )

    return sic, x, y


# ============================================================
# CHECK ALL FOUR DAYS USE IDENTICAL GRID
# ============================================================

def validate_same_grid(
    reference_x,
    reference_y,
    x,
    y,
):
    """
    Reject grid differences.

    We deliberately do NOT silently interpolate or
    rearrange satellite inputs.
    """

    if reference_x.shape != x.shape:

        raise ValueError(
            "Satellite X-coordinate shapes differ."
        )

    if reference_y.shape != y.shape:

        raise ValueError(
            "Satellite Y-coordinate shapes differ."
        )

    if not np.allclose(
        reference_x,
        x,
        rtol=0.0,
        atol=1e-6,
        equal_nan=True,
    ):

        raise ValueError(
            "Satellite X coordinates differ "
            "between input days."
        )

    if not np.allclose(
        reference_y,
        y,
        rtol=0.0,
        atol=1e-6,
        equal_nan=True,
    ):

        raise ValueError(
            "Satellite Y coordinates differ "
            "between input days."
        )


# ============================================================
# COMPARE WITH FROZEN MEMBER-1 TRAINING GRID
# ============================================================

def validate_against_member1_grid(
    satellite_x,
    satellite_y,
    reference_file=REFERENCE_GRID_FILE,
):
    """
    Ensure G10016 grid coordinates are compatible
    with the grid used by the frozen Member-1 model.

    NO silent interpolation is performed.
    """

    reference_file = Path(
        reference_file
    )

    if not reference_file.exists():

        print()
        print(
            "WARNING: Member-1 reference NetCDF "
            "was not found:"
        )

        print(
            " ",
            reference_file,
        )

        print(
            "Satellite internal grid validation "
            "will continue, but training-grid "
            "comparison cannot be performed."
        )

        return False

    with xr.open_dataset(
        reference_file
    ) as ds:

        if (
            "x" not in ds.coords
            or "y" not in ds.coords
        ):

            raise ValueError(
                "Member-1 reference file does not "
                "contain x/y coordinates."
            )

        reference_x = np.asarray(
            ds["x"].values,
            dtype=np.float64,
        )

        reference_y = np.asarray(
            ds["y"].values,
            dtype=np.float64,
        )

    if reference_x.shape != satellite_x.shape:

        raise ValueError(
            "G10016 X grid does not match "
            "Member-1 training grid shape."
        )

    if reference_y.shape != satellite_y.shape:

        raise ValueError(
            "G10016 Y grid does not match "
            "Member-1 training grid shape."
        )

    if not np.allclose(
        reference_x,
        satellite_x,
        rtol=0.0,
        atol=1e-6,
        equal_nan=True,
    ):

        max_difference = float(
            np.nanmax(
                np.abs(
                    reference_x
                    - satellite_x
                )
            )
        )

        raise ValueError(
            "G10016 X coordinates do not match "
            "the frozen Member-1 grid. "
            f"Maximum difference: {max_difference}"
        )

    if not np.allclose(
        reference_y,
        satellite_y,
        rtol=0.0,
        atol=1e-6,
        equal_nan=True,
    ):

        max_difference = float(
            np.nanmax(
                np.abs(
                    reference_y
                    - satellite_y
                )
            )
        )

        raise ValueError(
            "G10016 Y coordinates do not match "
            "the frozen Member-1 grid. "
            f"Maximum difference: {max_difference}"
        )

    print()
    print(
        "Member-1 grid compatibility: PASSED"
    )

    return True


# ============================================================
# MAIN PUBLIC FUNCTION
# ============================================================

def load_latest_satellite_input(
    cache_dir=CACHE_DIR,
    validate_member1_grid=True,
):
    """
    Load the latest four consecutive Antarctic SIC maps
    containing valid observations.

    If a downloaded daily file contains no valid SIC values,
    exclude that date and retry with the next latest
    consecutive four-day window.

    Returns the input grids, dates, source files, and metadata.
    """

    print()
    print("=" * 70)
    print(
        "POLARGUARD NEAR-REAL-TIME "
        "ANTARCTIC SATELLITE INGESTION"
    )
    print("=" * 70)

    remaining_files = list(
        discover_recent_files()
    )

    while True:
        selected = find_latest_four_consecutive(
            remaining_files
        )

        local_paths = download_selected_files(
            selected,
            cache_dir=cache_dir,
        )

        maps = []
        reference_x = None
        reference_y = None
        invalid_date = None

        for index, path in enumerate(local_paths):
            try:
                sic, x, y = load_daily_sic(path)

            except ValueError as exc:
                if "No valid SIC values found" not in str(exc):
                    raise

                invalid_date = selected[index]["date"]

                print(
                    f"Skipping {invalid_date}: "
                    "the source file contains no valid SIC values."
                )
                break

            if index == 0:
                reference_x = x
                reference_y = y
            else:
                validate_same_grid(
                    reference_x,
                    reference_y,
                    x,
                    y,
                )

            maps.append(sic)

        if invalid_date is None:
            break

        previous_count = len(remaining_files)

        remaining_files = [
            item
            for item in remaining_files
            if item["date"] != invalid_date
        ]

        if len(remaining_files) == previous_count:
            raise RuntimeError(
                f"Could not exclude invalid SIC date "
                f"{invalid_date} and find another "
                "four-day candidate window."
            )

    if len(maps) != 4:
        raise RuntimeError(
            "PolarGuard requires exactly four "
            "consecutive SIC observations."
        )

    # Chronological order:
    # maps[0] = t-3
    # maps[1] = t-2
    # maps[2] = t-1
    # maps[3] = current

    lag3 = maps[0]
    lag2 = maps[1]
    lag1 = maps[2]
    current = maps[3]

    current_date_python = selected[-1]["date"]

    current_date = np.datetime64(
        current_date_python,
        "D",
    )

    if validate_member1_grid:
        grid_match = validate_against_member1_grid(
            reference_x,
            reference_y,
        )
    else:
        grid_match = None

    today = _today_utc()

    provider_lag_days = (
        today - current_date_python
    ).days

    valid_cells = int(
        np.isfinite(current).sum()
    )

    mean_sic = float(
        np.nanmean(current)
    )

    bundle = {
        "current": current,
        "lag1": lag1,
        "lag2": lag2,
        "lag3": lag3,

        "x": reference_x,
        "y": reference_y,

        # The frozen Member 1 service expects numpy.datetime64.
        "date": current_date,

        "dates": [
            np.datetime64(item["date"], "D")
            for item in selected
        ],

        "files": [
            str(path)
            for path in local_paths
        ],

        "source_urls": [
            item["url"]
            for item in selected
        ],

        "provider": "NOAA / NSIDC",
        "dataset_id": DATASET_ID,
        "dataset_version": DATASET_VERSION,
        "product_type": (
            "Near-Real-Time Satellite-Derived "
            "Sea-Ice Concentration"
        ),
        "hemisphere": "South",
        "crs": "EPSG:3412",
        "grid_shape": EXPECTED_SHAPE,
        "grid_matches_member1": grid_match,
        "provider_lag_days": provider_lag_days,
        "valid_current_cells": valid_cells,
        "mean_current_sic": mean_sic,
    }

    return bundle


# ============================================================
# COMMAND-LINE TEST
# ============================================================

if __name__ == "__main__":

    try:

        bundle = (
            load_latest_satellite_input()
        )

        print()
        print("=" * 70)
        print(
            "SATELLITE INGESTION TEST: SUCCESS"
        )
        print("=" * 70)

        print(
            "Provider:",
            bundle["provider"],
        )

        print(
            "Dataset:",
            bundle["dataset_id"],
            "Version",
            bundle["dataset_version"],
        )

        print(
            "Product:",
            bundle["product_type"],
        )

        print(
            "Initialization date:",
            bundle["date"],
        )

        print(
            "Four input dates:",
            bundle["dates"],
        )

        print(
            "Grid shape:",
            bundle["current"].shape,
        )

        print(
            "CRS:",
            bundle["crs"],
        )

        print(
            "Member-1 grid match:",
            bundle[
                "grid_matches_member1"
            ],
        )

        print(
            "Provider lag:",
            bundle[
                "provider_lag_days"
            ],
            "day(s)",
        )

        print(
            "Valid current cells:",
            bundle[
                "valid_current_cells"
            ],
        )

        print(
            "Mean current SIC:",
            round(
                bundle[
                    "mean_current_sic"
                ],
                6,
            ),
        )

        print()
        print(
            "CURRENT shape:",
            bundle[
                "current"
            ].shape,
        )

        print(
            "LAG1 shape:",
            bundle[
                "lag1"
            ].shape,
        )

        print(
            "LAG2 shape:",
            bundle[
                "lag2"
            ].shape,
        )

        print(
            "LAG3 shape:",
            bundle[
                "lag3"
            ].shape,
        )

        print()
        print(
            "READY FOR FROZEN "
            "POLARGUARD MEMBER-1 MODEL"
        )

    except Exception as exc:

        print()
        print("=" * 70)
        print(
            "SATELLITE INGESTION TEST: FAILED"
        )
        print("=" * 70)

        print(
            type(exc).__name__ + ":",
            exc,
        )

        raise