import sys
"""
PolarGuard Environmental Data Service
======================================

Purpose
-------
Provide one standardized environmental-input interface for the frozen
PolarGuard Member-2 iceberg trajectory model.

Supported operating modes:

1. MANUAL
   - User supplies wind, ocean-current and SIC values.
   - Useful for historical validation, demonstrations and controlled tests.

2. NEAR_REAL_TIME
   - Will retrieve environmental variables automatically from official
     providers.
   - Provider-specific retrieval is added as separate functions so the
     frozen Member-2 service never needs to change.

Important
---------
This module does NOT modify or retrain Member-2.

Member-2 environmental inputs:
    wind_u10
    wind_v10
    ocean_uo
    ocean_vo
    sea_ice_sic
    sea_ice_available
"""

from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import subprocess
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

import math
import numpy as np


# ============================================================
# CONSTANTS
# ============================================================

MODE_MANUAL = "manual"
MODE_NEAR_REAL_TIME = "near_real_time"

VALID_MODES = {
    MODE_MANUAL,
    MODE_NEAR_REAL_TIME,
}


# Member-2 expects SIC in 0..1.
MIN_SIC = 0.0
MAX_SIC = 1.0


# Broad physical sanity bounds.
#
# These are validation guards rather than statements that larger
# values are physically impossible under every Antarctic condition.
MAX_ABS_WIND_MS = 100.0
MAX_ABS_OCEAN_CURRENT_MS = 10.0


# ============================================================
# RESULT OBJECT
# ============================================================

@dataclass
class EnvironmentalInputs:
    """
    Standard environmental input package used by PolarGuard Member-2.
    """

    mode: str

    requested_date: str
    latitude: float
    longitude: float

    wind_u10: float
    wind_v10: float

    ocean_uo: float
    ocean_vo: float

    sea_ice_sic: float
    sea_ice_available: int

    wind_speed_ms: float
    ocean_speed_ms: float

    wind_source: str
    ocean_source: str
    sea_ice_source: str

    wind_timestamp: Optional[str]
    ocean_timestamp: Optional[str]
    sea_ice_timestamp: Optional[str]

    synchronized: bool
    synchronization_note: str

    retrieved_at_utc: str

    def to_dict(self):
        return asdict(self)


# ============================================================
# BASIC HELPERS
# ============================================================

def _utc_now_string():
    """
    Current UTC timestamp for provenance metadata.
    """

    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

def _normalize_date(value):
    """
    Convert common date inputs into YYYY-MM-DD.
    """

    if value is None:
        raise ValueError(
            "A date is required."
        )

    # numpy datetime64
    if isinstance(value, np.datetime64):
        value = str(
            value.astype("datetime64[D]")
        )

    # datetime/date-like objects
    elif hasattr(value, "strftime"):
        value = value.strftime(
            "%Y-%m-%d"
        )

    else:
        value = str(value).strip()

    try:
        parsed = datetime.strptime(
            value[:10],
            "%Y-%m-%d",
        )

    except ValueError as error:
        raise ValueError(
            f"Invalid date: {value}. "
            "Expected YYYY-MM-DD."
        ) from error

    return parsed.strftime(
        "%Y-%m-%d"
    )


def _validate_coordinate(
    latitude,
    longitude,
):
    """
    Validate WGS84 coordinate.
    """

    latitude = float(latitude)
    longitude = float(longitude)

    if not np.isfinite(latitude):
        raise ValueError(
            "Latitude must be finite."
        )

    if not np.isfinite(longitude):
        raise ValueError(
            "Longitude must be finite."
        )

    if not -90.0 <= latitude <= 90.0:
        raise ValueError(
            "Latitude must be between -90 and 90 degrees."
        )

    if not -180.0 <= longitude <= 180.0:
        raise ValueError(
            "Longitude must be between -180 and 180 degrees."
        )

    return latitude, longitude


def _validate_finite(
    value,
    name,
):
    """
    Convert a value to float and ensure it is finite.
    """

    try:
        value = float(value)

    except (TypeError, ValueError) as error:
        raise ValueError(
            f"{name} must be numeric."
        ) from error

    if not np.isfinite(value):
        raise ValueError(
            f"{name} must be finite."
        )

    return value


def _validate_wind_component(
    value,
    name,
):
    """
    Validate wind vector component in m/s.
    """

    value = _validate_finite(
        value,
        name,
    )

    if abs(value) > MAX_ABS_WIND_MS:
        raise ValueError(
            f"{name}={value} m/s is outside the "
            f"prototype sanity limit ±{MAX_ABS_WIND_MS} m/s."
        )

    return value


