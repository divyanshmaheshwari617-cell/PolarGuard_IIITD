import numpy as np

from risk_engine import build_risk_grid

from routing_engine import (
    astar_route,
    summarize_route_risk
)

from vessel_constraints import (
    build_navigation_mask,
    apply_navigation_constraints,
    summarize_navigation_constraints
)


def build_navigation_route(
    sic,
    uncertainty,
    grid_lat,
    grid_lon,
    iceberg_positions,
    start_lat,
    start_lon,
    destination_lat,
    destination_lon,
    vessel_profile="MEDIUM_ICE_CAPABILITY",
    safety_radius_km=10.0,
    influence_radius_km=30.0,
):
    """
    PolarGuard navigation integration service.

    Combines:

    - Member 1 sea-ice forecast
    - Member 1 uncertainty
    - Member 2 predicted iceberg positions
    - vessel constraints
    - A* routing

    Returns a complete navigation decision package.

    IMPORTANT:
    This is prototype decision-support logic.
    It is not certified operational navigation guidance.
    """

    # ========================================================
    # VALIDATE INPUT ARRAYS
    # ========================================================

    sic = np.asarray(
        sic,
        dtype=float
    )

    uncertainty = np.asarray(
        uncertainty,
        dtype=float
    )

    grid_lat = np.asarray(
        grid_lat,
        dtype=float
    )

    grid_lon = np.asarray(
        grid_lon,
        dtype=float
    )

    if (
        sic.shape != uncertainty.shape
        or
        sic.shape != grid_lat.shape
        or
        sic.shape != grid_lon.shape
    ):
        raise ValueError(
            "SIC, uncertainty, latitude and longitude "
            "grids must have matching shapes."
        )

    # ========================================================
    # 1. BUILD ENVIRONMENTAL RISK GRID
    # ========================================================

    risk = build_risk_grid(
        sic=sic,
        uncertainty=uncertainty,
        grid_lat=grid_lat,
        grid_lon=grid_lon,
        iceberg_positions=iceberg_positions,
        safety_radius_km=safety_radius_km,
        influence_radius_km=influence_radius_km
    )

    # ========================================================
    # 2. APPLY VESSEL-SPECIFIC HARD CONSTRAINTS
    # ========================================================

    navigation_mask = build_navigation_mask(
        sic=sic,

        iceberg_risk=
            risk["iceberg_risk"],

        uncertainty_risk=
            risk["uncertainty_risk"],

        blocked_mask=
            risk["blocked_mask"],

        profile_name=
            vessel_profile
    )

    constrained_cost = (
        apply_navigation_constraints(
            routing_cost=
                risk["routing_cost"],

            navigation_mask=
                navigation_mask
        )
    )

    # ========================================================
    # 3. FIND ROUTE
    # ========================================================

    route = astar_route(
        routing_cost=
            constrained_cost,

        grid_lat=
            grid_lat,

        grid_lon=
            grid_lon,

        start_lat=
            start_lat,

        start_lon=
            start_lon,

        destination_lat=
            destination_lat,

        destination_lon=
            destination_lon
    )

    # ========================================================
    # 4. SUMMARIZE CONSTRAINTS
    # ========================================================

    constraint_summary = (
        summarize_navigation_constraints(
            navigation_mask
        )
    )

    # ========================================================
    # 5. SUMMARIZE ROUTE RISK
    # ========================================================

    route_summary = (
        summarize_route_risk(
            route_result=
                route,

            combined_risk=
                risk["combined_risk"],

            sea_ice_risk=
                risk["sea_ice_risk"],

            iceberg_risk=
                risk["iceberg_risk"],

            uncertainty_risk=
                risk["uncertainty_risk"]
        )
    )

    # ========================================================
    # 6. BUILD HUMAN-READABLE RECOMMENDATION
    # ========================================================

    recommendation = build_navigation_recommendation(
        route=route,
        route_summary=route_summary,
        constraint_summary=constraint_summary,
        vessel_profile=vessel_profile
    )

    # ========================================================
    # FINAL PACKAGE
    # ========================================================

    return {
        "success":
            route["success"],

        "route":
            route,

        "route_summary":
            route_summary,

        "constraint_summary":
            constraint_summary,

        "recommendation":
            recommendation,

        "risk":
            risk,

        "navigation_mask":
            navigation_mask,

        "constrained_cost":
            constrained_cost,

        "vessel_profile":
            vessel_profile,

        "safety_radius_km":
            float(
                safety_radius_km
            ),

        "influence_radius_km":
            float(
                influence_radius_km
            )
    }


def build_navigation_recommendation(
    route,
    route_summary,
    constraint_summary,
    vessel_profile
):
    """
    Generate explainable prototype navigation recommendation.
    """

    if not route["success"]:

        return {
            "status":
                "NO SAFE ROUTE",

            "message":
                "No valid route was found using the selected "
                "vessel constraints and environmental forecast.",

            "reason":
                route["reason"]
        }

    classification = (
        route_summary[
            "classification"
        ]
    )

    max_risk = (
        route_summary[
            "max_risk"
        ]
    )

    distance = (
        route[
            "total_distance_km"
        ]
    )

    if classification == "LOW":

        status = (
            "LOW RISK ROUTE"
        )

        message = (
            "PolarGuard found a lower-risk route that "
            "remains within the selected prototype "
            "vessel constraints."
        )

    elif classification == "MODERATE":

        status = (
            "MODERATE RISK ROUTE"
        )

        message = (
            "A route is available, but forecast environmental "
            "conditions produce moderate navigation risk."
        )

    elif classification == "HIGH":

        status = (
            "HIGH RISK ROUTE"
        )

        message = (
            "A route is available, but it passes through "
            "areas with elevated forecast navigation risk."
        )

    else:

        status = (
            "VERY HIGH RISK ROUTE"
        )

        message = (
            "A route was mathematically found, but forecast "
            "risk remains very high. Operational review is required."
        )

    return {
        "status":
            status,

        "message":
            message,

        "route_distance_km":
            float(
                distance
            ),

        "maximum_route_risk":
            float(
                max_risk
            ),

        "risk_classification":
            classification,

        "vessel_profile":
            vessel_profile,

        "blocked_cells":
            int(
                constraint_summary[
                    "blocked_cells"
                ]
            ),

        "blocked_percent":
            float(
                constraint_summary[
                    "blocked_percent"
                ]
            )
    }