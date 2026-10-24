from __future__ import annotations

from datetime import date, datetime
from typing import Any

import numpy as np
from pyproj import Transformer

from current_iceberg_service import load_current_icebergs
from satellite_data_service import load_latest_satellite_input
from operational_status_service import build_environmental_status

from risk_engine import build_risk_grid
from navigation_service import build_navigation_route
from hazard_engine import (
    build_hazard_zones,
    summarize_hazard_grid,
    analyze_route_hazards,
    generate_route_alerts,
)
from alternative_routing import (
    build_alternative_route,
    compare_routes,
)


# ============================================================
# PROTOTYPE VESSEL PROFILES
#
# These are PolarGuard prototype decision-support profiles.
# They are NOT official Polar Class certifications.
# ============================================================

VESSEL_PROFILES = {
    "LOW": {
        "name": "LOW_ICE_CAPABILITY",
        "label": "Low Ice Capability",
        "max_sic": 0.30,
        "iceberg_exclusion_risk": 0.60,
        "uncertainty_limit": 0.70,
    },
    "MEDIUM": {
        "name": "MEDIUM_ICE_CAPABILITY",
        "label": "Medium Ice Capability",
        "max_sic": 0.55,
        "iceberg_exclusion_risk": 0.75,
        "uncertainty_limit": 0.85,
    },
    "HIGH": {
        "name": "HIGH_ICE_CAPABILITY",
        "label": "High Ice Capability",
        "max_sic": 0.80,
        "iceberg_exclusion_risk": 0.90,
        "uncertainty_limit": 1.00,
    },
}


# ============================================================
# JSON HELPERS
# ============================================================

def json_safe(value: Any) -> Any:
    """
    Convert Python / NumPy values into JSON-safe values.

    Important:
    JSON does not support NaN, +inf or -inf.
    Those values are converted to None.
    """

    if value is None:
        return None

    # --------------------------------------------------------
    # NumPy arrays
    # --------------------------------------------------------

    if isinstance(value, np.ndarray):
        return json_safe(
            value.tolist()
        )

    # --------------------------------------------------------
    # NumPy scalar
    # --------------------------------------------------------

    if isinstance(value, np.generic):
        return json_safe(
            value.item()
        )

    # --------------------------------------------------------
    # Python floating-point values
    #
    # Converts:
    # nan  -> None
    # inf  -> None
    # -inf -> None
    # --------------------------------------------------------

    if isinstance(value, float):
        if not np.isfinite(value):
            return None

        return value

    # --------------------------------------------------------
    # Dates
    # --------------------------------------------------------

    if isinstance(
        value,
        (date, datetime),
    ):
        return value.isoformat()

    # --------------------------------------------------------
    # Dictionaries
    # --------------------------------------------------------

    if isinstance(value, dict):
        return {
            str(key): json_safe(item)
            for key, item in value.items()
        }

    # --------------------------------------------------------
    # Lists / tuples
    # --------------------------------------------------------

    if isinstance(
        value,
        (list, tuple),
    ):
        return [
            json_safe(item)
            for item in value
        ]

    # --------------------------------------------------------
    # Other date-like objects
    # --------------------------------------------------------

    if hasattr(
        value,
        "isoformat",
    ):
        try:
            return value.isoformat()
        except Exception:
            pass

    return value
def finite_number(value: Any) -> float | None:
    try:
        number = float(value)

        if np.isfinite(number):
            return number

    except Exception:
        pass

    return None


# ============================================================
# GRID HELPERS
# ============================================================