def _validate_ocean_component(
    value,
    name,
):
    """
    Validate ocean-current component in m/s.
    """

    value = _validate_finite(
        value,
        name,
    )

    if abs(value) > MAX_ABS_OCEAN_CURRENT_MS:
        raise ValueError(
            f"{name}={value} m/s is outside the "
            f"prototype sanity limit "
            f"±{MAX_ABS_OCEAN_CURRENT_MS} m/s."
        )

    return value


def _validate_sic(
    sea_ice_sic,
    sea_ice_available,
):
    """
    Validate Member-2 SIC input.

    Frozen Member-2 convention:
    - real SIC available:
        SIC in [0,1], available=1

    - SIC unavailable:
        frozen-model fallback SIC=0.8, available=0

    This preserves the training/service convention already used by
    PolarGuard Member-2.
    """

    sea_ice_available = int(
        sea_ice_available
    )

    if sea_ice_available not in {
        0,
        1,
    }:
        raise ValueError(
            "sea_ice_available must be 0 or 1."
        )

    if sea_ice_available == 0:

        # IMPORTANT:
        # Preserve Member-2's existing frozen missing-SIC convention.
        return 0.8, 0

    sea_ice_sic = _validate_finite(
        sea_ice_sic,
        "sea_ice_sic",
    )

    if not (
        MIN_SIC
        <= sea_ice_sic
        <= MAX_SIC
    ):
        raise ValueError(
            "Sea-ice concentration must be between "
            "0 and 1."
        )

    return (
        float(sea_ice_sic),
        1,
    )


def _speed(
    u,
    v,
):
    """
    Vector speed from U/V components.
    """

    return float(
        math.hypot(
            float(u),
            float(v),
        )
    )


# ============================================================
# MANUAL / HISTORICAL MODE
# ============================================================

def load_manual_environment(
    *,
    date,
    latitude,
    longitude,
    wind_u10,
    wind_v10,
    ocean_uo,
    ocean_vo,
    sea_ice_sic,
    sea_ice_available=1,
    wind_source="Manual / Historical Input",
    ocean_source="Manual / Historical Input",
    sea_ice_source="Manual / Historical Input",
    wind_timestamp=None,
    ocean_timestamp=None,
    sea_ice_timestamp=None,
):
    """
    Build a validated environmental package from manually supplied
    environmental variables.

    This is suitable for:
        - historical testing
        - SIH demonstration
        - manually downloaded official data
        - controlled model tests
    """

    requested_date = _normalize_date(
        date
    )

    latitude, longitude = (
        _validate_coordinate(
            latitude,
            longitude,
        )
    )

    wind_u10 = (
        _validate_wind_component(
            wind_u10,
            "wind_u10",
        )
    )

    wind_v10 = (
        _validate_wind_component(
            wind_v10,
            "wind_v10",
        )
    )

    ocean_uo = (
        _validate_ocean_component(
            ocean_uo,
            "ocean_uo",
        )
    )

    ocean_vo = (
        _validate_ocean_component(
            ocean_vo,
            "ocean_vo",
        )
    )

    (
        sea_ice_sic,
        sea_ice_available,
    ) = _validate_sic(
        sea_ice_sic,
        sea_ice_available,
    )

    wind_speed = _speed(
        wind_u10,
        wind_v10,
    )

    ocean_speed = _speed(
        ocean_uo,
        ocean_vo,
    )

    # Manual mode cannot automatically prove that user-supplied
    # environmental values have matching timestamps.
    synchronized = False

    synchronization_note = (
        "Manual inputs validated. Temporal synchronization "
        "must be confirmed from the source timestamps supplied "
        "by the user."
    )

    # If all timestamps are explicitly provided and their date
    # matches the requested date, we can mark this package as
    # date-synchronized.
    timestamps = [
        wind_timestamp,
        ocean_timestamp,
        sea_ice_timestamp,
    ]

    if all(
        timestamp is not None
        for timestamp in timestamps
    ):

        timestamp_dates = []

        for timestamp in timestamps:

            try:
                timestamp_dates.append(
                    _normalize_date(
                        timestamp
                    )
                )

            except Exception:
                timestamp_dates.append(
                    None
                )

        if all(
            timestamp_date
            == requested_date
            for timestamp_date
            in timestamp_dates
        ):
            synchronized = True

            synchronization_note = (
                "Manual environmental source timestamps all "
                "match the requested initialization date."
            )

        else:
            synchronization_note = (
                "Manual environmental inputs are valid, but one "
                "or more supplied source timestamps do not match "
                "the requested initialization date."
            )

    return EnvironmentalInputs(
        mode=MODE_MANUAL,

        requested_date=requested_date,

        latitude=latitude,
        longitude=longitude,

        wind_u10=wind_u10,
        wind_v10=wind_v10,

        ocean_uo=ocean_uo,
        ocean_vo=ocean_vo,

        sea_ice_sic=sea_ice_sic,
        sea_ice_available=sea_ice_available,

        wind_speed_ms=wind_speed,
        ocean_speed_ms=ocean_speed,

        wind_source=str(
            wind_source
        ),
        ocean_source=str(
            ocean_source
        ),
        sea_ice_source=str(
            sea_ice_source
        ),

        wind_timestamp=(
            None
            if wind_timestamp is None
            else str(wind_timestamp)
        ),

        ocean_timestamp=(
            None
            if ocean_timestamp is None
            else str(ocean_timestamp)
        ),

        sea_ice_timestamp=(
            None
            if sea_ice_timestamp is None
            else str(sea_ice_timestamp)
        ),

        synchronized=synchronized,

        synchronization_note=(
            synchronization_note
        ),

        retrieved_at_utc=(
            _utc_now_string()
        ),
    )


