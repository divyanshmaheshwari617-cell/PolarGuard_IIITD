from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import copernicusmarine
import numpy as np
import xarray as xr


# ============================================================
# PolarGuard - Copernicus Marine Ocean Current Bridge
# ============================================================
#
# Purpose:
#   Retrieve real operational near-surface ocean-current data
#   from Copernicus Marine and return a machine-readable JSON
#   response for the main PolarGuard Python 3.14 application.
#
# This bridge runs inside the Python 3.13 venv_grib environment.
#
# IMPORTANT:
#   - No synthetic ocean-current values are generated.
#   - uo / vo are taken directly from Copernicus Marine.
#   - The grid point nearest the requested iceberg position
#     is selected.
#   - The time nearest the current UTC time is selected from
#     the operational analysis/forecast product.
# ============================================================


DATASET_ID = (
    "cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i"
)

# Small geographical subset around requested position.
BOX_HALF_SIZE_DEG = 0.20

# Copernicus near-surface level starts at approximately 0.494 m.
MIN_DEPTH = 0.49402499198913574
MAX_DEPTH = 1.0

# Geographic sanity check.
MAX_GRID_DISTANCE_KM = 100.0


def normalize_longitude(
    longitude: float,
) -> float:
    """
    Convert longitude to [-180, 180).
    """

    return (
        (float(longitude) + 180.0)
        % 360.0
    ) - 180.0


def haversine_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """
    Great-circle distance in kilometres.
    """

    earth_radius_km = 6371.0088

    lat1_rad = math.radians(
        float(lat1)
    )
    lon1_rad = math.radians(
        float(lon1)
    )

    lat2_rad = math.radians(
        float(lat2)
    )
    lon2_rad = math.radians(
        float(lon2)
    )

    dlat = (
        lat2_rad
        - lat1_rad
    )

    dlon = (
        lon2_rad
        - lon1_rad
    )

    # Dateline-safe longitude difference.
    dlon = (
        dlon + math.pi
    ) % (
        2.0 * math.pi
    ) - math.pi

    a = (
        math.sin(
            dlat / 2.0
        ) ** 2
        +
        math.cos(
            lat1_rad
        )
        *
        math.cos(
            lat2_rad
        )
        *
        math.sin(
            dlon / 2.0
        ) ** 2
    )

    c = (
        2.0
        *
        math.atan2(
            math.sqrt(a),
            math.sqrt(
                max(
                    0.0,
                    1.0 - a,
                )
            ),
        )
    )

    return (
        earth_radius_km
        * c
    )


def to_iso(
    value,
):
    """
    Convert NumPy/xarray datetime to ISO string.
    """

    if value is None:
        return None

    try:
        return np.datetime_as_string(
            np.datetime64(
                value
            ),
            unit="s",
        )

    except Exception:
        return str(value)


def find_variable(
    dataset,
    candidates,
):
    """
    Find first available variable from candidates.
    """

    for name in candidates:

        if name in dataset.data_vars:
            return name

    raise KeyError(
        "Required variable not found. "
        f"Candidates={candidates}, "
        f"available={list(dataset.data_vars)}"
    )


def find_coordinate(
    dataset,
    candidates,
):
    """
    Find first available coordinate from candidates.
    """

    for name in candidates:

        if name in dataset.coords:
            return name

    raise KeyError(
        "Required coordinate not found. "
        f"Candidates={candidates}, "
        f"available={list(dataset.coords)}"
    )


def extract_scalar(
    data_array,
) -> float:
    """
    Extract one finite scalar value.
    """

    values = np.asarray(
        data_array.values,
        dtype=float,
    ).squeeze()

    if values.size != 1:

        raise RuntimeError(
            "Expected one ocean-current value, "
            f"but received shape {values.shape}."
        )

    value = float(values)

    if not np.isfinite(value):

        raise RuntimeError(
            "Ocean-current value is not finite."
        )

    return value