def projected_grid_to_latlon(
    x_coords: np.ndarray,
    y_coords: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:

    x_grid, y_grid = np.meshgrid(
        np.asarray(x_coords, dtype=float),
        np.asarray(y_coords, dtype=float),
    )

    transformer = Transformer.from_crs(
        "EPSG:3412",
        "EPSG:4326",
        always_xy=True,
    )

    grid_lon, grid_lat = transformer.transform(
        x_grid,
        y_grid,
    )

    return (
        np.asarray(grid_lat, dtype=float),
        np.asarray(grid_lon, dtype=float),
    )


# ============================================================
# CURRENT ICEBERGS
# ============================================================

def _current_iceberg_records() -> list[dict[str, Any]]:
    bundle = load_current_icebergs()

    dataframe = bundle.get("dataframe")

    if dataframe is None:
        raise RuntimeError(
            "Current iceberg service did not return a dataframe."
        )

    records: list[dict[str, Any]] = []

    for _, row in dataframe.iterrows():

        latitude = finite_number(
            row.get("latitude")
        )

        longitude = finite_number(
            row.get("longitude")
        )

        if latitude is None or longitude is None:
            continue

        iceberg_id = str(
            row.get(
                "iceberg_id",
                "UNKNOWN",
            )
        ).upper()

        observation_date = row.get(
            "observation_date"
        )

        age_days = row.get(
            "age_days"
        )

        freshness = row.get(
            "freshness_status",
            "UNKNOWN",
        )

        records.append(
            {
                "iceberg_id": iceberg_id,
                "latitude": latitude,
                "longitude": longitude,
                "observation_date": (
                    str(observation_date)
                    if observation_date is not None
                    else None
                ),
                "age_days": (
                    int(age_days)
                    if age_days is not None
                    and str(age_days) != "nan"
                    else None
                ),
                "freshness_status": str(
                    freshness
                ),
            }
        )

    return records


def get_iceberg_intelligence() -> dict[str, Any]:
    records = _current_iceberg_records()

    observed_dates = [
        item["observation_date"]
        for item in records
        if item["observation_date"]
    ]

    latest_observation = (
        max(observed_dates)
        if observed_dates
        else None
    )

    fresh = sum(
        1
        for item in records
        if str(
            item["freshness_status"]
        ).upper()
        in {"FRESH", "CURRENT"}
    )

    aging = sum(
        1
        for item in records
        if str(
            item["freshness_status"]
        ).upper()
        == "AGING"
    )

    return {
        "ok": True,
        "provider": "BYU Scatterometer Climate Pathfinder",
        "mode": "latest_available",
        "iceberg_count": len(records),
        "latest_observation": latest_observation,
        "fresh_count": fresh,
        "aging_count": aging,
        "icebergs": records,
        "trajectory_status": {
            "current_hazards": "READY",
            "future_nrt_forecast": "WAITING_FOR_4_REAL_DAILY_POSITIONS",
            "note": (
                "Current BYU positions are used directly as navigation "
                "hazards. Fully synchronized future Member-2 forecasting "
                "requires four consecutive real daily iceberg positions."
            ),
        },
    }


# ============================================================
# ENVIRONMENT
# ============================================================

def get_environment_intelligence(
    latitude: float,
    longitude: float,
) -> dict[str, Any]:

    result = build_environmental_status(
    date=date.today(),
    latitude=float(latitude),
    longitude=float(longitude),
)

    return {
        "ok": True,
        "mode": "near_real_time",
        "latitude": float(latitude),
        "longitude": float(longitude),
        "status": json_safe(result),
    }


# ============================================================
# CURRENT ROUTING ENVIRONMENT
# ============================================================

def _current_environment_bundle():
    satellite = load_latest_satellite_input()

    sic = np.asarray(
        satellite["current"],
        dtype=np.float32,
    )

    x_coords = np.asarray(
        satellite["x"],
        dtype=float,
    )

    y_coords = np.asarray(
        satellite["y"],
        dtype=float,
    )

    grid_lat, grid_lon = (
        projected_grid_to_latlon(
            x_coords,
            y_coords,
        )
    )

    # CURRENT is an observation, not a Member-1 forecast.
    uncertainty = np.where(
        np.isfinite(sic),
        0.0,
        np.nan,
    ).astype(np.float32)

    return {
        "sic": sic,
        "uncertainty": uncertainty,
        "x": x_coords,
        "y": y_coords,
        "grid_lat": grid_lat,
        "grid_lon": grid_lon,
        "date": str(
            satellite.get("date")
        ),
        "provider_lag_days": satellite.get(
            "provider_lag_days"
        ),
    }


def _iceberg_positions():
    return [
        {
            "latitude": item["latitude"],
            "longitude": item["longitude"],
        }
        for item in _current_iceberg_records()
    ]


# ============================================================
# RISK INTELLIGENCE
# ============================================================

def get_risk_intelligence(
    vessel_profile: str = "MEDIUM",
    safety_radius_km: float = 8.0,
    influence_radius_km: float = 24.0,
) -> dict[str, Any]:

    profile_key = (
        vessel_profile
        .strip()
        .upper()
    )

    if profile_key not in VESSEL_PROFILES:
        profile_key = "MEDIUM"

    profile = VESSEL_PROFILES[
        profile_key
    ]

    env = _current_environment_bundle()
    iceberg_positions = (
        _iceberg_positions()
    )

    risk = build_risk_grid(
        sic=env["sic"],
        uncertainty=env["uncertainty"],
        grid_lat=env["grid_lat"],
        grid_lon=env["grid_lon"],
        iceberg_positions=iceberg_positions,
        safety_radius_km=float(
            safety_radius_km
        ),
        influence_radius_km=float(
            influence_radius_km
        ),
    )

    combined = np.asarray(
        risk["combined_risk"],
        dtype=float,
    )

    valid = np.isfinite(combined)

    if valid.any():
        values = combined[valid]

        mean_risk = float(
            np.mean(values)
        )

        max_risk = float(
            np.max(values)
        )

        low_cells = int(
            np.sum(values < 0.25)
        )

        moderate_cells = int(
            np.sum(
                (values >= 0.25)
                & (values < 0.50)
            )
        )

        high_cells = int(
            np.sum(
                (values >= 0.50)
                & (values < 0.75)
            )
        )

        very_high_cells = int(
            np.sum(values >= 0.75)
        )

        valid_count = int(
            values.size
        )
    else:
        mean_risk = None
        max_risk = None
        low_cells = 0
        moderate_cells = 0
        high_cells = 0
        very_high_cells = 0
        valid_count = 0

    hazard = build_hazard_zones(
        sic=env["sic"],
        uncertainty_risk=risk[
            "uncertainty_risk"
        ],
        iceberg_risk=risk[
            "iceberg_risk"
        ],
        vessel_max_sic=float(
            profile["max_sic"]
        ),
        iceberg_exclusion_risk=float(
            profile[
                "iceberg_exclusion_risk"
            ]
        ),
    )

    hazard_summary = (
        summarize_hazard_grid(
            hazard
        )
    )

    return {
        "ok": True,
        "mode": "CURRENT",
        "initialization_date": env["date"],
        "provider_lag_days": env[
            "provider_lag_days"
        ],
        "iceberg_count": len(
            iceberg_positions
        ),
        "vessel_profile": profile,
        "safety_radius_km": float(
            safety_radius_km
        ),
        "influence_radius_km": float(
            influence_radius_km
        ),
        "risk_summary": {
            "valid_cells": valid_count,
            "mean_risk": mean_risk,
            "max_risk": max_risk,
            "low_cells": low_cells,
            "moderate_cells": moderate_cells,
            "high_cells": high_cells,
            "very_high_cells": (
                very_high_cells
            ),
        },
        "hazard_summary": json_safe(
            hazard_summary
        ),
        "scientific_note": (
            "Risk values are PolarGuard prototype weighted "
            "decision-support scores, not calibrated collision "
            "probabilities."
        ),
    }


# ============================================================
# NAVIGATION
# ============================================================
def get_navigation_decision(
    start_lat: float,
    start_lon: float,
    destination_lat: float,
    destination_lon: float,
    vessel_profile: str = "MEDIUM",
    safety_radius_km: float = 8.0,
    influence_radius_km: float = 24.0,
) -> dict[str, Any]:

    # --------------------------------------------------------
    # Normalize frontend vessel profile
    # React sends: LOW / MEDIUM / HIGH
    # Navigation engine expects:
    # LOW_ICE_CAPABILITY / MEDIUM_ICE_CAPABILITY /
    # HIGH_ICE_CAPABILITY
    # --------------------------------------------------------

    profile_key = (
        str(vessel_profile)
        .strip()
        .upper()
    )

    if profile_key not in VESSEL_PROFILES:
        profile_key = "MEDIUM"

    profile = VESSEL_PROFILES[
        profile_key
    ]

    engine_profile_name = str(
        profile["name"]
    )


    # --------------------------------------------------------
    # Load latest-available sea-ice environment
    # --------------------------------------------------------

    env = _current_environment_bundle()


    # --------------------------------------------------------
    # Load latest real BYU iceberg positions
    # --------------------------------------------------------

    iceberg_positions = (
        _iceberg_positions()
    )


    # --------------------------------------------------------
    # Build primary navigation route
    # --------------------------------------------------------

    navigation = build_navigation_route(
        sic=env["sic"],

        uncertainty=env[
            "uncertainty"
        ],

        grid_lat=env[
            "grid_lat"
        ],

        grid_lon=env[
            "grid_lon"
        ],

        iceberg_positions=(
            iceberg_positions
        ),

        start_lat=float(
            start_lat
        ),

        start_lon=float(
            start_lon
        ),

        destination_lat=float(
            destination_lat
        ),

        destination_lon=float(
            destination_lon
        ),

        # IMPORTANT:
        # navigation_service expects the full profile name.
        vessel_profile=(
            engine_profile_name
        ),

        safety_radius_km=float(
            safety_radius_km
        ),

        influence_radius_km=float(
            influence_radius_km
        ),
    )


    # --------------------------------------------------------
    # Base API response
    # --------------------------------------------------------

    response: dict[str, Any] = {
        "ok": True,

        "success": bool(
            navigation.get(
                "success",
                False,
            )
        ),

        "mode": "CURRENT",

        "initialization_date": env[
            "date"
        ],

        "provider_lag_days": env[
            "provider_lag_days"
        ],

        "iceberg_count": len(
            iceberg_positions
        ),

        "vessel_profile": (
            profile
        ),

        "recommendation": (
            json_safe(
                navigation.get(
                    "recommendation"
                )
            )
        ),

        "constraint_summary": (
            json_safe(
                navigation.get(
                    "constraint_summary"
                )
            )
        ),
    }


    # --------------------------------------------------------
    # Route not available
    # --------------------------------------------------------

    if not navigation.get(
        "success",
        False,
    ):

        raw_route = navigation.get(
            "route"
        ) or {}

        response["route"] = {
            "success": False,

            "reason": str(
                raw_route.get(
                    "reason",
                    "No safe route was found.",
                )
            ),

            "distance_km": 0.0,

            "accumulated_cost": (
                json_safe(
                    raw_route.get(
                        "accumulated_cost"
                    )
                )
            ),

            "path_coordinates": [],

            "path_cell_count": 0,

            "start_cell": (
                json_safe(
                    raw_route.get(
                        "start_cell"
                    )
                )
            ),

            "destination_cell": (
                json_safe(
                    raw_route.get(
                        "destination_cell"
                    )
                )
            ),
        }

        response["alerts"] = []

        response["alternative"] = {
            "success": False,
            "reason": (
                "Primary route is unavailable."
            ),
            "route": None,
        }

        response["comparison"] = None

        response[
            "scientific_note"
        ] = (
            "No navigable route was found "
            "for the requested coordinates "
            "under the selected prototype "
            "vessel constraints."
        )

        return json_safe(response)

        response["route"] = (
            json_safe(
                navigation.get(
                    "route"
                )
            )
        )

        response[
            "scientific_note"
        ] = (
            "No navigable route was found "
            "for the requested coordinates "
            "under the selected prototype "
            "vessel constraints."
        )

        return json_safe(response)


    # --------------------------------------------------------
    # Primary route
    # --------------------------------------------------------

    primary_route = navigation[
        "route"
    ]


    # --------------------------------------------------------
    # Route hazard analysis
    # --------------------------------------------------------

    route_hazard_summary = None
    route_alerts = []

    try:

        profile_data = navigation[
            "navigation_mask"
        ]["profile"]


        hazard = build_hazard_zones(
            sic=env["sic"],

            uncertainty_risk=navigation[
                "risk"
            ]["uncertainty_risk"],

            iceberg_risk=navigation[
                "risk"
            ]["iceberg_risk"],

            vessel_max_sic=float(
                profile_data[
                    "max_sic"
                ]
            ),

            iceberg_exclusion_risk=float(
                profile_data[
                    "iceberg_exclusion_risk"
                ]
            ),
        )


        route_hazard_summary = (
            analyze_route_hazards(
                path_indices=primary_route[
                    "path_indices"
                ],

                sic=env["sic"],

                uncertainty_risk=navigation[
                    "risk"
                ]["uncertainty_risk"],

                iceberg_risk=navigation[
                    "risk"
                ]["iceberg_risk"],

                combined_hazard=hazard[
                    "combined_hazard"
                ],
            )
        )


        route_alerts = (
            generate_route_alerts(
                route_hazard_summary=(
                    route_hazard_summary
                ),

                vessel_max_sic=float(
                    profile_data[
                        "max_sic"
                    ]
                ),

                iceberg_exclusion_risk=float(
                    profile_data[
                        "iceberg_exclusion_risk"
                    ]
                ),
            )
        )


    except Exception as exc:

        route_alerts = [
            (
                "Hazard summary could not "
                f"be generated: {exc}"
            )
        ]


    # --------------------------------------------------------
    # Alternative route
    # --------------------------------------------------------

    alternative = {
        "success": False,
        "reason": (
            "Alternative route not available."
        ),
    }

    comparison = None


    try:

        alternative_cost = np.array(
            navigation["risk"][
                "routing_cost"
            ],
            dtype=float,
            copy=True,
        )


        alternative_cost[
            navigation[
                "navigation_mask"
            ]["blocked_mask"]
        ] = np.inf


        alternative = (
            build_alternative_route(
                routing_cost=alternative_cost,

                grid_lat=env[
                    "grid_lat"
                ],

                grid_lon=env[
                    "grid_lon"
                ],

                start_lat=float(
                    start_lat
                ),

                start_lon=float(
                    start_lon
                ),

                destination_lat=float(
                    destination_lat
                ),

                destination_lon=float(
                    destination_lon
                ),

                primary_path=primary_route[
                    "path_indices"
                ],
            )
        )


        if alternative.get(
            "success",
            False,
        ):

            comparison = (
                compare_routes(
                    primary_route,
                    alternative[
                        "route"
                    ],
                )
            )


    except Exception as exc:

        alternative = {
            "success": False,
            "reason": str(exc),
        }


    # --------------------------------------------------------
    # Final successful route response
    # --------------------------------------------------------

    response.update(
        {
            "route": {
                "distance_km": (
    json_safe(
        primary_route.get(
            "total_distance_km",
            primary_route.get(
                "distance_km"
            ),
        )
    )
                ),

                "accumulated_cost": (
                    primary_route.get(
                        "accumulated_cost"
                    )
                ),

                "path_coordinates": (
                    json_safe(
                        primary_route.get(
                            "path_coordinates",
                            [],
                        )
                    )
                ),

                "path_cell_count": len(
                    primary_route.get(
                        "path_indices",
                        [],
                    )
                ),
            },


            "route_summary": (
                json_safe(
                    navigation.get(
                        "route_summary"
                    )
                )
            ),


            "hazard_summary": (
                json_safe(
                    route_hazard_summary
                )
            ),


            "alerts": (
                json_safe(
                    route_alerts
                )
            ),


            "alternative": {

                "success": bool(
                    alternative.get(
                        "success",
                        False,
                    )
                ),

                "reason": (
                    alternative.get(
                        "reason"
                    )
                ),

                "route": (
                    {
                        "distance_km": (
                            alternative[
                                "route"
                            ].get(
                                "distance_km"
                            )
                        ),

                        "accumulated_cost": (
                            alternative[
                                "route"
                            ].get(
                                "accumulated_cost"
                            )
                        ),

                        "path_coordinates": (
                            json_safe(
                                alternative[
                                    "route"
                                ].get(
                                    "path_coordinates",
                                    [],
                                )
                            )
                        ),
                    }

                    if alternative.get(
                        "success",
                        False,
                    )

                    else None
                ),
            },


            "comparison": (
                json_safe(
                    comparison
                )
            ),


            "scientific_note": (
                "CURRENT routing uses latest-available "
                "observed sea ice and real BYU iceberg "
                "positions. Wind and ocean current are "
                "environmental status / Member-2 forcing "
                "inputs and are not directly included in "
                "the current A* cost surface."
            ),
        }
    )


    return response
# ============================================================
# MODEL INTELLIGENCE
# ============================================================

def get_model_intelligence() -> dict[str, Any]:

    return {
        "ok": True,
        "sea_ice": {
            "name": (
                "PolarGuard Sea-Ice Member-1"
            ),
            "version": (
                "hybrid-v1-frozen"
            ),
            "status": "FROZEN",
            "test_year": 2025,
            "metrics": {
                "24h": {
                    "mae": 0.008854,
                    "rmse": 0.036288,
                    "within_5pp_percent": 94.87,
                    "rmse_improvement_vs_persistence_percent": 4.56,
                },
                "48h": {
                    "mae": 0.012707,
                    "rmse": 0.050063,
                    "within_5pp_percent": 93.18,
                    "rmse_improvement_vs_persistence_percent": 5.73,
                },
                "72h": {
                    "mae": 0.015287,
                    "rmse": 0.059311,
                    "within_5pp_percent": 92.33,
                    "rmse_improvement_vs_persistence_percent": 7.04,
                },
            },
            "note": (
                "within_5pp_percent means the percentage "
                "of grid-cell forecasts within +/-5 SIC "
                "percentage points of observation. It is "
                "not generic classification accuracy."
            ),
        },
        "iceberg": {
            "name": (
                "PolarGuard Iceberg Member-2"
            ),
            "version": (
                "environment-v1-frozen"
            ),
            "status": "FROZEN",
            "test_year": 2025,
            "metrics": {
                "24h": {
                    "rmse_km": 3.744,
                    "within_5km_percent": 92.23,
                    "baseline_rmse_km": 4.366,
                    "rmse_improvement_percent": 14.23,
                },
                "48h": {
                    "rmse_km": 6.389,
                    "within_5km_percent": 80.33,
                    "baseline_rmse_km": 7.913,
                    "rmse_improvement_percent": 19.25,
                },
                "72h": {
                    "rmse_km": 9.389,
                    "within_5km_percent": 69.48,
                    "baseline_rmse_km": 11.828,
                    "rmse_improvement_percent": 20.61,
                },
            },
        },
        "risk": {
            "status": "READY",
            "mode": (
                "prototype weighted risk"
            ),
        },
        "navigation": {
            "status": "READY",
            "algorithm": (
                "A* + vessel constraints"
            ),
        },
        "disclaimer": (
            "Prototype decision-support system. "
            "Not certified operational vessel navigation."
        ),
    }