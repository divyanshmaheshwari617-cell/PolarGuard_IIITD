import numpy as np

from navigation_service import (
    build_navigation_route
)


# ============================================================
# TEST GRID
# ============================================================

rows = 60
cols = 60

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
    0.12,
    dtype=float
)

# Heavy sea-ice barrier
sic[
    20:42,
    24:35
] = 0.72


# ============================================================
# UNCERTAINTY
# ============================================================

uncertainty = np.full(
    (rows, cols),
    0.025,
    dtype=float
)


# ============================================================
# PREDICTED ICEBERG
# ============================================================

iceberg_positions = [
    {
        "latitude": -75.25,
        "longitude": -41.0
    }
]


# ============================================================
# NAVIGATION REQUEST
# ============================================================

result = build_navigation_route(
    sic=sic,
    uncertainty=uncertainty,
    grid_lat=grid_lat,
    grid_lon=grid_lon,
    iceberg_positions=iceberg_positions,

    start_lat=-75.80,
    start_lon=-42.50,

    destination_lat=-74.70,
    destination_lon=-39.50,

    vessel_profile=
        "MEDIUM_ICE_CAPABILITY",

    safety_radius_km=8.0,
    influence_radius_km=25.0
)


# ============================================================
# RESULTS
# ============================================================

print()
print(
    "POLARGUARD NAVIGATION SERVICE TEST"
)

print(
    "=================================="
)

print()

print(
    "Route success:",
    result["success"]
)

print(
    "Recommendation:",
    result[
        "recommendation"
    ]["status"]
)

print(
    "Message:",
    result[
        "recommendation"
    ]["message"]
)

print()

if result["success"]:

    route = result[
        "route"
    ]

    summary = result[
        "route_summary"
    ]

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

    print(
        "Route points:",
        len(
            route[
                "path_coordinates"
            ]
        )
    )

    print(
        "Mean route risk:",
        round(
            summary[
                "mean_risk"
            ],
            3
        )
    )

    print(
        "Maximum route risk:",
        round(
            summary[
                "max_risk"
            ],
            3
        )
    )

    print(
        "Risk classification:",
        summary[
            "classification"
        ]
    )

print()

constraints = result[
    "constraint_summary"
]

print(
    "Blocked cells:",
    constraints[
        "blocked_cells"
    ]
)

print(
    "Blocked percentage:",
    round(
        constraints[
            "blocked_percent"
        ],
        2
    ),
    "%"
)

print(
    "Blocked by SIC:",
    constraints[
        "blocked_by_sic"
    ]
)

print(
    "Blocked by iceberg:",
    constraints[
        "blocked_by_iceberg"
    ]
)

print()


# ============================================================
# AUTOMATIC CHECKS
# ============================================================

assert result[
    "success"
]

assert len(
    result[
        "route"
    ][
        "path_coordinates"
    ]
) > 1

assert (
    result[
        "route"
    ][
        "total_distance_km"
    ]
    >
    0
)

assert (
    result[
        "constraint_summary"
    ][
        "blocked_cells"
    ]
    >
    0
)

print(
    "ALL NAVIGATION SERVICE CHECKS PASSED"
)

print(
    "POLARGUARD NAVIGATION INTEGRATION COMPLETE"
)