def download_subset(
    latitude: float,
    longitude: float,
    output_directory: Path,
):
    """
    Download a small operational Copernicus Marine subset.

    No explicit time range is supplied here so the operational
    product can expose its currently available analysis/forecast
    time axis.

    The extraction stage then chooses the time nearest current UTC.
    """

    longitude = normalize_longitude(
        longitude
    )

    minimum_longitude = (
        longitude
        - BOX_HALF_SIZE_DEG
    )

    maximum_longitude = (
        longitude
        + BOX_HALF_SIZE_DEG
    )

    minimum_latitude = (
        float(latitude)
        - BOX_HALF_SIZE_DEG
    )

    maximum_latitude = (
        float(latitude)
        + BOX_HALF_SIZE_DEG
    )

    return copernicusmarine.subset(
        dataset_id=DATASET_ID,

        variables=[
            "uo",
            "vo",
        ],

        minimum_longitude=(
            minimum_longitude
        ),

        maximum_longitude=(
            maximum_longitude
        ),

        minimum_latitude=(
            minimum_latitude
        ),

        maximum_latitude=(
            maximum_latitude
        ),

        minimum_depth=MIN_DEPTH,
        maximum_depth=MAX_DEPTH,

        output_directory=str(
            output_directory
        ),

        output_filename=(
            "ocean_current_subset.nc"
        ),

        overwrite=True,
    )


def select_current_nearest(
    dataset: xr.Dataset,
    requested_latitude: float,
    requested_longitude: float,
):
    """
    Select:

      1. Time nearest current UTC.
      2. Near-surface depth.
      3. Grid point nearest requested location.

    This prevents PolarGuard from blindly selecting the final
    forecast timestamp of the Copernicus operational product.
    """

    # --------------------------------------------------------
    # Discover coordinate / variable names
    # --------------------------------------------------------

    lat_name = find_coordinate(
        dataset,
        [
            "latitude",
            "lat",
        ],
    )

    lon_name = find_coordinate(
        dataset,
        [
            "longitude",
            "lon",
        ],
    )

    time_name = find_coordinate(
        dataset,
        [
            "time",
        ],
    )

    depth_name = None

    for candidate in [
        "depth",
        "depthu",
        "depthv",
    ]:

        if candidate in dataset.coords:
            depth_name = candidate
            break

    u_name = find_variable(
        dataset,
        [
            "uo",
            "u",
        ],
    )

    v_name = find_variable(
        dataset,
        [
            "vo",
            "v",
        ],
    )

    # --------------------------------------------------------
    # Find available time nearest current UTC
    # --------------------------------------------------------

    now_utc = datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None,
        microsecond=0,
    )

    requested_time = np.datetime64(
        now_utc,
        "s",
    )

    available_times = np.asarray(
        dataset[
            time_name
        ].values
    ).astype(
        "datetime64[s]"
    )

    if available_times.size == 0:

        raise RuntimeError(
            "Copernicus dataset contains "
            "no time coordinates."
        )

    time_differences = np.abs(
        available_times
        - requested_time
    )

    nearest_time_index = int(
        np.argmin(
            time_differences
        )
    )

    selected_time_value = (
        available_times[
            nearest_time_index
        ]
    )

    # --------------------------------------------------------
    # Select nearest geographical point + time
    # --------------------------------------------------------

    requested_lon_normalized = (
        normalize_longitude(
            requested_longitude
        )
    )

    point = dataset.sel(
        {
            lat_name: float(
                requested_latitude
            ),

            lon_name: float(
                requested_lon_normalized
            ),

            time_name: (
                selected_time_value
            ),
        },

        method="nearest",
    )

    # --------------------------------------------------------
    # Select nearest surface depth
    # --------------------------------------------------------

    if depth_name is not None:

        depth_values = np.asarray(
            dataset[
                depth_name
            ].values,
            dtype=float,
        )

        if depth_values.size == 0:

            raise RuntimeError(
                "Copernicus dataset contains "
                "no depth coordinates."
            )

        surface_depth = float(
            depth_values[
                np.nanargmin(
                    np.abs(
                        depth_values
                    )
                )
            ]
        )

        point = point.sel(
            {
                depth_name: (
                    surface_depth
                ),
            },

            method="nearest",
        )

    # --------------------------------------------------------
    # Extract selected location
    # --------------------------------------------------------

    selected_latitude = float(
        np.asarray(
            point[
                lat_name
            ].values
        ).squeeze()
    )

    selected_longitude = (
        normalize_longitude(
            float(
                np.asarray(
                    point[
                        lon_name
                    ].values
                ).squeeze()
            )
        )
    )

    distance_km = haversine_km(
        requested_latitude,
        requested_longitude,
        selected_latitude,
        selected_longitude,
    )

    if (
        distance_km
        > MAX_GRID_DISTANCE_KM
    ):

        raise RuntimeError(
            "Nearest Copernicus Marine "
            "grid point is "
            f"{distance_km:.2f} km away. "
            "This exceeds the "
            f"{MAX_GRID_DISTANCE_KM:.0f} km "
            "geographic safety check."
        )

    # --------------------------------------------------------
    # Extract ocean-current components
    # --------------------------------------------------------

    uo = extract_scalar(
        point[
            u_name
        ]
    )

    vo = extract_scalar(
        point[
            v_name
        ]
    )

    current_speed = math.hypot(
        uo,
        vo,
    )

    # --------------------------------------------------------
    # Selected depth
    # --------------------------------------------------------

    selected_depth = None

    if depth_name is not None:

        selected_depth = float(
            np.asarray(
                point[
                    depth_name
                ].values
            ).squeeze()
        )

    # --------------------------------------------------------
    # Selected timestamp
    # --------------------------------------------------------

    selected_time = to_iso(
        point[
            time_name
        ].values
    )

    time_offset_seconds = abs(
        int(
            (
                selected_time_value
                - requested_time
            )
            / np.timedelta64(
                1,
                "s",
            )
        )
    )

    time_offset_hours = (
        time_offset_seconds
        / 3600.0
    )

    # --------------------------------------------------------
    # Return result
    # --------------------------------------------------------

    return {
        "uo": uo,
        "vo": vo,

        "current_speed_ms": (
            current_speed
        ),

        "requested_latitude": float(
            requested_latitude
        ),

        "requested_longitude": float(
            requested_lon_normalized
        ),

        "grid_latitude": (
            selected_latitude
        ),

        "grid_longitude": (
            selected_longitude
        ),

        "distance_km": (
            distance_km
        ),

        "depth_m": (
            selected_depth
        ),

        "timestamp": (
            selected_time
        ),

        "requested_time_utc": (
            to_iso(
                requested_time
            )
        ),

        "time_offset_hours": float(
            time_offset_hours
        ),
    }


