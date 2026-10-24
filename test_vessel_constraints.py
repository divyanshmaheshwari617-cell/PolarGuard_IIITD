import numpy as np

from risk_engine import (
    build_risk_grid
)

from routing_engine import (
    astar_route,
    summarize_route_risk
)

from vessel_constraints import (
    build_navigation_mask,
    apply_navigation_constraints,
    summarize_navigation_constraints
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

# Strong sea-ice region
sic[
    15:35,
    20:30
] = 0.70


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
# BUILD RISK GRID
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
# VESSEL HARD CONSTRAINTS
# ============================================================

navigation_mask = build_navigation_mask(
    sic=sic,

    iceberg_risk=
        risk["iceberg_risk"],

    uncertainty_risk=
        risk["uncertainty_risk"],

    blocked_mask=
        risk["blocked_mask"],

    profile_name=
        "MEDIUM_ICE_CAPABILITY"
)


constrained_cost = (
    apply_navigation_constraints(
        routing_cost=
            risk["routing_cost"],

        navigation_mask=
            navigation_mask
    )
)


# ============================================================
# ROUTE
# ============================================================

route = astar_route(
    routing_cost=
        constrained_cost,

    grid_lat=
        grid_lat,

    grid_lon=
        grid_lon,

    start_lat=
        -75.80,

    start_lon=
        -42.50,

    destination_lat=
        -74.70,

    destination_lon=
        -39.50
)


# ============================================================
# SUMMARIES
# ============================================================

constraint_summary = (
    summarize_navigation_constraints(
        navigation_mask
    )
)


print()
print(
    "POLARGUARD VESSEL CONSTRAINT TEST"
)

print(
    "================================="
)

print()

print(
    "Vessel:",
    navigation_mask[
        "profile"
    ]["name"]
)

print(
    "Maximum permitted SIC:",
    navigation_mask[
        "profile"
    ]["max_sic"]
)

print()

print(
    "Blocked cells:",
    constraint_summary[
        "blocked_cells"
    ]
)

print(
    "Blocked percentage:",
    round(
        constraint_summary[
            "blocked_percent"
        ],
        2
    ),
    "%"
)

print(
    "Blocked by sea ice:",
    constraint_summary[
        "blocked_by_sic"
    ]
)

print(
    "Blocked by iceberg:",
    constraint_summary[
        "blocked_by_iceberg"
    ]
)

print(
    "Blocked by uncertainty:",
    constraint_summary[
        "blocked_by_uncertainty"
    ]
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
    "Route points:",
    len(
        route[
            "path_coordinates"
        ]
    )
)

print(
    "Route distance:",
    round(
        route[
            "total_distance_km"
        ],
        2
    ),
    "km"
)


if route["success"]:

    route_summary = summarize_route_risk(
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

    print()

    print(
        "Route classification:",
        route_summary[
            "classification"
        ]
    )

    print(
        "Maximum route risk:",
        round(
            route_summary[
                "max_risk"
            ],
            3
        )
    )


# ============================================================
# AUTOMATIC CHECKS
# ============================================================

assert (
    constraint_summary[
        "blocked_by_sic"
    ]
    >
    0
)

assert (
    constraint_summary[
        "blocked_by_iceberg"
    ]
    >
    0
)

assert route["success"]

for row, col in route[
    "path_indices"
]:

    assert not navigation_mask[
        "blocked_mask"
    ][row, col]


print()
print(
    "ALL VESSEL CONSTRAINT CHECKS PASSED"
)

print(
    "HARD HAZARD AVOIDANCE TEST COMPLETE"
)