import heapq
import math
import numpy as np


def haversine_km(lat1, lon1, lat2, lon2):
    """
    Great-circle distance in kilometres.
    """

    R = 6371.0088

    lat1 = math.radians(float(lat1))
    lon1 = math.radians(float(lon1))
    lat2 = math.radians(float(lat2))
    lon2 = math.radians(float(lon2))

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2.0) ** 2
        +
        math.cos(lat1)
        *
        math.cos(lat2)
        *
        math.sin(dlon / 2.0) ** 2
    )

    c = 2.0 * math.atan2(
        math.sqrt(a),
        math.sqrt(1.0 - a)
    )

    return R * c


def nearest_grid_cell(
    grid_lat,
    grid_lon,
    target_lat,
    target_lon
):
    """
    Find nearest grid cell to a lat/lon point.
    """

    distance_squared = (
        (grid_lat - target_lat) ** 2
        +
        (
            (grid_lon - target_lon)
            *
            np.cos(
                np.radians(target_lat)
            )
        ) ** 2
    )

    flat_index = np.nanargmin(
        distance_squared
    )

    row, col = np.unravel_index(
        flat_index,
        grid_lat.shape
    )

    return int(row), int(col)


def get_neighbors(
    row,
    col,
    rows,
    cols
):
    """
    8-direction movement.
    """

    directions = [
        (-1, 0),
        (1, 0),
        (0, -1),
        (0, 1),

        (-1, -1),
        (-1, 1),
        (1, -1),
        (1, 1),
    ]

    neighbors = []

    for dr, dc in directions:

        nr = row + dr
        nc = col + dc

        if (
            0 <= nr < rows
            and
            0 <= nc < cols
        ):
            neighbors.append(
                (nr, nc)
            )

    return neighbors


def heuristic(
    row,
    col,
    goal_row,
    goal_col,
    grid_lat,
    grid_lon
):
    """
    A* heuristic:
    direct geographic distance to goal.
    """

    return haversine_km(
        grid_lat[row, col],
        grid_lon[row, col],
        grid_lat[goal_row, goal_col],
        grid_lon[goal_row, goal_col]
    )


def reconstruct_path(
    came_from,
    current
):
    """
    Reconstruct A* route.
    """

    path = [
        current
    ]

    while current in came_from:

        current = (
            came_from[current]
        )

        path.append(
            current
        )

    path.reverse()

    return path


