import numpy as np

from hazard_engine import (
    build_hazard_zones,
    analyze_route_hazards,
    generate_route_alerts,
    summarize_hazard_grid,
)


rows = 40
cols = 40


# ============================================================
# TEST ENVIRONMENT
# ============================================================

sic = np.full(
    (rows, cols),
    0.20,
    dtype=float
)

uncertainty_risk = np.full(
    (rows, cols),
    0.20,
    dtype=float
)

iceberg_risk = np.zeros(
    (rows, cols),
    dtype=float
)


# High sea-ice region
sic[
    10:20,
    15:25
] = 0.70


# Iceberg hazard region
iceberg_risk[
    20:30,
    20:30
] = 0.85


# High uncertainty region
uncertainty_risk[
    5:10,
    5:15
] = 0.80


# ============================================================
# BUILD HAZARD ZONES
# ============================================================

hazards = build_hazard_zones(
    sic=sic,

    uncertainty_risk=
        uncertainty_risk,

    iceberg_risk=
        iceberg_risk,

    vessel_max_sic=
        0.55,

    iceberg_exclusion_risk=
        0.75,
)


summary = summarize_hazard_grid(
    hazards
)


print()
print(
    "POLARGUARD HAZARD ENGINE TEST"
)

print(
    "============================="
)

print()

print(
    "Critical cells:",
    summary[
        "critical_cells"
    ]
)

print(
    "Critical grid:",
    round(
        summary[
            "critical_percent"
        ],
        2
    ),
    "%"
)

print(
    "Warning cells:",
    summary[
        "warning_cells"
    ]
)

print(
    "Warning grid:",
    round(
        summary[
            "warning_percent"
        ],
        2
    ),
    "%"
)


# ============================================================
# SAFE TEST ROUTE
# ============================================================

path_indices = [
    (30, 2),
    (31, 3),
    (32, 4),
    (33, 5),
    (34, 6),
]


route_summary = analyze_route_hazards(
    path_indices=
        path_indices,

    sic=
        sic,

    uncertainty_risk=
        uncertainty_risk,

    iceberg_risk=
        iceberg_risk,

    combined_hazard=
        hazards[
            "combined_hazard"
        ],
)


alerts = generate_route_alerts(
    route_hazard_summary=
        route_summary,

    vessel_max_sic=
        0.55,

    iceberg_exclusion_risk=
        0.75,
)


print()

print(
    "Route hazard level:",
    route_summary[
        "hazard_level"
    ]
)

print(
    "Maximum SIC:",
    route_summary[
        "max_sic"
    ]
)

print(
    "Maximum iceberg risk:",
    route_summary[
        "max_iceberg_risk"
    ]
)

print(
    "Maximum uncertainty risk:",
    route_summary[
        "max_uncertainty_risk"
    ]
)


print()

print(
    "ROUTE ALERTS"
)

print(
    "------------"
)

for alert in alerts:

    print(
        alert["severity"],
        "-",
        alert["message"]
    )


# ============================================================
# AUTOMATIC TESTS
# ============================================================

assert (
    summary[
        "critical_cells"
    ]
    >
    0
)

assert (
    np.count_nonzero(
        hazards[
            "sea_ice_blocked"
        ]
    )
    >
    0
)

assert (
    np.count_nonzero(
        hazards[
            "iceberg_blocked"
        ]
    )
    >
    0
)

assert (
    np.count_nonzero(
        hazards[
            "uncertainty_high"
        ]
    )
    >
    0
)

assert (
    route_summary[
        "route_cells"
    ]
    ==
    len(
        path_indices
    )
)

assert len(
    alerts
) > 0


print()

print(
    "ALL HAZARD ENGINE CHECKS PASSED"
)

print(
    "POLARGUARD HAZARD ENGINE COMPLETE"
)