# ============================================================
# NEAR-REAL-TIME PROVIDER HOOKS
# ============================================================
def refresh_latest_ecmwf_wind():
    """
    Download the latest available ECMWF IFS 10 m wind
    into the PolarGuard environment cache.

    The main PolarGuard environment can use ecmwf-opendata directly,
    so GRIB reading still remains isolated in the Python 3.13 bridge.
    """

    from ecmwf.opendata import Client

    project_root = Path(__file__).resolve().parent

    cache_dir = (
        project_root
        / "data"
        / "environment_cache"
        / "ecmwf"
    )

    cache_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = (
        cache_dir
        / "latest_wind.grib2"
    )

    metadata_file = (
        cache_dir
        / "latest_wind_metadata.json"
    )

    print(
        "Checking latest ECMWF IFS wind..."
    )

    client = Client(
        source="ecmwf",
        model="ifs",
        resol="0p25",
    )

    temp_file = (
        cache_dir
        / "latest_wind_download.grib2"
    )

    try:
        client.retrieve(
            type="fc",
            step=0,
            param=[
                "10u",
                "10v",
            ],
            target=str(
                temp_file
            ),
        )

        if not temp_file.exists():
            raise RuntimeError(
                "ECMWF download completed but "
                "temporary GRIB file was not created."
            )

        if (
            temp_file.stat().st_size
            <= 0
        ):
            raise RuntimeError(
                "Downloaded ECMWF GRIB file is empty."
            )

        # Replace previous cached file only after
        # the new download has succeeded.
        if output_file.exists():
            output_file.unlink()

        temp_file.replace(
            output_file
        )

        metadata = {
            "provider": (
                "ECMWF Open Data IFS"
            ),
            "variables": [
                "10u",
                "10v",
            ],
            "forecast_step_hours": 0,
            "downloaded_at_utc": (
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
            "file": str(
                output_file
            ),
            "file_size_bytes": (
                output_file.stat().st_size
            ),
        }

        with open(
            metadata_file,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                metadata,
                file,
                indent=2,
            )

        return {
            "success": True,
            "file": str(
                output_file
            ),
            "metadata_file": str(
                metadata_file
            ),
            "file_size_bytes": (
                output_file.stat().st_size
            ),
        }

    finally:
        if temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass
def load_near_real_time_wind(
    *,
    date,
    latitude,
    longitude,
):
    """
    Retrieve latest available ECMWF IFS 10 m wind through
    the Python 3.13 GRIB bridge.

    Important:
    The returned provider timestamp may differ from the requested
    date. Full synchronization is checked later by the environmental
    service.
    """

    import json
    import subprocess
    from pathlib import Path
    refresh_latest_ecmwf_wind()
    project_root = Path(__file__).resolve().parent

    bridge_script = (
        project_root
        / "ecmwf_wind_bridge.py"
    )

    grib_python = Path(sys.executable)

    if not bridge_script.exists():
        raise FileNotFoundError(
            f"ECMWF wind bridge not found: "
            f"{bridge_script}"
        )

    if not grib_python.exists():
        raise FileNotFoundError(
            f"Python 3.13 GRIB environment not found: "
            f"{grib_python}"
        )

    command = [
        str(grib_python),
        str(bridge_script),
        str(float(latitude)),
        str(float(longitude)),
    ]

    completed = subprocess.run(
        command,
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=120,
    )

    stdout = (
        completed.stdout.strip()
    )

    stderr = (
        completed.stderr.strip()
    )

    if not stdout:
        raise RuntimeError(
            "ECMWF wind bridge returned no output. "
            f"stderr={stderr}"
        )

    # Bridge is designed to return one JSON object.
    # Using the last non-empty line also protects against
    # accidental informational output from libraries.
    json_line = [
        line.strip()
        for line in stdout.splitlines()
        if line.strip()
    ][-1]

    try:
        result = json.loads(
            json_line
        )

    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Could not decode ECMWF bridge response. "
            f"stdout={stdout} "
            f"stderr={stderr}"
        ) from error

    if (
        completed.returncode != 0
        or not result.get(
            "success",
            False,
        )
    ):
        raise RuntimeError(
            "ECMWF wind retrieval failed: "
            f"{result.get('error', stderr)}"
        )

    distance_km = float(
        result["distance_km"]
    )

    if distance_km > 100.0:
        raise RuntimeError(
            "ECMWF nearest grid point is too far "
            f"from the requested position: "
            f"{distance_km:.2f} km"
        )

    return {
        "u10": float(
            result["u10"]
        ),

        "v10": float(
            result["v10"]
        ),

        "source": (
            result.get(
                "source",
                "ECMWF Open Data IFS",
            )
        ),

        "timestamp": (
            result.get(
                "valid_time"
            )
        ),

        "model_initialization": (
            result.get(
                "model_initialization"
            )
        ),

        "forecast_step": (
            result.get(
                "forecast_step"
            )
        ),

        "grid_latitude": float(
            result["grid_latitude"]
        ),

        "grid_longitude": float(
            result["grid_longitude"]
        ),

        "distance_km": (
            distance_km
        ),

        "requested_date": (
            _normalize_date(
                date
            )
        ),
    }

