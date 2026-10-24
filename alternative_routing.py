import numpy as np

from routing_engine import astar_route


def _route_distance_km(route):
    """
    Read distance from the routing_engine result without assuming
    one historical key name.
    """
    for key in (
        "total_distance_km",
        "distance_km",
        "route_distance_km",
    ):
        if key in route:
            return float(route[key])

    raise KeyError(
        "Route result does not contain a recognized distance key. "
        f"Available keys: {sorted(route.keys())}"
    )


def _route_cost(route):
    """
    Read accumulated route cost when routing_engine exposes it.
    Returns None if the current routing_engine version does not.
    """
    for key in (
        "accumulated_cost",
        "total_cost",
        "route_cost",
        "navigation_cost",
    ):
        if key in route:
            return float(route[key])

    return None


def route_overlap_percent(primary_path, alternative_path):
    """
    Percentage of alternative-route interior cells also used by
    the primary route. Shared start/end cells are ignored.
    """

    if not primary_path or not alternative_path:
        return 100.0

    primary = set(
        tuple(cell)
        for cell in primary_path[1:-1]
    )

    alternative = [
        tuple(cell)
        for cell in alternative_path[1:-1]
    ]

    if not alternative:
        return 100.0

    overlap = sum(
        1
        for cell in alternative
        if cell in primary
    )

    return (
        100.0
        * overlap
        / len(alternative)
    )


def build_route_penalty_mask(
    shape,
    primary_path,
    corridor_radius_cells=1,
):
    """
    Build a mask around the recommended-route corridor.
    """

    rows, cols = shape
    mask = np.zeros(
        shape,
        dtype=bool,
    )

    if not primary_path:
        return mask

    for row, col in primary_path:

        for dr in range(
            -corridor_radius_cells,
            corridor_radius_cells + 1,
        ):

            for dc in range(
                -corridor_radius_cells,
                corridor_radius_cells + 1,
            ):

                rr = row + dr
                cc = col + dc

                if (
                    0 <= rr < rows
                    and
                    0 <= cc < cols
                ):
                    mask[rr, cc] = True

    # Both routes must retain the same endpoints.
    start_row, start_col = primary_path[0]
    end_row, end_col = primary_path[-1]

    mask[start_row, start_col] = False
    mask[end_row, end_col] = False

    return mask


def build_alternative_route(
    routing_cost,
    grid_lat,
    grid_lon,
    start_lat,
    start_lon,
    destination_lat,
    destination_lon,
    primary_path,
    target_max_overlap_percent=65.0,
):
    """
    Search for a genuinely different safe A* route.

    Existing infinite/blocked navigation cells stay blocked.
    Only the already-safe cells around the primary route receive
    an extra cost penalty.
    """

    routing_cost = np.asarray(
        routing_cost,
        dtype=float,
    )

    grid_lat = np.asarray(
        grid_lat,
        dtype=float,
    )

    grid_lon = np.asarray(
        grid_lon,
        dtype=float,
    )

    if (
        routing_cost.shape
        != grid_lat.shape
        or
        routing_cost.shape
        != grid_lon.shape
    ):
        raise ValueError(
            "routing_cost, grid_lat and grid_lon "
            "must have matching shapes."
        )

    if not primary_path:
        return {
            "success": False,
            "reason": "Primary route is empty.",
            "route": None,
            "overlap_percent": 100.0,
            "corridor_radius_cells": None,
            "penalty_multiplier": None,
        }

    attempts = [
        (0, 4.0),
        (0, 8.0),
        (1, 4.0),
        (1, 8.0),
        (1, 15.0),
        (2, 8.0),
        (2, 15.0),
        (2, 30.0),
    ]

    best = None

    for corridor_radius, multiplier in attempts:

        penalty_mask = build_route_penalty_mask(
            routing_cost.shape,
            primary_path,
            corridor_radius_cells=corridor_radius,
        )

        alternative_cost = routing_cost.copy()

        finite_penalized = (
            penalty_mask
            &
            np.isfinite(
                alternative_cost
            )
        )

        alternative_cost[
            finite_penalized
        ] *= multiplier

        route = astar_route(
            routing_cost=alternative_cost,
            grid_lat=grid_lat,
            grid_lon=grid_lon,
            start_lat=start_lat,
            start_lon=start_lon,
            destination_lat=destination_lat,
            destination_lon=destination_lon,
        )

        if not route["success"]:
            continue

        overlap = route_overlap_percent(
            primary_path,
            route["path_indices"],
        )

        candidate = {
            "success": True,
            "reason": "Alternative route found.",
            "route": route,
            "overlap_percent": float(
                overlap
            ),
            "corridor_radius_cells": int(
                corridor_radius
            ),
            "penalty_multiplier": float(
                multiplier
            ),
        }

        if (
            best is None
            or
            overlap
            <
            best["overlap_percent"]
        ):
            best = candidate

        if (
            overlap
            <=
            target_max_overlap_percent
        ):
            return candidate

    if best is not None:

        best["reason"] = (
            "Best alternative found, but route separation "
            "is limited by the currently navigable corridor."
        )

        return best

    return {
        "success": False,
        "reason": (
            "No second navigable route exists between the "
            "selected endpoints under the current forecast "
            "and vessel constraints."
        ),
        "route": None,
        "overlap_percent": 100.0,
        "corridor_radius_cells": None,
        "penalty_multiplier": None,
    }


def compare_routes(
    primary_route,
    alternative_route,
):
    """
    Compare two successful routing_engine route dictionaries.
    Compatible with PolarGuard's total_distance_km key.
    """

    if (
        not primary_route
        or
        not primary_route.get(
            "success",
            False,
        )
    ):
        raise ValueError(
            "Primary route must be successful."
        )

    if (
        not alternative_route
        or
        not alternative_route.get(
            "success",
            False,
        )
    ):
        raise ValueError(
            "Alternative route must be successful."
        )

    primary_distance = _route_distance_km(
        primary_route
    )

    alternative_distance = _route_distance_km(
        alternative_route
    )

    extra_distance = (
        alternative_distance
        -
        primary_distance
    )

    distance_change_percent = (
        100.0
        *
        extra_distance
        /
        primary_distance
        if primary_distance > 0
        else 0.0
    )

    primary_cost = _route_cost(
        primary_route
    )

    alternative_cost = _route_cost(
        alternative_route
    )

    if (
        primary_cost is not None
        and
        alternative_cost is not None
        and
        primary_cost > 0
    ):
        cost_change_percent = (
            100.0
            *
            (
                alternative_cost
                -
                primary_cost
            )
            /
            primary_cost
        )
    else:
        cost_change_percent = None

    return {
        "primary_distance_km":
            primary_distance,

        "alternative_distance_km":
            alternative_distance,

        "extra_distance_km":
            extra_distance,

        "distance_change_percent":
            distance_change_percent,

        "primary_accumulated_cost":
            primary_cost,

        "alternative_accumulated_cost":
            alternative_cost,

        "cost_change_percent":
            cost_change_percent,
    }
