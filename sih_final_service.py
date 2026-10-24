from pathlib import Path

import numpy as np
import xarray as xr

from pyproj import Transformer

from sea_ice_service import (
    predict_sea_ice,
    load_uncertainty,
)

from polarguard_pipeline import (
    run_polarguard,
)

from navigation_service import (
    build_navigation_route,
)

from hazard_engine import (
    build_hazard_zones,
    analyze_route_hazards,
    generate_route_alerts,
    summarize_hazard_grid,
)

from alternative_routing import (
    build_alternative_route,
    compare_routes,
)

from cesium_data_service import (
    build_sea_ice_visualization,
)


# ============================================================
# CONFIGURATION
# ============================================================

SEA_ICE_HISTORY_FILE = Path(
    "data/processed/sea_ice_2019_2025.nc"
)

SUPPORTED_HORIZONS = (
    "24h",
    "48h",
    "72h",
)

VESSEL_PROFILE_ALIASES = {

    "LOW":
        "LOW_ICE_CAPABILITY",

    "LOW_ICE_CAPABILITY":
        "LOW_ICE_CAPABILITY",

    "MEDIUM":
        "MEDIUM_ICE_CAPABILITY",

    "MEDIUM_ICE_CAPABILITY":
        "MEDIUM_ICE_CAPABILITY",

    "HIGH":
        "HIGH_ICE_CAPABILITY",

    "HIGH_ICE_CAPABILITY":
        "HIGH_ICE_CAPABILITY",
}


# ============================================================
# BASIC VALIDATION
# ============================================================

def _finite_float(
    value,
    name,
):

    try:
        number = float(value)

    except Exception as exc:

        raise ValueError(
            f"{name} must be numeric."
        ) from exc

    if not np.isfinite(number):

        raise ValueError(
            f"{name} must be finite."
        )

    return number


def _validate_latitude(
    value,
    name,
):

    value = _finite_float(
        value,
        name,
    )

    if not (
        -90.0
        <= value
        <= -40.0
    ):

        raise ValueError(
            f"{name} must be between "
            "-90 and -40 degrees "
            "for the Antarctic prototype."
        )

    return value


def _validate_longitude(
    value,
    name,
):

    value = _finite_float(
        value,
        name,
    )

    if not (
        -180.0
        <= value
        <= 180.0
    ):

        raise ValueError(
            f"{name} must be between "
            "-180 and 180 degrees."
        )

    return value


# ============================================================
# HORIZON NORMALIZATION
# ============================================================

def normalize_horizon(
    horizon,
):

    value = str(
        horizon
    ).strip().lower()

    value = value.replace(
        "+",
        "",
    )

    aliases = {

        "24":
            "24h",

        "24h":
            "24h",

        "48":
            "48h",

        "48h":
            "48h",

        "72":
            "72h",

        "72h":
            "72h",
    }

    if value not in aliases:

        raise ValueError(
            "Routing horizon must be "
            "24h, 48h or 72h."
        )

    return aliases[value]


# ============================================================
# VESSEL PROFILE NORMALIZATION
# ============================================================

def normalize_vessel_profile(
    vessel_profile,
):

    value = (
        str(
            vessel_profile
        )
        .strip()
        .upper()
        .replace(
            " ",
            "_",
        )
    )

    if value not in (
        VESSEL_PROFILE_ALIASES
    ):

        raise ValueError(
            "Vessel profile must be "
            "LOW, MEDIUM or HIGH."
        )

    return (
        VESSEL_PROFILE_ALIASES[
            value
        ]
    )


# ============================================================
# LOAD MEMBER 1 HISTORY
# ============================================================

def load_member1_history():
    dataset_path = SEA_ICE_HISTORY_FILE

    if not dataset_path.is_file():
        try:
            import streamlit as st
            from huggingface_hub import hf_hub_download

            dataset_path = Path(
                hf_hub_download(
                    repo_id="divyanshmahesh/PolarGuard-Data",
                    filename="sea_ice_2019_2025.nc",
                    repo_type="dataset",
                    token=st.secrets["HF_TOKEN"],
                )
            )
        except Exception as exc:
            raise FileNotFoundError(
                "Member 1 sea-ice history is missing locally, and its "
                "Hugging Face download failed. Check the HF_TOKEN "
                "Streamlit secret and access to the PolarGuard-Data dataset."
            ) from exc

    return xr.open_dataarray(dataset_path)