def load_near_real_time_ocean_current(
    *,
    date,
    latitude,
    longitude,
):
    """
    Retrieve latest available near-surface ocean current
    from Copernicus Marine through the Python 3.13 bridge.

    The real provider timestamp is preserved so PolarGuard
    can later determine whether environmental inputs are
    temporally synchronized.

    No synthetic or historical fallback is used.
    """

    import json
    import subprocess
    from pathlib import Path

    project_root = Path(
        __file__
    ).resolve().parent

    bridge_script = (
        project_root
        / "copernicus_ocean_bridge.py"
    )

    # venv_grib was created one directory above
    # the main PolarGuard project directory.
    grib_python = (
        project_root.parent
        / "venv_grib"
        / "Scripts"
        / "python.exe"
    )

    if not bridge_script.exists():
        raise FileNotFoundError(
            "Copernicus ocean bridge not found: "
            f"{bridge_script}"
        )

    if not grib_python.exists():
        raise FileNotFoundError(
            "Python 3.13 GRIB environment not found: "
            f"{grib_python}"
        )

    command = [
        str(grib_python),
        str(bridge_script),
        str(float(latitude)),
        str(float(longitude)),
    ]

    completed = subprocess.run(
        command,
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=300,
    )

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()

    if not stdout:
        raise RuntimeError(
            "Copernicus ocean bridge returned no output. "
            f"stderr={stderr}"
        )

    # Copernicus Marine may print INFO messages before
    # the bridge's JSON result, so search backwards for
    # the final valid JSON object.
    result = None

    for line in reversed(
        stdout.splitlines()
    ):
        line = line.strip()

        if not line:
            continue

        try:
            candidate = json.loads(
                line
            )

            if isinstance(
                candidate,
                dict,
            ):
                result = candidate
                break

        except json.JSONDecodeError:
            continue

    if result is None:
        raise RuntimeError(
            "Could not find a valid JSON response "
            "from Copernicus ocean bridge. "
            f"stdout={stdout} "
            f"stderr={stderr}"
        )

    if (
        completed.returncode != 0
        or not result.get(
            "success",
            False,
        )
    ):
        raise RuntimeError(
            "Copernicus ocean-current retrieval failed: "
            f"{result.get('error', stderr)}"
        )

    uo = float(
        result["uo"]
    )

    vo = float(
        result["vo"]
    )

    distance_km = float(
        result["distance_km"]
    )

    if distance_km > 100.0:
        raise RuntimeError(
            "Copernicus nearest grid point is too far "
            "from the requested location: "
            f"{distance_km:.2f} km"
        )

    current_speed_ms = float(
        result.get(
            "current_speed_ms",
            (
                uo ** 2
                + vo ** 2
            ) ** 0.5,
        )
    )

    return {
        "uo": uo,
        "vo": vo,

        "source": result.get(
            "source",
            (
                "Copernicus Marine "
                "Global Ocean Physics "
                "Analysis and Forecast"
            ),
        ),

        "timestamp": result.get(
            "timestamp"
        ),

        "dataset_id": result.get(
            "dataset_id"
        ),

        "depth_m": result.get(
            "depth_m"
        ),

        "grid_latitude": float(
            result["grid_latitude"]
        ),

        "grid_longitude": float(
            result["grid_longitude"]
        ),

        "distance_km": distance_km,

        "current_speed_ms": (
            current_speed_ms
        ),

        "time_offset_hours": result.get(
            "time_offset_hours"
        ),

        "retrieved_at_utc": result.get(
            "retrieved_at_utc"
        ),

        "requested_date": _normalize_date(
            date
        ),
    }


