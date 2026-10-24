from pathlib import Path

import numpy as np
import xarray as xr

from pyproj import Transformer

from sea_ice_service import (
    predict_sea_ice,
    load_uncertainty,
)


# ============================================================
# CONFIGURATION
# ============================================================

SEA_ICE_HISTORY_FILE = Path(
    "data/processed/sea_ice_2019_2025.nc"
)


# Number of original NSIDC grid cells represented by
# one Cesium display point/polygon sample.
#
# Larger number = faster visualization.
# Smaller number = more detail.
DEFAULT_SAMPLE_STEP = 8


# Ignore extremely small SIC values for the 3D display.
DEFAULT_MIN_SIC = 0.05


# ============================================================
# LOAD FROZEN MEMBER 1 HISTORY
# ============================================================

def load_sea_ice_history():

    if not SEA_ICE_HISTORY_FILE.exists():

        raise FileNotFoundError(
            f"Sea-ice file not found: "
            f"{SEA_ICE_HISTORY_FILE.resolve()}"
        )

    return xr.open_dataarray(
        SEA_ICE_HISTORY_FILE
    )


# ============================================================
# MEMBER 1 SYNCHRONIZED FORECAST BUNDLE
# ============================================================

def get_member1_bundle(
    initialization_date
):

    ds = load_sea_ice_history()

    try:

        target_date = np.datetime64(
            initialization_date,
            "D",
        )

        dates = (
            ds.time.values
            .astype("datetime64[D]")
        )

        matches = np.where(
            dates == target_date
        )[0]

        if len(matches) == 0:

            raise ValueError(
                "Sea-ice history does not contain "
                f"{initialization_date}."
            )

        current_index = int(
            matches[0]
        )

        if current_index < 3:

            raise ValueError(
                "At least three previous daily "
                "sea-ice observations are required."
            )


        current = np.asarray(
            ds.values[current_index],
            dtype=np.float32,
        )

        lag1 = np.asarray(
            ds.values[current_index - 1],
            dtype=np.float32,
        )

        lag2 = np.asarray(
            ds.values[current_index - 2],
            dtype=np.float32,
        )

        lag3 = np.asarray(
            ds.values[current_index - 3],
            dtype=np.float32,
        )


        x_coords = np.asarray(
            ds.x.values,
            dtype=float,
        )

        y_coords = np.asarray(
            ds.y.values,
            dtype=float,
        )


        forecasts = predict_sea_ice(

            current=current,

            lag1=lag1,

            lag2=lag2,

            lag3=lag3,

            x_coords=x_coords,

            y_coords=y_coords,

            # IMPORTANT:
            # Frozen Member 1 service expects NumPy datetime64.
            date=target_date,
        )


        uncertainty = (
            load_uncertainty()
        )


        return {

            "date":
                str(target_date),

            "current":
                current,

            "forecast_24h":
                np.asarray(
                    forecasts["24h"],
                    dtype=float,
                ),

            "forecast_48h":
                np.asarray(
                    forecasts["48h"],
                    dtype=float,
                ),

            "forecast_72h":
                np.asarray(
                    forecasts["72h"],
                    dtype=float,
                ),

            "uncertainty_24h":
                np.asarray(
                    uncertainty["24h"],
                    dtype=float,
                ),

            "uncertainty_48h":
                np.asarray(
                    uncertainty["48h"],
                    dtype=float,
                ),

            "uncertainty_72h":
                np.asarray(
                    uncertainty["72h"],
                    dtype=float,
                ),

            "x":
                x_coords,

            "y":
                y_coords,
        }

    finally:

        ds.close()


# ============================================================
# EPSG:3412 -> WGS84
# ============================================================

def projected_grid_to_latlon(
    x_coords,
    y_coords,
):

    x_grid, y_grid = np.meshgrid(

        np.asarray(
            x_coords,
            dtype=float,
        ),

        np.asarray(
            y_coords,
            dtype=float,
        ),
    )


    transformer = Transformer.from_crs(

        "EPSG:3412",

        "EPSG:4326",

        always_xy=True,
    )


    grid_lon, grid_lat = (
        transformer.transform(
            x_grid,
            y_grid,
        )
    )


    return (

        np.asarray(
            grid_lat,
            dtype=float,
        ),

        np.asarray(
            grid_lon,
            dtype=float,
        ),
    )