def locate_downloaded_file(
    temp_path: Path,
) -> Path:
    """
    Locate NetCDF produced by Copernicus Marine.
    """

    expected_file = (
        temp_path
        / "ocean_current_subset.nc"
    )

    if expected_file.exists():
        return expected_file

    candidates = list(
        temp_path.glob(
            "*.nc"
        )
    )

    if not candidates:

        raise FileNotFoundError(
            "Copernicus Marine subset "
            "did not produce a NetCDF file."
        )

    return candidates[0]


def main():
    """
    CLI entry point.

    Example:

        python copernicus_ocean_bridge.py -53.55 -29.95
    """

    parser = argparse.ArgumentParser(
        description=(
            "PolarGuard Copernicus Marine "
            "ocean-current bridge"
        )
    )

    parser.add_argument(
        "latitude",
        type=float,
        help="Requested latitude",
    )

    parser.add_argument(
        "longitude",
        type=float,
        help="Requested longitude",
    )

    args = parser.parse_args()

    try:

        # ----------------------------------------------------
        # Temporary subset download
        # ----------------------------------------------------

        with tempfile.TemporaryDirectory(
            prefix=(
                "polarguard_ocean_"
            )
        ) as temp_dir:

            temp_path = Path(
                temp_dir
            )

            download_subset(
                latitude=(
                    args.latitude
                ),

                longitude=(
                    args.longitude
                ),

                output_directory=(
                    temp_path
                ),
            )

            netcdf_file = (
                locate_downloaded_file(
                    temp_path
                )
            )

            dataset = xr.open_dataset(
                netcdf_file
            )

            try:

                result = (
                    select_current_nearest(
                        dataset,
                        requested_latitude=(
                            args.latitude
                        ),
                        requested_longitude=(
                            args.longitude
                        ),
                    )
                )

            finally:

                dataset.close()

        # ----------------------------------------------------
        # Final machine-readable result
        # ----------------------------------------------------

        output = {
            "success": True,

            "source": (
                "Copernicus Marine "
                "Global Ocean Physics "
                "Analysis and Forecast"
            ),

            "dataset_id": (
                DATASET_ID
            ),

            **result,

            "retrieved_at_utc": (
                datetime.now(
                    timezone.utc
                )
                .replace(
                    microsecond=0
                )
                .isoformat()
                .replace(
                    "+00:00",
                    "Z",
                )
            ),
        }

        print(
            json.dumps(
                output,
                separators=(
                    ",",
                    ":",
                ),
            )
        )

    except Exception as error:

        error_output = {
            "success": False,
            "error": str(
                error
            ),
        }

        print(
            json.dumps(
                error_output,
                separators=(
                    ",",
                    ":",
                ),
            )
        )

        sys.exit(1)


if __name__ == "__main__":
    main()