def load_near_real_time_sic(
    *,
    date,
    latitude,
    longitude,
):
    """
    Automatic SIC provider hook.

    Stage 2C will connect this function to PolarGuard's
    existing NOAA/NSIDC near-real-time satellite SIC service.

    No synthetic SIC is returned here.
    """

    raise NotImplementedError(
        "Near-real-time SIC point extraction "
        "has not been connected yet."
    )


def load_near_real_time_sic(
    *,
    date,
    latitude,
    longitude,
):
    """
    Retrieve near-real-time sea-ice concentration (SIC)
    at a requested geographic location.

    Data source:
        NOAA/NSIDC G10016 Version 4
        Near-Real-Time Antarctic sea-ice concentration.

    PolarGuard's existing satellite_data_service is reused
    to obtain the latest real satellite SIC grid.

    The requested latitude/longitude (EPSG:4326) is projected
    to the PolarGuard Antarctic stereographic grid
    (EPSG:3412), then the nearest grid cell is selected.

    No synthetic SIC is generated.
    """

    import numpy as np
    from pyproj import Transformer

    from satellite_data_service import (
        load_latest_satellite_input,
    )

    # --------------------------------------------------------
    # Validate requested position
    # --------------------------------------------------------

    latitude = float(latitude)
    longitude = float(longitude)

    if not np.isfinite(latitude):
        raise ValueError(
            "SIC latitude must be finite."
        )

    if not np.isfinite(longitude):
        raise ValueError(
            "SIC longitude must be finite."
        )

    if not (-90.0 <= latitude <= 90.0):
        raise ValueError(
            f"Invalid latitude: {latitude}"
        )

    if not (-180.0 <= longitude <= 180.0):
        raise ValueError(
            f"Invalid longitude: {longitude}"
        )

    # --------------------------------------------------------
    # Load latest real NOAA/NSIDC satellite bundle
    # --------------------------------------------------------

    bundle = load_latest_satellite_input()

    required_keys = [
        "current",
        "x",
        "y",
        "date",
    ]

    missing = [
        key
        for key in required_keys
        if key not in bundle
    ]

    if missing:
        raise RuntimeError(
            "Satellite SIC bundle is missing "
            f"required fields: {missing}"
        )

    sic_grid = np.asarray(
        bundle["current"],
        dtype=float,
    )

    x_coords = np.asarray(
        bundle["x"],
        dtype=float,
    )

    y_coords = np.asarray(
        bundle["y"],
        dtype=float,
    )

    # --------------------------------------------------------
    # Validate grid
    # --------------------------------------------------------

    if sic_grid.ndim != 2:
        raise RuntimeError(
            "Satellite SIC grid must be 2-D. "
            f"Received shape {sic_grid.shape}."
        )

    if x_coords.ndim != 1:
        raise RuntimeError(
            "Satellite x coordinates must be 1-D."
        )

    if y_coords.ndim != 1:
        raise RuntimeError(
            "Satellite y coordinates must be 1-D."
        )

    expected_shape = (
        len(y_coords),
        len(x_coords),
    )

    if sic_grid.shape != expected_shape:
        raise RuntimeError(
            "Satellite SIC grid shape does not "
            "match x/y coordinates. "
            f"SIC={sic_grid.shape}, "
            f"expected={expected_shape}"
        )

    # --------------------------------------------------------
    # Convert WGS84 latitude/longitude -> EPSG:3412
    #
    # always_xy=True means:
    # input  = longitude, latitude
    # output = x, y
    # --------------------------------------------------------

    transformer = Transformer.from_crs(
        "EPSG:4326",
        "EPSG:3412",
        always_xy=True,
    )

    point_x, point_y = transformer.transform(
        longitude,
        latitude,
    )

    if (
        not np.isfinite(point_x)
        or not np.isfinite(point_y)
    ):
        raise RuntimeError(
            "Could not project requested position "
            "to EPSG:3412."
        )

    # --------------------------------------------------------
    # Find nearest PolarGuard grid cell
    # --------------------------------------------------------

    x_index = int(
        np.argmin(
            np.abs(
                x_coords
                - point_x
            )
        )
    )

    y_index = int(
        np.argmin(
            np.abs(
                y_coords
                - point_y
            )
        )
    )

    grid_x = float(
        x_coords[x_index]
    )

    grid_y = float(
        y_coords[y_index]
    )

    grid_distance_m = float(
        np.hypot(
            grid_x - point_x,
            grid_y - point_y,
        )
    )

    grid_distance_km = (
        grid_distance_m
        / 1000.0
    )

    # 25 km grid means the nearest grid centre should normally
    # be much closer than this. This guard helps catch projection
    # or coordinate mistakes.
    if grid_distance_km > 50.0:
        raise RuntimeError(
            "Nearest NOAA/NSIDC SIC grid cell is "
            f"{grid_distance_km:.2f} km away. "
            "Possible projection/grid mismatch."
        )

    # --------------------------------------------------------
    # Extract SIC
    # --------------------------------------------------------

    sic_value = float(
        sic_grid[
            y_index,
            x_index,
        ]
    )

    sic_available = int(
        np.isfinite(
            sic_value
        )
    )

    # IMPORTANT:
    # Do NOT convert an unavailable satellite cell to 0.
    #
    # The frozen Member-2 missing-SIC convention is handled
    # later by environmental_data_service:
    #     SIC = 0.8
    #     sea_ice_available = 0
    #
    # Here we preserve the actual availability state.
    if sic_available:
        sic_value = float(
            np.clip(
                sic_value,
                0.0,
                1.0,
            )
        )
    else:
        sic_value = None

    # --------------------------------------------------------
    # Provider timestamp
    # --------------------------------------------------------

    satellite_date = bundle["date"]

    try:
        timestamp = np.datetime_as_string(
            np.datetime64(
                satellite_date
            ),
            unit="D",
        )
    except Exception:
        timestamp = str(
            satellite_date
        )

    # --------------------------------------------------------
    # Optional source metadata
    # --------------------------------------------------------

    metadata = bundle.get(
        "metadata",
        {},
    )

    if not isinstance(
        metadata,
        dict,
    ):
        metadata = {}

    source = (
        metadata.get("provider")
        or metadata.get("source")
        or (
            "NOAA/NSIDC G10016 Version 4 "
            "Near-Real-Time Antarctic Sea Ice"
        )
    )

    provider_lag_days = bundle.get(
        "provider_lag_days"
    )

    if provider_lag_days is None:
        provider_lag_days = metadata.get(
            "provider_lag_days"
        )

    # --------------------------------------------------------
    # Return environmental-service format
    # --------------------------------------------------------

    return {
        "sic": sic_value,

        "available": (
            sic_available
        ),

        # Include the exact frozen Member-2 feature name too.
        "sea_ice_available": (
            sic_available
        ),

        "source": source,

        "timestamp": timestamp,

        "requested_date": (
            _normalize_date(
                date
            )
        ),

        "requested_latitude": (
            latitude
        ),

        "requested_longitude": (
            longitude
        ),

        "projected_x": float(
            point_x
        ),

        "projected_y": float(
            point_y
        ),

        "grid_x": grid_x,
        "grid_y": grid_y,

        "grid_x_index": (
            x_index
        ),

        "grid_y_index": (
            y_index
        ),

        "grid_distance_km": (
            grid_distance_km
        ),

        "provider_lag_days": (
            provider_lag_days
        ),
    }