# ============================================================
# BUILD MEMBER 1 FORECAST BUNDLE
# ============================================================

def get_member1_bundle(
    initialization_date,
):

    ds = load_member1_history()

    try:

        target_date = np.datetime64(
            initialization_date,
            "D",
        )

        dates = (
            ds.time.values
            .astype(
                "datetime64[D]"
            )
        )

        matches = np.where(
            dates
            ==
            target_date
        )[0]

        if len(matches) == 0:

            raise ValueError(
                "Sea-ice history does not "
                f"contain {initialization_date}."
            )

        current_index = int(
            matches[0]
        )

        if current_index < 3:

            raise ValueError(
                "At least three previous "
                "daily sea-ice maps are "
                "required."
            )

        current = np.asarray(
            ds.values[
                current_index
            ],
            dtype=np.float32,
        )

        lag1 = np.asarray(
            ds.values[
                current_index - 1
            ],
            dtype=np.float32,
        )

        lag2 = np.asarray(
            ds.values[
                current_index - 2
            ],
            dtype=np.float32,
        )

        lag3 = np.asarray(
            ds.values[
                current_index - 3
            ],
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

        forecasts = (
            predict_sea_ice(

                current=current,

                lag1=lag1,

                lag2=lag2,

                lag3=lag3,

                x_coords=x_coords,

                y_coords=y_coords,

                date=target_date,
            )
        )

        uncertainty = (
            load_uncertainty()
        )

        return {

            "date":
                str(
                    target_date
                ),

            "current":
                current,

            "forecast_24h":
                np.asarray(
                    forecasts[
                        "24h"
                    ],
                    dtype=float,
                ),

            "forecast_48h":
                np.asarray(
                    forecasts[
                        "48h"
                    ],
                    dtype=float,
                ),

            "forecast_72h":
                np.asarray(
                    forecasts[
                        "72h"
                    ],
                    dtype=float,
                ),

            "uncertainty_24h":
                np.asarray(
                    uncertainty[
                        "24h"
                    ],
                    dtype=float,
                ),

            "uncertainty_48h":
                np.asarray(
                    uncertainty[
                        "48h"
                    ],
                    dtype=float,
                ),

            "uncertainty_72h":
                np.asarray(
                    uncertainty[
                        "72h"
                    ],
                    dtype=float,
                ),

            "x":
                x_coords,

            "y":
                y_coords,
        }

    finally:

        try:
            ds.close()

        except Exception:
            pass


# ============================================================
# PROJECT MEMBER 1 GRID TO WGS84
# ============================================================

def projected_grid_to_latlon(
    x_coords,
    y_coords,
):

    x_grid, y_grid = (
        np.meshgrid(

            np.asarray(
                x_coords,
                dtype=float,
            ),

            np.asarray(
                y_coords,
                dtype=float,
            ),
        )
    )

    transformer = (
        Transformer.from_crs(

            "EPSG:3412",

            "EPSG:4326",

            always_xy=True,
        )
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
# ROUTE -> GEOJSON
# ============================================================

def route_to_geojson(
    route,
    route_name,
    routing_horizon,
    vessel_profile,
    safety_radius_km,
    overlap_percent=None,
):

    if (
        route is None
        or
        not route.get(
            "path_coordinates"
        )
    ):

        return None

    properties = {

        "name":
            route_name,

        "system":
            "PolarGuard",

        "product_type":
            (
                "prototype "
                "decision-support route"
            ),

        "routing_horizon":
            routing_horizon,

        "vessel_profile":
            vessel_profile,

        "safety_radius_km":
            float(
                safety_radius_km
            ),

        "distance_km":
            float(
                route[
                    "total_distance_km"
                ]
            ),
    }

    if (
        overlap_percent
        is not None
    ):

        properties[
            "route_overlap_percent"
        ] = float(
            overlap_percent
        )

    coordinates = [

        [
            float(
                point[
                    "longitude"
                ]
            ),

            float(
                point[
                    "latitude"
                ]
            ),
        ]

        for point
        in route[
            "path_coordinates"
        ]
    ]

    return {

        "type":
            "FeatureCollection",

        "features": [

            {

                "type":
                    "Feature",

                "properties":
                    properties,

                "geometry": {

                    "type":
                        "LineString",

                    "coordinates":
                        coordinates,
                },
            }
        ],
    }


# ============================================================
# SIMPLE NUMPY -> JSON CONVERTER
# ============================================================

def to_builtin(
    value,
):

    if isinstance(
        value,
        np.ndarray,
    ):

        return value.tolist()

    if isinstance(
        value,
        np.integer,
    ):

        return int(
            value
        )

    if isinstance(
        value,
        np.floating,
    ):

        number = float(
            value
        )

        if np.isfinite(
            number
        ):

            return number

        return None

    if isinstance(
        value,
        np.bool_,
    ):

        return bool(
            value
        )

    if isinstance(
        value,
        dict,
    ):

        return {

            str(key):
                to_builtin(
                    item
                )

            for key, item
            in value.items()
        }

    if isinstance(
        value,
        (
            list,
            tuple,
        ),
    ):

        return [

            to_builtin(
                item
            )

            for item
            in value
        ]

    return value


# ============================================================
# BUILD ICEBERG TRAJECTORY PACKAGE
# ============================================================

def build_iceberg_package(
    combined_result,
    history,
):

    iceberg_result = (
        combined_result[
            "iceberg"
        ]
    )

    forecasts = (
        iceberg_result[
            "forecast"
        ]
    )

    current = (
        history[
            "current"
        ]
    )

    return {

        "history": [

            {
                "stage":
                    "t-3",

                "latitude":
                    float(
                        history[
                            "lat_tm3"
                        ]
                    ),

                "longitude":
                    float(
                        history[
                            "lon_tm3"
                        ]
                    ),
            },

            {
                "stage":
                    "t-2",

                "latitude":
                    float(
                        history[
                            "lat_tm2"
                        ]
                    ),

                "longitude":
                    float(
                        history[
                            "lon_tm2"
                        ]
                    ),
            },

            {
                "stage":
                    "t-1",

                "latitude":
                    float(
                        history[
                            "lat_tm1"
                        ]
                    ),

                "longitude":
                    float(
                        history[
                            "lon_tm1"
                        ]
                    ),
            },
        ],

        "current": {

            "stage":
                "current",

            "latitude":
                float(
                    current[
                        "latitude"
                    ]
                ),

            "longitude":
                float(
                    current[
                        "longitude"
                    ]
                ),
        },

        "forecast": {

            "24h":
                to_builtin(
                    forecasts[
                        "24h"
                    ]
                ),

            "48h":
                to_builtin(
                    forecasts[
                        "48h"
                    ]
                ),

            "72h":
                to_builtin(
                    forecasts[
                        "72h"
                    ]
                ),
        },

        "local_sea_ice":
            to_builtin(
                combined_result.get(
                    "sea_ice",
                    {},
                )
            ),

        "planning_buffer_km":
            10.0,

        "model_version":
            "environment-v1-frozen",
    }


# ============================================================
# RUN COMPLETE POLARGUARD MISSION
# ============================================================

def run_sih_mission(

    initialization_date,

    lat_tm3,
    lon_tm3,

    lat_tm2,
    lon_tm2,

    lat_tm1,
    lon_tm1,

    current_latitude,
    current_longitude,

    wind_u10,
    wind_v10,

    ocean_uo,
    ocean_vo,

    routing_horizon,

    start_lat,
    start_lon,

    destination_lat,
    destination_lon,

    vessel_profile="MEDIUM",

    safety_radius_km=10.0,

    sample_step=6,
):

    # ========================================================
    # NORMALIZE INPUTS
    # ========================================================

    routing_horizon = (
        normalize_horizon(
            routing_horizon
        )
    )

    vessel_profile = (
        normalize_vessel_profile(
            vessel_profile
        )
    )


    # ========================================================
    # VALIDATE ICEBERG POSITIONS
    # ========================================================

    lat_tm3 = _validate_latitude(
        lat_tm3,
        "lat_tm3",
    )

    lon_tm3 = _validate_longitude(
        lon_tm3,
        "lon_tm3",
    )

    lat_tm2 = _validate_latitude(
        lat_tm2,
        "lat_tm2",
    )

    lon_tm2 = _validate_longitude(
        lon_tm2,
        "lon_tm2",
    )

    lat_tm1 = _validate_latitude(
        lat_tm1,
        "lat_tm1",
    )

    lon_tm1 = _validate_longitude(
        lon_tm1,
        "lon_tm1",
    )

    current_latitude = (
        _validate_latitude(
            current_latitude,
            "current_latitude",
        )
    )

    current_longitude = (
        _validate_longitude(
            current_longitude,
            "current_longitude",
        )
    )


    # ========================================================
    # VALIDATE ROUTE ENDPOINTS
    # ========================================================

    start_lat = _validate_latitude(
        start_lat,
        "start_lat",
    )

    start_lon = _validate_longitude(
        start_lon,
        "start_lon",
    )

    destination_lat = (
        _validate_latitude(
            destination_lat,
            "destination_lat",
        )
    )

    destination_lon = (
        _validate_longitude(
            destination_lon,
            "destination_lon",
        )
    )


    # ========================================================
    # VALIDATE ENVIRONMENT
    # ========================================================

    wind_u10 = _finite_float(
        wind_u10,
        "wind_u10",
    )

    wind_v10 = _finite_float(
        wind_v10,
        "wind_v10",
    )

    ocean_uo = _finite_float(
        ocean_uo,
        "ocean_uo",
    )

    ocean_vo = _finite_float(
        ocean_vo,
        "ocean_vo",
    )

    safety_radius_km = (
        _finite_float(
            safety_radius_km,
            "safety_radius_km",
        )
    )

    if safety_radius_km <= 0:

        raise ValueError(
            "safety_radius_km "
            "must be greater than zero."
        )

    sample_step = int(
        sample_step
    )

    if (
        sample_step < 1
        or
        sample_step > 20
    ):

        raise ValueError(
            "sample_step must be "
            "between 1 and 20."
        )


    # ========================================================
    # MEMBER 1 FULL SEA-ICE FORECAST
    # ========================================================

    member1_bundle = (
        get_member1_bundle(
            initialization_date
        )
    )


    # ========================================================
    # MEMBER 2
    #
    # IMPORTANT:
    # Member 2 receives initialization-date SIC through the
    # frozen run_polarguard pipeline.
    #
    # Future Member 1 forecasts are NOT fed back into Member 2.
    # ========================================================

    combined_result = (
        run_polarguard(

            lat_tm3=
                lat_tm3,

            lon_tm3=
                lon_tm3,

            lat_tm2=
                lat_tm2,

            lon_tm2=
                lon_tm2,

            lat_tm1=
                lat_tm1,

            lon_tm1=
                lon_tm1,

            current_latitude=
                current_latitude,

            current_longitude=
                current_longitude,

            date=
                str(
                    initialization_date
                ),

            wind_u10=
                wind_u10,

            wind_v10=
                wind_v10,

            ocean_uo=
                ocean_uo,

            ocean_vo=
                ocean_vo,
        )
    )


    iceberg_forecasts = (
        combined_result[
            "iceberg"
        ][
            "forecast"
        ]
    )


    # ========================================================
    # SELECT SYNCHRONIZED ROUTING HORIZON
    # ========================================================

    sic_lookup = {

        "24h":
            "forecast_24h",

        "48h":
            "forecast_48h",

        "72h":
            "forecast_72h",
    }

    uncertainty_lookup = {

        "24h":
            "uncertainty_24h",

        "48h":
            "uncertainty_48h",

        "72h":
            "uncertainty_72h",
    }


    route_sic = (
        member1_bundle[
            sic_lookup[
                routing_horizon
            ]
        ]
    )

    route_uncertainty = (
        member1_bundle[
            uncertainty_lookup[
                routing_horizon
            ]
        ]
    )

    route_iceberg = (
        iceberg_forecasts[
            routing_horizon
        ]
    )


    # ========================================================
    # GRID COORDINATES
    # ========================================================

    (
        route_grid_lat,
        route_grid_lon,
    ) = projected_grid_to_latlon(

        member1_bundle[
            "x"
        ],

        member1_bundle[
            "y"
        ],
    )


    # ========================================================
    # REAL RISK + A* NAVIGATION
    # ========================================================

    influence_radius_km = max(

        safety_radius_km
        +
        10.0,

        safety_radius_km
        *
        3.0,
    )


    navigation_result = (
        build_navigation_route(

            sic=
                route_sic,

            uncertainty=
                route_uncertainty,

            grid_lat=
                route_grid_lat,

            grid_lon=
                route_grid_lon,

            iceberg_positions=[

                {

                    "latitude":
                        float(
                            route_iceberg[
                                "latitude"
                            ]
                        ),

                    "longitude":
                        float(
                            route_iceberg[
                                "longitude"
                            ]
                        ),
                }
            ],

            start_lat=
                start_lat,

            start_lon=
                start_lon,

            destination_lat=
                destination_lat,

            destination_lon=
                destination_lon,

            vessel_profile=
                vessel_profile,

            safety_radius_km=
                safety_radius_km,

            influence_radius_km=
                influence_radius_km,
        )
    )


    # ========================================================
    # VESSEL PROFILE USED BY NAVIGATION SERVICE
    # ========================================================

    vessel_profile_data = (
        navigation_result[
            "navigation_mask"
        ][
            "profile"
        ]
    )


    # ========================================================
    # HAZARD GRID
    # ========================================================

    hazard_result = (
        build_hazard_zones(

            sic=
                route_sic,

            uncertainty_risk=
                navigation_result[
                    "risk"
                ][
                    "uncertainty_risk"
                ],

            iceberg_risk=
                navigation_result[
                    "risk"
                ][
                    "iceberg_risk"
                ],

            vessel_max_sic=
                float(
                    vessel_profile_data[
                        "max_sic"
                    ]
                ),

            iceberg_exclusion_risk=
                float(
                    vessel_profile_data[
                        "iceberg_exclusion_risk"
                    ]
                ),
        )
    )


    hazard_grid_summary = (
        summarize_hazard_grid(
            hazard_result
        )
    )


    # ========================================================
    # ROUTE HAZARDS
    # ========================================================

    route_hazard_summary = None
    route_alerts = []

    if navigation_result[
        "success"
    ]:

        route_hazard_summary = (
            analyze_route_hazards(

                path_indices=
                    navigation_result[
                        "route"
                    ][
                        "path_indices"
                    ],

                sic=
                    route_sic,

                uncertainty_risk=
                    navigation_result[
                        "risk"
                    ][
                        "uncertainty_risk"
                    ],

                iceberg_risk=
                    navigation_result[
                        "risk"
                    ][
                        "iceberg_risk"
                    ],

                combined_hazard=
                    hazard_result[
                        "combined_hazard"
                    ],
            )
        )

        route_alerts = (
            generate_route_alerts(

                route_hazard_summary=
                    route_hazard_summary,

                vessel_max_sic=
                    float(
                        vessel_profile_data[
                            "max_sic"
                        ]
                    ),

                iceberg_exclusion_risk=
                    float(
                        vessel_profile_data[
                            "iceberg_exclusion_risk"
                        ]
                    ),
            )
        )


    # ========================================================
    # ALTERNATIVE ROUTE
    # ========================================================

    alternative_result = {

        "success":
            False,

        "reason":
            (
                "Recommended route "
                "is unavailable."
            ),

        "route":
            None,

        "overlap_percent":
            100.0,

        "corridor_radius_cells":
            None,

        "penalty_multiplier":
            None,
    }


    alternative_hazard_summary = None
    alternative_alerts = []
    route_comparison = None


    if navigation_result[
        "success"
    ]:

        alternative_base_cost = (
            np.array(

                navigation_result[
                    "risk"
                ][
                    "routing_cost"
                ],

                dtype=float,

                copy=True,
            )
        )

        alternative_base_cost[
            navigation_result[
                "navigation_mask"
            ][
                "blocked_mask"
            ]
        ] = np.inf


        alternative_result = (
            build_alternative_route(

                routing_cost=
                    alternative_base_cost,

                grid_lat=
                    route_grid_lat,

                grid_lon=
                    route_grid_lon,

                start_lat=
                    start_lat,

                start_lon=
                    start_lon,

                destination_lat=
                    destination_lat,

                destination_lon=
                    destination_lon,

                primary_path=
                    navigation_result[
                        "route"
                    ][
                        "path_indices"
                    ],
            )
        )


        if alternative_result.get(
            "success",
            False,
        ):

            alternative_route = (
                alternative_result[
                    "route"
                ]
            )

            alternative_hazard_summary = (
                analyze_route_hazards(

                    path_indices=
                        alternative_route[
                            "path_indices"
                        ],

                    sic=
                        route_sic,

                    uncertainty_risk=
                        navigation_result[
                            "risk"
                        ][
                            "uncertainty_risk"
                        ],

                    iceberg_risk=
                        navigation_result[
                            "risk"
                        ][
                            "iceberg_risk"
                        ],

                    combined_hazard=
                        hazard_result[
                            "combined_hazard"
                        ],
                )
            )

            alternative_alerts = (
                generate_route_alerts(

                    route_hazard_summary=
                        alternative_hazard_summary,

                    vessel_max_sic=
                        float(
                            vessel_profile_data[
                                "max_sic"
                            ]
                        ),

                    iceberg_exclusion_risk=
                        float(
                            vessel_profile_data[
                                "iceberg_exclusion_risk"
                            ]
                        ),
                )
            )


            route_comparison = (
                compare_routes(

                    navigation_result[
                        "route"
                    ],

                    alternative_route,
                )
            )


    # ========================================================
    # CESIUM VISUALIZATION PACKAGE
    # ========================================================

    sea_ice_visualization = (
        build_sea_ice_visualization(

            initialization_date=
                str(
                    initialization_date
                ),

            sample_step=
                sample_step,
        )
    )


    history = {

        "lat_tm3":
            lat_tm3,

        "lon_tm3":
            lon_tm3,

        "lat_tm2":
            lat_tm2,

        "lon_tm2":
            lon_tm2,

        "lat_tm1":
            lat_tm1,

        "lon_tm1":
            lon_tm1,

        "current": {

            "latitude":
                current_latitude,

            "longitude":
                current_longitude,
        },
    }


    iceberg_visualization = (
        build_iceberg_package(

            combined_result=
                combined_result,

            history=
                history,
        )
    )


    # ========================================================
    # ROUTE GEOJSON
    # ========================================================

    recommended_geojson = None
    alternative_geojson = None


    if navigation_result[
        "success"
    ]:

        recommended_geojson = (
            route_to_geojson(

                route=
                    navigation_result[
                        "route"
                    ],

                route_name=
                    "Recommended Route",

                routing_horizon=
                    routing_horizon,

                vessel_profile=
                    vessel_profile,

                safety_radius_km=
                    safety_radius_km,
            )
        )


    if alternative_result.get(
        "success",
        False,
    ):

        alternative_geojson = (
            route_to_geojson(

                route=
                    alternative_result[
                        "route"
                    ],

                route_name=
                    "Alternative Route",

                routing_horizon=
                    routing_horizon,

                vessel_profile=
                    vessel_profile,

                safety_radius_km=
                    safety_radius_km,

                overlap_percent=
                    alternative_result[
                        "overlap_percent"
                    ],
            )
        )


    # ========================================================
    # DECISION SUMMARY
    # ========================================================

    recommended_distance = None

    if navigation_result[
        "success"
    ]:

        recommended_distance = float(

            navigation_result[
                "route"
            ][
                "total_distance_km"
            ]
        )


    alternative_distance = None

    if alternative_result.get(
        "success",
        False,
    ):

        alternative_distance = float(

            alternative_result[
                "route"
            ][
                "total_distance_km"
            ]
        )


    # ========================================================
    # FINAL API-SAFE RESULT
    # ========================================================

    result = {

        "system":
            "PolarGuard",

        "mode":
            (
                "SIH prototype "
                "decision support"
            ),

        "initialization_date":
            str(
                initialization_date
            ),

        "routing_horizon":
            routing_horizon,

        "models": {

            "sea_ice":
                "hybrid-v1-frozen",

            "iceberg":
                "environment-v1-frozen",

            "navigation":
                (
                    "A* + PolarGuard "
                    "Risk Engine"
                ),
        },


        "mission_input": {

            "start": {

                "latitude":
                    start_lat,

                "longitude":
                    start_lon,
            },

            "destination": {

                "latitude":
                    destination_lat,

                "longitude":
                    destination_lon,
            },

            "vessel_profile":
                vessel_profile,

            "iceberg_safety_radius_km":
                safety_radius_km,

            "influence_radius_km":
                influence_radius_km,

            "environment": {

                "wind_u10_mps":
                    wind_u10,

                "wind_v10_mps":
                    wind_v10,

                "ocean_uo_mps":
                    ocean_uo,

                "ocean_vo_mps":
                    ocean_vo,
            },
        },


        "sea_ice":
            sea_ice_visualization,


        "iceberg":
            iceberg_visualization,


        "navigation": {

            "success":
                bool(
                    navigation_result[
                        "success"
                    ]
                ),

            "recommendation":
                navigation_result.get(
                    "recommendation"
                ),

            "route_summary":
                to_builtin(
                    navigation_result.get(
                        "route_summary"
                    )
                ),

            "constraint_summary":
                to_builtin(
                    navigation_result.get(
                        "constraint_summary"
                    )
                ),

            "recommended_route":
                {

                    "available":
                        bool(
                            navigation_result[
                                "success"
                            ]
                        ),

                    "distance_km":
                        recommended_distance,

                    "geojson":
                        recommended_geojson,
                },


            "alternative_route":
                {

                    "available":
                        bool(
                            alternative_result.get(
                                "success",
                                False,
                            )
                        ),

                    "reason":
                        alternative_result.get(
                            "reason"
                        ),

                    "distance_km":
                        alternative_distance,

                    "overlap_percent":
                        (
                            float(
                                alternative_result[
                                    "overlap_percent"
                                ]
                            )

                            if alternative_result.get(
                                "overlap_percent"
                            )
                            is not None

                            else None
                        ),

                    "geojson":
                        alternative_geojson,
                },


            "comparison":
                to_builtin(
                    route_comparison
                ),
        },


        "hazards": {

            "grid_summary":
                to_builtin(
                    hazard_grid_summary
                ),

            "recommended_route":
                {

                    "summary":
                        to_builtin(
                            route_hazard_summary
                        ),

                    "alerts":
                        to_builtin(
                            route_alerts
                        ),
                },

            "alternative_route":
                {

                    "summary":
                        to_builtin(
                            alternative_hazard_summary
                        ),

                    "alerts":
                        to_builtin(
                            alternative_alerts
                        ),
                },
        },


        "decision_summary": {

            "recommended_route_available":
                bool(
                    navigation_result[
                        "success"
                    ]
                ),

            "recommended_distance_km":
                recommended_distance,

            "alternative_route_available":
                bool(
                    alternative_result.get(
                        "success",
                        False,
                    )
                ),

            "alternative_distance_km":
                alternative_distance,

            "route_overlap_percent":
                (
                    float(
                        alternative_result[
                            "overlap_percent"
                        ]
                    )

                    if alternative_result.get(
                        "success",
                        False,
                    )

                    else None
                ),

            "routing_horizon":
                routing_horizon,

            "vessel_profile":
                vessel_profile,
        },


        "disclaimer": (
            "PolarGuard is a research "
            "prototype decision-support "
            "system. Risk values, vessel "
            "profiles and iceberg buffers "
            "are prototype planning aids "
            "and are not certified "
            "operational navigation advice."
        ),
    }


    return to_builtin(
        result
    )