def astar_route(
    routing_cost,
    grid_lat,
    grid_lon,
    start_lat,
    start_lon,
    destination_lat,
    destination_lon,
    blocked_cost=np.inf
):
    """
    Find a minimum-cost route using A*.

    routing_cost:
        output from risk_engine.py

    Returns dictionary containing:
        success
        path_indices
        path_coordinates
        total_distance_km
        accumulated_cost
        start_cell
        destination_cell
    """

    routing_cost = np.asarray(
        routing_cost,
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
        routing_cost.shape
        !=
        grid_lat.shape
        or
        routing_cost.shape
        !=
        grid_lon.shape
    ):
        raise ValueError(
            "routing_cost, grid_lat and grid_lon "
            "must have matching shapes."
        )

    rows, cols = (
        routing_cost.shape
    )

    start = nearest_grid_cell(
        grid_lat,
        grid_lon,
        start_lat,
        start_lon
    )

    goal = nearest_grid_cell(
        grid_lat,
        grid_lon,
        destination_lat,
        destination_lon
    )

    if not np.isfinite(
        routing_cost[start]
    ):
        return {
            "success": False,
            "reason": "Start cell is blocked.",
            "path_indices": [],
            "path_coordinates": [],
            "total_distance_km": 0.0,
            "accumulated_cost": np.inf,
            "start_cell": start,
            "destination_cell": goal
        }

    if not np.isfinite(
        routing_cost[goal]
    ):
        return {
            "success": False,
            "reason": "Destination cell is blocked.",
            "path_indices": [],
            "path_coordinates": [],
            "total_distance_km": 0.0,
            "accumulated_cost": np.inf,
            "start_cell": start,
            "destination_cell": goal
        }

    open_heap = []

    heapq.heappush(
        open_heap,
        (
            heuristic(
                start[0],
                start[1],
                goal[0],
                goal[1],
                grid_lat,
                grid_lon
            ),
            0.0,
            start
        )
    )

    came_from = {}

    g_score = {
        start: 0.0
    }

    closed_set = set()

    while open_heap:

        _, current_g, current = (
            heapq.heappop(
                open_heap
            )
        )

        if current in closed_set:
            continue

        if current == goal:

            path_indices = reconstruct_path(
                came_from,
                current
            )

            path_coordinates = []

            total_distance_km = 0.0

            for row, col in path_indices:

                path_coordinates.append(
                    {
                        "latitude":
                            float(
                                grid_lat[
                                    row,
                                    col
                                ]
                            ),

                        "longitude":
                            float(
                                grid_lon[
                                    row,
                                    col
                                ]
                            ),

                        "row":
                            int(row),

                        "col":
                            int(col),

                        "routing_cost":
                            float(
                                routing_cost[
                                    row,
                                    col
                                ]
                            )
                    }
                )

            for i in range(
                1,
                len(
                    path_coordinates
                )
            ):

                previous = (
                    path_coordinates[
                        i - 1
                    ]
                )

                current_point = (
                    path_coordinates[
                        i
                    ]
                )

                total_distance_km += (
                    haversine_km(
                        previous[
                            "latitude"
                        ],
                        previous[
                            "longitude"
                        ],
                        current_point[
                            "latitude"
                        ],
                        current_point[
                            "longitude"
                        ]
                    )
                )

            return {
                "success": True,
                "reason": "Route found.",
                "path_indices":
                    path_indices,
                "path_coordinates":
                    path_coordinates,
                "total_distance_km":
                    float(
                        total_distance_km
                    ),
                "accumulated_cost":
                    float(
                        current_g
                    ),
                "start_cell":
                    start,
                "destination_cell":
                    goal
            }

        closed_set.add(
            current
        )

        current_row = (
            current[0]
        )

        current_col = (
            current[1]
        )

        for neighbor in get_neighbors(
            current_row,
            current_col,
            rows,
            cols
        ):

            if neighbor in closed_set:
                continue

            neighbor_row = (
                neighbor[0]
            )

            neighbor_col = (
                neighbor[1]
            )

            cell_cost = (
                routing_cost[
                    neighbor_row,
                    neighbor_col
                ]
            )

            if (
                not np.isfinite(
                    cell_cost
                )
            ):
                continue

            movement_distance = (
                haversine_km(
                    grid_lat[
                        current_row,
                        current_col
                    ],
                    grid_lon[
                        current_row,
                        current_col
                    ],
                    grid_lat[
                        neighbor_row,
                        neighbor_col
                    ],
                    grid_lon[
                        neighbor_row,
                        neighbor_col
                    ]
                )
            )

            if (
                movement_distance
                <=
                0.0
            ):
                continue

            average_cost = (
                routing_cost[
                    current_row,
                    current_col
                ]
                +
                cell_cost
            ) / 2.0

            tentative_g = (
                current_g
                +
                movement_distance
                *
                average_cost
            )

            previous_best = (
                g_score.get(
                    neighbor,
                    np.inf
                )
            )

            if (
                tentative_g
                <
                previous_best
            ):

                came_from[
                    neighbor
                ] = current

                g_score[
                    neighbor
                ] = tentative_g

                h_score = heuristic(
                    neighbor_row,
                    neighbor_col,
                    goal[0],
                    goal[1],
                    grid_lat,
                    grid_lon
                )

                f_score = (
                    tentative_g
                    +
                    h_score
                )

                heapq.heappush(
                    open_heap,
                    (
                        f_score,
                        tentative_g,
                        neighbor
                    )
                )

    return {
        "success": False,
        "reason": "No valid route found.",
        "path_indices": [],
        "path_coordinates": [],
        "total_distance_km": 0.0,
        "accumulated_cost": np.inf,
        "start_cell": start,
        "destination_cell": goal
    }


def summarize_route_risk(
    route_result,
    combined_risk,
    sea_ice_risk=None,
    iceberg_risk=None,
    uncertainty_risk=None
):
    """
    Produce a simple route risk summary.
    """

    if not route_result[
        "success"
    ]:

        return {
            "mean_risk":
                np.nan,
            "max_risk":
                np.nan,
            "classification":
                "NO ROUTE"
        }

    path = route_result[
        "path_indices"
    ]

    risk_values = []

    sea_ice_values = []

    iceberg_values = []

    uncertainty_values = []

    for row, col in path:

        risk_values.append(
            combined_risk[
                row,
                col
            ]
        )

        if sea_ice_risk is not None:

            sea_ice_values.append(
                sea_ice_risk[
                    row,
                    col
                ]
            )

        if iceberg_risk is not None:

            iceberg_values.append(
                iceberg_risk[
                    row,
                    col
                ]
            )

        if uncertainty_risk is not None:

            uncertainty_values.append(
                uncertainty_risk[
                    row,
                    col
                ]
            )

    risk_values = np.asarray(
        risk_values,
        dtype=float
    )

    mean_risk = float(
        np.nanmean(
            risk_values
        )
    )

    max_risk = float(
        np.nanmax(
            risk_values
        )
    )

    if max_risk < 0.25:

        classification = "LOW"

    elif max_risk < 0.50:

        classification = "MODERATE"

    elif max_risk < 0.75:

        classification = "HIGH"

    else:

        classification = "VERY HIGH"

    result = {
        "mean_risk":
            mean_risk,

        "max_risk":
            max_risk,

        "classification":
            classification
    }

    if sea_ice_values:

        result[
            "max_sea_ice_risk"
        ] = float(
            np.nanmax(
                sea_ice_values
            )
        )

    if iceberg_values:

        result[
            "max_iceberg_risk"
        ] = float(
            np.nanmax(
                iceberg_values
            )
        )

    if uncertainty_values:

        result[
            "max_uncertainty_risk"
        ] = float(
            np.nanmax(
                uncertainty_values
            )
        )

    return result