# ============================================================
# NEAR-REAL-TIME MODE
# ============================================================

def load_near_real_time_environment(
    *,
    date,
    latitude,
    longitude,
):
    """
    Build the automatic environmental input package.

    This intentionally fails until every provider hook is connected.
    PolarGuard should never report an automatic environmental package
    using fabricated fallback environmental data.
    """

    requested_date = _normalize_date(
        date
    )

    latitude, longitude = (
        _validate_coordinate(
            latitude,
            longitude,
        )
    )

    wind = load_near_real_time_wind(
        date=requested_date,
        latitude=latitude,
        longitude=longitude,
    )

    ocean = (
        load_near_real_time_ocean_current(
            date=requested_date,
            latitude=latitude,
            longitude=longitude,
        )
    )

    sic = load_near_real_time_sic(
        date=requested_date,
        latitude=latitude,
        longitude=longitude,
    )

    wind_u10 = (
        _validate_wind_component(
            wind["u10"],
            "wind_u10",
        )
    )

    wind_v10 = (
        _validate_wind_component(
            wind["v10"],
            "wind_v10",
        )
    )

    ocean_uo = (
        _validate_ocean_component(
            ocean["uo"],
            "ocean_uo",
        )
    )

    ocean_vo = (
        _validate_ocean_component(
            ocean["vo"],
            "ocean_vo",
        )
    )

    sea_ice_sic, sea_ice_available = (
        _validate_sic(
            sic["sic"],
            sic.get(
                "available",
                1,
            ),
        )
    )

    wind_timestamp = wind.get(
        "timestamp"
    )

    ocean_timestamp = ocean.get(
        "timestamp"
    )

    sea_ice_timestamp = sic.get(
        "timestamp"
    )

    timestamps = [
        wind_timestamp,
        ocean_timestamp,
        sea_ice_timestamp,
    ]

    synchronized = False

    synchronization_note = (
        "One or more automatic provider timestamps are missing."
    )

    if all(
        timestamp is not None
        for timestamp in timestamps
    ):

        source_dates = [
            _normalize_date(
                timestamp
            )
            for timestamp in timestamps
        ]

        if all(
            source_date
            == requested_date
            for source_date
            in source_dates
        ):
            synchronized = True

            synchronization_note = (
                "Wind, ocean-current and sea-ice provider "
                "dates match the requested initialization date."
            )

        else:
            synchronization_note = (
                "Environmental provider data were retrieved, "
                "but their dates are not fully synchronized."
            )

    return EnvironmentalInputs(
        mode=MODE_NEAR_REAL_TIME,

        requested_date=requested_date,

        latitude=latitude,
        longitude=longitude,

        wind_u10=wind_u10,
        wind_v10=wind_v10,

        ocean_uo=ocean_uo,
        ocean_vo=ocean_vo,

        sea_ice_sic=sea_ice_sic,
        sea_ice_available=sea_ice_available,

        wind_speed_ms=_speed(
            wind_u10,
            wind_v10,
        ),

        ocean_speed_ms=_speed(
            ocean_uo,
            ocean_vo,
        ),

        wind_source=wind.get(
            "source",
            "Automatic Wind Provider",
        ),

        ocean_source=ocean.get(
            "source",
            "Automatic Ocean Provider",
        ),

        sea_ice_source=sic.get(
            "source",
            "Automatic SIC Provider",
        ),

        wind_timestamp=wind_timestamp,
        ocean_timestamp=ocean_timestamp,
        sea_ice_timestamp=(
            sea_ice_timestamp
        ),

        synchronized=synchronized,

        synchronization_note=(
            synchronization_note
        ),

        retrieved_at_utc=(
            _utc_now_string()
        ),
    )


