import sys
import json
import math
from pathlib import Path

import numpy as np
import xarray as xr


GRIB_FILE = Path(
    "data/environment_cache/ecmwf/latest_wind.grib2"
)


def longitude_to_minus180_180(lon):
    lon = np.asarray(lon, dtype=float)
    return ((lon + 180.0) % 360.0) - 180.0


def haversine_distance_km(
    lat1,
    lon1,
    lat2,
    lon2,
):
    earth_radius_km = 6371.0088

    lat1 = np.radians(
        np.asarray(lat1, dtype=float)
    )
    lon1 = np.radians(
        np.asarray(lon1, dtype=float)
    )

    lat2 = math.radians(float(lat2))
    lon2 = math.radians(float(lon2))

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
    arr = np.asarray(
        value.values
        if hasattr(value, "values")
        else value
    )
    return float(arr.squeeze())


def scalar_string(dataset, name):
    if name not in dataset.coords:
        return None

    try:
        return str(dataset[name].values)
    except Exception:
        return None


def find_wind_variables(dataset):
    u_name = None
    v_name = None

    for name in ["u10", "10u"]:
        if name in dataset.data_vars:
            u_name = name
            break

    for name in ["v10", "10v"]:
        if name in dataset.data_vars:
            v_name = name
            break

    if u_name is None or v_name is None:
        raise KeyError(
            f"Wind variables not found. "
            f"Available: {list(dataset.data_vars)}"
        )

    return u_name, v_name


def select_nearest_point(
    dataset,
    target_lat,
    target_lon,
):
    lat_coord = dataset["latitude"]
    lon_coord = dataset["longitude"]

    lat_values = np.asarray(
        lat_coord.values,
        dtype=float,
    )

    lon_values = longitude_to_minus180_180(
        lon_coord.values
    )

    target_lon = float(
        longitude_to_minus180_180(
            target_lon
        )
    )

    # Regular latitude / longitude grid
    if (
        lat_coord.ndim == 1
        and lon_coord.ndim == 1
        and lat_coord.dims != lon_coord.dims
    ):
        native_lon_values = np.asarray(
            lon_coord.values,
            dtype=float,
        )

        target_lon_native = target_lon

        if (
            np.nanmax(native_lon_values) > 180.0
            and target_lon < 0.0
        ):
            target_lon_native = (
                target_lon + 360.0
            )

        point = dataset.sel(
            latitude=float(target_lat),
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
        )

    # Paired/reduced grid
    if lat_values.shape == lon_values.shape:
        distances = haversine_distance_km(
            lat_values,
            lon_values,
            target_lat,
            target_lon,
        )

        flat_index = int(
            np.nanargmin(distances)
        )

        index_tuple = np.unravel_index(
            flat_index,
            lat_values.shape,
        )

        indexers = {}

        for dim, index in zip(
            lat_coord.dims,
            index_tuple,
        ):
            indexers[dim] = int(index)

        point = dataset.isel(
            indexers
        )

        actual_lat = float(
            lat_values[index_tuple]
        )

        actual_lon = float(
            lon_values[index_tuple]
        )

        distance_km = float(
            distances[index_tuple]
        )

        return (
            point,
            actual_lat,
            actual_lon,
            distance_km,
        )

    raise RuntimeError(
        "Unsupported ECMWF grid structure."
    )


def extract_wind(
    latitude,
    longitude,
):
    if not GRIB_FILE.exists():
        raise FileNotFoundError(
            f"GRIB file not found: "
            f"{GRIB_FILE.resolve()}"
        )

    dataset = xr.open_dataset(
        GRIB_FILE,
        engine="cfgrib",
    )

    try:
        u_name, v_name = (
            find_wind_variables(
                dataset
            )
        )

        (
            point,
            actual_lat,
            actual_lon,
            distance_km,
        ) = select_nearest_point(
            dataset,
            latitude,
            longitude,
        )

        if distance_km > 100.0:
            raise RuntimeError(
                "Nearest ECMWF grid point is "
                "more than 100 km away."
            )

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

        return {
            "success": True,

            "source": (
                "ECMWF Open Data IFS"
            ),

            "u10": u10,
            "v10": v10,

            "wind_speed_ms": (
                wind_speed
            ),

            "requested_latitude": (
                float(latitude)
            ),

            "requested_longitude": (
                float(longitude)
            ),

            "grid_latitude": (
                actual_lat
            ),

            "grid_longitude": (
                actual_lon
            ),

            "distance_km": (
                distance_km
            ),

            "model_initialization": (
                scalar_string(
                    point,
                    "time",
                )
            ),

            "forecast_step": (
                scalar_string(
                    point,
                    "step",
                )
            ),

            "valid_time": (
                scalar_string(
                    point,
                    "valid_time",
                )
            ),
        }

    finally:
        dataset.close()


def main():
    try:
        if len(sys.argv) != 3:
            raise ValueError(
                "Usage: "
                "python ecmwf_wind_bridge.py "
                "<latitude> <longitude>"
            )

        latitude = float(
            sys.argv[1]
        )

        longitude = float(
            sys.argv[2]
        )

        result = extract_wind(
            latitude,
            longitude,
        )

        print(
            json.dumps(
                result,
                separators=(",", ":"),
            )
        )

    except Exception as error:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": str(error),
                },
                separators=(",", ":"),
            )
        )
        sys.exit(1)


if __name__ == "__main__":
    main()