# ============================================================
# SIC COLOR
# ============================================================

def sic_color_rgba(
    value
):

    value = float(
        np.clip(
            value,
            0.0,
            1.0,
        )
    )


    if value < 0.10:

        return [
            239,
            246,
            255,
            90,
        ]


    if value < 0.30:

        return [
            219,
            234,
            254,
            120,
        ]


    if value < 0.50:

        return [
            191,
            219,
            254,
            145,
        ]


    if value < 0.70:

        return [
            147,
            197,
            253,
            170,
        ]


    if value < 0.90:

        return [
            96,
            165,
            250,
            195,
        ]


    return [
        37,
        99,
        235,
        220,
    ]


# ============================================================
# UNCERTAINTY COLOR
# ============================================================

def uncertainty_color_rgba(
    value
):

    if not np.isfinite(value):

        return [
            0,
            0,
            0,
            0,
        ]


    normalized = float(
        np.clip(
            value / 0.10,
            0.0,
            1.0,
        )
    )


    alpha = int(
        40
        +
        normalized * 150
    )


    return [
        245,
        158,
        11,
        alpha,
    ]


# ============================================================
# BUILD CESIUM DISPLAY CELLS
# ============================================================

def build_display_cells(
    values,
    grid_lat,
    grid_lon,
    sample_step=DEFAULT_SAMPLE_STEP,
    minimum_value=DEFAULT_MIN_SIC,
):

    values = np.asarray(
        values,
        dtype=float,
    )

    grid_lat = np.asarray(
        grid_lat,
        dtype=float,
    )

    grid_lon = np.asarray(
        grid_lon,
        dtype=float,
    )


    if (
        values.shape
        != grid_lat.shape
        or
        values.shape
        != grid_lon.shape
    ):

        raise ValueError(
            "Values, latitude and longitude "
            "grids must have matching shapes."
        )


    cells = []


    rows, cols = (
        values.shape
    )


    for row in range(
        0,
        rows,
        sample_step,
    ):

        for col in range(
            0,
            cols,
            sample_step,
        ):

            value = values[
                row,
                col
            ]


            latitude = grid_lat[
                row,
                col
            ]


            longitude = grid_lon[
                row,
                col
            ]


            if not (
                np.isfinite(value)
                and
                np.isfinite(latitude)
                and
                np.isfinite(longitude)
            ):

                continue


            if value < minimum_value:

                continue


            cells.append({

                "latitude":
                    float(latitude),

                "longitude":
                    float(longitude),

                "value":
                    float(value),

                "percentage":
                    float(
                        value * 100.0
                    ),

                "color":
                    sic_color_rgba(
                        value
                    ),
            })


    return cells


# ============================================================
# BUILD UNCERTAINTY DISPLAY
# ============================================================

def build_uncertainty_cells(
    values,
    grid_lat,
    grid_lon,
    sample_step=DEFAULT_SAMPLE_STEP,
):

    values = np.asarray(
        values,
        dtype=float,
    )

    cells = []


    rows, cols = (
        values.shape
    )


    for row in range(
        0,
        rows,
        sample_step,
    ):

        for col in range(
            0,
            cols,
            sample_step,
        ):

            value = values[
                row,
                col
            ]


            latitude = grid_lat[
                row,
                col
            ]


            longitude = grid_lon[
                row,
                col
            ]


            if not (
                np.isfinite(value)
                and
                np.isfinite(latitude)
                and
                np.isfinite(longitude)
            ):

                continue


            cells.append({

                "latitude":
                    float(latitude),

                "longitude":
                    float(longitude),

                "value":
                    float(value),

                "percentage_points":
                    float(
                        value * 100.0
                    ),

                "color":
                    uncertainty_color_rgba(
                        value
                    ),
            })


    return cells


# ============================================================
# BASIC GRID STATISTICS
# ============================================================

def grid_statistics(
    values
):

    values = np.asarray(
        values,
        dtype=float,
    )


    valid = values[
        np.isfinite(values)
    ]


    if valid.size == 0:

        return {

            "valid_cells":
                0,

            "mean":
                None,

            "minimum":
                None,

            "maximum":
                None,
        }


    return {

        "valid_cells":
            int(
                valid.size
            ),

        "mean":
            float(
                np.mean(valid)
            ),

        "minimum":
            float(
                np.min(valid)
            ),

        "maximum":
            float(
                np.max(valid)
            ),
    }


