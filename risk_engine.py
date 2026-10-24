import numpy as np


def normalize_sic(sic):
    """
    Convert Sea-Ice Concentration to risk.

    SIC expected:
        0.0 = no sea ice
        1.0 = 100% sea ice

    Returns:
        risk from 0.0 to 1.0
    """

    sic = np.asarray(
        sic,
        dtype=float
    )

    return np.clip(
        sic,
        0.0,
        1.0
    )


def normalize_uncertainty(
    uncertainty,
    scale=0.10
):
    """
    Convert Member 1 historical RMSE uncertainty
    into a normalized routing penalty.

    Example:
        uncertainty = 0.03
        scale = 0.10

        risk = 0.30

    IMPORTANT:
    This is a prototype routing penalty.
    It is NOT a collision probability.
    """

    uncertainty = np.asarray(
        uncertainty,
        dtype=float
    )

    risk = (
        uncertainty
        /
        scale
    )

    return np.clip(
        risk,
        0.0,
        1.0
    )


def haversine_km(
    lat1,
    lon1,
    lat2,
    lon2
):
    """
    Calculate great-circle distance
    between coordinates in kilometres.

    Supports NumPy arrays.
    """

    earth_radius_km = 6371.0088

    lat1 = np.radians(
        lat1
    )

    lon1 = np.radians(
        lon1
    )

    lat2 = np.radians(
        lat2
    )

    lon2 = np.radians(
        lon2
    )

    delta_lat = (
        lat2
        -
        lat1
    )

    delta_lon = (
        lon2
        -
        lon1
    )

    a = (
        np.sin(
            delta_lat / 2.0
        ) ** 2
        +
        np.cos(lat1)
        *
        np.cos(lat2)
        *
        np.sin(
            delta_lon / 2.0
        ) ** 2
    )

    c = (
        2.0
        *
        np.arctan2(
            np.sqrt(a),
            np.sqrt(
                1.0 - a
            )
        )
    )

    distance_km = (
        earth_radius_km
        *
        c
    )

    return distance_km


def iceberg_proximity_risk(
    grid_lat,
    grid_lon,
    iceberg_lat,
    iceberg_lon,
    safety_radius_km=10.0,
    influence_radius_km=30.0
):
    """
    Create risk around one predicted iceberg.

    Risk logic:

    distance <= safety_radius
        risk = 1.0

    safety_radius < distance < influence_radius
        risk gradually decreases

    distance >= influence_radius
        risk = 0.0

    IMPORTANT:
    These radii are planning parameters,
    not calibrated collision probabilities.
    """

    if (
        influence_radius_km
        <=
        safety_radius_km
    ):

        raise ValueError(
            "influence_radius_km must be greater "
            "than safety_radius_km."
        )

    distance = haversine_km(
        grid_lat,
        grid_lon,
        iceberg_lat,
        iceberg_lon
    )

    risk = np.zeros_like(
        distance,
        dtype=float
    )

    inside_safety_zone = (
        distance
        <=
        safety_radius_km
    )

    risk[
        inside_safety_zone
    ] = 1.0

    transition_zone = (
        (
            distance
            >
            safety_radius_km
        )
        &
        (
            distance
            <
            influence_radius_km
        )
    )

    risk[
        transition_zone
    ] = (
        influence_radius_km
        -
        distance[
            transition_zone
        ]
    ) / (
        influence_radius_km
        -
        safety_radius_km
    )

    return risk


def build_iceberg_risk(
    grid_lat,
    grid_lon,
    iceberg_positions,
    safety_radius_km=10.0,
    influence_radius_km=30.0
):
    """
    Combine risk from multiple iceberg positions.

    The maximum iceberg risk at each cell is used.

    iceberg_positions example:

    [
        {
            "latitude": -75.50,
            "longitude": -41.00
        },
        {
            "latitude": -75.60,
            "longitude": -40.80
        }
    ]
    """

    iceberg_risk = np.zeros_like(
        grid_lat,
        dtype=float
    )

    for iceberg in iceberg_positions:

        iceberg_latitude = float(
            iceberg["latitude"]
        )

        iceberg_longitude = float(
            iceberg["longitude"]
        )

        local_risk = (
            iceberg_proximity_risk(
                grid_lat=grid_lat,
                grid_lon=grid_lon,
                iceberg_lat=iceberg_latitude,
                iceberg_lon=iceberg_longitude,
                safety_radius_km=safety_radius_km,
                influence_radius_km=influence_radius_km
            )
        )

        iceberg_risk = np.maximum(
            iceberg_risk,
            local_risk
        )

    return iceberg_risk


