from pathlib import Path
import math

import numpy as np
import xarray as xr


# ============================================================
# CONFIG
# ============================================================

GRIB_FILE = Path(
    "data/environment_cache/ecmwf/latest_wind.grib2"
)

# Example current BYU iceberg position
TARGET_LAT = -53.55
TARGET_LON = -29.95


# ============================================================
# HELPERS
# ============================================================

def longitude_to_minus180_180(lon):
    """
    Convert any longitude to [-180, 180).
    """

    lon = np.asarray(lon, dtype=float)

    return (
        (lon + 180.0) % 360.0
    ) - 180.0


def haversine_distance_km(
    lat1,
    lon1,
    lat2,
    lon2,
):
    """
    Vectorized Haversine distance.
    """

    earth_radius_km = 6371.0088

    lat1 = np.radians(
        np.asarray(lat1, dtype=float)
    )

    lon1 = np.radians(
        np.asarray(lon1, dtype=float)
    )

    lat2 = math.radians(
        float(lat2)
    )

    lon2 = math.radians(
        float(lon2)
    )

    dlat = lat1 - lat2

    dlon = (
        lon1 - lon2 + np.pi
    ) % (2.0 * np.pi) - np.pi

    a = (
        np.sin(dlat / 2.0) ** 2
        +
        np.cos(lat1)
        * math.cos(lat2)
        * np.sin(dlon / 2.0) ** 2
    )

    c = 2.0 * np.arctan2(
        np.sqrt(a),
        np.sqrt(
            np.maximum(
                0.0,
                1.0 - a,
            )
        ),
    )

    return earth_radius_km * c


def scalar_float(value):
    """
    Safely convert xarray/numpy scalar to float.
    """

    arr = np.asarray(
        value.values
        if hasattr(value, "values")
        else value
    )

    return float(
        arr.squeeze()
    )


def scalar_string(
    dataset,
    name,
):
    """
    Safely display a scalar coordinate.
    """

    if name not in dataset.coords:
        return "unknown"

    try:
        return str(
            dataset[name].values
        )

    except Exception:
        return "unknown"


# ============================================================
# VARIABLE DETECTION
# ============================================================

def find_wind_variables(dataset):

    u_candidates = [
        "u10",
        "10u",
    ]

    v_candidates = [
        "v10",
        "10v",
    ]

    u_name = next(
        (
            name
            for name in u_candidates
            if name in dataset.data_vars
        ),
        None,
    )

    v_name = next(
        (
            name
            for name in v_candidates
            if name in dataset.data_vars
        ),
        None,
    )

    if (
        u_name is None
        or v_name is None
    ):
        raise KeyError(
            "Could not find 10 m wind variables. "
            f"Available: {list(dataset.data_vars)}"
        )

    return u_name, v_name


# ============================================================
# ROBUST NEAREST POINT
# ============================================================

def select_nearest_ecmwf_point(
    dataset,
    target_lat,
    target_lon,
):
    """
    Select nearest ECMWF grid point.

    Handles both:

    1. Regular latitude/longitude grids
    2. Reduced/paired ECMWF GRIB grids where latitude and
       longitude share a single 'values' dimension
    """

    if "latitude" not in dataset.coords:
        raise KeyError(
            "Dataset has no latitude coordinate."
        )

    if "longitude" not in dataset.coords:
        raise KeyError(
            "Dataset has no longitude coordinate."
        )

    lat_coord = dataset["latitude"]
    lon_coord = dataset["longitude"]

    lat_values = np.asarray(
        lat_coord.values,
        dtype=float,
    )

    lon_values = (
        longitude_to_minus180_180(
            lon_coord.values
        )
    )

    target_lon = float(
        longitude_to_minus180_180(
            target_lon
        )
    )

    # --------------------------------------------------------
    # CASE 1
    # Regular independent latitude / longitude dimensions
    # --------------------------------------------------------

    if (
        lat_coord.ndim == 1
        and lon_coord.ndim == 1
        and lat_coord.dims
        != lon_coord.dims
    ):

        target_lon_native = (
            target_lon + 360.0
            if (
                np.nanmax(
                    lon_coord.values
                ) > 180.0
                and target_lon < 0.0
            )
            else target_lon
        )

        point = dataset.sel(
            latitude=float(
                target_lat
            ),
            longitude=float(
                target_lon_native
            ),
            method="nearest",
        )

        actual_lat = scalar_float(
            point["latitude"]
        )

        actual_lon = float(
            longitude_to_minus180_180(
                scalar_float(
                    point["longitude"]
                )
            )
        )

        distance_km = float(
            haversine_distance_km(
                actual_lat,
                actual_lon,
                target_lat,
                target_lon,
            )
        )

        return (
            point,
            actual_lat,
            actual_lon,
            distance_km,
            "regular lat/lon grid",
        )

    # --------------------------------------------------------
    # CASE 2
    # Paired / reduced grid
    # --------------------------------------------------------

    if (
        lat_values.shape
        == lon_values.shape
    ):

        distances = (
            haversine_distance_km(
                lat_values,
                lon_values,
                target_lat,
                target_lon,
            )
        )

        flat_index = int(
            np.nanargmin(
                distances
            )
        )

        index_tuple = (
            np.unravel_index(
                flat_index,
                lat_values.shape,
            )
        )

        indexers = {}

        for dim, index in zip(
            lat_coord.dims,
            index_tuple,
        ):
            indexers[dim] = int(
                index
            )

        point = dataset.isel(
            indexers
        )

        actual_lat = float(
            lat_values[
                index_tuple
            ]
        )

        actual_lon = float(
            lon_values[
                index_tuple
            ]
        )

        distance_km = float(
            distances[
                index_tuple
            ]
        )

        return (
            point,
            actual_lat,
            actual_lon,
            distance_km,
            "paired/reduced ECMWF grid",
        )

    raise RuntimeError(
        "Unsupported ECMWF latitude/longitude grid layout. "
        f"latitude shape={lat_values.shape}, "
        f"longitude shape={lon_values.shape}, "
        f"latitude dims={lat_coord.dims}, "
        f"longitude dims={lon_coord.dims}"
    )