# ============================================================
# BUILD COMPLETE CESIUM SEA-ICE PACKAGE
# ============================================================

def build_sea_ice_visualization(
    initialization_date,
    sample_step=DEFAULT_SAMPLE_STEP,
):

    bundle = get_member1_bundle(
        initialization_date
    )


    grid_lat, grid_lon = (
        projected_grid_to_latlon(

            bundle["x"],

            bundle["y"],
        )
    )


    horizon_mapping = {

        "current": {
            "sic":
                bundle[
                    "current"
                ],

            "uncertainty":
                None,
        },


        "24h": {
            "sic":
                bundle[
                    "forecast_24h"
                ],

            "uncertainty":
                bundle[
                    "uncertainty_24h"
                ],
        },


        "48h": {
            "sic":
                bundle[
                    "forecast_48h"
                ],

            "uncertainty":
                bundle[
                    "uncertainty_48h"
                ],
        },


        "72h": {
            "sic":
                bundle[
                    "forecast_72h"
                ],

            "uncertainty":
                bundle[
                    "uncertainty_72h"
                ],
        },
    }


    horizons = {}


    for horizon, data in (
        horizon_mapping.items()
    ):

        sic_values = data[
            "sic"
        ]


        uncertainty_values = data[
            "uncertainty"
        ]


        horizon_result = {

            "sic_cells":
                build_display_cells(

                    sic_values,

                    grid_lat,

                    grid_lon,

                    sample_step=
                        sample_step,
                ),


            "sic_statistics":
                grid_statistics(
                    sic_values
                ),
        }


        if (
            uncertainty_values
            is not None
        ):

            horizon_result[
                "uncertainty_cells"
            ] = (
                build_uncertainty_cells(

                    uncertainty_values,

                    grid_lat,

                    grid_lon,

                    sample_step=
                        sample_step,
                )
            )


            horizon_result[
                "uncertainty_statistics"
            ] = (
                grid_statistics(
                    uncertainty_values
                )
            )


        else:

            horizon_result[
                "uncertainty_cells"
            ] = []


            horizon_result[
                "uncertainty_statistics"
            ] = None


        horizons[
            horizon
        ] = horizon_result


    return {

        "system":
            "PolarGuard",

        "initialization_date":
            bundle["date"],

        "coordinate_system":
            "WGS84 / EPSG:4326",

        "source_grid":
            "NSIDC EPSG:3412",

        "sample_step":
            int(
                sample_step
            ),

        "full_grid_shape": [
            int(
                grid_lat.shape[0]
            ),
            int(
                grid_lat.shape[1]
            ),
        ],

        "model_version":
            "hybrid-v1-frozen",

        "horizons":
            horizons,

        "disclaimer": (
            "Sea-ice cells are downsampled "
            "for Cesium visualization only. "
            "PolarGuard forecasting and routing "
            "continue to use the full-resolution grid."
        ),
    }


# ============================================================
# SIMPLE LOCAL TEST
# ============================================================

if __name__ == "__main__":

    print(
        "POLARGUARD CESIUM DATA SERVICE TEST"
    )

    print(
        "=================================="
    )


    result = (
        build_sea_ice_visualization(
            "2025-12-28",
            sample_step=12,
        )
    )


    print(
        "Initialization:",
        result[
            "initialization_date"
        ],
    )


    print(
        "Full grid:",
        result[
            "full_grid_shape"
        ],
    )


    print(
        "Current display cells:",
        len(
            result[
                "horizons"
            ][
                "current"
            ][
                "sic_cells"
            ]
        ),
    )


    print(
        "+24h display cells:",
        len(
            result[
                "horizons"
            ][
                "24h"
            ][
                "sic_cells"
            ]
        ),
    )


    print(
        "+48h display cells:",
        len(
            result[
                "horizons"
            ][
                "48h"
            ][
                "sic_cells"
            ]
        ),
    )


    print(
        "+72h display cells:",
        len(
            result[
                "horizons"
            ][
                "72h"
            ][
                "sic_cells"
            ]
        ),
    )


    print(
        "CESIUM DATA SERVICE TEST COMPLETE"
    )