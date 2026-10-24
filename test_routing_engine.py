import numpy as np

from risk_engine import (
    build_risk_grid
)

from routing_engine import (
    astar_route,
    summarize_route_risk
)


# ============================================================
# GRID
# ============================================================

rows = 50
cols = 50

latitudes = np.linspace(
    -76.0,
    -74.5,
    rows
)

longitudes = np.linspace(
    -43.0,
    -39.0,
    cols
)

grid_lon, grid_lat = np.meshgrid(
    longitudes,
    latitudes
)


# ============================================================
# SEA ICE
# ============================================================

sic = np.full(
    (rows, cols),
    0.15,
    dtype=float
)

# Create a high sea-ice obstacle
sic[
    15:35,
    20:30
] = 0.95


# ============================================================
# UNCERTAINTY
# ============================================================

uncertainty = np.full(
    (rows, cols),
    0.02,
    dtype=float
)


# ============================================================
# ICEBERG
# ============================================================

iceberg_positions = [
    {
        "latitude": -75.25,
        "longitude": -41.0
    }
]


# ============================================================
# RISK GRID
# ============================================================

risk = build_risk_grid(
    sic=sic,
    uncertainty=uncertainty,
    grid_lat=grid_lat,
    grid_lon=grid_lon,
    iceberg_positions=iceberg_positions,
    safety_radius_km=8.0,
    influence_radius_km=25.0
)


# ============================================================
# ROUTE
# ============================================================

start_lat = -75.80
start_lon = -42.50

destination_lat = -74.70
destination_lon = -39.50


route = astar_route(
    routing_cost=
        risk["routing_cost"],

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


# ============================================================
# OUTPUT
# ============================================================

print()
print(
    "POLARGUARD ROUTING ENGINE TEST"
)

print(
    "=============================="
)

print()

print(
    "Route success:",
    route["success"]
)

print(
    "Reason:",
    route["reason"]
)

print(
    "Start cell:",
    route["start_cell"]
)

print(
    "Destination cell:",
    route["destination_cell"]
)

print(
    "Route points:",
    len(
        route["path_coordinates"]
    )
)

print(
    "Route distance:",
    round(
        route["total_distance_km"],
        2
    ),
    "km"
)

print(
    "Accumulated routing cost:",
    round(
        route["accumulated_cost"],
        2
    )
)


# ============================================================
# RISK SUMMARY
# ============================================================

summary = summarize_route_risk(
    route_result=route,

    combined_risk=
        risk["combined_risk"],

    sea_ice_risk=
        risk["sea_ice_risk"],

    iceberg_risk=
        risk["iceberg_risk"],

    uncertainty_risk=
        risk["uncertainty_risk"]
)


print()

print(
    "Mean route risk:",
    round(
        summary["mean_risk"],
        3
    )
)

print(
    "Maximum route risk:",
    round(
        summary["max_risk"],
        3
    )
)

print(
    "Route classification:",
    summary["classification"]
)


print()

print(
    "Maximum sea-ice risk:",
    round(
        summary[
            "max_sea_ice_risk"
        ],
        3
    )
)

print(
    "Maximum iceberg risk:",
    round(
        summary[
            "max_iceberg_risk"
        ],
        3
    )
)

print(
    "Maximum uncertainty risk:",
    round(
        summary[
            "max_uncertainty_risk"
        ],
        3
    )
)


# ============================================================
# BASIC TESTS
# ============================================================

assert route["success"]

assert (
    len(
        route[
            "path_coordinates"
        ]
    )
    >
    1
)

assert (
    route[
        "total_distance_km"
    ]
    >
    0
)

assert (
    summary[
        "mean_risk"
    ]
    >=
    0
)

assert (
    summary[
        "max_risk"
    ]
    <=
    1
)


print()

print(
    "ALL ROUTING CHECKS PASSED"
)

print(
    "A* ROUTING ENGINE TEST COMPLETE"
)