def build_risk_grid(
    sic,
    uncertainty,
    grid_lat,
    grid_lon,
    iceberg_positions,
    sea_ice_weight=4.0,
    iceberg_weight=6.0,
    uncertainty_weight=2.0,
    safety_radius_km=10.0,
    influence_radius_km=30.0
):
    """
    Build PolarGuard navigation risk/cost grid.

    Inputs
    ------

    sic:
        Sea-Ice Concentration grid.
        Expected values 0.0 to 1.0.

    uncertainty:
        Member 1 historical forecast-error RMSE grid.

    grid_lat:
        Latitude of each routing grid cell.

    grid_lon:
        Longitude of each routing grid cell.

    iceberg_positions:
        Predicted iceberg positions.

    Example:

        [
            {
                "latitude": -75.5,
                "longitude": -41.0
            }
        ]

    Returns
    -------

    dictionary:

        sea_ice_risk
        iceberg_risk
        uncertainty_risk
        combined_risk
        routing_cost
        blocked_mask
    """

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
        sic.shape
        !=
        uncertainty.shape
    ):

        raise ValueError(
            "SIC and uncertainty grids "
            "must have the same shape."
        )

    if (
        grid_lat.shape
        !=
        sic.shape
    ):

        raise ValueError(
            "grid_lat shape must match SIC shape."
        )

    if (
        grid_lon.shape
        !=
        sic.shape
    ):

        raise ValueError(
            "grid_lon shape must match SIC shape."
        )

    sea_ice_risk = (
        normalize_sic(
            sic
        )
    )

    uncertainty_risk = (
        normalize_uncertainty(
            uncertainty
        )
    )

    iceberg_risk = (
        build_iceberg_risk(
            grid_lat=grid_lat,
            grid_lon=grid_lon,
            iceberg_positions=iceberg_positions,
            safety_radius_km=safety_radius_km,
            influence_radius_km=influence_radius_km
        )
    )

    total_weight = (
        sea_ice_weight
        +
        iceberg_weight
        +
        uncertainty_weight
    )

    weighted_risk = (
        sea_ice_weight
        *
        sea_ice_risk
        +
        iceberg_weight
        *
        iceberg_risk
        +
        uncertainty_weight
        *
        uncertainty_risk
    )

    combined_risk = (
        weighted_risk
        /
        total_weight
    )

    routing_cost = (
        1.0
        +
        weighted_risk
    )

    invalid_sic = (
        ~np.isfinite(
            sic
        )
    )

    invalid_coordinates = (
        ~np.isfinite(
            grid_lat
        )
        |
        ~np.isfinite(
            grid_lon
        )
    )

    blocked_mask = (
        invalid_sic
        |
        invalid_coordinates
    )

    routing_cost[
        blocked_mask
    ] = np.inf

    combined_risk[
        blocked_mask
    ] = np.nan

    return {
        "sea_ice_risk":
            sea_ice_risk,

        "iceberg_risk":
            iceberg_risk,

        "uncertainty_risk":
            uncertainty_risk,

        "combined_risk":
            combined_risk,

        "routing_cost":
            routing_cost,

        "blocked_mask":
            blocked_mask
    }


def classify_risk(
    risk_value
):
    """
    Simple prototype decision-support category.
    """

    if not np.isfinite(
        risk_value
    ):

        return "BLOCKED"

    if risk_value < 0.25:

        return "LOW"

    if risk_value < 0.50:

        return "MODERATE"

    if risk_value < 0.75:

        return "HIGH"

    return "VERY HIGH"