# ============================================================
# MAIN PUBLIC INTERFACE
# ============================================================

def load_environmental_inputs(
    *,
    mode,
    date,
    latitude,
    longitude,
    wind_u10=None,
    wind_v10=None,
    ocean_uo=None,
    ocean_vo=None,
    sea_ice_sic=None,
    sea_ice_available=1,
    wind_source="Manual / Historical Input",
    ocean_source="Manual / Historical Input",
    sea_ice_source="Manual / Historical Input",
    wind_timestamp=None,
    ocean_timestamp=None,
    sea_ice_timestamp=None,
):
    """
    Unified PolarGuard environmental-data interface.

    Examples
    --------

    Manual:

        load_environmental_inputs(
            mode="manual",
            date="2025-08-15",
            latitude=-70.0,
            longitude=20.0,
            wind_u10=5.0,
            wind_v10=-2.0,
            ocean_uo=0.10,
            ocean_vo=-0.05,
            sea_ice_sic=0.70,
        )

    Near-real-time:

        load_environmental_inputs(
            mode="near_real_time",
            date="2026-09-02",
            latitude=-70.0,
            longitude=20.0,
        )
    """

    mode = str(
        mode
    ).strip().lower()

    if mode not in VALID_MODES:
        raise ValueError(
            f"Unknown mode '{mode}'. "
            f"Expected one of: {sorted(VALID_MODES)}"
        )

    if mode == MODE_MANUAL:

        required = {
            "wind_u10": wind_u10,
            "wind_v10": wind_v10,
            "ocean_uo": ocean_uo,
            "ocean_vo": ocean_vo,
        }

        missing = [
            name
            for name, value
            in required.items()
            if value is None
        ]

        if (
            int(sea_ice_available) == 1
            and sea_ice_sic is None
        ):
            missing.append(
                "sea_ice_sic"
            )

        if missing:
            raise ValueError(
                "Manual mode is missing required inputs: "
                + ", ".join(missing)
            )

        return load_manual_environment(
            date=date,
            latitude=latitude,
            longitude=longitude,

            wind_u10=wind_u10,
            wind_v10=wind_v10,

            ocean_uo=ocean_uo,
            ocean_vo=ocean_vo,

            sea_ice_sic=sea_ice_sic,
            sea_ice_available=(
                sea_ice_available
            ),

            wind_source=wind_source,
            ocean_source=ocean_source,
            sea_ice_source=(
                sea_ice_source
            ),

            wind_timestamp=(
                wind_timestamp
            ),

            ocean_timestamp=(
                ocean_timestamp
            ),

            sea_ice_timestamp=(
                sea_ice_timestamp
            ),
        )

    return (
        load_near_real_time_environment(
            date=date,
            latitude=latitude,
            longitude=longitude,
        )
    )