# ============================================================
# MAIN
# ============================================================

print("=" * 76)
print(
    "POLARGUARD - ECMWF ANTARCTIC WIND EXTRACTION"
)
print("=" * 76)

if not GRIB_FILE.exists():

    raise FileNotFoundError(
        f"GRIB file not found: "
        f"{GRIB_FILE.resolve()}"
    )


print()
print(
    f"GRIB file        : "
    f"{GRIB_FILE.resolve()}"
)

print(
    f"Requested lat    : "
    f"{TARGET_LAT}"
)

print(
    f"Requested lon    : "
    f"{TARGET_LON}"
)


# ============================================================
# OPEN GRIB
# ============================================================

print()
print(
    "Opening ECMWF GRIB2..."
)

dataset = xr.open_dataset(
    GRIB_FILE,
    engine="cfgrib",
)

print(
    "GRIB2 opened successfully."
)


# ============================================================
# INSPECT GRID
# ============================================================

print()
print("-" * 76)
print(
    "DATASET INFORMATION"
)
print("-" * 76)

print(
    f"Dimensions       : "
    f"{dict(dataset.sizes)}"
)

print(
    f"Variables        : "
    f"{list(dataset.data_vars)}"
)

print(
    f"Coordinates      : "
    f"{list(dataset.coords)}"
)

print(
    f"Latitude shape   : "
    f"{dataset['latitude'].shape}"
)

print(
    f"Longitude shape  : "
    f"{dataset['longitude'].shape}"
)

print(
    f"Latitude dims    : "
    f"{dataset['latitude'].dims}"
)

print(
    f"Longitude dims   : "
    f"{dataset['longitude'].dims}"
)


# ============================================================
# FIND VARIABLES
# ============================================================

u_name, v_name = (
    find_wind_variables(
        dataset
    )
)


# ============================================================
# FIND TRUE NEAREST POINT
# ============================================================

(
    point,
    actual_lat,
    actual_lon,
    distance_km,
    grid_type,
) = select_nearest_ecmwf_point(
    dataset,
    TARGET_LAT,
    TARGET_LON,
)


# ============================================================
# EXTRACT WIND
# ============================================================

u10 = scalar_float(
    point[u_name]
)

v10 = scalar_float(
    point[v_name]
)

wind_speed = math.hypot(
    u10,
    v10,
)


# ============================================================
# TIME INFORMATION
# ============================================================

model_time = (
    scalar_string(
        point,
        "time",
    )
)

forecast_step = (
    scalar_string(
        point,
        "step",
    )
)

valid_time = (
    scalar_string(
        point,
        "valid_time",
    )
)


# ============================================================
# DISPLAY
# ============================================================

print()
print("=" * 76)
print(
    "ECMWF WIND RESULT"
)
print("=" * 76)

print()
print(
    "Requested iceberg location"
)

print(
    f"Latitude                 : "
    f"{TARGET_LAT:.4f}"
)

print(
    f"Longitude                : "
    f"{TARGET_LON:.4f}"
)


print()
print(
    "Nearest ECMWF grid point"
)

print(
    f"Grid type                : "
    f"{grid_type}"
)

print(
    f"Latitude                 : "
    f"{actual_lat:.4f}"
)

print(
    f"Longitude                : "
    f"{actual_lon:.4f}"
)

print(
    f"Distance from request    : "
    f"{distance_km:.2f} km"
)


print()
print(
    "Wind"
)

print(
    f"Variable U               : "
    f"{u_name}"
)

print(
    f"Variable V               : "
    f"{v_name}"
)

print(
    f"10 m U wind              : "
    f"{u10:.4f} m/s"
)

print(
    f"10 m V wind              : "
    f"{v10:.4f} m/s"
)

print(
    f"10 m wind speed          : "
    f"{wind_speed:.4f} m/s"
)


print()
print(
    "ECMWF timing"
)

print(
    f"Model initialization     : "
    f"{model_time}"
)

print(
    f"Forecast step            : "
    f"{forecast_step}"
)

print(
    f"Valid time               : "
    f"{valid_time}"
)


# ============================================================
# FINAL SANITY CHECK
# ============================================================

print()
print("-" * 76)
print(
    "GEOGRAPHIC SANITY CHECK"
)
print("-" * 76)

lon_error = abs(
    (
        actual_lon
        - TARGET_LON
        + 180.0
    )
    % 360.0
    - 180.0
)

lat_error = abs(
    actual_lat
    - TARGET_LAT
)

print(
    f"Latitude difference      : "
    f"{lat_error:.4f}°"
)

print(
    f"Longitude difference     : "
    f"{lon_error:.4f}°"
)


if distance_km > 100.0:

    raise RuntimeError(
        "Nearest ECMWF grid point is more than "
        "100 km from the requested iceberg position. "
        "Do not use this wind value."
    )


print()
print("=" * 76)
print(
    "ECMWF Antarctic wind extraction: READY"
)
print(
    "Geographic nearest-point check : PASSED"
)
print("=" * 76)


dataset.close()