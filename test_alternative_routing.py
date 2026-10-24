import numpy as np

from routing_engine import astar_route

from alternative_routing import (
    build_alternative_route,
    compare_routes,
    route_overlap_percent,
)


def route_distance(route):

    if "total_distance_km" in route:
        return route["total_distance_km"]

    if "distance_km" in route:
        return route["distance_km"]

    raise KeyError(
        f"No distance key. Available keys: {sorted(route.keys())}"
    )


rows = 60
cols = 60

routing_cost = np.ones(
    (rows, cols),
    dtype=float,
)

grid_lat = np.zeros(
    (rows, cols),
    dtype=float,
)

grid_lon = np.zeros(
    (rows, cols),
    dtype=float,
)


for row in range(rows):

    for col in range(cols):

        grid_lat[row, col] = (
            -76.0
            +
            row * 0.025
        )

        grid_lon[row, col] = (
            -44.0
            +
            col * 0.04
        )


# Central blocked hazard.
routing_cost[
    22:38,
    26:34
] = np.inf


start_lat = grid_lat[8, 8]
start_lon = grid_lon[8, 8]

destination_lat = grid_lat[50, 50]
destination_lon = grid_lon[50, 50]


primary = astar_route(
    routing_cost=routing_cost,
    grid_lat=grid_lat,
    grid_lon=grid_lon,
    start_lat=start_lat,
    start_lon=start_lon,
    destination_lat=destination_lat,
    destination_lon=destination_lon,
)


assert primary["success"]


print()
print(
    "POLARGUARD ALTERNATIVE ROUTE TEST"
)
print(
    "================================="
)
print()

print(
    "Primary success:",
    primary["success"],
)

print(
    "Primary route keys:",
    sorted(
        primary.keys()
    ),
)

print(
    "Primary distance:",
    round(
        route_distance(
            primary
        ),
        2,
    ),
    "km",
)


alternative = build_alternative_route(
    routing_cost=routing_cost,
    grid_lat=grid_lat,
    grid_lon=grid_lon,
    start_lat=start_lat,
    start_lon=start_lon,
    destination_lat=destination_lat,
    destination_lon=destination_lon,
    primary_path=primary[
        "path_indices"
    ],
)


print(
    "Alternative success:",
    alternative["success"],
)


if not alternative["success"]:

    raise AssertionError(
        alternative["reason"]
    )


alt_route = alternative[
    "route"
]


print(
    "Alternative route keys:",
    sorted(
        alt_route.keys()
    ),
)


overlap = route_overlap_percent(
    primary["path_indices"],
    alt_route["path_indices"],
)


comparison = compare_routes(
    primary,
    alt_route,
)


print(
    "Alternative distance:",
    round(
        route_distance(
            alt_route
        ),
        2,
    ),
    "km",
)

print(
    "Route overlap:",
    round(
        overlap,
        2,
    ),
    "%",
)

print(
    "Extra distance:",
    round(
        comparison[
            "extra_distance_km"
        ],
        2,
    ),
    "km",
)

print(
    "Distance change:",
    round(
        comparison[
            "distance_change_percent"
        ],
        2,
    ),
    "%",
)

print(
    "Penalty multiplier:",
    alternative[
        "penalty_multiplier"
    ],
)

print(
    "Corridor radius:",
    alternative[
        "corridor_radius_cells"
    ],
    "cells",
)


assert overlap < 100.0


print()
print(
    "ALL ALTERNATIVE ROUTING CHECKS PASSED"
)

print(
    "POLARGUARD ALTERNATIVE ROUTING COMPLETE"
)