# ============================================================
# MEMBER-2 ADAPTER
# ============================================================

def to_member2_environment(
    environment,
):
    """
    Extract only the six environmental features expected by the
    frozen Member-2 model.
    """

    if isinstance(
        environment,
        EnvironmentalInputs,
    ):
        data = (
            environment.to_dict()
        )

    elif isinstance(
        environment,
        dict,
    ):
        data = environment

    else:
        raise TypeError(
            "environment must be EnvironmentalInputs or dict."
        )

    required = [
        "wind_u10",
        "wind_v10",
        "ocean_uo",
        "ocean_vo",
        "sea_ice_sic",
        "sea_ice_available",
    ]

    missing = [
        key
        for key in required
        if key not in data
    ]

    if missing:
        raise ValueError(
            "Environment is missing Member-2 fields: "
            + ", ".join(missing)
        )

    return {
        "wind_u10": float(
            data["wind_u10"]
        ),
        "wind_v10": float(
            data["wind_v10"]
        ),
        "ocean_uo": float(
            data["ocean_uo"]
        ),
        "ocean_vo": float(
            data["ocean_vo"]
        ),
        "sea_ice_sic": float(
            data["sea_ice_sic"]
        ),
        "sea_ice_available": int(
            data["sea_ice_available"]
        ),
    }


# ============================================================
# TERMINAL SELF-TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 76)
    print(
        "POLARGUARD - ENVIRONMENTAL DATA SERVICE"
    )
    print("=" * 76)

    print()
    print(
        "Testing MANUAL / HISTORICAL mode..."
    )
    print()

    test_environment = (
        load_environmental_inputs(
            mode="manual",

            date="2025-08-15",

            latitude=-70.25,
            longitude=20.50,

            wind_u10=6.20,
            wind_v10=-3.10,

            ocean_uo=0.18,
            ocean_vo=-0.07,

            sea_ice_sic=0.72,
            sea_ice_available=1,

            wind_source=(
                "Manual Test Wind"
            ),

            ocean_source=(
                "Manual Test Ocean"
            ),

            sea_ice_source=(
                "Manual Test SIC"
            ),

            wind_timestamp=(
                "2025-08-15T12:00:00"
            ),

            ocean_timestamp=(
                "2025-08-15T12:00:00"
            ),

            sea_ice_timestamp=(
                "2025-08-15T00:00:00"
            ),
        )
    )

    result = (
        test_environment.to_dict()
    )

    for key, value in result.items():
        print(
            f"{key:28s}: {value}"
        )

    print()
    print("-" * 76)

    print(
        "Frozen Member-2 environmental adapter:"
    )

    member2_inputs = (
        to_member2_environment(
            test_environment
        )
    )

    for key, value in (
        member2_inputs.items()
    ):
        print(
            f"{key:28s}: {value}"
        )

    print()
    print("=" * 76)

    print(
        "Manual environmental mode: READY"
    )

    print(
        "Near-real-time provider hooks: "
        "NOT CONNECTED YET"
    )

    print(
        "No synthetic automatic environmental "
        "data created."
    )

    print("=" * 76)