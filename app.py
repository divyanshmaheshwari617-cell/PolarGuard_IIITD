import json
import pandas as pd
from validation_2025_ui import render_validation_2025
from polarguard_ui import (
    apply_polarguard_theme,
    render_commandbar,
    render_hero,
    render_section,
    render_sidebar,
    render_current_conditions,
    render_timeline,
    render_iceberg_badge,
    render_panel,
)
from operational_forecast_service import (
    build_operational_forecast_bundle,
    get_operational_horizon,
)

from sea_ice_intelligence_service import (
    format_horizon_display_metrics,
)
import pydeck as pdk
import folium
from folium.plugins import Fullscreen, MeasureControl, MousePosition
from streamlit_folium import st_folium
from pyproj import Transformer
import os
import tempfile
import time
from huggingface_hub import hf_hub_download
from polarguard_map_ui import (
    create_polarguard_map,
    add_map_hud,
    add_navigation_legend,
    add_current_icebergs,
    add_route_endpoints,
    add_recommended_route,
    add_alternative_route,
    add_iceberg_trajectory,
    add_uncertainty_cells,
    add_risk_cells,
    finalize_polarguard_map,
)

import matplotlib.pyplot as plt
import numpy as np
import streamlit as st
import xarray as xr
from datetime import date

from sea_ice_service import predict_sea_ice, load_uncertainty
from satellite_data_service import load_latest_satellite_input
from current_iceberg_service import load_current_icebergs
from operational_status_service import build_environmental_status
from polarguard_pipeline import run_polarguard
from navigation_service import build_navigation_route
from risk_engine import build_risk_grid
from vessel_constraints import build_navigation_mask
from routing_engine import nearest_grid_cell
from hazard_engine import (
    build_hazard_zones,
    analyze_route_hazards,
    generate_route_alerts,
    summarize_hazard_grid,
)
from alternative_routing import (
    build_alternative_route,
    compare_routes,
)


# ============================================================
# CONFIGURATION
# ============================================================

HF_REPO_ID = "divyanshmahesh/PolarGuard-Data"

if os.path.exists("data/processed/test_2025.nc"):
    HISTORICAL_FILE = "data/processed/test_2025.nc"
else:
    HISTORICAL_FILE = hf_hub_download(
        repo_id=HF_REPO_ID,
        filename="test_2025.nc",
     repo_type="dataset",
        token=st.secrets["HF_TOKEN"],
    )

if os.path.exists("data/processed/sea_ice_2019_2025.nc"):
    SEA_ICE_HISTORY_FILE = "data/processed/sea_ice_2019_2025.nc"
else:
    SEA_ICE_HISTORY_FILE = hf_hub_download(
        repo_id=HF_REPO_ID,
        filename="sea_ice_2019_2025.nc",
        repo_type="dataset",
        token=st.secrets["HF_TOKEN"],
    )

EXPECTED_Y = 332
EXPECTED_X = 316


st.set_page_config(
    page_title="PolarGuard Forecasting System",
    page_icon="🧊",
    layout="wide"
)

# ============================================================
# PRESENTATION-ONLY UI POLISH
# ============================================================

# ============================================================
# POLARGUARD ADVANCED UI V2
# ============================================================

apply_polarguard_theme()

render_commandbar()

render_hero()
# ============================================================
# LOAD HISTORICAL DATA
# ============================================================

@st.cache_resource
def load_historical():
    return xr.open_dataarray(HISTORICAL_FILE)


@st.cache_data(ttl=3600, show_spinner=False)
def get_latest_satellite_route_bundle():
    """
    Load the latest available NOAA/NSIDC G10016 V4 Antarctic SIC
    observations and run the frozen Member 1 forecast for routing.

    Returns the same key layout used by get_member1_map_bundle(), plus
    source/provenance metadata. This lets the navigation engine consume
    near-real-time sea-ice conditions without changing either frozen ML model.
    """
    satellite_bundle = load_latest_satellite_input()

    current = np.asarray(satellite_bundle["current"], dtype=np.float32)
    lag1 = np.asarray(satellite_bundle["lag1"], dtype=np.float32)
    lag2 = np.asarray(satellite_bundle["lag2"], dtype=np.float32)
    lag3 = np.asarray(satellite_bundle["lag3"], dtype=np.float32)

    x_coords = np.asarray(satellite_bundle["x"])
    y_coords = np.asarray(satellite_bundle["y"])
    current_date = np.datetime64(satellite_bundle["date"], "D")

    validate_grid(
        current,
        lag1,
        lag2,
        lag3,
    )

    forecasts = predict_sea_ice(
        current=current,
        lag1=lag1,
        lag2=lag2,
        lag3=lag3,
        x_coords=x_coords,
        y_coords=y_coords,
        date=current_date,
    )

    uncertainty = load_uncertainty()

    return {
        "date": str(current_date),
        "current": current,
        "forecast_24h": np.asarray(forecasts["24h"]),
        "forecast_48h": np.asarray(forecasts["48h"]),
        "forecast_72h": np.asarray(forecasts["72h"]),
        "uncertainty_24h": np.asarray(uncertainty["24h"]),
        "uncertainty_48h": np.asarray(uncertainty["48h"]),
        "uncertainty_72h": np.asarray(uncertainty["72h"]),
        "x": x_coords,
        "y": y_coords,
        "source": "NOAA / NSIDC G10016 Version 4 Near-Real-Time Satellite",
        "provider_lag_days": int(satellite_bundle.get("provider_lag_days", 0)),
        "valid_current_cells": int(
            satellite_bundle.get(
                "valid_current_cells",
                np.isfinite(current).sum(),
            )
        ),
        "mean_current_sic": float(
            satellite_bundle.get(
                "mean_current_sic",
                np.nanmean(current),
            )
        ),
    }
@st.cache_data(ttl=3600, show_spinner=False)
def get_operational_forecast_bundle():
    """
    Build the complete PolarGuard operational forecast package.

    Includes:
    - CURRENT observed SIC
    - Member-1 +24H/+48H/+72H SIC forecasts
    - RMSE-based forecast uncertainty
    - current genuine BYU iceberg observations
    - operational Member-2 predictions only where genuine
      four-day observation history is available
    """

    member1_bundle = (
        get_latest_satellite_route_bundle()
    )

    return (
        build_operational_forecast_bundle(
            member1_bundle=
                member1_bundle,

            run_member2=True,
        )
    )
# ============================================================
# FINAL OPERATIONAL HORIZON HELPERS
# ============================================================

def normalize_operational_ui_horizon(value):
    """
    Convert existing Streamlit horizon labels to the
    operational coordinator labels.
    """

    lookup = {
        "All": "CURRENT",
        "Current": "CURRENT",
        "CURRENT": "CURRENT",

        "+24h": "+24H",
        "+24H": "+24H",

        "+48h": "+48H",
        "+48H": "+48H",

        "+72h": "+72H",
        "+72H": "+72H",
    }

    value = str(value)

    if value not in lookup:
        raise ValueError(
            f"Unsupported operational horizon: {value}"
        )

    return lookup[value]


def get_operational_navigation_inputs(
    operational_bundle,
    horizon,
):
    """
    Return horizon-matched SIC, uncertainty and iceberg hazards.

    CURRENT:
        observed SIC + observed iceberg positions

    FUTURE:
        Member-1 SIC forecast + RMSE uncertainty +
        Member-2 iceberg predictions only where genuinely available
    """

    operational_horizon = (
        normalize_operational_ui_horizon(horizon)
    )

    state = get_operational_horizon(
        operational_bundle,
        operational_horizon,
    )

    sic = np.asarray(
        state["sic"],
        dtype=float,
    )

    uncertainty = state.get(
        "uncertainty"
    )

    if uncertainty is None:
        uncertainty = np.where(
            np.isfinite(sic),
            0.0,
            np.nan,
        )
    else:
        uncertainty = np.asarray(
            uncertainty,
            dtype=float,
        )

    iceberg_positions = []

    for item in state.get(
        "iceberg_positions",
        [],
    ):
        latitude = item.get("latitude")
        longitude = item.get("longitude")

        if (
            latitude is None
            or longitude is None
        ):
            continue

        iceberg_positions.append(
            {
                "iceberg_id": item.get(
                    "iceberg_id",
                    "UNKNOWN",
                ),
                "latitude": float(latitude),
                "longitude": float(longitude),
            }
        )

    return {
        "operational_horizon":
            operational_horizon,

        "sic":
            sic,

        "uncertainty":
            uncertainty,

        "iceberg_positions":
            iceberg_positions,

        "metrics":
            state["sea_ice_metrics"],

        "iceberg_hazard_count":
            len(iceberg_positions),

        "trajectory_coverage":
            state["trajectory_coverage"],
    }
@st.cache_data(ttl=1800, show_spinner=False)
def get_operational_environment_status(requested_date, latitude, longitude):
    """
    Load the real near-real-time environmental forcing status used by
    PolarGuard Member 2: ECMWF wind, Copernicus current, and NOAA/NSIDC SIC.
    Provider timestamps are preserved; no synthetic synchronization is claimed.
    """
    return build_environmental_status(
        date=str(requested_date),
        latitude=float(latitude),
        longitude=float(longitude),
    )


@st.cache_data(ttl=3600, show_spinner=False)
def get_latest_observed_iceberg_hazards():
    """
    Load the latest real Antarctic iceberg positions from BYU.

    These observations are used directly as CURRENT-route hazard locations.
    No synthetic trajectory points are created.
    """
    bundle = load_current_icebergs()
    dataframe = bundle["dataframe"].copy()

    if dataframe.empty:
        raise RuntimeError(
            "The current BYU iceberg service returned no usable observations."
        )

    positions = []

    for _, row in dataframe.iterrows():
        latitude = float(row["latitude"])
        longitude = float(row["longitude"])

        if not (
            np.isfinite(latitude)
            and np.isfinite(longitude)
        ):
            continue

        positions.append(
            {
                "iceberg_id": str(row["iceberg_id"]).upper(),
                "latitude": latitude,
                "longitude": longitude,
                "observation_date": str(row["observation_date"]),
                "age_days": int(row["age_days"]),
                "freshness_status": str(row["freshness_status"]),
            }
        )

    if not positions:
        raise RuntimeError(
            "No finite current iceberg coordinates were available."
        )

    observation_dates = sorted(
        {
            item["observation_date"]
            for item in positions
        }
    )

    return {
        "positions": positions,
        "iceberg_count": len(positions),
        "source": "BYU Scatterometer Climate Pathfinder",
        "source_type": "Near-real-time observed iceberg positions",
        "page_last_revised": bundle.get("page_last_revised"),
        "retrieved_at_utc": bundle.get("retrieved_at_utc"),
        "observation_dates": observation_dates,
        "latest_observation_date": (
            max(observation_dates)
            if observation_dates
            else None
        ),
        "oldest_observation_date": (
            min(observation_dates)
            if observation_dates
            else None
        ),
        "max_age_days": max(
            item["age_days"]
            for item in positions
        ),
    }


# ============================================================
# MEMBER 1 MAP-OVERLAY HELPERS
# ============================================================

@st.cache_resource
def load_full_sea_ice_history():
    """Open the frozen 2019-2025 Member 1 SIC history lazily."""
    return xr.open_dataarray(SEA_ICE_HISTORY_FILE)


@st.cache_data(show_spinner=False)
def get_member1_map_bundle(initialization_date_string):
    """
    Build a date-synchronized Member 1 map bundle for the iceberg page.

    This uses the frozen Member 1 service only for visualization/downstream
    decision support. Future SIC forecasts are NOT fed back into Member 2.
    """
    ds = load_full_sea_ice_history()
    target_date = np.datetime64(initialization_date_string, "D")
    dates = ds.time.values.astype("datetime64[D]")

    matches = np.where(dates == target_date)[0]
    if len(matches) == 0:
        raise ValueError(
            f"Sea-ice history does not contain {initialization_date_string}."
        )

    current_index = int(matches[0])
    if current_index < 3:
        raise ValueError(
            "At least three previous daily sea-ice maps are required "
            "for a synchronized Member 1 overlay."
        )

    current = np.asarray(ds.values[current_index], dtype=np.float32)
    lag1 = np.asarray(ds.values[current_index - 1], dtype=np.float32)
    lag2 = np.asarray(ds.values[current_index - 2], dtype=np.float32)
    lag3 = np.asarray(ds.values[current_index - 3], dtype=np.float32)

    x_coords = np.asarray(ds.x.values)
    y_coords = np.asarray(ds.y.values)

    forecasts = predict_sea_ice(
        current=current,
        lag1=lag1,
        lag2=lag2,
        lag3=lag3,
        x_coords=x_coords,
        y_coords=y_coords,
        date=target_date,
    )

    uncertainty = load_uncertainty()

    return {
        "date": str(target_date),
        "current": current,
        "forecast_24h": np.asarray(forecasts["24h"]),
        "forecast_48h": np.asarray(forecasts["48h"]),
        "forecast_72h": np.asarray(forecasts["72h"]),
        "uncertainty_24h": np.asarray(uncertainty["24h"]),
        "uncertainty_48h": np.asarray(uncertainty["48h"]),
        "uncertainty_72h": np.asarray(uncertainty["72h"]),
        "x": x_coords,
        "y": y_coords,
    }


def sic_color(value):
    """Readable blue scale for SIC values in [0, 1]."""
    if value < 0.10:
        return "#eff6ff"
    if value < 0.30:
        return "#dbeafe"
    if value < 0.50:
        return "#bfdbfe"
    if value < 0.70:
        return "#93c5fd"
    if value < 0.90:
        return "#60a5fa"
    return "#2563eb"


def projected_grid_to_latlon(x_coords, y_coords):
    """
    Convert the frozen Member 1 EPSG:3412 grid to WGS84 latitude/longitude.

    This is used by the routing engine so every SIC grid cell has a
    geographic position.
    """
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
# SITE + FORECAST-AWARE SEA-ICE HELPERS
# ============================================================

def get_site_sic(
    sic,
    grid_lat,
    grid_lon,
    latitude,
    longitude,
):
    """
    Return sea-ice concentration at the model-grid cell nearest
    to the requested geographic position.
    """
    row, col = nearest_grid_cell(
        grid_lat,
        grid_lon,
        float(latitude),
        float(longitude),
    )

    value = float(sic[row, col])

    if not np.isfinite(value):
        return {
            "available": False,
            "sic": None,
            "sic_percent": None,
            "row": int(row),
            "col": int(col),
        }

    value = float(np.clip(value, 0.0, 1.0))

    return {
        "available": True,
        "sic": value,
        "sic_percent": value * 100.0,
        "row": int(row),
        "col": int(col),
        "grid_latitude": float(grid_lat[row, col]),
        "grid_longitude": float(grid_lon[row, col]),
    }


def classify_site_ice(sic_percent):
    """Simple display-only SIC class for the selected location."""
    sic_percent = float(sic_percent)

    if sic_percent < 15.0:
        return "LOW ICE"
    if sic_percent < 40.0:
        return "MODERATE ICE"
    if sic_percent < 70.0:
        return "HIGH ICE"
    return "VERY HIGH ICE"


def calculate_route_ice_exposure(path_indices, sic):
    """
    Summarize SIC encountered along a calculated route.
    """
    values = []

    for row, col in path_indices:
        value = float(sic[row, col])

        if np.isfinite(value):
            values.append(value)

    if not values:
        return {
            "mean_sic_percent": None,
            "max_sic_percent": None,
            "ice_exposure_percent": None,
        }

    values = np.asarray(values, dtype=float)

    return {
        "mean_sic_percent": float(np.mean(values) * 100.0),
        "max_sic_percent": float(np.max(values) * 100.0),
        "ice_exposure_percent": float(np.mean(values >= 0.15) * 100.0),
    }


def build_forecast_aware_environment(operational_bundle):
    """
    Build a conservative planning environment spanning CURRENT to +72H.

    For each grid cell:
    - SIC is the maximum expected SIC over CURRENT/+24H/+48H/+72H.
    - uncertainty is the maximum available uncertainty over the same horizons.
    - iceberg positions are the union of observed/predicted positions.

    This does not retrain or alter either frozen model.
    """
    horizons = ["CURRENT", "+24H", "+48H", "+72H"]

    sic_fields = []
    uncertainty_fields = []
    iceberg_positions = []
    seen = set()

    for horizon in horizons:
        nav = get_operational_navigation_inputs(
            operational_bundle,
            horizon,
        )

        sic_fields.append(
            np.asarray(nav["sic"], dtype=float)
        )

        uncertainty_fields.append(
            np.asarray(nav["uncertainty"], dtype=float)
        )

        for iceberg in nav["iceberg_positions"]:
            key = (
                str(iceberg.get("iceberg_id", "UNKNOWN")),
                round(float(iceberg["latitude"]), 4),
                round(float(iceberg["longitude"]), 4),
            )

            if key in seen:
                continue

            seen.add(key)
            iceberg_positions.append(dict(iceberg))

    sic_stack = np.stack(sic_fields, axis=0)
    uncertainty_stack = np.stack(uncertainty_fields, axis=0)

    valid_sic = np.any(np.isfinite(sic_stack), axis=0)
    valid_uncertainty = np.any(
        np.isfinite(uncertainty_stack),
        axis=0,
    )

    with np.errstate(all="ignore"):
        forecast_sic = np.nanmax(sic_stack, axis=0)
        forecast_uncertainty = np.nanmax(
            uncertainty_stack,
            axis=0,
        )

    forecast_sic = np.where(
        valid_sic,
        forecast_sic,
        np.nan,
    )

    forecast_uncertainty = np.where(
        valid_uncertainty,
        forecast_uncertainty,
        np.nan,
    )

    finite_sic = forecast_sic[np.isfinite(forecast_sic)]

    if finite_sic.size:
        mean_sic = float(np.mean(finite_sic))
        maximum_sic = float(np.max(finite_sic))
        ice_covered_grid = float(
            np.mean(finite_sic >= 0.15) * 100.0
        )
    else:
        mean_sic = np.nan
        maximum_sic = np.nan
        ice_covered_grid = np.nan

    finite_uncertainty = forecast_uncertainty[
        np.isfinite(forecast_uncertainty)
    ]

    mean_uncertainty = (
        float(np.mean(finite_uncertainty))
        if finite_uncertainty.size
        else np.nan
    )

    return {
        "sic": forecast_sic,
        "uncertainty": forecast_uncertainty,
        "iceberg_positions": iceberg_positions,
        "operational_horizon": "CURRENT → +72H",
        "metrics": {
            "mean_sic": (
                f"{mean_sic * 100.0:.1f}%"
                if np.isfinite(mean_sic)
                else "N/A"
            ),
            "maximum_sic": (
                f"{maximum_sic * 100.0:.1f}%"
                if np.isfinite(maximum_sic)
                else "N/A"
            ),
            "ice_covered_grid": (
                f"{ice_covered_grid:.1f}%"
                if np.isfinite(ice_covered_grid)
                else "N/A"
            ),
            "uncertainty": (
                f"{mean_uncertainty * 100.0:.2f} SIC pp"
                if np.isfinite(mean_uncertainty)
                else "N/A"
            ),
        },
        "iceberg_hazard_count": len(iceberg_positions),
        "trajectory_coverage": "CURRENT through +72H union",
    }


def _connected_component_cells(valid_mask, start):
    """
    Return one 8-connected component of navigable cells.
    """
    rows, cols = valid_mask.shape
    stack = [start]
    seen = {start}
    component = []

    directions = (
        (-1, -1), (-1, 0), (-1, 1),
        (0, -1),           (0, 1),
        (1, -1),  (1, 0),  (1, 1),
    )

    while stack:
        row, col = stack.pop()
        component.append((row, col))

        for dr, dc in directions:
            nr = row + dr
            nc = col + dc

            if (
                0 <= nr < rows
                and 0 <= nc < cols
                and valid_mask[nr, nc]
                and (nr, nc) not in seen
            ):
                seen.add((nr, nc))
                stack.append((nr, nc))

    return component


def _approx_geo_distance_km(lat1, lon1, lat2, lon2):
    """
    Fast approximation used only for choosing demo endpoints.
    """
    mean_lat = np.radians((lat1 + lat2) / 2.0)
    dy = (lat2 - lat1) * 111.0
    dx = (lon2 - lon1) * 111.0 * np.cos(mean_lat)
    return float(np.hypot(dx, dy))


def find_safe_demo_route(
    sic,
    uncertainty,
    grid_lat,
    grid_lon,
    iceberg_positions,
    vessel_profile,
    safety_radius_km,
    influence_radius_km,
):
    """
    Find two real, navigable ocean grid cells that are connected and
    far enough apart to make a meaningful routing demonstration.

    The function does not invent coordinates. It selects them directly
    from the synchronized Member 1 / Member 2 risk grid.
    """

    risk = build_risk_grid(
        sic=sic,
        uncertainty=uncertainty,
        grid_lat=grid_lat,
        grid_lon=grid_lon,
        iceberg_positions=iceberg_positions,
        safety_radius_km=safety_radius_km,
        influence_radius_km=influence_radius_km,
    )

    nav_mask = build_navigation_mask(
        sic=sic,
        iceberg_risk=risk["iceberg_risk"],
        uncertainty_risk=risk["uncertainty_risk"],
        blocked_mask=risk["blocked_mask"],
        profile_name=vessel_profile,
    )

    valid = ~nav_mask["blocked_mask"]

    # Prefer genuinely lower-risk cells for demo endpoints.
    endpoint_candidates = (
        valid
        & np.isfinite(risk["combined_risk"])
        & (risk["combined_risk"] <= 0.35)
        & np.isfinite(grid_lat)
        & np.isfinite(grid_lon)
    )

    # If the low-risk filter is too strict, use every navigable cell.
    if np.count_nonzero(endpoint_candidates) < 50:
        endpoint_candidates = (
            valid
            & np.isfinite(grid_lat)
            & np.isfinite(grid_lon)
        )

    coords = np.argwhere(endpoint_candidates)

    if len(coords) < 2:
        raise RuntimeError(
            "The selected forecast/vessel profile does not contain enough "
            "navigable cells for an automatic demo route."
        )

    # Build connected components only on candidate cells. We scan from
    # distributed seeds instead of every cell to keep Streamlit responsive.
    sampled_seed_indices = np.linspace(
        0,
        len(coords) - 1,
        min(80, len(coords)),
        dtype=int,
    )

    best_component = []

    visited_global = set()

    for idx in sampled_seed_indices:
        seed = tuple(int(v) for v in coords[idx])

        if seed in visited_global:
            continue

        component = _connected_component_cells(
            endpoint_candidates,
            seed,
        )

        visited_global.update(component)

        if len(component) > len(best_component):
            best_component = component

    if len(best_component) < 2:
        raise RuntimeError(
            "No connected navigable region large enough for a demo route "
            "was found."
        )

    # Sample the component for fast endpoint selection.
    stride = max(len(best_component) // 1200, 1)
    sampled = best_component[::stride]

    # Two-sweep farthest-point search.
    seed = sampled[len(sampled) // 2]

    def farthest_from(cell, candidates):
        r0, c0 = cell
        lat0 = float(grid_lat[r0, c0])
        lon0 = float(grid_lon[r0, c0])

        best = cell
        best_distance = -1.0

        for rr, cc in candidates:
            distance = _approx_geo_distance_km(
                lat0,
                lon0,
                float(grid_lat[rr, cc]),
                float(grid_lon[rr, cc]),
            )

            # Prefer a useful SIH demo length without forcing an extreme route.
            if distance > best_distance:
                best_distance = distance
                best = (rr, cc)

        return best, best_distance

    endpoint_a, _ = farthest_from(seed, sampled)
    endpoint_b, total_distance = farthest_from(endpoint_a, sampled)

    # If the component is enormous, choose a point closer to 250-450 km
    # from endpoint A so the demo remains readable.
    if total_distance > 500.0:
        ar, ac = endpoint_a
        alat = float(grid_lat[ar, ac])
        alon = float(grid_lon[ar, ac])

        target = 320.0
        best_score = float("inf")
        selected_b = endpoint_b
        selected_distance = total_distance

        for rr, cc in sampled:
            distance = _approx_geo_distance_km(
                alat,
                alon,
                float(grid_lat[rr, cc]),
                float(grid_lon[rr, cc]),
            )

            if 140.0 <= distance <= 500.0:
                score = abs(distance - target)

                if score < best_score:
                    best_score = score
                    selected_b = (rr, cc)
                    selected_distance = distance

        endpoint_b = selected_b
        total_distance = selected_distance

    ar, ac = endpoint_a
    br, bc = endpoint_b

    return {
        "start_lat": float(grid_lat[ar, ac]),
        "start_lon": float(grid_lon[ar, ac]),
        "destination_lat": float(grid_lat[br, bc]),
        "destination_lon": float(grid_lon[br, bc]),
        "approx_distance_km": float(total_distance),
        "start_cell": (int(ar), int(ac)),
        "destination_cell": (int(br), int(bc)),
        "risk": risk,
        "navigation_mask": nav_mask,
    }


def explain_blocked_endpoint(
    navigation_result,
    grid_lat,
    grid_lon,
    requested_lat,
    requested_lon,
):
    """
    Explain why the nearest routing cell to a requested endpoint is blocked.
    """
    row, col = nearest_grid_cell(
        grid_lat,
        grid_lon,
        requested_lat,
        requested_lon,
    )

    nav_mask = navigation_result["navigation_mask"]
    risk = navigation_result["risk"]

    reasons = []

    if bool(nav_mask["blocked_by_sic"][row, col]):
        reasons.append("SIC exceeds the selected vessel limit")

    if bool(nav_mask["blocked_by_iceberg"][row, col]):
        reasons.append("inside the vessel iceberg exclusion threshold")

    if bool(nav_mask["blocked_by_uncertainty"][row, col]):
        reasons.append("forecast uncertainty exceeds the selected prototype limit")

    if bool(risk["blocked_mask"][row, col]):
        reasons.append("invalid/masked environmental grid cell")

    if not reasons and bool(nav_mask["blocked_mask"][row, col]):
        reasons.append("blocked by a combined navigation constraint")

    return {
        "row": int(row),
        "col": int(col),
        "latitude": float(grid_lat[row, col]),
        "longitude": float(grid_lon[row, col]),
        "sic": (
            float(risk["sea_ice_risk"][row, col])
            if np.isfinite(risk["sea_ice_risk"][row, col])
            else np.nan
        ),
        "iceberg_risk": (
            float(risk["iceberg_risk"][row, col])
            if np.isfinite(risk["iceberg_risk"][row, col])
            else np.nan
        ),
        "uncertainty_risk": (
            float(risk["uncertainty_risk"][row, col])
            if np.isfinite(risk["uncertainty_risk"][row, col])
            else np.nan
        ),
        "reasons": reasons,
    }



def _route_points_to_records(path_coordinates, route_name):
    records = []

    for sequence, point in enumerate(path_coordinates):
        records.append(
            {
                "route": route_name,
                "sequence": int(sequence),
                "latitude": float(point["latitude"]),
                "longitude": float(point["longitude"]),
            }
        )

    return records


def _route_geojson(path_coordinates, route_name, properties=None):
    props = {
        "name": route_name,
        "system": "PolarGuard",
        "product_type": "prototype decision-support route",
    }

    if properties:
        props.update(properties)

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": props,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [
                            float(point["longitude"]),
                            float(point["latitude"]),
                        ]
                        for point in path_coordinates
                    ],
                },
            }
        ],
    }


def _build_navigation_exports(nav_route_display):
    route = nav_route_display["route"]

    recommended_properties = {
        "routing_horizon": nav_route_display["routing_horizon"],
        "vessel_profile": nav_route_display["vessel_profile_label"],
        "safety_radius_km": float(
            nav_route_display["safety_radius_km"]
        ),
        "distance_km": float(
            route["total_distance_km"]
        ),
    }

    exports = {
        "recommended_geojson": json.dumps(
            _route_geojson(
                route["path_coordinates"],
                "Recommended Route",
                recommended_properties,
            ),
            indent=2,
        ),
        "recommended_csv": pd.DataFrame(
            _route_points_to_records(
                route["path_coordinates"],
                "Recommended Route",
            )
        ).to_csv(index=False),
    }

    alternative_result = nav_route_display.get(
        "alternative_route"
    )

    alternative_route = None

    if (
        alternative_result is not None
        and alternative_result.get("success", False)
    ):
        alternative_route = alternative_result["route"]

        alternative_properties = {
            "routing_horizon": nav_route_display["routing_horizon"],
            "vessel_profile": nav_route_display["vessel_profile_label"],
            "safety_radius_km": float(
                nav_route_display["safety_radius_km"]
            ),
            "distance_km": float(
                alternative_route["total_distance_km"]
            ),
            "route_overlap_percent": float(
                alternative_result["overlap_percent"]
            ),
        }

        exports["alternative_geojson"] = json.dumps(
            _route_geojson(
                alternative_route["path_coordinates"],
                "Alternative Route",
                alternative_properties,
            ),
            indent=2,
        )

        exports["alternative_csv"] = pd.DataFrame(
            _route_points_to_records(
                alternative_route["path_coordinates"],
                "Alternative Route",
            )
        ).to_csv(index=False)

    summary = {
        "system": "PolarGuard",
        "mode": "prototype decision support",
        "routing_horizon": nav_route_display[
            "routing_horizon"
        ],
        "routing_data_source": nav_route_display.get(
            "routing_data_source"
        ),
        "routing_environment_date": nav_route_display.get(
            "routing_environment_date"
        ),
        "routing_provider_lag_days": nav_route_display.get(
            "routing_provider_lag_days"
        ),
        "route_operational_status": nav_route_display.get(
            "route_operational_status"
        ),
        "iceberg_data_source": nav_route_display.get(
            "iceberg_data_source"
        ),
        "iceberg_count_used": nav_route_display.get(
            "iceberg_count_used"
        ),
        "vessel_profile": nav_route_display[
            "vessel_profile_label"
        ],
        "iceberg_safety_radius_km": float(
            nav_route_display["safety_radius_km"]
        ),
        "recommended_route": {
            "distance_km": float(
                route["total_distance_km"]
            ),
            "hazard_summary": nav_route_display.get(
                "route_hazard_summary"
            ),
            "alerts": nav_route_display.get(
                "route_alerts",
                [],
            ),
        },
        "alternative_route": {
            "available": bool(
                alternative_route is not None
            ),
            "distance_km": (
                float(
                    alternative_route["total_distance_km"]
                )
                if alternative_route is not None
                else None
            ),
            "overlap_percent": (
                float(
                    alternative_result["overlap_percent"]
                )
                if alternative_route is not None
                else None
            ),
            "hazard_summary": nav_route_display.get(
                "alternative_hazard_summary"
            ),
            "alerts": nav_route_display.get(
                "alternative_alerts",
                [],
            ),
        },
        "comparison": nav_route_display.get(
            "route_comparison"
        ),
        "disclaimer": (
            "Prototype decision support only. "
            "Not certified operational navigation."
        ),
    }

    exports["summary_json"] = json.dumps(
        summary,
        indent=2,
        default=str,
    )

    return exports


def _operational_navigation_alerts(nav_route_display):
    alerts = []

    route_hazard = (
        nav_route_display.get("route_hazard_summary")
        or {}
    )

    max_sic = route_hazard.get("max_sic")
    max_iceberg = route_hazard.get(
        "max_iceberg_risk"
    )
    max_uncertainty = route_hazard.get(
        "max_uncertainty_risk"
    )

    if (
        max_sic is not None
        and np.isfinite(max_sic)
    ):
        if max_sic >= 0.60:
            alerts.append(
                (
                    "CRITICAL",
                    f"HIGH SIC AHEAD — recommended route reaches "
                    f"{max_sic * 100.0:.1f}% SIC.",
                )
            )
        elif max_sic >= 0.40:
            alerts.append(
                (
                    "WARNING",
                    f"ELEVATED SIC — recommended route reaches "
                    f"{max_sic * 100.0:.1f}% SIC.",
                )
            )

    if (
        max_iceberg is not None
        and np.isfinite(max_iceberg)
    ):
        if max_iceberg >= 0.75:
            alerts.append(
                (
                    "CRITICAL",
                    "ICEBERG EXCLUSION RISK — high prototype "
                    "iceberg-proximity risk occurs along the route.",
                )
            )
        elif max_iceberg >= 0.30:
            alerts.append(
                (
                    "WARNING",
                    "ICEBERG PROXIMITY WATCH — elevated iceberg "
                    "risk occurs along the route.",
                )
            )

    if (
        max_uncertainty is not None
        and np.isfinite(max_uncertainty)
    ):
        if max_uncertainty >= 0.75:
            alerts.append(
                (
                    "WARNING",
                    "HIGH FORECAST UNCERTAINTY — the historical "
                    "forecast-error proxy is elevated along the route.",
                )
            )
        elif max_uncertainty >= 0.50:
            alerts.append(
                (
                    "INFO",
                    "FORECAST UNCERTAINTY WATCH — uncertainty "
                    "should be considered in the navigation decision.",
                )
            )

    alternative = nav_route_display.get(
        "alternative_route"
    )

    if (
        alternative is not None
        and alternative.get("success", False)
    ):
        alerts.append(
            (
                "INFO",
                "ALTERNATIVE ROUTE AVAILABLE — PolarGuard found "
                "a second navigable corridor for comparison.",
            )
        )

    if not alerts:
        alerts.append(
            (
                "SAFE",
                "NO MAJOR ROUTE ALERT — no major prototype hazard "
                "threshold is triggered along the recommended route.",
            )
        )

    return alerts


def hazard_zone_color(level):
    """Display color for prototype navigation hazard zones."""
    if level == "critical":
        return "#dc2626"
    if level == "warning":
        return "#f59e0b"
    return "#94a3b8"


def uncertainty_color(value):
    """Yellow-to-red scale for historical per-grid RMSE uncertainty."""
    if value < 0.01:
        return "#fef3c7"
    if value < 0.02:
        return "#fde68a"
    if value < 0.03:
        return "#fbbf24"
    if value < 0.05:
        return "#f97316"
    return "#dc2626"


def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(
        int(hex_color[i:i + 2], 16)
        for i in (0, 2, 4)
    )


def _rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(
        *[
            int(np.clip(round(channel), 0, 255))
            for channel in rgb
        ]
    )


def _interpolate_palette(value, stops):
    """Linearly interpolate a value in [0, 1] across hex-color stops."""
    value = float(np.clip(value, 0.0, 1.0))

    for index in range(len(stops) - 1):
        left_value, left_color = stops[index]
        right_value, right_color = stops[index + 1]

        if value <= right_value:
            span = max(right_value - left_value, 1e-12)
            ratio = (value - left_value) / span

            left_rgb = _hex_to_rgb(left_color)
            right_rgb = _hex_to_rgb(right_color)

            rgb = tuple(
                left_rgb[channel]
                + ratio * (right_rgb[channel] - left_rgb[channel])
                for channel in range(3)
            )

            return _rgb_to_hex(rgb)

    return stops[-1][1]


def operational_sic_color(value):
    """
    PolarGuard sea-ice concentration palette.

    Dark blue -> cyan -> yellow -> orange -> red.
    The value is real SIC in [0, 1], not a risk probability.
    """
    stops = [
        (0.00, "#04162f"),
        (0.15, "#073b78"),
        (0.35, "#0077b6"),
        (0.55, "#00c2d7"),
        (0.70, "#f6e652"),
        (0.85, "#ff9f1c"),
        (1.00, "#ef233c"),
    ]
    return _interpolate_palette(value, stops)


def add_operational_map_style(
    fmap,
    show_sic_legend=False,
):
    """
    Apply the DisasterGuard-inspired dark operational treatment to
    standard OpenStreetMap tiles without requiring a commercial API key.
    """

    style_html = """
    <style>
      .leaflet-container {
          background: #06111f !important;
          font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont,
                       "Segoe UI", sans-serif;
      }

      .leaflet-tile-pane {
          filter: brightness(0.42) contrast(1.25) saturate(0.55);
      }

      .leaflet-control-layers,
      .leaflet-bar a,
      .leaflet-control-scale-line {
          background: rgba(5, 15, 28, 0.92) !important;
          color: #e6f7ff !important;
          border-color: rgba(77, 208, 225, 0.32) !important;
      }

      .leaflet-control-layers label {
          color: #d9f5ff !important;
      }

      .leaflet-control-layers-separator {
          border-top-color: rgba(255, 255, 255, 0.18) !important;
      }

      .leaflet-popup-content-wrapper,
      .leaflet-popup-tip {
          background: #071827 !important;
          color: #ecfeff !important;
      }

      .leaflet-tooltip {
          background: rgba(5, 15, 28, 0.94) !important;
          border: 1px solid rgba(77, 208, 225, 0.38) !important;
          color: #ecfeff !important;
          box-shadow: 0 8px 24px rgba(0, 0, 0, 0.28) !important;
      }
    </style>
    """

    fmap.get_root().html.add_child(
        folium.Element(style_html)
    )

    if show_sic_legend:
        legend_html = """
        <div style="
            position: fixed;
            left: 18px;
            bottom: 28px;
            z-index: 9999;
            width: 260px;
            padding: 12px 14px;
            border-radius: 12px;
            border: 1px solid rgba(94,234,212,0.30);
            background: rgba(4,17,31,0.92);
            color: #e6fbff;
            box-shadow: 0 10px 28px rgba(0,0,0,0.38);
            font-size: 12px;
        ">
          <div style="
              font-weight: 800;
              letter-spacing: 0.06em;
              margin-bottom: 7px;
          ">
            SEA-ICE CONCENTRATION (%)
          </div>

          <div style="
              height: 12px;
              border-radius: 999px;
              background: linear-gradient(
                  90deg,
                  #04162f 0%,
                  #073b78 15%,
                  #0077b6 35%,
                  #00c2d7 55%,
                  #f6e652 70%,
                  #ff9f1c 85%,
                  #ef233c 100%
              );
              border: 1px solid rgba(255,255,255,0.18);
          "></div>

          <div style="
              display:flex;
              justify-content:space-between;
              margin-top:4px;
              color:#b8d9e5;
          ">
            <span>0</span>
            <span>25</span>
            <span>50</span>
            <span>75</span>
            <span>100</span>
          </div>

          <div style="
              margin-top:7px;
              color:#8fb7c6;
              line-height:1.35;
          ">
            NOAA/NSIDC SIC field · NaN/invalid cells remain masked
          </div>
        </div>
        """

        fmap.get_root().html.add_child(
            folium.Element(legend_html)
        )


def _format_latitude(latitude):
    latitude = float(latitude)
    hemisphere = "N" if latitude >= 0 else "S"
    return f"{abs(latitude):.0f}°{hemisphere}"


def _format_longitude(longitude):
    longitude = float(longitude)

    if abs(longitude) < 1e-9:
        return "0°"

    if abs(abs(longitude) - 180.0) < 1e-9:
        return "180°"

    hemisphere = "E" if longitude > 0 else "W"
    return f"{abs(longitude):.0f}°{hemisphere}"


def _reference_label_icon(text):
    return folium.DivIcon(
        html=(
            '<div style="'
            'display:inline-block;'
            'white-space:nowrap;'
            'padding:2px 5px;'
            'border-radius:5px;'
            'border:1px solid rgba(125,211,252,0.34);'
            'background:rgba(3,15,28,0.80);'
            'color:#dff8ff;'
            'font-size:10px;'
            'font-weight:700;'
            'line-height:1.1;'
            'text-shadow:0 1px 2px #000;'
            'pointer-events:none;'
            '">'
            f'{text}'
            '</div>'
        ),
        icon_size=(72, 18),
        icon_anchor=(0, 9),
    )


def add_geographic_reference_grid(
    fmap,
    center_lat,
    center_lon,
    latitude_span=12.0,
    longitude_span=30.0,
    name="Latitude / Longitude Grid",
):
    """
    Add navigation-reference latitude/longitude lines and labels.

    This is a visual graticule for orientation in standard Leaflet/Web
    Mercator. It does not change the EPSG:3412 scientific model grid.
    """

    center_lat = float(center_lat)
    center_lon = float(center_lon)

    lat_min = max(-84.0, center_lat - float(latitude_span))
    lat_max = min(-40.0, center_lat + float(latitude_span))

    # Use denser reference lines for local mission views.
    if latitude_span <= 2.0:
        lat_step = 0.5
    elif latitude_span <= 5.0:
        lat_step = 1.0
    else:
        lat_step = 5.0

    if longitude_span <= 5.0:
        lon_step = 1.0
    elif longitude_span <= 15.0:
        lon_step = 5.0
    else:
        lon_step = 10.0

    lon_min = center_lon - float(longitude_span)
    lon_max = center_lon + float(longitude_span)

    group = folium.FeatureGroup(
        name=name,
        show=True,
    )

    first_lat = np.ceil(lat_min / lat_step) * lat_step
    latitude_values = np.arange(
        first_lat,
        lat_max + lat_step * 0.5,
        lat_step,
    )

    first_lon = np.ceil(lon_min / lon_step) * lon_step
    longitude_values = np.arange(
        first_lon,
        lon_max + lon_step * 0.5,
        lon_step,
    )

    # Horizontal latitude references.
    for latitude in latitude_values:
        points = []

        for longitude in np.linspace(
            lon_min,
            lon_max,
            121,
        ):
            wrapped_lon = (
                (float(longitude) + 180.0) % 360.0
            ) - 180.0

            points.append(
                [
                    float(latitude),
                    wrapped_lon,
                ]
            )

        folium.PolyLine(
            points,
            color="#7dd3fc",
            weight=1,
            opacity=0.32,
            dash_array="5,7",
            interactive=False,
        ).add_to(group)

        label_lon = (
            (lon_min + 0.03 * (lon_max - lon_min) + 180.0)
            % 360.0
        ) - 180.0

        folium.Marker(
            location=[
                float(latitude),
                float(label_lon),
            ],
            icon=_reference_label_icon(
                _format_latitude(latitude)
            ),
            interactive=False,
        ).add_to(group)

    # Vertical longitude references.
    for longitude in longitude_values:
        wrapped_lon = (
            (float(longitude) + 180.0) % 360.0
        ) - 180.0

        folium.PolyLine(
            [
                [float(lat_min), wrapped_lon],
                [float(lat_max), wrapped_lon],
            ],
            color="#7dd3fc",
            weight=1,
            opacity=0.28,
            dash_array="5,7",
            interactive=False,
        ).add_to(group)

        folium.Marker(
            location=[
                float(lat_max - 0.04 * (lat_max - lat_min)),
                wrapped_lon,
            ],
            icon=_reference_label_icon(
                _format_longitude(wrapped_lon)
            ),
            interactive=False,
        ).add_to(group)

    group.add_to(fmap)
    return group


def add_position_reference_card(
    fmap,
    latitude,
    longitude,
    title="MISSION POSITION",
):
    """Add a compact always-visible geographic position reference."""

    latitude = float(latitude)
    longitude = float(longitude)

    lat_text = (
        f"{abs(latitude):.4f}°"
        f"{'S' if latitude < 0 else 'N'}"
    )

    lon_text = (
        f"{abs(longitude):.4f}°"
        f"{'W' if longitude < 0 else 'E'}"
    )

    html = f"""
    <div style="
        position: fixed;
        left: 18px;
        top: 18px;
        z-index: 9998;
        min-width: 205px;
        padding: 10px 12px;
        border-radius: 10px;
        border: 1px solid rgba(125,211,252,0.30);
        background: rgba(3,15,28,0.90);
        color: #e6fbff;
        box-shadow: 0 8px 22px rgba(0,0,0,0.32);
        font-size: 12px;
    ">
      <div style="
          color:#7dd3fc;
          font-size:10px;
          font-weight:800;
          letter-spacing:0.08em;
          margin-bottom:4px;
      ">
        {title}
      </div>
      <div style="font-weight:750;">
        {lat_text} &nbsp; | &nbsp; {lon_text}
      </div>
    </div>
    """

    fmap.get_root().html.add_child(
        folium.Element(html)
    )


def add_projected_grid_overlay(
    fmap,
    values,
    x_coords,
    y_coords,
    name,
    opacity=0.42,
    sample_step=6,
    mode="sic",
):
    """
    Add a geographically connected EPSG:3412 model-grid overlay.

    Sea-ice concentration is rendered with joined projected grid polygons,
    not a point HeatMap, so the display follows the real PolarGuard SIC field.
    Uncertainty is rendered with the same grid geometry.

    Display sampling changes visualization density only. The frozen model
    output remains the full 332 x 316 grid.
    """

    transformer = Transformer.from_crs(
        "EPSG:3412",
        "EPSG:4326",
        always_xy=True,
    )

    values = np.asarray(values, dtype=float)
    x_coords = np.asarray(x_coords, dtype=float)
    y_coords = np.asarray(y_coords, dtype=float)

    if values.shape != (len(y_coords), len(x_coords)):
        raise ValueError(
            "Overlay values must match the supplied y/x coordinate grid."
        )

    step = max(int(sample_step), 1)

    group = folium.FeatureGroup(
        name=name,
        show=True,
    )

    ny, nx = values.shape

    dx = float(np.nanmedian(np.abs(np.diff(x_coords))))
    dy = float(np.nanmedian(np.abs(np.diff(y_coords))))

    if not np.isfinite(dx) or dx <= 0:
        raise ValueError("Unable to determine valid x-grid spacing.")

    if not np.isfinite(dy) or dy <= 0:
        raise ValueError("Unable to determine valid y-grid spacing.")

    for iy in range(0, ny, step):
        iy2 = min(iy + step, ny)

        for ix in range(0, nx, step):
            ix2 = min(ix + step, nx)

            block = values[iy:iy2, ix:ix2]

            if not np.isfinite(block).any():
                continue

            value = float(np.nanmean(block))

            if mode == "sic":
                if value < 0.02:
                    continue

                value = float(np.clip(value, 0.0, 1.0))
                color = operational_sic_color(value)
                tooltip = (
                    f"Sea-Ice Concentration: {value * 100.0:.1f}%"
                )

            else:
                if value < 0.002:
                    continue

                color = uncertainty_color(value)
                tooltip = (
                    "Historical RMSE uncertainty: "
                    f"{value * 100.0:.2f} SIC pp"
                )

            x0 = float(x_coords[ix] - dx / 2.0)
            x1 = float(x_coords[ix2 - 1] + dx / 2.0)
            y0 = float(y_coords[iy] - dy / 2.0)
            y1 = float(y_coords[iy2 - 1] + dy / 2.0)

            corners_xy = [
                (x0, y0),
                (x1, y0),
                (x1, y1),
                (x0, y1),
            ]

            polygon = []
            longitudes = []
            valid_polygon = True

            for px, py in corners_xy:
                lon, lat = transformer.transform(
                    px,
                    py,
                )

                if not (
                    np.isfinite(lat)
                    and np.isfinite(lon)
                ):
                    valid_polygon = False
                    break

                if abs(float(lat)) >= 85.0:
                    valid_polygon = False
                    break

                polygon.append(
                    [
                        float(lat),
                        float(lon),
                    ]
                )
                longitudes.append(float(lon))

            if not valid_polygon:
                continue

            if max(longitudes) - min(longitudes) > 180.0:
                continue

            folium.Polygon(
                locations=polygon,
                color=color,
                weight=0.35 if mode == "sic" else 0.0,
                opacity=min(float(opacity) + 0.18, 1.0),
                fill=True,
                fill_color=color,
                fill_opacity=float(opacity),
                tooltip=tooltip,
            ).add_to(group)

    group.add_to(fmap)
    return group


# ============================================================
# LOAD + PREPROCESS NEW NETCDF DATA
# ============================================================

def load_and_prepare_uploaded_netcdf(path):
    """
    Accepts either:
    1. Already processed DataArray NetCDF
    2. Raw/standard Dataset NetCDF containing cdr_seaice_conc

    Returns:
        xarray.DataArray with dimensions:
        (time, y, x)

    Expected SIC:
        0.0 to 1.0
        NaN for invalid cells
    """

    # --------------------------------------------------------
    # TRY AS DATAARRAY
    # --------------------------------------------------------

    try:
        da = xr.open_dataarray(path)

        if {"time", "y", "x"}.issubset(set(da.dims)):

            da = da.transpose(
                "time",
                "y",
                "x"
            )

            da = da.astype(
                np.float32
            )

            da = da.where(
                (da >= 0.0)
                &
                (da <= 1.0)
            )

            if da.shape[1:] != (
                EXPECTED_Y,
                EXPECTED_X
            ):
                raise ValueError(
                    f"Uploaded grid is {da.shape[1:]}. "
                    f"Expected ({EXPECTED_Y}, {EXPECTED_X})."
                )

            if (
                "x" not in da.coords
                or
                "y" not in da.coords
            ):
                raise ValueError(
                    "Uploaded file must contain x and y coordinates."
                )

            da = da.sortby("time")

            return da

    except Exception:
        pass


    # --------------------------------------------------------
    # OPEN AS DATASET
    # --------------------------------------------------------

    ds = xr.open_dataset(path)


    # --------------------------------------------------------
    # FIND SIC VARIABLE
    # --------------------------------------------------------

    if "cdr_seaice_conc" in ds.data_vars:

        da = ds["cdr_seaice_conc"]

    else:

        candidates = []

        for variable in ds.data_vars:

            variable_data = ds[variable]

            if {
                "time",
                "y",
                "x"
            }.issubset(
                set(variable_data.dims)
            ):

                candidates.append(
                    variable
                )

        if len(candidates) == 0:

            ds.close()

            raise ValueError(
                "No sea-ice concentration variable "
                "with dimensions (time, y, x) was found."
            )

        da = ds[candidates[0]]


    # --------------------------------------------------------
    # STANDARDIZE DIMENSIONS
    # --------------------------------------------------------

    da = da.transpose(
        "time",
        "y",
        "x"
    )

    da = da.astype(
        np.float32
    )


    # --------------------------------------------------------
    # MASK INVALID VALUES
    # --------------------------------------------------------

    da = da.where(
        (da >= 0.0)
        &
        (da <= 1.0)
    )


    # --------------------------------------------------------
    # VALIDATE GRID
    # --------------------------------------------------------

    if da.shape[1:] != (
        EXPECTED_Y,
        EXPECTED_X
    ):

        ds.close()

        raise ValueError(
            f"Uploaded grid is {da.shape[1:]}. "
            f"Expected ({EXPECTED_Y}, {EXPECTED_X})."
        )


    # --------------------------------------------------------
    # VALIDATE COORDINATES
    # --------------------------------------------------------

    if (
        "x" not in da.coords
        or
        "y" not in da.coords
    ):

        ds.close()

        raise ValueError(
            "Uploaded file must contain x and y coordinates."
        )


    # --------------------------------------------------------
    # SORT BY TIME
    # --------------------------------------------------------

    da = da.sortby(
        "time"
    )

    return da


# ============================================================
# HELPER: GET FOUR DAILY MAPS
# ============================================================

def get_four_maps(data, current_index):

    if current_index < 3:
        raise ValueError(
            "At least three previous daily maps are required."
        )

    lag3 = data.values[current_index - 3]
    lag2 = data.values[current_index - 2]
    lag1 = data.values[current_index - 1]
    current = data.values[current_index]

    return current, lag1, lag2, lag3


# ============================================================
# HELPER: VALIDATE MAPS
# ============================================================

def validate_grid(
    current,
    lag1,
    lag2,
    lag3
):

    expected_shape = (
        EXPECTED_Y,
        EXPECTED_X
    )

    arrays = {
        "Current": current,
        "Lag 1": lag1,
        "Lag 2": lag2,
        "Lag 3": lag3
    }

    for name, arr in arrays.items():

        if arr.shape != expected_shape:

            raise ValueError(
                f"{name} map shape is {arr.shape}. "
                f"Expected {expected_shape}."
            )

    if not np.isfinite(current).any():

        raise ValueError(
            "Current SIC map contains no valid data."
        )


# ============================================================
# HELPER: SHOW MAP
# ============================================================

def show_map(
    data,
    title,
    label="Sea-Ice Concentration",
    vmin=None,
    vmax=None
):

    fig, ax = plt.subplots(
        figsize=(5, 5)
    )

    image = ax.imshow(
        data,
        vmin=vmin,
        vmax=vmax
    )

    ax.set_title(title)

    ax.axis("off")

    plt.colorbar(
        image,
        ax=ax,
        fraction=0.046,
        pad=0.04,
        label=label
    )

    st.pyplot(fig)

    plt.close(fig)


# ============================================================
# HELPER: SHOW INPUT MAPS
# ============================================================

def show_inputs(
    current,
    lag1,
    lag2,
    lag3,
    current_date
):

    st.subheader(
        "Input Sea-Ice Maps"
    )

    input_maps = [
        (
            "Lag 3",
            lag3,
            current_date
            - np.timedelta64(3, "D")
        ),
        (
            "Lag 2",
            lag2,
            current_date
            - np.timedelta64(2, "D")
        ),
        (
            "Lag 1",
            lag1,
            current_date
            - np.timedelta64(1, "D")
        ),
        (
            "Current",
            current,
            current_date
        )
    ]

    columns = st.columns(4)

    for (
        name,
        data,
        map_date
    ), column in zip(
        input_maps,
        columns
    ):

        with column:

            show_map(
                data,
                f"{name}\n{map_date}",
                vmin=0,
                vmax=1
            )

            st.metric(
                "Mean SIC",
                f"{np.nanmean(data):.4f}"
            )


# ============================================================
# HELPER: RUN FORECAST
# ============================================================

def run_forecast(
    current,
    lag1,
    lag2,
    lag3,
    x_coords,
    y_coords,
    current_date
):

    with st.spinner(
        "Generating PolarGuard forecast..."
    ):

        forecasts = predict_sea_ice(
            current=current,
            lag1=lag1,
            lag2=lag2,
            lag3=lag3,
            x_coords=x_coords,
            y_coords=y_coords,
            date=current_date
        )

        uncertainty = load_uncertainty()

    return forecasts, uncertainty


# ============================================================
# HELPER: DISPLAY FORECAST
# ============================================================

def display_forecasts(
    forecasts,
    uncertainty,
    current_date
):

    st.success(
        "Forecast generated successfully."
    )

    horizons = [
        "24h",
        "48h",
        "72h"
    ]

    offsets = {
        "24h": 1,
        "48h": 2,
        "72h": 3
    }


    # --------------------------------------------------------
    # FORECAST MAPS
    # --------------------------------------------------------

    st.subheader(
        "Forecast Maps"
    )

    columns = st.columns(3)

    for horizon, column in zip(
        horizons,
        columns
    ):

        prediction = forecasts[
            horizon
        ]

        target_date = (
            current_date
            +
            np.timedelta64(
                offsets[horizon],
                "D"
            )
        )

        with column:

            show_map(
                prediction,
                f"+{horizon}\n{target_date}",
                vmin=0,
                vmax=1
            )

            st.metric(
                "Mean Predicted SIC",
                f"{np.nanmean(prediction):.4f}"
            )

            st.write(
                "Valid grid cells:",
                f"{np.isfinite(prediction).sum():,}"
            )


    # --------------------------------------------------------
    # UNCERTAINTY
    # --------------------------------------------------------

    st.subheader(
        "Forecast Uncertainty"
    )

    st.info(
        "Uncertainty is historical per-grid-cell RMSE "
        "derived from 2024 validation residuals. "
        "It is not a calibrated 95% confidence interval."
    )

    columns = st.columns(3)

    for horizon, column in zip(
        horizons,
        columns
    ):

        unc = uncertainty[
            horizon
        ]

        with column:

            show_map(
                unc,
                f"+{horizon} Uncertainty",
                label="Historical RMSE"
            )

            mean_uncertainty = (
                np.nanmean(unc)
            )

            st.metric(
                "Mean Uncertainty",
                f"{mean_uncertainty:.4f}"
            )

            st.caption(
                f"≈ {mean_uncertainty * 100:.2f} "
                "SIC percentage points"
            )


# ============================================================
# HELPER: HISTORICAL ACCURACY
# ============================================================

def calculate_historical_accuracy(
    ds,
    current_index,
    forecasts
):

    st.subheader(
        "Historical Accuracy Check"
    )

    if current_index + 3 >= len(
        ds.time
    ):

        st.info(
            "Future observations are not available "
            "for all three forecast horizons."
        )

        return


    current = ds.values[
        current_index
    ]

    results = []


    for horizon, offset in [
        ("24h", 1),
        ("48h", 2),
        ("72h", 3)
    ]:

        actual = ds.values[
            current_index + offset
        ]

        prediction = forecasts[
            horizon
        ]


        valid = (
            np.isfinite(actual)
            &
            np.isfinite(prediction)
        )


        if valid.sum() == 0:

            continue


        error = (
            prediction[valid]
            -
            actual[valid]
        )


        mae = np.mean(
            np.abs(error)
        )


        rmse = np.sqrt(
            np.mean(
                error ** 2
            )
        )


        within5 = (
            np.mean(
                np.abs(error)
                <= 0.05
            )
            * 100
        )


        # Persistence baseline

        persistence_valid = (
            np.isfinite(actual)
            &
            np.isfinite(current)
        )


        persistence_error = (
            current[persistence_valid]
            -
            actual[persistence_valid]
        )


        persistence_rmse = (
            np.sqrt(
                np.mean(
                    persistence_error ** 2
                )
            )
        )


        if persistence_rmse > 0:

            improvement = (
                (
                    persistence_rmse
                    -
                    rmse
                )
                /
                persistence_rmse
                *
                100
            )

        else:

            improvement = 0.0


        results.append(
            {
                "Horizon":
                    horizon,

                "MAE":
                    f"{mae:.6f}",

                "RMSE":
                    f"{rmse:.6f}",

                "Within ±5 SIC points":
                    f"{within5:.2f}%",

                "Persistence RMSE":
                    f"{persistence_rmse:.6f}",

                "RMSE Improvement":
                    f"{improvement:+.2f}%"
            }
        )


    st.table(
        results
    )


# ============================================================
# SIDEBAR
# ============================================================

render_sidebar()

st.sidebar.markdown(
    """
    <div style="
        margin-top:16px;
        color:#607f93;
        font-size:8px;
        font-weight:900;
        letter-spacing:.13em;
    ">
        MISSION MODULE
    </div>
    """,
    unsafe_allow_html=True,
)
mode = st.sidebar.radio(
    "Forecast Mode",
    [
        "Historical Demo",
        "Upload New Data",
        "Near-Real-Time Satellite",
                "Iceberg Trajectory",
        "Polar Updates",
        "2025 Validation",
    ]
)


st.sidebar.divider()

st.sidebar.markdown(
    """
### Model Outputs

- +24 hour SIC
- +48 hour SIC
- +72 hour SIC
- Forecast uncertainty
"""
)


# ============================================================
# MODE 1: HISTORICAL DEMO
# ============================================================

if mode == "Historical Demo":

    st.header(
        "Historical Forecast Demo"
    )

    st.write(
        "Select a date from the held-out 2025 dataset. "
        "PolarGuard automatically loads that day and "
        "the previous three days."
    )


    try:

        ds = load_historical()

    except Exception as e:

        st.error(
            f"Could not load historical dataset: {e}"
        )

        st.stop()


    dates = ds.time.values.astype(
        "datetime64[D]"
    )


    available_dates = (
        dates[3:]
    )


    date_strings = [
        str(date)
        for date
        in available_dates
    ]


    default_index = max(
        0,
        len(date_strings) - 4
    )


    selected_date_string = (
        st.selectbox(
            "Select Current SIC Date",
            date_strings,
            index=default_index
        )
    )


    current_date = (
        np.datetime64(
            selected_date_string,
            "D"
        )
    )


    if st.button(
        "🚀 Predict Sea Ice",
        type="primary",
        key="historical_button"
    ):

        matches = np.where(
            dates == current_date
        )[0]


        if len(matches) == 0:

            st.error(
                "Selected date not found."
            )

            st.stop()


        current_index = int(
            matches[0]
        )


        try:

            (
                current,
                lag1,
                lag2,
                lag3
            ) = get_four_maps(
                ds,
                current_index
            )


            validate_grid(
                current,
                lag1,
                lag2,
                lag3
            )


            x_coords = (
                ds.x.values
            )

            y_coords = (
                ds.y.values
            )


        except Exception as e:

            st.error(
                str(e)
            )

            st.stop()


        # ----------------------------------------------------
        # SHOW DATES
        # ----------------------------------------------------

        st.divider()

        st.subheader(
            "Forecast Initialization"
        )

        c1, c2, c3, c4 = (
            st.columns(4)
        )


        c1.metric(
            "Lag 3",
            str(
                dates[
                    current_index - 3
                ]
            )
        )

        c2.metric(
            "Lag 2",
            str(
                dates[
                    current_index - 2
                ]
            )
        )

        c3.metric(
            "Lag 1",
            str(
                dates[
                    current_index - 1
                ]
            )
        )

        c4.metric(
            "Current",
            str(
                dates[
                    current_index
                ]
            )
        )


        show_inputs(
            current,
            lag1,
            lag2,
            lag3,
            current_date
        )


        # ----------------------------------------------------
        # FORECAST
        # ----------------------------------------------------

        try:

            (
                forecasts,
                uncertainty
            ) = run_forecast(
                current,
                lag1,
                lag2,
                lag3,
                x_coords,
                y_coords,
                current_date
            )

        except Exception as e:

            st.error(
                f"Forecast failed: {e}"
            )

            st.stop()


        display_forecasts(
            forecasts,
            uncertainty,
            current_date
        )


        # ----------------------------------------------------
        # ACCURACY CHECK
        # ----------------------------------------------------

        calculate_historical_accuracy(
            ds,
            current_index,
            forecasts
        )


# ============================================================
# MODE 2: UPLOAD NEW DATA
# ============================================================

elif mode == "Upload New Data":

    st.header(
        "Forecast From New Sea-Ice Data"
    )

    st.write(
        "Upload a compatible Antarctic sea-ice "
        "NetCDF file containing at least four "
        "consecutive daily SIC maps."
    )


    st.info(
        "Required grid: 332 × 316. "
        "Required dimensions: time, y, x. "
        "SIC must represent values from 0.0 to 1.0."
    )


    uploaded_file = (
        st.file_uploader(
            "Upload NetCDF file",
            type=[
                "nc",
                "nc4"
            ]
        )
    )


    if uploaded_file is not None:

        temporary_path = None
        uploaded_ds = None


        try:

            # ------------------------------------------------
            # SAVE UPLOADED FILE
            # ------------------------------------------------

            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".nc"
            ) as temp_file:

                temp_file.write(
                    uploaded_file.getbuffer()
                )

                temporary_path = (
                    temp_file.name
                )


            # ------------------------------------------------
            # LOAD + PREPROCESS
            # ------------------------------------------------

            uploaded_ds = (
                load_and_prepare_uploaded_netcdf(
                    temporary_path
                )
            )


            # ------------------------------------------------
            # CHECK TIME
            # ------------------------------------------------

            if "time" not in uploaded_ds.coords:

                raise ValueError(
                    "Uploaded file must contain "
                    "a time coordinate."
                )


            if len(uploaded_ds.time) < 4:

                raise ValueError(
                    "Uploaded file must contain "
                    "at least four daily observations."
                )


            upload_dates = (
                uploaded_ds.time.values.astype(
                    "datetime64[D]"
                )
            )


            # ------------------------------------------------
            # FIND FOUR CONSECUTIVE-DAY WINDOWS
            # ------------------------------------------------

            valid_indices = []


            for index in range(
                3,
                len(upload_dates)
            ):

                expected_dates = np.array(
                    [
                        upload_dates[index]
                        - np.timedelta64(3, "D"),

                        upload_dates[index]
                        - np.timedelta64(2, "D"),

                        upload_dates[index]
                        - np.timedelta64(1, "D"),

                        upload_dates[index]
                    ],
                    dtype="datetime64[D]"
                )


                actual_dates = (
                    upload_dates[
                        index - 3:
                        index + 1
                    ]
                )


                if np.array_equal(
                    expected_dates,
                    actual_dates
                ):

                    valid_indices.append(
                        index
                    )


            if len(valid_indices) == 0:

                raise ValueError(
                    "No four consecutive daily observations "
                    "were found in the uploaded file."
                )


            # ------------------------------------------------
            # FILE INFORMATION
            # ------------------------------------------------

            st.success(
                "NetCDF file loaded successfully."
            )


            c1, c2, c3 = (
                st.columns(3)
            )


            c1.metric(
                "Daily Maps",
                len(upload_dates)
            )


            c2.metric(
                "Grid",
                f"{uploaded_ds.shape[1]} × "
                f"{uploaded_ds.shape[2]}"
            )


            c3.metric(
                "Consecutive Forecast Dates",
                len(valid_indices)
            )


            st.write(
                "Available date range:",
                f"{upload_dates[0]} → "
                f"{upload_dates[-1]}"
            )


            # ------------------------------------------------
            # SELECT INITIALIZATION DATE
            # ------------------------------------------------

            valid_date_strings = [
                str(
                    upload_dates[index]
                )
                for index
                in valid_indices
            ]


            selected_upload_date = (
                st.selectbox(
                    "Select Forecast Initialization Date",
                    valid_date_strings,
                    index=(
                        len(
                            valid_date_strings
                        ) - 1
                    )
                )
            )


            current_date = (
                np.datetime64(
                    selected_upload_date,
                    "D"
                )
            )


            current_index = int(
                np.where(
                    upload_dates
                    ==
                    current_date
                )[0][0]
            )


            # ------------------------------------------------
            # GENERATE FORECAST
            # ------------------------------------------------

            if st.button(
                "🚀 Generate New Forecast",
                type="primary",
                key="upload_button"
            ):

                (
                    current,
                    lag1,
                    lag2,
                    lag3
                ) = get_four_maps(
                    uploaded_ds,
                    current_index
                )


                validate_grid(
                    current,
                    lag1,
                    lag2,
                    lag3
                )


                # --------------------------------------------
                # COORDINATES
                # --------------------------------------------

                x_coords = (
                    uploaded_ds.x.values
                )

                y_coords = (
                    uploaded_ds.y.values
                )


                if len(x_coords) != EXPECTED_X:

                    raise ValueError(
                        f"X coordinate count is "
                        f"{len(x_coords)}. "
                        f"Expected {EXPECTED_X}."
                    )


                if len(y_coords) != EXPECTED_Y:

                    raise ValueError(
                        f"Y coordinate count is "
                        f"{len(y_coords)}. "
                        f"Expected {EXPECTED_Y}."
                    )


                # --------------------------------------------
                # INPUT DATES
                # --------------------------------------------

                st.divider()

                st.subheader(
                    "Forecast Initialization"
                )


                c1, c2, c3, c4 = (
                    st.columns(4)
                )


                c1.metric(
                    "Lag 3",
                    str(
                        upload_dates[
                            current_index - 3
                        ]
                    )
                )


                c2.metric(
                    "Lag 2",
                    str(
                        upload_dates[
                            current_index - 2
                        ]
                    )
                )


                c3.metric(
                    "Lag 1",
                    str(
                        upload_dates[
                            current_index - 1
                        ]
                    )
                )


                c4.metric(
                    "Current",
                    str(
                        upload_dates[
                            current_index
                        ]
                    )
                )


                # --------------------------------------------
                # INPUT MAPS
                # --------------------------------------------

                show_inputs(
                    current,
                    lag1,
                    lag2,
                    lag3,
                    current_date
                )


                # --------------------------------------------
                # RUN MODEL
                # --------------------------------------------

                try:

                    (
                        forecasts,
                        uncertainty
                    ) = run_forecast(
                        current,
                        lag1,
                        lag2,
                        lag3,
                        x_coords,
                        y_coords,
                        current_date
                    )

                except Exception as e:

                    st.error(
                        f"Forecast failed: {e}"
                    )

                    st.stop()


                # --------------------------------------------
                # DISPLAY FORECAST
                # --------------------------------------------

                display_forecasts(
                    forecasts,
                    uncertainty,
                    current_date
                )


                st.info(
                    "This is a new-data forecast. "
                    "Future actual observations are "
                    "not required to generate the "
                    "24h, 48h and 72h predictions."
                )


        except Exception as e:

            st.error(
                f"Unable to process uploaded file: {e}"
            )


        finally:

            # Best-effort cleanup
            if (
                temporary_path is not None
                and
                os.path.exists(
                    temporary_path
                )
            ):

                try:

                    os.remove(
                        temporary_path
                    )

                except PermissionError:

                    pass


# ============================================================
# MODE 3: NEAR-REAL-TIME SATELLITE
# ============================================================

elif mode == "Near-Real-Time Satellite":

    st.header(
        "🛰️ Near-Real-Time Antarctic Satellite Forecast"
    )

    st.write(
        "PolarGuard automatically downloads the latest four consecutive "
        "Antarctic sea-ice concentration observations from NOAA / NSIDC "
        "G10016 Version 4 and runs the frozen Sea-Ice AI model."
    )

    st.info(
        "This is near-real-time satellite-derived sea-ice concentration, "
        "not a continuous live satellite stream. The provider may publish "
        "data with a short operational delay."
    )

    if st.button(
        "🛰️ Load Latest Satellite Data & Forecast",
        type="primary",
        key="satellite_forecast_button"
    ):

        try:

            with st.spinner(
                "Loading latest NOAA / NSIDC Antarctic satellite observations..."
            ):

                satellite_bundle = load_latest_satellite_input()

            current = satellite_bundle["current"]
            lag1 = satellite_bundle["lag1"]
            lag2 = satellite_bundle["lag2"]
            lag3 = satellite_bundle["lag3"]

            x_coords = satellite_bundle["x"]
            y_coords = satellite_bundle["y"]

            current_date = satellite_bundle["date"]

            validate_grid(
                current,
                lag1,
                lag2,
                lag3
            )

            st.success(
                "Latest Antarctic satellite observations loaded successfully."
            )

            st.divider()

            st.subheader(
                "Satellite Data Status"
            )

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "Latest Observation",
                str(current_date)
            )

            c2.metric(
    "Data Status",
    "CURRENT"
)

            c3.metric(
                "Valid Grid Cells",
                f"{satellite_bundle['valid_current_cells']:,}"
            )

            c4.metric(
                "Mean SIC",
                f"{satellite_bundle['mean_current_sic'] * 100:.1f}%"
            )

            st.caption(
                "Source: NOAA / NSIDC G10016 Version 4 · "
                "Southern Hemisphere · EPSG:3412 · "
                f"Grid {satellite_bundle['grid_shape'][0]} × "
                f"{satellite_bundle['grid_shape'][1]}"
            )

            st.divider()

            st.subheader(
                "Forecast Initialization"
            )

            input_dates = satellite_bundle["dates"]

            d1, d2, d3, d4 = st.columns(4)

            d1.metric(
                "Lag 3",
                str(input_dates[0])
            )

            d2.metric(
                "Lag 2",
                str(input_dates[1])
            )

            d3.metric(
                "Lag 1",
                str(input_dates[2])
            )

            d4.metric(
                "Current",
                str(input_dates[3])
            )

            show_inputs(
                current,
                lag1,
                lag2,
                lag3,
                current_date
            )

            try:

                forecasts, uncertainty = run_forecast(
                    current,
                    lag1,
                    lag2,
                    lag3,
                    x_coords,
                    y_coords,
                    current_date
                )

            except Exception as e:

                st.error(
                    f"Satellite-initialized forecast failed: {e}"
                )

                st.stop()

            display_forecasts(
                forecasts,
                uncertainty,
                current_date
            )

            st.session_state["satellite_bundle"] = satellite_bundle
            st.session_state["sea_ice_current"] = current
            st.session_state["sea_ice_24h"] = np.asarray(forecasts["24h"])
            st.session_state["sea_ice_48h"] = np.asarray(forecasts["48h"])
            st.session_state["sea_ice_72h"] = np.asarray(forecasts["72h"])
            st.session_state["sea_ice_uncertainty_24h"] = np.asarray(uncertainty["24h"])
            st.session_state["sea_ice_uncertainty_48h"] = np.asarray(uncertainty["48h"])
            st.session_state["sea_ice_uncertainty_72h"] = np.asarray(uncertainty["72h"])
            st.session_state["sea_ice_x"] = x_coords
            st.session_state["sea_ice_y"] = y_coords
            st.session_state["sea_ice_init_date"] = current_date
            st.session_state["sea_ice_source"] = (
                "NOAA / NSIDC G10016 Version 4 Near-Real-Time Satellite"
            )

            st.success(
                "Near-real-time satellite → PolarGuard Sea-Ice AI → "
                "+24h / +48h / +72h pipeline is ready."
            )

        except Exception as e:

            st.error(
                "Unable to load or process the latest satellite data."
            )

            st.exception(e)


# ============================================================
# MODE 4: ICEBERG TRAJECTORY
# ============================================================

elif mode == "Iceberg Trajectory":

    st.header(
        "🧭 Iceberg Trajectory Forecast"
    )

    st.write(
        "Enter four consecutive daily iceberg positions. "
        "PolarGuard automatically extracts the local sea-ice "
        "concentration from Member 1 and passes it to the "
        "frozen Member 2 trajectory model."
    )

    st.info(
        "For this prototype, ERA5 wind and GLORYS ocean-current "
        "values are entered manually. The local sea-ice "
        "concentration is obtained automatically from Member 1."
    )

    st.subheader(
        "Iceberg Position History"
    )

    lat_col, lon_col = st.columns(2)

    with lat_col:

        lat_tm3 = st.number_input(
            "Latitude t-3",
            value=-75.75435,
            format="%.6f"
        )

        lat_tm2 = st.number_input(
            "Latitude t-2",
            value=-75.69135,
            format="%.6f"
        )

        lat_tm1 = st.number_input(
            "Latitude t-1",
            value=-75.63525,
            format="%.6f"
        )

        current_latitude = st.number_input(
            "Current Latitude",
            value=-75.611000,
            format="%.6f"
        )

    with lon_col:

        lon_tm3 = st.number_input(
            "Longitude t-3",
            value=-41.10950,
            format="%.6f"
        )

        lon_tm2 = st.number_input(
            "Longitude t-2",
            value=-41.09485,
            format="%.6f"
        )

        lon_tm1 = st.number_input(
            "Longitude t-1",
            value=-41.08170,
            format="%.6f"
        )

        current_longitude = st.number_input(
            "Current Longitude",
            value=-41.076000,
            format="%.6f"
        )

    initialization_date = st.date_input(
        "Initialization Date",
        value=date(2019, 1, 4),
        min_value=date(2019, 1, 1),
        max_value=date(2025, 12, 31)
    )

    st.divider()

    st.subheader(
        "Environmental Conditions"
    )

    env_col1, env_col2 = st.columns(2)

    with env_col1:

        wind_u10 = st.number_input(
            "ERA5 Wind U10 (m/s)",
            value=-3.0,
            format="%.3f"
        )

        wind_v10 = st.number_input(
            "ERA5 Wind V10 (m/s)",
            value=2.0,
            format="%.3f"
        )

    with env_col2:

        ocean_uo = st.number_input(
            "GLORYS Ocean U (m/s)",
            value=-0.05,
            format="%.3f"
        )

        ocean_vo = st.number_input(
            "GLORYS Ocean V (m/s)",
            value=0.03,
            format="%.3f"
        )

    st.divider()

    if st.button(
        "🚀 Run Combined Member 1 + Member 2 Forecast",
        type="primary",
        key="iceberg_button"
    ):

        try:

            with st.spinner(
                "Running PolarGuard Member 1 → Member 2 pipeline..."
            ):

                combined_result = run_polarguard(
                    lat_tm3=lat_tm3,
                    lon_tm3=lon_tm3,
                    lat_tm2=lat_tm2,
                    lon_tm2=lon_tm2,
                    lat_tm1=lat_tm1,
                    lon_tm1=lon_tm1,
                    current_latitude=current_latitude,
                    current_longitude=current_longitude,
                    date=str(initialization_date),
                    wind_u10=wind_u10,
                    wind_v10=wind_v10,
                    ocean_uo=ocean_uo,
                    ocean_vo=ocean_vo
                )

            st.session_state["combined_iceberg_result"] = combined_result

        except Exception as e:

            st.error(
                f"Combined forecast failed: {e}"
            )

    if "combined_iceberg_result" in st.session_state:

        result = st.session_state[
            "combined_iceberg_result"
        ]

        sea_ice_result = result[
            "sea_ice"
        ]

        iceberg_result = result[
            "iceberg"
        ]

        forecasts = iceberg_result[
            "forecast"
        ]

        st.success(
            "Combined forecast generated successfully."
        )

        st.divider()

        st.subheader(
            "Member 1 → Member 2 Sea-Ice Connection"
        )

        if sea_ice_result.get(
            "available",
            False
        ):

            local_sic = sea_ice_result.get(
                "sic"
            )

            st.metric(
                "Local Sea-Ice Concentration",
                f"{local_sic * 100:.1f}%"
            )

        else:

            st.warning(
                "Local sea-ice concentration was unavailable. "
                "Member 2 used its frozen missing-SIC policy."
            )

        grid_x = sea_ice_result.get(
            "grid_x"
        )

        grid_y = sea_ice_result.get(
            "grid_y"
        )

        if (
            grid_x is not None
            and
            grid_y is not None
        ):

            st.caption(
                f"Nearest NSIDC grid cell: "
                f"X = {grid_x:.0f} m, "
                f"Y = {grid_y:.0f} m"
            )

        st.divider()

        st.subheader(
            "Predicted Iceberg Positions"
        )

        forecast_24 = forecasts[
            "24h"
        ]

        forecast_48 = forecasts[
            "48h"
        ]

        forecast_72 = forecasts[
            "72h"
        ]

        c24, c48, c72 = st.columns(3)

        with c24:

            st.markdown(
                "### +24 Hours"
            )

            st.metric(
                "Latitude",
                f"{forecast_24['latitude']:.6f}"
            )

            st.metric(
                "Longitude",
                f"{forecast_24['longitude']:.6f}"
            )

            st.metric(
                "Displacement",
                f"{forecast_24['predicted_displacement_km']:.3f} km"
            )

        with c48:

            st.markdown(
                "### +48 Hours"
            )

            st.metric(
                "Latitude",
                f"{forecast_48['latitude']:.6f}"
            )

            st.metric(
                "Longitude",
                f"{forecast_48['longitude']:.6f}"
            )

            st.metric(
                "Displacement",
                f"{forecast_48['predicted_displacement_km']:.3f} km"
            )

        with c72:

            st.markdown(
                "### +72 Hours"
            )

            st.metric(
                "Latitude",
                f"{forecast_72['latitude']:.6f}"
            )

            st.metric(
                "Longitude",
                f"{forecast_72['longitude']:.6f}"
            )

            st.metric(
                "Displacement",
                f"{forecast_72['predicted_displacement_km']:.3f} km"
            )

        st.divider()

        # ========================================================
        # SIH DECISION-SUPPORT CONTROLS
        # ========================================================

        st.subheader("🎛️ Forecast Decision View")

        # ========================================================
        # PHASE 2: ANIMATED FORECAST TIMELINE
        # ========================================================
        playback_frames = ["All", "+24h", "+48h", "+72h"]

        if "sih_focus_horizon" not in st.session_state:
            st.session_state["sih_focus_horizon"] = "All"

        if "sih_animation_playing" not in st.session_state:
            st.session_state["sih_animation_playing"] = False

        animation_control_1, animation_control_2, animation_control_3, animation_control_4 = (
            st.columns([0.9, 0.9, 0.9, 2.0])
        )

        with animation_control_1:
            if st.button(
                "▶ Play",
                use_container_width=True,
                key="sih_animation_play",
            ):
                # Start from Current when replaying after the final frame.
                if st.session_state["sih_focus_horizon"] == "+72h":
                    st.session_state["sih_focus_horizon"] = "All"
                st.session_state["sih_animation_playing"] = True
                st.rerun()

        with animation_control_2:
            if st.button(
                "⏸ Pause",
                use_container_width=True,
                key="sih_animation_pause",
            ):
                st.session_state["sih_animation_playing"] = False
                st.rerun()

        with animation_control_3:
            if st.button(
                "⏮ Reset",
                use_container_width=True,
                key="sih_animation_reset",
            ):
                st.session_state["sih_animation_playing"] = False
                st.session_state["sih_focus_horizon"] = "All"
                st.rerun()

        with animation_control_4:
            animation_speed = st.slider(
                "Animation step duration (seconds)",
                min_value=0.8,
                max_value=5.0,
                value=1.8,
                step=0.2,
                key="sih_animation_speed",
                help="Time each forecast frame stays visible before moving to the next horizon.",
            )

        if st.session_state["sih_animation_playing"]:
            st.success(
                "▶ Forecast playback running: Current → +24h → +48h → +72h"
            )
        else:
            st.caption(
                "Use Play for automatic forecast playback, Pause to stop at the "
                "current frame, or Reset to return to Current."
            )

        timeline_col, layer_col, buffer_col = st.columns([1.4, 1.0, 1.0])

        with timeline_col:
            selected_horizon = st.radio(
                "Focus forecast horizon",
                playback_frames,
                horizontal=True,
                key="sih_focus_horizon",
                format_func=lambda value: "Current" if value == "All" else value,
            )

        with layer_col:
            show_sic_context = st.toggle(
                "Local Sea-Ice Context",
                value=True,
                key="sih_show_sic_context",
                help=(
                    "Shows a local Member 1 SIC context circle at the iceberg. "
                    "Use Sea-Ice Map Layers below for the full synchronized grid."
                ),
            )

        with buffer_col:
            show_safety_buffer = st.toggle(
                "Navigation Safety Buffer",
                value=True,
                key="sih_show_safety_buffer",
                help=(
                    "Presentation/planning buffer around forecast positions. "
                    "It is not a calibrated collision-probability region."
                ),
            )

        safety_buffer_km = 10.0
        if show_safety_buffer:
            safety_buffer_km = st.slider(
                "Planning buffer radius (km)",
                min_value=2.0,
                max_value=25.0,
                value=10.0,
                step=1.0,
                key="sih_buffer_radius",
            )
                # ============================================================
        # OPERATIONAL SEA-ICE INTELLIGENCE
        # Uses the SAME horizon selector as the existing forecast UI
        # ============================================================

        try:
            operational_bundle = get_operational_forecast_bundle()

            horizon_lookup = {
                "All": "CURRENT",
                "+24h": "+24H",
                "+48h": "+48H",
                "+72h": "+72H",
            }

            operational_horizon = horizon_lookup[selected_horizon]

            seaice_metrics = operational_bundle[
                "sea_ice"
            ][operational_horizon]["metrics"]

            st.markdown("### 🧊 Sea-Ice Intelligence")

            metric_1, metric_2, metric_3, metric_4 = st.columns(4)

            with metric_1:
                st.metric(
                    "Mean SIC",
                    seaice_metrics["mean_sic"],
                )

            with metric_2:
                st.metric(
                    "Maximum SIC",
                    seaice_metrics["maximum_sic"],
                )

            with metric_3:
                st.metric(
                    "Ice-Covered Grid",
                    seaice_metrics["ice_covered_grid"],
                )

            with metric_4:
                st.metric(
                    "RMSE-Based Uncertainty",
                    seaice_metrics["uncertainty"],
                )

            st.caption(
                "Ice-covered grid = percentage of valid Antarctic grid cells "
                "with SIC ≥ 15%. Forecast uncertainty is RMSE-based and "
                "is not a calibrated confidence interval."
            )

        except Exception as seaice_intelligence_error:
            st.warning(
                "Operational sea-ice intelligence is temporarily unavailable: "
                f"{seaice_intelligence_error}"
            )
        with st.expander("🗺️ Sea-Ice Map Layers", expanded=True):
            layer_c1, layer_c2, layer_c3, layer_c4 = st.columns(4)

            with layer_c1:
                show_full_sic_layer = st.toggle(
                    "Sea-Ice Forecast Layer",
                    value=True,
                    key="sih_full_sic_layer",
                )

            with layer_c2:
                show_uncertainty_layer = st.toggle(
                    "Uncertainty Layer",
                    value=False,
                    key="sih_uncertainty_layer",
                    help=(
                        "Historical per-grid-cell RMSE from 2024 validation. "
                        "This is not a calibrated confidence interval."
                    ),
                )

            with layer_c3:
                sic_layer_opacity = st.slider(
                    "Sea-Ice Opacity",
                    min_value=0.10,
                    max_value=0.80,
                    value=0.42,
                    step=0.05,
                    key="sih_sic_opacity",
                )

            with layer_c4:
                overlay_detail = st.selectbox(
                    "Overlay Detail",
                    ["Balanced", "Detailed", "Fast"],
                    index=0,
                    key="sih_overlay_detail",
                    help=(
                        "This changes display sampling only. The Member 1 model "
                        "still predicts the full 332 × 316 grid."
                    ),
                )

            overlay_step_lookup = {
                "Detailed": 3,
                "Balanced": 5,
                "Fast": 8,
            }
            overlay_step = overlay_step_lookup[overlay_detail]

            uncertainty_opacity = 0.28
            if show_uncertainty_layer:
                uncertainty_opacity = st.slider(
                    "Uncertainty Opacity",
                    min_value=0.10,
                    max_value=0.60,
                    value=0.28,
                    step=0.05,
                    key="sih_uncertainty_opacity",
                )

        member1_map_bundle = None
        member1_overlay_error = None

        if show_full_sic_layer or show_uncertainty_layer:
            try:
                with st.spinner("Preparing synchronized Member 1 map layers..."):
                    member1_map_bundle = get_member1_map_bundle(
                        str(initialization_date)
                    )
            except Exception as overlay_error:
                member1_overlay_error = str(overlay_error)
                st.warning(
                    "The trajectory forecast is still available, but the full "
                    f"sea-ice overlay could not be prepared: {overlay_error}"
                )

        # Horizon-aware operational summary cards
        current_frame_active = (
            selected_horizon == "All"
            and st.session_state.get("sih_animation_playing", False)
        )

        if selected_horizon == "+24h":
            selected_forecast = forecast_24
            selected_label = "24h"
        elif selected_horizon == "+48h":
            selected_forecast = forecast_48
            selected_label = "48h"
        elif selected_horizon == "+72h":
            selected_forecast = forecast_72
            selected_label = "72h"
        elif current_frame_active:
            selected_forecast = {
                "latitude": float(current_latitude),
                "longitude": float(current_longitude),
                "predicted_displacement_km": 0.0,
            }
            selected_label = "Current"
        else:
            # Manual "Current" view keeps the complete trajectory summary available.
            selected_forecast = forecast_72
            selected_label = "72h"

        if selected_horizon == "+24h":
            selected_sic_key = "forecast_24h"
            selected_uncertainty_key = "uncertainty_24h"
            selected_sic_label = "+24h Sea-Ice Forecast"
        elif selected_horizon == "+48h":
            selected_sic_key = "forecast_48h"
            selected_uncertainty_key = "uncertainty_48h"
            selected_sic_label = "+48h Sea-Ice Forecast"
        elif selected_horizon == "+72h":
            selected_sic_key = "forecast_72h"
            selected_uncertainty_key = "uncertainty_72h"
            selected_sic_label = "+72h Sea-Ice Forecast"
        else:
            selected_sic_key = "current"
            selected_uncertainty_key = None
            selected_sic_label = "Current Sea-Ice Concentration"

        # ========================================================
        # PHASE 3: REAL POLARGUARD ROUTE PLANNING
        # ========================================================

        st.markdown("#### 🛰️ Data & Model Status")

        model_status_1, model_status_2, model_status_3, model_status_4 = (
            st.columns(4)
        )

        model_status_1.metric(
            "Sea-Ice Model",
            "Hybrid v1 • Frozen",
        )

        model_status_2.metric(
            "Iceberg Model",
            "Environment v1 • Frozen",
        )

        model_status_3.metric(
            "Initialization",
            initialization_date.strftime("%d %b %Y"),
        )

        satellite_route_available = True

        model_status_4.metric(
            "Routing Capability",
            "Satellite-Aware",
        )

        st.caption(
            "Frozen ML outputs feed the risk and routing layers. "
            "The navigation layer does not retrain or alter the sea-ice "
            "or iceberg models."
        )

        st.subheader("🚢 Safe Route Planning")

        st.caption(
            "Plan an A* route using the frozen Member 1 sea-ice forecast, "
            "Member 1 historical RMSE uncertainty, the matching Member 2 "
            "iceberg forecast, and prototype vessel constraints."
        )

        with st.expander("Navigation Request", expanded=True):

            routing_environment_source = st.selectbox(
                "Routing sea-ice environment",
                [
                    "Latest Near-Real-Time Satellite",
                    "Synchronized Historical / Demo",
                ],
                index=0,
                key="nav_environment_source",
                help=(
                    "Latest Near-Real-Time Satellite uses NOAA/NSIDC G10016 V4 "
                    "as the current SIC state, then Member 1 +24h/+48h/+72h "
                    "forecasts for the selected route horizon."
                ),
            )

            use_satellite_routing = (
                routing_environment_source
                == "Latest Near-Real-Time Satellite"
            )

            route_environment_bundle = None
            route_environment_error = None
            current_iceberg_bundle = None

            if use_satellite_routing:
                try:
                    with st.spinner(
                        "Loading latest NOAA/NSIDC satellite route environment..."
                    ):
                        route_environment_bundle = (
                            get_latest_satellite_route_bundle()
                        )

                    # Make map overlays and routing use the same sea-ice source.
                    member1_map_bundle = route_environment_bundle

                    route_source_date = route_environment_bundle["date"]
                    route_source_lag = route_environment_bundle[
                        "provider_lag_days"
                    ]

                    source_c1, source_c2, source_c3, source_c4 = st.columns(4)

                    source_c1.metric(
    "Route Data Source",
    "CURRENT",
)
                    source_c2.metric(
    "Observation",
    "CURRENT",
)
                    source_c3.metric(
    "Data Status",
    "CURRENT",
)
                    source_c4.metric(
                        "Valid SIC Cells",
                        f"{route_environment_bundle['valid_current_cells']:,}",
                    )

                    current_iceberg_bundle = None

                    try:
                        with st.spinner(
                            "Loading latest observed Antarctic iceberg hazards..."
                        ):
                            current_iceberg_bundle = (
                                get_latest_observed_iceberg_hazards()
                            )

                        ice_c1, ice_c2, ice_c3 = st.columns(3)

                        ice_c1.metric(
                            "Observed Icebergs",
                            f"{current_iceberg_bundle['iceberg_count']}",
                        )
                        ice_c2.metric(
                            "Latest Iceberg Observation",
                            current_iceberg_bundle[
                                "latest_observation_date"
                            ] or "N/A",
                        )
                        ice_c3.metric(
                            "Iceberg Source",
                            "BYU SCP",
                        )

                        st.success(
                            "🛰️ CURRENT routing is connected to the latest "
                            "available NOAA/NSIDC sea ice and real BYU observed "
                            "iceberg positions."
                        )

                        st.markdown("#### 🌐 Operational Environmental Forcing")
                        st.caption(
                            "Optional live provider check for the selected iceberg position. "
                            "It uses ECMWF IFS wind, Copernicus Marine ocean current, and "
                            "NOAA/NSIDC G10016 SIC. Provider timestamps are shown exactly "
                            "as supplied and may differ."
                        )

                        refresh_environment = st.button(
                            "🌐 Refresh Real Environmental Status",
                            key="refresh_operational_environment",
                            use_container_width=True,
                        )

                        if refresh_environment:
                            try:
                                with st.spinner(
                                    "Retrieving ECMWF wind, Copernicus current, and "
                                    "NOAA/NSIDC SIC..."
                                ):
                                    st.session_state["operational_environment_status"] = (
                                        get_operational_environment_status(
                                            str(date.today()),
                                            current_latitude,
                                            current_longitude,
                                        )
                                    )
                            except Exception as environment_status_error:
                                st.session_state.pop(
                                    "operational_environment_status",
                                    None,
                                )
                                st.error(
                                    "Operational environmental forcing could not be loaded: "
                                    f"{environment_status_error}"
                                )

                        environment_status = st.session_state.get(
                            "operational_environment_status"
                        )

                        if environment_status is not None:
                            env_wind = environment_status["wind"]
                            env_ocean = environment_status["ocean"]
                            env_ice = environment_status["sea_ice"]

                            env_c1, env_c2, env_c3, env_c4 = st.columns(4)

                            env_c1.metric(
                                "ECMWF Wind",
                                f"{env_wind['speed_ms']:.2f} m/s",
                                help=f"Timestamp: {env_wind['timestamp']}",
                            )
                            env_c2.metric(
                                "Copernicus Current",
                                f"{env_ocean['speed_ms']:.3f} m/s",
                                help=f"Timestamp: {env_ocean['timestamp']}",
                            )
                            env_c3.metric(
                                "Local Satellite SIC",
                                (
                                    f"{env_ice['sic'] * 100.0:.1f}%"
                                    if env_ice["available"]
                                    else "Unavailable"
                                ),
                                help=f"Timestamp: {env_ice['timestamp']}",
                            )
                            env_c4.metric(
                                "Environment Sync",
                                (
                                    "Synchronized"
                                    if environment_status["environment_synchronized"]
                                    else "Partial"
                                ),
                            )

                            st.caption(
                                f"Wind: {env_wind['timestamp']} · "
                                f"Ocean: {env_ocean['timestamp']} · "
                                f"Sea ice: {env_ice['timestamp']}"
                            )

                            if environment_status["environment_synchronized"]:
                                st.success(
                                    "Environmental provider dates satisfy the current "
                                    "synchronization rule."
                                )
                            else:
                                st.warning(
                                    "Environmental forcing is latest-available but not fully "
                                    "time-synchronized. "
                                    + environment_status["environment_sync_note"]
                                )

                            st.info(
    "CURRENT satellite-derived Antarctic sea-ice observation is loaded "
    "from the latest available NOAA / NSIDC data."
)

                    except Exception as current_iceberg_error:
                        current_iceberg_bundle = None
                        st.error(
                            "Current iceberg hazards could not be prepared: "
                            f"{current_iceberg_error}"
                        )

                    if str(initialization_date) != str(route_source_date):
                        st.warning(
                            "Temporal synchronization note: the sea-ice routing "
                            f"environment is initialized on {route_source_date}, "
                            "while the current iceberg forecast was initialized on "
                            f"{initialization_date}. For a fully synchronized "
                            "operational run, provide iceberg observations from the "
                            "same initialization date. The route still uses the "
                            "latest satellite sea-ice environment."
                        )

                except Exception as satellite_route_error:
                    route_environment_error = str(satellite_route_error)
                    st.error(
                        "Latest satellite routing data could not be prepared: "
                        f"{satellite_route_error}"
                    )

            else:
                if member1_map_bundle is None:
                    try:
                        with st.spinner(
                            "Preparing synchronized historical route environment..."
                        ):
                            member1_map_bundle = get_member1_map_bundle(
                                str(initialization_date)
                            )
                    except Exception as historical_route_error:
                        route_environment_error = str(historical_route_error)
                        st.error(
                            "Historical routing environment could not be prepared: "
                            f"{historical_route_error}"
                        )

                route_environment_bundle = member1_map_bundle

                if route_environment_bundle is not None:
                    st.info(
                        "📚 Routing is using the historical/demo sea-ice environment "
                        f"initialized on {route_environment_bundle['date']}."
                    )

            route_control_1, route_control_2, route_control_3 = st.columns(
                [1.0, 1.0, 1.2]
            )

            with route_control_1:
                routing_horizon_options = (
                    [
                        "AUTO — Forecast Aware",
                        "CURRENT",
                        "+24h",
                        "+48h",
                        "+72h",
                    ]
                    if use_satellite_routing
                    else ["+24h", "+48h", "+72h"]
                )

                routing_horizon = st.selectbox(
                    "Routing forecast horizon",
                    routing_horizon_options,
                    index=0,
                    key="nav_routing_horizon",
                    help=(
                        "CURRENT uses the latest available satellite SIC and real "
                        "observed BYU iceberg positions. Future horizons use the "
                        "matching Member 1 forecast and Member 2 trajectory output."
                    ),
                )

                if routing_horizon == "AUTO — Forecast Aware":
                    st.caption(
                        "🛡️ AUTO considers CURRENT, +24h, +48h and +72h "
                        "conditions together and plans against the conservative "
                        "combined hazard environment."
                    )
                elif routing_horizon == "CURRENT":
                    st.caption(
                        "🟢 CURRENT = near-real-time observed environment. "
                        "No iceberg trajectory prediction is used."
                    )
                elif use_satellite_routing:
                    st.caption(
                        "🟡 Forecast horizon: sea ice is initialized from the "
                        "latest satellite observation. The iceberg forecast is only "
                        "fully synchronized when its initialization date matches."
                    )

            with route_control_2:
                vessel_profile_label = st.selectbox(
                    "Prototype vessel capability",
                    [
                        "Low Ice Capability",
                        "Medium Ice Capability",
                        "High Ice Capability",
                    ],
                    index=1,
                    key="nav_vessel_profile_label",
                    help=(
                        "Prototype decision-support profiles only; these are not "
                        "official Polar Class certifications."
                    ),
                )

            with route_control_3:
                route_buffer_km = st.slider(
                    "Iceberg safety radius (km)",
                    min_value=2.0,
                    max_value=25.0,
                    value=10.0,
                    step=1.0,
                    key="nav_route_buffer_km",
                    help=(
                        "Cells close to the matching predicted iceberg position "
                        "receive strong risk and may be blocked by vessel constraints."
                    ),
                )

            vessel_profile_lookup = {
                "Low Ice Capability": "LOW_ICE_CAPABILITY",
                "Medium Ice Capability": "MEDIUM_ICE_CAPABILITY",
                "High Ice Capability": "HIGH_ICE_CAPABILITY",
            }

            selected_vessel_profile = vessel_profile_lookup[
                vessel_profile_label
            ]

            demo_route_button = st.button(
                "🎯 Find Safe Demo Route",
                use_container_width=True,
                key="nav_find_safe_demo_route",
                help=(
                    "Search the real synchronized forecast grid for connected, "
                    "navigable start and destination cells."
                ),
            )

            if demo_route_button:

                if route_environment_bundle is None:
                    st.error(
                        "No route environment is available. Check the selected "
                        "routing sea-ice source above."
                    )

                if route_environment_bundle is not None:
                    operational_bundle_for_demo = (
                        get_operational_forecast_bundle()
                    )

                    if (
                        use_satellite_routing
                        and routing_horizon
                        == "AUTO — Forecast Aware"
                    ):
                        demo_nav = (
                            build_forecast_aware_environment(
                                operational_bundle_for_demo
                            )
                        )
                        demo_sic = demo_nav["sic"]
                        demo_uncertainty = demo_nav[
                            "uncertainty"
                        ]
                        demo_iceberg_positions = demo_nav[
                            "iceberg_positions"
                        ]

                    elif use_satellite_routing:
                        demo_nav = (
                            get_operational_navigation_inputs(
                                operational_bundle_for_demo,
                                routing_horizon,
                            )
                        )
                        demo_sic = demo_nav["sic"]
                        demo_uncertainty = demo_nav[
                            "uncertainty"
                        ]
                        demo_iceberg_positions = demo_nav[
                            "iceberg_positions"
                        ]

                    else:
                        demo_sic_key_lookup = {
                            "+24h": "forecast_24h",
                            "+48h": "forecast_48h",
                            "+72h": "forecast_72h",
                        }

                        demo_uncertainty_key_lookup = {
                            "+24h": "uncertainty_24h",
                            "+48h": "uncertainty_48h",
                            "+72h": "uncertainty_72h",
                        }

                        demo_iceberg_lookup = {
                            "+24h": forecast_24,
                            "+48h": forecast_48,
                            "+72h": forecast_72,
                        }

                        demo_sic = route_environment_bundle[
                            demo_sic_key_lookup[
                                routing_horizon
                            ]
                        ]
                        demo_uncertainty = (
                            route_environment_bundle[
                                demo_uncertainty_key_lookup[
                                    routing_horizon
                                ]
                            ]
                        )

                        demo_iceberg = demo_iceberg_lookup[
                            routing_horizon
                        ]

                        demo_iceberg_positions = [
                            {
                                "latitude": float(
                                    demo_iceberg["latitude"]
                                ),
                                "longitude": float(
                                    demo_iceberg["longitude"]
                                ),
                            }
                        ]

                    try:
                        with st.spinner(
                            "Searching the real forecast grid for a connected safe demo route..."
                        ):
                            demo_grid_lat, demo_grid_lon = (
                                projected_grid_to_latlon(
                                    route_environment_bundle["x"],
                                    route_environment_bundle["y"],
                                )
                            )

                            demo_route = find_safe_demo_route(
                                sic=demo_sic,
                                uncertainty=demo_uncertainty,
                                grid_lat=demo_grid_lat,
                                grid_lon=demo_grid_lon,
                                iceberg_positions=demo_iceberg_positions,
                                vessel_profile=selected_vessel_profile,
                                safety_radius_km=float(route_buffer_km),
                                influence_radius_km=float(
                                    max(
                                        route_buffer_km + 10.0,
                                        route_buffer_km * 3.0,
                                    )
                                ),
                            )

                        st.session_state["nav_start_lat"] = (
                            demo_route["start_lat"]
                        )
                        st.session_state["nav_start_lon"] = (
                            demo_route["start_lon"]
                        )
                        st.session_state["nav_destination_lat"] = (
                            demo_route["destination_lat"]
                        )
                        st.session_state["nav_destination_lon"] = (
                            demo_route["destination_lon"]
                        )
                        st.session_state["nav_route_display"] = None
                        st.session_state["nav_demo_route_message"] = (
                            "Real-grid demo coordinates loaded. "
                            f"Approximate endpoint separation: "
                            f"{demo_route['approx_distance_km']:.0f} km."
                        )
                        st.rerun()

                    except Exception as demo_route_error:
                        st.error(
                            "Automatic demo-route search failed: "
                            f"{demo_route_error}"
                        )

            if st.session_state.get("nav_demo_route_message"):
                st.info(
                    "🎯 "
                    + st.session_state["nav_demo_route_message"]
                )

            coord_col1, coord_col2, coord_col3, coord_col4 = st.columns(4)

            with coord_col1:
                route_start_lat = st.number_input(
                    "Start latitude",
                    min_value=-90.0,
                    max_value=-40.0,
                    value=float(
                        max(-89.0, min(-40.1, current_latitude + 0.20))
                    ),
                    step=0.01,
                    format="%.5f",
                    key="nav_start_lat",
                )

            with coord_col2:
                route_start_lon = st.number_input(
                    "Start longitude",
                    min_value=-180.0,
                    max_value=180.0,
                    value=float(
                        max(-179.0, min(179.0, current_longitude - 0.80))
                    ),
                    step=0.01,
                    format="%.5f",
                    key="nav_start_lon",
                )

            with coord_col3:
                route_destination_lat = st.number_input(
                    "Destination latitude",
                    min_value=-90.0,
                    max_value=-40.0,
                    value=float(
                        max(-89.0, min(-40.1, current_latitude + 0.70))
                    ),
                    step=0.01,
                    format="%.5f",
                    key="nav_destination_lat",
                )

            with coord_col4:
                route_destination_lon = st.number_input(
                    "Destination longitude",
                    min_value=-180.0,
                    max_value=180.0,
                    value=float(
                        max(-179.0, min(179.0, current_longitude + 1.20))
                    ),
                    step=0.01,
                    format="%.5f",
                    key="nav_destination_lon",
                )

            # ============================================================
            # SELECTED DESTINATION SEA-ICE FORECAST
            # ============================================================

            if route_environment_bundle is not None:
                try:
                    operational_bundle_for_site = (
                        get_operational_forecast_bundle()
                    )

                    site_grid_lat, site_grid_lon = (
                        projected_grid_to_latlon(
                            route_environment_bundle["x"],
                            route_environment_bundle["y"],
                        )
                    )

                    st.markdown(
                        "#### 🧊 Selected Destination Sea-Ice Forecast"
                    )

                    site_rows = []

                    site_horizons = [
                        ("CURRENT", "Current"),
                        ("+24H", "+24 h"),
                        ("+48H", "+48 h"),
                        ("+72H", "+72 h"),
                    ]

                    for (
                        backend_horizon,
                        display_horizon,
                    ) in site_horizons:
                        state = get_operational_horizon(
                            operational_bundle_for_site,
                            backend_horizon,
                        )

                        site_result = get_site_sic(
                            sic=np.asarray(
                                state["sic"],
                                dtype=float,
                            ),
                            grid_lat=site_grid_lat,
                            grid_lon=site_grid_lon,
                            latitude=route_destination_lat,
                            longitude=route_destination_lon,
                        )

                        if site_result["available"]:
                            ice_percent = site_result[
                                "sic_percent"
                            ]

                            site_rows.append(
                                {
                                    "Time": display_horizon,
                                    "Ice Concentration": (
                                        f"{ice_percent:.1f}%"
                                    ),
                                    "Condition": (
                                        classify_site_ice(
                                            ice_percent
                                        )
                                    ),
                                }
                            )
                        else:
                            site_rows.append(
                                {
                                    "Time": display_horizon,
                                    "Ice Concentration": "N/A",
                                    "Condition": (
                                        "No valid grid data"
                                    ),
                                }
                            )

                    st.dataframe(
                        pd.DataFrame(site_rows),
                        hide_index=True,
                        use_container_width=True,
                    )

                except Exception as site_sic_error:
                    st.warning(
                        "Selected-destination sea-ice forecast "
                        "is unavailable: "
                        f"{site_sic_error}"
                    )

            calculate_route = st.button(
                "🧭 Calculate Safe Route",
                type="primary",
                use_container_width=True,
                key="nav_calculate_route",
            )

        if "nav_route_display" not in st.session_state:
            st.session_state["nav_route_display"] = None

        # Routing consumes the environment selected in Navigation Request.
        # This can be either latest near-real-time satellite sea ice or the
        # date-synchronized historical/demo bundle.
        if calculate_route:

            if route_environment_bundle is None:
                st.error(
                    "Routing could not start because the selected sea-ice "
                    "environment is unavailable."
                )

            if route_environment_bundle is not None:

                operational_bundle = (
                    get_operational_forecast_bundle()
                )

                route_iceberg = None

                if (
                    use_satellite_routing
                    and routing_horizon
                    == "AUTO — Forecast Aware"
                ):
                    operational_nav = (
                        build_forecast_aware_environment(
                            operational_bundle
                        )
                    )

                elif use_satellite_routing:
                    operational_nav = (
                        get_operational_navigation_inputs(
                            operational_bundle,
                            routing_horizon,
                        )
                    )

                else:
                    route_sic_key_lookup = {
                        "+24h": "forecast_24h",
                        "+48h": "forecast_48h",
                        "+72h": "forecast_72h",
                    }

                    route_uncertainty_key_lookup = {
                        "+24h": "uncertainty_24h",
                        "+48h": "uncertainty_48h",
                        "+72h": "uncertainty_72h",
                    }

                    route_iceberg_lookup = {
                        "+24h": forecast_24,
                        "+48h": forecast_48,
                        "+72h": forecast_72,
                    }

                    route_sic = route_environment_bundle[
                        route_sic_key_lookup[
                            routing_horizon
                        ]
                    ]

                    route_uncertainty = (
                        route_environment_bundle[
                            route_uncertainty_key_lookup[
                                routing_horizon
                            ]
                        ]
                    )

                    route_iceberg = route_iceberg_lookup[
                        routing_horizon
                    ]

                    route_iceberg_positions = [
                        {
                            "latitude": float(
                                route_iceberg[
                                    "latitude"
                                ]
                            ),
                            "longitude": float(
                                route_iceberg[
                                    "longitude"
                                ]
                            ),
                        }
                    ]

                    finite_route_sic = route_sic[
                        np.isfinite(route_sic)
                    ]

                    route_operational_horizon = (
                        routing_horizon.upper()
                    )

                    route_seaice_metrics = {
                        "mean_sic": (
                            f"{np.mean(finite_route_sic) * 100.0:.1f}%"
                            if finite_route_sic.size
                            else "N/A"
                        ),
                        "ice_covered_grid": (
                            f"{np.mean(finite_route_sic >= 0.15) * 100.0:.1f}%"
                            if finite_route_sic.size
                            else "N/A"
                        ),
                    }

                    route_trajectory_coverage = (
                        "Historical/demo Member 2"
                    )
                    route_iceberg_hazard_count = len(
                        route_iceberg_positions
                    )

                    operational_nav = None

                if operational_nav is not None:
                    route_sic = operational_nav["sic"]
                    route_uncertainty = operational_nav[
                        "uncertainty"
                    ]
                    route_iceberg_positions = (
                        operational_nav[
                            "iceberg_positions"
                        ]
                    )
                    route_operational_horizon = (
                        operational_nav[
                            "operational_horizon"
                        ]
                    )
                    route_seaice_metrics = operational_nav[
                        "metrics"
                    ]
                    route_trajectory_coverage = (
                        operational_nav[
                            "trajectory_coverage"
                        ]
                    )
                    route_iceberg_hazard_count = (
                        operational_nav[
                            "iceberg_hazard_count"
                        ]
                    )

                # ============================================================
                # OPERATIONAL FORECAST STATUS
                # ============================================================

                st.markdown(
                    "#### Operational Forecast Status"
                )

                status_c1, status_c2, status_c3, status_c4 = (
                    st.columns(4)
                )

                with status_c1:
                    st.metric(
                        "Forecast Horizon",
                        route_operational_horizon,
                    )

                with status_c2:
                    st.metric(
                        "Mean SIC",
                        route_seaice_metrics[
                            "mean_sic"
                        ],
                    )

                with status_c3:
                    st.metric(
                        "Ice-Covered Grid",
                        route_seaice_metrics[
                            "ice_covered_grid"
                        ],
                    )

                with status_c4:
                    st.metric(
                        "Iceberg Hazards",
                        route_iceberg_hazard_count,
                    )

                if (
                    routing_horizon
                    == "AUTO — Forecast Aware"
                ):
                    st.caption(
                        "AUTO route planning combines CURRENT, "
                        "+24h, +48h and +72h SIC, uncertainty "
                        "and available iceberg hazards."
                    )
                elif (
                    route_operational_horizon
                    == "CURRENT"
                ):
                    st.caption(
                        "CURRENT routing uses observed sea ice "
                        "and the latest genuine iceberg "
                        "observations."
                    )
                else:
                    st.caption(
                        "Future routing uses the matching "
                        "Member-1 sea-ice forecast and RMSE "
                        "uncertainty. Member-2 iceberg "
                        "trajectories are included only where "
                        "genuine operational history is "
                        "available."
                    )

                try:
                    if (
                        routing_horizon == "CURRENT"
                        and use_satellite_routing
                        and not route_iceberg_positions
                    ):
                        raise RuntimeError(
                            "CURRENT near-real-time routing requires real observed "
                            "iceberg hazards, but none are available."
                        )

                    with st.spinner(
                        "Building risk grid and calculating A* safe route..."
                    ):
                        route_grid_lat, route_grid_lon = (
                            projected_grid_to_latlon(
                                route_environment_bundle["x"],
                                route_environment_bundle["y"],
                            )
                        )

                        navigation_result = build_navigation_route(
                            sic=route_sic,
                            uncertainty=route_uncertainty,
                            grid_lat=route_grid_lat,
                            grid_lon=route_grid_lon,
                            iceberg_positions=route_iceberg_positions,
                            start_lat=float(route_start_lat),
                            start_lon=float(route_start_lon),
                            destination_lat=float(route_destination_lat),
                            destination_lon=float(route_destination_lon),
                            vessel_profile=selected_vessel_profile,
                            safety_radius_km=float(route_buffer_km),
                            influence_radius_km=float(
                                max(route_buffer_km + 10.0, route_buffer_km * 3.0)
                            ),
                        )

                    vessel_profile_data = navigation_result[
                        "navigation_mask"
                    ]["profile"]

                    hazard_result = build_hazard_zones(
                        sic=route_sic,
                        uncertainty_risk=navigation_result["risk"][
                            "uncertainty_risk"
                        ],
                        iceberg_risk=navigation_result["risk"][
                            "iceberg_risk"
                        ],
                        vessel_max_sic=float(
                            vessel_profile_data["max_sic"]
                        ),
                        iceberg_exclusion_risk=float(
                            vessel_profile_data[
                                "iceberg_exclusion_risk"
                            ]
                        ),
                    )

                    hazard_grid_summary = summarize_hazard_grid(
                        hazard_result
                    )

                    route_hazard_summary = analyze_route_hazards(
                        path_indices=navigation_result["route"][
                            "path_indices"
                        ],
                        sic=route_sic,
                        uncertainty_risk=navigation_result["risk"][
                            "uncertainty_risk"
                        ],
                        iceberg_risk=navigation_result["risk"][
                            "iceberg_risk"
                        ],
                        combined_hazard=hazard_result[
                            "combined_hazard"
                        ],
                    )

                    route_ice_stats = (
                        calculate_route_ice_exposure(
                            navigation_result["route"][
                                "path_indices"
                            ],
                            route_sic,
                        )
                    )

                    route_alerts = generate_route_alerts(
                        route_hazard_summary=route_hazard_summary,
                        vessel_max_sic=float(
                            vessel_profile_data["max_sic"]
                        ),
                        iceberg_exclusion_risk=float(
                            vessel_profile_data[
                                "iceberg_exclusion_risk"
                            ]
                        ),
                    )

                    alternative_result = {
                        "success": False,
                        "reason": "Primary route is unavailable.",
                        "route": None,
                        "overlap_percent": 100.0,
                        "corridor_radius_cells": None,
                        "penalty_multiplier": None,
                    }
                    alternative_hazard_summary = None
                    alternative_alerts = []
                    alternative_ice_stats = None
                    route_comparison = None

                    if navigation_result["success"]:
                        alternative_base_cost = np.array(
                            navigation_result["risk"]["routing_cost"],
                            dtype=float,
                            copy=True,
                        )

                        alternative_base_cost[
                            navigation_result["navigation_mask"]["blocked_mask"]
                        ] = np.inf

                        alternative_result = build_alternative_route(
                            routing_cost=alternative_base_cost,
                            grid_lat=route_grid_lat,
                            grid_lon=route_grid_lon,
                            start_lat=float(route_start_lat),
                            start_lon=float(route_start_lon),
                            destination_lat=float(route_destination_lat),
                            destination_lon=float(route_destination_lon),
                            primary_path=navigation_result["route"][
                                "path_indices"
                            ],
                        )

                        if alternative_result["success"]:
                            alternative_hazard_summary = analyze_route_hazards(
                                path_indices=alternative_result["route"][
                                    "path_indices"
                                ],
                                sic=route_sic,
                                uncertainty_risk=navigation_result["risk"][
                                    "uncertainty_risk"
                                ],
                                iceberg_risk=navigation_result["risk"][
                                    "iceberg_risk"
                                ],
                                combined_hazard=hazard_result[
                                    "combined_hazard"
                                ],
                            )

                            alternative_ice_stats = (
                                calculate_route_ice_exposure(
                                    alternative_result["route"][
                                        "path_indices"
                                    ],
                                    route_sic,
                                )
                            )

                            alternative_alerts = generate_route_alerts(
                                route_hazard_summary=alternative_hazard_summary,
                                vessel_max_sic=float(
                                    vessel_profile_data["max_sic"]
                                ),
                                iceberg_exclusion_risk=float(
                                    vessel_profile_data[
                                        "iceberg_exclusion_risk"
                                    ]
                                ),
                            )

                            route_comparison = compare_routes(
                                navigation_result["route"],
                                alternative_result["route"],
                            )

                    # Keep route, hazard, and alternative-route display information
                    # in Streamlit session state.
                    endpoint_diagnostics = {}

                    if not navigation_result["success"]:
                        failure_reason = navigation_result["route"]["reason"]

                        if "Start cell is blocked" in failure_reason:
                            endpoint_diagnostics["start"] = explain_blocked_endpoint(
                                navigation_result=navigation_result,
                                grid_lat=route_grid_lat,
                                grid_lon=route_grid_lon,
                                requested_lat=float(route_start_lat),
                                requested_lon=float(route_start_lon),
                            )

                        if "Destination cell is blocked" in failure_reason:
                            endpoint_diagnostics["destination"] = explain_blocked_endpoint(
                                navigation_result=navigation_result,
                                grid_lat=route_grid_lat,
                                grid_lon=route_grid_lon,
                                requested_lat=float(route_destination_lat),
                                requested_lon=float(route_destination_lon),
                            )

                    st.session_state["nav_route_display"] = {
                        "success": bool(navigation_result["success"]),
                        "route": navigation_result["route"],
                        "route_summary": navigation_result["route_summary"],
                        "constraint_summary": navigation_result[
                            "constraint_summary"
                        ],
                        "recommendation": navigation_result["recommendation"],
                        "routing_horizon": routing_horizon,
                        "routing_data_source": (
                            route_environment_bundle.get(
                                "source",
                                "Historical / Demo Sea-Ice"
                            )
                        ),
                        "routing_environment_date": route_environment_bundle[
                            "date"
                        ],
                        "routing_provider_lag_days": route_environment_bundle.get(
                            "provider_lag_days"
                        ),
                        "route_operational_status": (
                            "NEAR-REAL-TIME CURRENT"
                            if (
                                use_satellite_routing
                                and routing_horizon == "CURRENT"
                                and current_iceberg_bundle is not None
                            )
                            else (
                                "FORECAST - NOT FULLY TIME-SYNCHRONIZED"
                                if (
                                    use_satellite_routing
                                    and routing_horizon != "CURRENT"
                                    and str(initialization_date)
                                    != str(route_environment_bundle["date"])
                                )
                                else "FORECAST / SYNCHRONIZED DEMO"
                            )
                        ),
                        "iceberg_data_source": (
                            current_iceberg_bundle["source"]
                            if (
                                routing_horizon == "CURRENT"
                                and current_iceberg_bundle is not None
                            )
                            else "Frozen Member 2 trajectory forecast"
                        ),
                        "iceberg_count_used": int(
                            len(route_iceberg_positions)
                        ),
                        "vessel_profile_label": vessel_profile_label,
                        "safety_radius_km": float(route_buffer_km),
                        "iceberg_position": (
                            {
                                "latitude": float(route_iceberg["latitude"]),
                                "longitude": float(route_iceberg["longitude"]),
                            }
                            if route_iceberg is not None
                            else None
                        ),
                        "start": {
                            "latitude": float(route_start_lat),
                            "longitude": float(route_start_lon),
                        },
                        "destination": {
                            "latitude": float(route_destination_lat),
                            "longitude": float(route_destination_lon),
                        },
                        "endpoint_diagnostics": endpoint_diagnostics,
                        "hazard_grid_summary": hazard_grid_summary,
                        "route_hazard_summary": route_hazard_summary,
                        "route_alerts": route_alerts,
                        "hazard_warning_zone": hazard_result[
                            "warning_zone"
                        ],
                        "hazard_critical_zone": hazard_result[
                            "critical_zone"
                        ],
                        "hazard_grid_lat": route_grid_lat,
                        "hazard_grid_lon": route_grid_lon,
                        "alternative_route": alternative_result,
                        "alternative_hazard_summary": alternative_hazard_summary,
                        "alternative_alerts": alternative_alerts,
                        "route_comparison": route_comparison,
                        "route_ice_stats": route_ice_stats,
                        "alternative_ice_stats": alternative_ice_stats,
                    }

                except Exception as route_error:
                    st.session_state["nav_route_display"] = None
                    st.error(
                        f"Route calculation failed: {route_error}"
                    )

        nav_route_display = st.session_state.get(
            "nav_route_display"
        )

        if nav_route_display is not None:

            if nav_route_display["success"]:

                recommendation = nav_route_display["recommendation"]
                route_data = nav_route_display["route"]
                route_risk_summary = nav_route_display["route_summary"]
                constraint_data = nav_route_display["constraint_summary"]

                st.success(
                    f"✅ {recommendation['status']} — "
                    f"{recommendation['message']}"
                )

                nav_metric_1, nav_metric_2, nav_metric_3, nav_metric_4 = (
                    st.columns(4)
                )

                nav_metric_1.metric(
                    "Route Distance",
                    f"{route_data['total_distance_km']:.1f} km",
                )

                nav_metric_2.metric(
                    "Maximum Route Risk",
                    f"{route_risk_summary['max_risk']:.2f}",
                )

                nav_metric_3.metric(
                    "Risk Class",
                    route_risk_summary["classification"],
                )

                nav_metric_4.metric(
                    "Blocked Grid",
                    f"{constraint_data['blocked_percent']:.1f}%",
                )

                status_label = nav_route_display.get(
                    "route_operational_status",
                    "PROTOTYPE ROUTE",
                )

                if status_label == "NEAR-REAL-TIME CURRENT":
                    st.success(
                        "🟢 Route Status: NEAR-REAL-TIME CURRENT — latest available "
                        "satellite SIC + real observed BYU iceberg hazards."
                    )
                elif status_label == "FORECAST - NOT FULLY TIME-SYNCHRONIZED":
                    st.warning(
                        "🟡 Route Status: FORECAST — sea ice is near-real-time, but "
                        "the iceberg forecast initialization is not fully synchronized "
                        "to the satellite observation date."
                    )
                else:
                    st.info(
                        f"Route Status: {status_label}"
                    )

                st.caption(
                    f"Route uses {nav_route_display['routing_horizon']} conditions "
                    f"from {nav_route_display.get('routing_data_source', 'the selected sea-ice source')} "
                    f"(environment date {nav_route_display.get('routing_environment_date', 'N/A')}); "
                    f"iceberg source: {nav_route_display.get('iceberg_data_source', 'N/A')}; "
                    f"iceberg hazards used: {nav_route_display.get('iceberg_count_used', 0)}; "
                    f"vessel: {nav_route_display['vessel_profile_label']}; "
                    f"planning radius: {nav_route_display['safety_radius_km']:.0f} km."
                )

                route_hazard = nav_route_display[
                    "route_hazard_summary"
                ]
                hazard_grid = nav_route_display[
                    "hazard_grid_summary"
                ]

                st.markdown("#### ⚠️ Route Hazard Intelligence")

                hz1, hz2, hz3, hz4 = st.columns(4)

                hz1.metric(
                    "Route Hazard",
                    route_hazard["hazard_level"],
                )

                hz2.metric(
                    "Maximum SIC",
                    (
                        f"{route_hazard['max_sic'] * 100.0:.1f}%"
                        if np.isfinite(route_hazard["max_sic"])
                        else "N/A"
                    ),
                )

                hz3.metric(
                    "Maximum Iceberg Risk",
                    (
                        f"{route_hazard['max_iceberg_risk']:.2f}"
                        if np.isfinite(
                            route_hazard["max_iceberg_risk"]
                        )
                        else "N/A"
                    ),
                )

                hz4.metric(
                    "Forecast Error Risk",
                    (
                        f"{route_hazard['max_uncertainty_risk']:.2f}"
                        if np.isfinite(
                            route_hazard["max_uncertainty_risk"]
                        )
                        else "N/A"
                    ),
                )

                route_ice_stats = nav_route_display.get(
                    "route_ice_stats"
                )

                if route_ice_stats is not None:
                    ice_m1, ice_m2, ice_m3 = st.columns(3)

                    ice_m1.metric(
                        "Average Ice on Route",
                        (
                            f"{route_ice_stats['mean_sic_percent']:.1f}%"
                            if route_ice_stats[
                                "mean_sic_percent"
                            ] is not None
                            else "N/A"
                        ),
                    )

                    ice_m2.metric(
                        "Maximum Ice on Route",
                        (
                            f"{route_ice_stats['max_sic_percent']:.1f}%"
                            if route_ice_stats[
                                "max_sic_percent"
                            ] is not None
                            else "N/A"
                        ),
                    )

                    ice_m3.metric(
                        "Route Through Ice ≥15%",
                        (
                            f"{route_ice_stats['ice_exposure_percent']:.1f}%"
                            if route_ice_stats[
                                "ice_exposure_percent"
                            ] is not None
                            else "N/A"
                        ),
                    )

                st.caption(
                    f"Selected routing grid: "
                    f"{hazard_grid['critical_percent']:.1f}% critical/avoid cells, "
                    f"{hazard_grid['warning_percent']:.1f}% warning cells."
                )

                st.markdown("#### 🚨 Route Alerts")

                for alert in nav_route_display["route_alerts"]:
                    severity = alert["severity"]
                    message = alert["message"]

                    if severity == "CRITICAL":
                        st.error(f"🚫 {message}")
                    elif severity == "WARNING":
                        st.warning(f"⚠️ {message}")
                    elif severity == "INFO":
                        st.info(f"ℹ️ {message}")
                    else:
                        st.success(f"✅ {message}")

                st.markdown("#### 🧠 Why PolarGuard Chose This Route")
                st.markdown(
                    "- A* minimizes combined navigation cost, not only distance.\n"
                    "- Vessel-blocked SIC cells are excluded.\n"
                    "- Iceberg exclusion cells are excluded.\n"
                    f"- The analysis uses synchronized "
                    f"{nav_route_display['routing_horizon']} sea-ice, "
                    "uncertainty and iceberg conditions."
                )

                st.markdown("#### 🛣️ Recommended vs Alternative Route")

                alternative_result = nav_route_display.get(
                    "alternative_route"
                )

                if (
                    alternative_result is not None
                    and alternative_result.get("success", False)
                ):
                    alternative_route_data = alternative_result["route"]
                    alternative_hazard = nav_route_display.get(
                        "alternative_hazard_summary"
                    )
                    route_comparison = nav_route_display.get(
                        "route_comparison"
                    )

                    comparison_rows = [
                        {
                            "Metric": "Distance",
                            "Recommended": (
                                f"{route_data['total_distance_km']:.1f} km"
                            ),
                            "Alternative": (
                                f"{alternative_route_data['total_distance_km']:.1f} km"
                            ),
                        },
                        {
                            "Metric": "Maximum SIC",
                            "Recommended": (
                                f"{route_hazard['max_sic'] * 100.0:.1f}%"
                            ),
                            "Alternative": (
                                f"{alternative_hazard['max_sic'] * 100.0:.1f}%"
                                if alternative_hazard is not None
                                else "N/A"
                            ),
                        },
                        {
                            "Metric": "Iceberg Risk",
                            "Recommended": (
                                f"{route_hazard['max_iceberg_risk']:.2f}"
                            ),
                            "Alternative": (
                                f"{alternative_hazard['max_iceberg_risk']:.2f}"
                                if alternative_hazard is not None
                                else "N/A"
                            ),
                        },
                        {
                            "Metric": "Forecast Error Risk",
                            "Recommended": (
                                f"{route_hazard['max_uncertainty_risk']:.2f}"
                            ),
                            "Alternative": (
                                f"{alternative_hazard['max_uncertainty_risk']:.2f}"
                                if alternative_hazard is not None
                                else "N/A"
                            ),
                        },
                        {
                            "Metric": "Hazard Level",
                            "Recommended": route_hazard["hazard_level"],
                            "Alternative": (
                                alternative_hazard["hazard_level"]
                                if alternative_hazard is not None
                                else "N/A"
                            ),
                        },
                    ]

                    st.dataframe(
                        pd.DataFrame(comparison_rows),
                        hide_index=True,
                        use_container_width=True,
                    )

                    cmp1, cmp2, cmp3 = st.columns(3)

                    cmp1.metric(
                        "Alternative Extra Distance",
                        (
                            f"{route_comparison['extra_distance_km']:+.1f} km"
                            if route_comparison is not None
                            else "N/A"
                        ),
                    )

                    cmp2.metric(
                        "Route Overlap",
                        f"{alternative_result['overlap_percent']:.1f}%",
                    )

                    cmp3.metric(
                        "Alternative Distance Change",
                        (
                            f"{route_comparison['distance_change_percent']:+.1f}%"
                            if route_comparison is not None
                            else "N/A"
                        ),
                    )

                    if alternative_result["overlap_percent"] <= 25.0:
                        st.success(
                            "✅ The alternative route is strongly separated "
                            "from the recommended route."
                        )
                    elif alternative_result["overlap_percent"] <= 65.0:
                        st.info(
                            "ℹ️ The alternative provides a meaningfully "
                            "different navigable option."
                        )
                    else:
                        st.warning(
                            "⚠️ Route separation is limited because the "
                            "currently navigable corridor is constrained."
                        )

                    if alternative_hazard is not None:
                        primary_score = route_hazard[
                            "max_combined_hazard"
                        ]
                        alternative_score = alternative_hazard[
                            "max_combined_hazard"
                        ]

                        if (
                            np.isfinite(primary_score)
                            and np.isfinite(alternative_score)
                            and alternative_score < primary_score
                        ):
                            st.info(
                                "Decision support: the alternative is "
                                "environmentally lower-risk at its highest-risk "
                                "point, but may require extra travel distance."
                            )
                        elif (
                            route_comparison is not None
                            and route_comparison["extra_distance_km"] > 0
                        ):
                            st.info(
                                "Decision support: the recommended route remains "
                                "the lower-cost primary option; the alternative "
                                "is retained as a distinct fallback corridor."
                            )

                    st.caption(
                        "The alternative is generated by penalizing the "
                        "recommended-route corridor and rerunning A*. Existing "
                        "unsafe/blocked cells remain unavailable."
                    )

                else:
                    alternative_reason = (
                        alternative_result.get("reason")
                        if alternative_result is not None
                        else "Alternative route was not evaluated."
                    )

                    st.warning(
                        "No independent alternative route is currently "
                        f"available. {alternative_reason}"
                    )

                st.markdown("#### 🚨 Operational Alert Center")

                for severity, message in _operational_navigation_alerts(
                    nav_route_display
                ):
                    if severity == "CRITICAL":
                        st.error(f"🚫 {message}")
                    elif severity == "WARNING":
                        st.warning(f"⚠️ {message}")
                    elif severity == "INFO":
                        st.info(f"ℹ️ {message}")
                    else:
                        st.success(f"✅ {message}")

                st.markdown("#### 📦 Route Export Center")

                route_exports = _build_navigation_exports(
                    nav_route_display
                )

                export_1, export_2, export_3 = st.columns(3)

                with export_1:
                    st.download_button(
                        "⬇️ Recommended GeoJSON",
                        data=route_exports[
                            "recommended_geojson"
                        ],
                        file_name="polarguard_recommended_route.geojson",
                        mime="application/geo+json",
                        use_container_width=True,
                    )

                    st.download_button(
                        "⬇️ Recommended CSV",
                        data=route_exports[
                            "recommended_csv"
                        ],
                        file_name="polarguard_recommended_route.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )

                with export_2:
                    if "alternative_geojson" in route_exports:
                        st.download_button(
                            "⬇️ Alternative GeoJSON",
                            data=route_exports[
                                "alternative_geojson"
                            ],
                            file_name="polarguard_alternative_route.geojson",
                            mime="application/geo+json",
                            use_container_width=True,
                        )

                        st.download_button(
                            "⬇️ Alternative CSV",
                            data=route_exports[
                                "alternative_csv"
                            ],
                            file_name="polarguard_alternative_route.csv",
                            mime="text/csv",
                            use_container_width=True,
                        )
                    else:
                        st.info(
                            "No alternative route is available "
                            "for this scenario."
                        )

                with export_3:
                    st.download_button(
                        "⬇️ Navigation Summary JSON",
                        data=route_exports[
                            "summary_json"
                        ],
                        file_name="polarguard_navigation_summary.json",
                        mime="application/json",
                        use_container_width=True,
                    )

                st.markdown("#### 📡 Current Decision Context")

                decision_1, decision_2, decision_3, decision_4 = (
                    st.columns(4)
                )

                decision_1.metric(
                    "Forecast Horizon",
                    nav_route_display["routing_horizon"],
                )

                decision_2.metric(
                    "Vessel Profile",
                    nav_route_display["vessel_profile_label"],
                )

                decision_3.metric(
                    "Iceberg Radius",
                    f"{nav_route_display['safety_radius_km']:.0f} km",
                )

                decision_4.metric(
                    "System Mode",
                    "Decision Support",
                )

                st.warning(
                    "⚠️ PolarGuard provides prototype decision support only. "
                    "It is not a certified navigation system and does not "
                    "replace the vessel master, ice navigator, official charts, "
                    "or authorized operational procedures."
                )

            else:
                st.error(
                    "🚫 NO SAFE ROUTE — "
                    f"{nav_route_display['route']['reason']}"
                )

                diagnostics = nav_route_display.get(
                    "endpoint_diagnostics",
                    {},
                )

                for endpoint_name, details in diagnostics.items():
                    pretty_name = endpoint_name.capitalize()

                    st.warning(
                        f"**{pretty_name} cell diagnosis**  \n"
                        f"Nearest routing cell: "
                        f"{details['latitude']:.5f}, "
                        f"{details['longitude']:.5f}  \n"
                        f"SIC risk: {details['sic']:.2f}  |  "
                        f"Iceberg risk: {details['iceberg_risk']:.2f}  |  "
                        f"Uncertainty risk: {details['uncertainty_risk']:.2f}  \n"
                        f"Reason: "
                        + (
                            "; ".join(details["reasons"])
                            if details["reasons"]
                            else "blocked by navigation constraints"
                        )
                    )

                st.info(
                    "Use **🎯 Find Safe Demo Route** to select start and destination "
                    "coordinates directly from the real navigable forecast grid."
                )

        if (
            nav_route_display is not None
            and nav_route_display.get("success", False)
        ):
            hazard_control_1, hazard_control_2, hazard_control_3 = st.columns(
                [1.0, 1.0, 1.6]
            )

            with hazard_control_1:
                show_warning_hazards = st.checkbox(
                    "🟠 Warning zones",
                    value=True,
                    key="nav_show_warning_hazards",
                )

            with hazard_control_2:
                show_critical_hazards = st.checkbox(
                    "🔴 Critical zones",
                    value=True,
                    key="nav_show_critical_hazards",
                )

            with hazard_control_3:
                hazard_overlay_detail = st.selectbox(
                    "Hazard overlay detail",
                    ["Fast", "Balanced", "Detailed"],
                    index=0,
                    key="nav_hazard_overlay_detail",
                    help=(
                        "Display resolution only; routing still uses "
                        "the full model grid."
                    ),
                )
        else:
            show_warning_hazards = False
            show_critical_hazards = False
            hazard_overlay_detail = "Fast"

        st.caption(
            "PolarGuard navigation outputs are prototype decision support. "
            "Risk weights, vessel profiles and planning radii are prototype "
            "parameters; they are not certified navigation rules or calibrated "
            "collision probabilities."
        )

        st.divider()

        status_col1, status_col2, status_col3, status_col4 = st.columns(4)

        status_col1.metric(
            "Initialization",
            initialization_date.strftime("%d %b %Y"),
        )

        if sea_ice_result.get("available", False):
            status_col2.metric(
                "Local SIC",
                f"{float(local_sic) * 100:.1f}%",
            )
        else:
            status_col2.metric(
                "Local SIC",
                "Unavailable",
            )

        status_col3.metric(
            f"{selected_label} Predicted Movement",
            f"{selected_forecast['predicted_displacement_km']:.2f} km",
        )

        status_col4.metric(
            f"{selected_label} Forecast Position",
            (
                f"{selected_forecast['latitude']:.3f}, "
                f"{selected_forecast['longitude']:.3f}"
            ),
        )

        if selected_horizon == "All" and current_frame_active:
            st.info(
                "Animation frame: Current observation. The synchronized sea-ice "
                "layer shows current SIC and the iceberg marker shows the initialization position."
            )
        elif selected_horizon == "All":
            st.info(
                "Current sea-ice layer with the complete forecast trajectory: "
                "Current → +24h → +48h → +72h."
            )
        else:
            st.info(
                f"Focused view: Current → {selected_horizon}. "
                f"Predicted position: "
                f"{selected_forecast['latitude']:.6f}, "
                f"{selected_forecast['longitude']:.6f}."
            )

        if member1_map_bundle is not None and show_full_sic_layer:
            selected_sic_values = member1_map_bundle[selected_sic_key]
            st.caption(
                f"🧊 Map layer: {selected_sic_label} • "
                f"Mean SIC {np.nanmean(selected_sic_values) * 100:.1f}% • "
                f"Full model grid {EXPECTED_Y} × {EXPECTED_X}"
            )

        if show_uncertainty_layer and selected_horizon == "All":
            st.info(
                "Select +24h, +48h or +72h to display the corresponding "
                "forecast-uncertainty layer."
            )

        with st.expander("📊 Frozen model performance", expanded=False):
            perf_df = pd.DataFrame(
                {
                    "Horizon": ["24h", "48h", "72h"],
                    "Iceberg RMSE (km)": [3.744, 6.389, 9.389],
                    "Within 5 km (%)": [92.23, 80.33, 69.48],
                    "RMSE improvement vs baseline (%)": [14.23, 19.25, 20.61],
                    "Sea-Ice within ±5 pp (%)": [94.87, 93.18, 92.33],
                }
            )
            st.dataframe(
                perf_df,
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                "Iceberg values are held-out 2025 results. Sea-ice percentages "
                "mean grid-cell forecasts within ±5 percentage points of observed SIC."
            )

        st.divider()

        st.subheader(
            "🧭 Antarctic Iceberg Trajectory"
        )

        st.caption(
            "Antarctica-focused operational map showing the observed iceberg path, "
            "the predicted 24h, 48h and 72h trajectory, synchronized sea ice, "
            "hazards and navigation layers. Zoom, pan, inspect markers and use fullscreen."
        )

        st.markdown(
            """
            <div style="padding:12px 15px;border:1px solid rgba(34,211,238,0.26);
                        border-radius:12px;background:linear-gradient(135deg,#071827,#0b2538);
                        color:#e6fbff;margin-bottom:10px;">
              <b>How to read the map</b><br>
              <span style="color:#cbd5e1;">Grey path</span> = observed movement
              &nbsp; • &nbsp;
              <span style="color:#0ea5e9;">Blue path</span> = PolarGuard forecast
              &nbsp; • &nbsp;
              🟡 Current &nbsp; 🟢 +24h &nbsp; 🔵 +48h &nbsp; 🟣 +72h
            </div>
            """,
            unsafe_allow_html=True,
        )

        # --------------------------------------------------------
        # TRAJECTORY DATA
        # --------------------------------------------------------

        trajectory_df = pd.DataFrame(
            {
                "latitude": [
                    lat_tm3,
                    lat_tm2,
                    lat_tm1,
                    current_latitude,
                    forecast_24["latitude"],
                    forecast_48["latitude"],
                    forecast_72["latitude"],
                ],
                "longitude": [
                    lon_tm3,
                    lon_tm2,
                    lon_tm1,
                    current_longitude,
                    forecast_24["longitude"],
                    forecast_48["longitude"],
                    forecast_72["longitude"],
                ],
                "stage": [
                    "t-3",
                    "t-2",
                    "t-1",
                    "Current",
                    "+24h",
                    "+48h",
                    "+72h",
                ],
                "kind": [
                    "Observed",
                    "Observed",
                    "Observed",
                    "Current",
                    "Forecast",
                    "Forecast",
                    "Forecast",
                ],
            }
        )

        # --------------------------------------------------------
        # MAP CONTROLS
        # --------------------------------------------------------

        map_control_1, map_control_2, map_control_3 = st.columns(3)

        with map_control_1:
            folium_zoom = st.slider(
                "Initial Zoom",
                min_value=3,
                max_value=9,
                value=5,
                step=1,
                key="folium_trajectory_zoom",
            )

        with map_control_2:
            show_observed_history = st.toggle(
                "Show Observed History",
                value=True,
                key="folium_show_history",
            )

        with map_control_3:
            show_coordinate_tool = st.toggle(
                "Show Mouse Coordinates",
                value=True,
                key="folium_mouse_coordinates",
            )

        # --------------------------------------------------------
        # ANTARCTICA-FOCUSED MAP
        # --------------------------------------------------------

        center_lat = float(
            np.mean(
                [
                    current_latitude,
                    forecast_24["latitude"],
                    forecast_48["latitude"],
                    forecast_72["latitude"],
                ]
            )
        )

        center_lon = float(
            np.mean(
                [
                    current_longitude,
                    forecast_24["longitude"],
                    forecast_48["longitude"],
                    forecast_72["longitude"],
                ]
            )
        )

        iceberg_map = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=folium_zoom,
            tiles=None,
            control_scale=True,
            prefer_canvas=True,
            zoom_control=True,
            dragging=True,
            scrollWheelZoom=True,
            doubleClickZoom=True,
            min_zoom=2,
            max_bounds=True,
            no_wrap=True,
        )
        # ============================================================
# POLARGUARD V2 — REAL OBSERVED ICEBERGS
# ============================================================

        if current_iceberg_bundle is not None:
           add_current_icebergs(
        iceberg_map,
        current_iceberg_bundle.get("positions", []),
        show_labels=True,
    )
           
        # --------------------------------------------------------
        # POLARGUARD ANTARCTIC OPERATIONAL BASEMAP
        # --------------------------------------------------------
                # --------------------------------------------------------
        # POLARGUARD ANTARCTIC OPERATIONAL HUD
        # Iceberg trajectory page
        # --------------------------------------------------------

        iceberg_hud_horizon = str(selected_label)

        iceberg_hud_date = str(initialization_date)

        iceberg_hud_count = (
            int(current_iceberg_bundle.get("iceberg_count", 0))
            if current_iceberg_bundle is not None
            else 0
        )

        add_map_hud(
            iceberg_map,
            horizon=iceberg_hud_horizon,
            initialization_date=iceberg_hud_date,
            iceberg_count=iceberg_hud_count,
            vessel_profile="ICEBERG TRACKING",
            uncertainty_available=(
                selected_uncertainty_key is not None
            ),
        )
        folium.TileLayer(
            tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            attr="© OpenStreetMap contributors",
            name="Antarctic Operations Base",
            overlay=False,
            control=True,
            max_zoom=19,
            no_wrap=True,
            bounds=[[-85.0, -180.0], [-40.0, 180.0]],
        ).add_to(iceberg_map)

        add_operational_map_style(
            iceberg_map,
            show_sic_legend=(
                member1_map_bundle is not None
                and show_full_sic_layer
            ),
        )

        add_geographic_reference_grid(
            iceberg_map,
            center_lat=center_lat,
            center_lon=center_lon,
            latitude_span=18.0,
            longitude_span=45.0,
        )

        add_position_reference_card(
            iceberg_map,
            current_latitude,
            current_longitude,
            title="CURRENT ICEBERG POSITION",
        )

        # --------------------------------------------------------
        # MEMBER 1 FULL SEA-ICE / UNCERTAINTY OVERLAYS
        # --------------------------------------------------------

        if member1_map_bundle is not None:
            if show_full_sic_layer:
                add_projected_grid_overlay(
                    fmap=iceberg_map,
                    values=member1_map_bundle[selected_sic_key],
                    x_coords=member1_map_bundle["x"],
                    y_coords=member1_map_bundle["y"],
                    name=selected_sic_label,
                    opacity=sic_layer_opacity,
                    sample_step=overlay_step,
                    mode="sic",
                )

            if (
                show_uncertainty_layer
                and selected_uncertainty_key is not None
            ):
                add_projected_grid_overlay(
                    fmap=iceberg_map,
                    values=member1_map_bundle[selected_uncertainty_key],
                    x_coords=member1_map_bundle["x"],
                    y_coords=member1_map_bundle["y"],
                    name=f"{selected_label} Forecast Uncertainty",
                    opacity=uncertainty_opacity,
                    sample_step=overlay_step,
                    mode="uncertainty",
                )

        # --------------------------------------------------------
        # ROUTING HAZARD ZONES
        # --------------------------------------------------------

        nav_hazard_display = st.session_state.get(
            "nav_route_display"
        )

        if (
            nav_hazard_display is not None
            and nav_hazard_display.get("success", False)
            and (show_warning_hazards or show_critical_hazards)
        ):
            hazard_grid_lat = nav_hazard_display["hazard_grid_lat"]
            hazard_grid_lon = nav_hazard_display["hazard_grid_lon"]
            warning_zone = nav_hazard_display["hazard_warning_zone"]
            critical_zone = nav_hazard_display["hazard_critical_zone"]

            hazard_step_lookup = {
                "Fast": 10,
                "Balanced": 7,
                "Detailed": 5,
            }
            hazard_step = hazard_step_lookup[
                hazard_overlay_detail
            ]

            def add_hazard_mask_layer(
                hazard_mask,
                layer_name,
                level,
                show_layer,
            ):
                if not show_layer:
                    return

                hazard_group = folium.FeatureGroup(
                    name=layer_name,
                    show=True,
                )

                rows, cols = hazard_mask.shape
                color = hazard_zone_color(level)

                for row in range(
                    0,
                    rows - hazard_step,
                    hazard_step,
                ):
                    for col in range(
                        0,
                        cols - hazard_step,
                        hazard_step,
                    ):
                        block = hazard_mask[
                            row:row + hazard_step,
                            col:col + hazard_step,
                        ]

                        if not np.any(block):
                            continue

                        r2 = min(
                            row + hazard_step,
                            rows - 1,
                        )
                        c2 = min(
                            col + hazard_step,
                            cols - 1,
                        )

                        corners = [
                            (
                                hazard_grid_lat[row, col],
                                hazard_grid_lon[row, col],
                            ),
                            (
                                hazard_grid_lat[row, c2],
                                hazard_grid_lon[row, c2],
                            ),
                            (
                                hazard_grid_lat[r2, c2],
                                hazard_grid_lon[r2, c2],
                            ),
                            (
                                hazard_grid_lat[r2, col],
                                hazard_grid_lon[r2, col],
                            ),
                        ]

                        if not all(
                            np.isfinite(lat)
                            and np.isfinite(lon)
                            for lat, lon in corners
                        ):
                            continue

                        corner_lons = [
                            lon for _, lon in corners
                        ]

                        if (
                            max(corner_lons)
                            - min(corner_lons)
                            > 180
                        ):
                            continue

                        folium.Polygon(
                            locations=[
                                [
                                    float(lat),
                                    float(lon),
                                ]
                                for lat, lon in corners
                            ],
                            color=color,
                            weight=0.6,
                            fill=True,
                            fill_color=color,
                            fill_opacity=(
                                0.20
                                if level == "warning"
                                else 0.28
                            ),
                            tooltip=(
                                "Warning navigation zone"
                                if level == "warning"
                                else "Critical / avoid navigation zone"
                            ),
                        ).add_to(
                            hazard_group
                        )

                hazard_group.add_to(
                    iceberg_map
                )

            add_hazard_mask_layer(
                warning_zone,
                "Warning Navigation Zones",
                "warning",
                show_warning_hazards,
            )

            add_hazard_mask_layer(
                critical_zone,
                "Critical / Avoid Navigation Zones",
                "critical",
                show_critical_hazards,
            )

        # --------------------------------------------------------
        # SAFE NAVIGATION ROUTE
        # --------------------------------------------------------

        nav_route_display = st.session_state.get(
            "nav_route_display"
        )

        if (
            nav_route_display is not None
            and nav_route_display.get("success", False)
        ):
            navigation_route_coordinates = [
                [
                    point["latitude"],
                    point["longitude"],
                ]
                for point in nav_route_display[
                    "route"
                ][
                    "path_coordinates"
                ]
            ]

            navigation_group = folium.FeatureGroup(
                name=(
                    "Recommended Safe Route "
                    f"({nav_route_display['routing_horizon']})"
                ),
                show=True,
            )

            if len(navigation_route_coordinates) >= 2:
                folium.PolyLine(
                    navigation_route_coordinates,
                    color="#16a34a",
                    weight=7,
                    opacity=0.95,
                    tooltip=(
                        "PolarGuard A* recommended lower-risk route"
                    ),
                ).add_to(navigation_group)

            route_start = nav_route_display["start"]
            route_destination = nav_route_display["destination"]

            folium.Marker(
                location=[
                    route_start["latitude"],
                    route_start["longitude"],
                ],
                tooltip="Vessel route start",
                popup=folium.Popup(
                    (
                        "<b>Vessel Start</b><br>"
                        f"Latitude: {route_start['latitude']:.5f}<br>"
                        f"Longitude: {route_start['longitude']:.5f}"
                    ),
                    max_width=260,
                ),
                icon=folium.Icon(
                    color="green",
                    icon="play",
                    prefix="fa",
                ),
            ).add_to(navigation_group)

            folium.Marker(
                location=[
                    route_destination["latitude"],
                    route_destination["longitude"],
                ],
                tooltip="Vessel destination",
                popup=folium.Popup(
                    (
                        "<b>Vessel Destination</b><br>"
                        f"Latitude: {route_destination['latitude']:.5f}<br>"
                        f"Longitude: {route_destination['longitude']:.5f}"
                    ),
                    max_width=260,
                ),
                icon=folium.Icon(
                    color="red",
                    icon="flag-checkered",
                    prefix="fa",
                ),
            ).add_to(navigation_group)

            navigation_group.add_to(
                iceberg_map
            )

            alternative_display = nav_route_display.get(
                "alternative_route"
            )

            if (
                alternative_display is not None
                and alternative_display.get("success", False)
            ):
                alternative_coordinates = [
                    [
                        point["latitude"],
                        point["longitude"],
                    ]
                    for point in alternative_display["route"][
                        "path_coordinates"
                    ]
                ]

                alternative_group = folium.FeatureGroup(
                    name=(
                        "Alternative Safe Route "
                        f"({nav_route_display['routing_horizon']})"
                    ),
                    show=True,
                )

                if len(alternative_coordinates) >= 2:
                    folium.PolyLine(
                        alternative_coordinates,
                        color="#2563eb",
                        weight=6,
                        opacity=0.88,
                        dash_array="10, 8",
                        tooltip=(
                            "PolarGuard alternative navigable route"
                        ),
                    ).add_to(alternative_group)

                alternative_group.add_to(
                    iceberg_map
                )

        # --------------------------------------------------------
        # FORECAST FOCUS / LAYER LOGIC
        # --------------------------------------------------------

        horizon_lookup = {
            "+24h": forecast_24,
            "+48h": forecast_48,
            "+72h": forecast_72,
        }

        # Optional local Member 1 SIC context.
        if (
            show_sic_context
            and sea_ice_result.get("available", False)
        ):
            sic_value = float(local_sic)

            if sic_value >= 0.8:
                sic_color = "#1d4ed8"
                sic_label = "High local sea-ice concentration"
            elif sic_value >= 0.4:
                sic_color = "#38bdf8"
                sic_label = "Moderate local sea-ice concentration"
            else:
                sic_color = "#bae6fd"
                sic_label = "Low local sea-ice concentration"

            folium.Circle(
                location=[current_latitude, current_longitude],
                radius=3500,
                color=sic_color,
                weight=2,
                fill=True,
                fill_color=sic_color,
                fill_opacity=0.10,
                tooltip=(
                    f"Member 1 local SIC: {sic_value * 100:.1f}% — "
                    f"{sic_label}"
                ),
            ).add_to(iceberg_map)

        # --------------------------------------------------------
        # OBSERVED PATH
        # --------------------------------------------------------

        if show_observed_history:

            observed_positions = [
                [lat_tm3, lon_tm3],
                [lat_tm2, lon_tm2],
                [lat_tm1, lon_tm1],
                [current_latitude, current_longitude],
            ]

            folium.PolyLine(
                observed_positions,
                color="#64748b",
                weight=4,
                opacity=0.85,
                tooltip="Observed iceberg movement",
            ).add_to(iceberg_map)

            observed_labels = [
                ("t-3", lat_tm3, lon_tm3),
                ("t-2", lat_tm2, lon_tm2),
                ("t-1", lat_tm1, lon_tm1),
            ]

            for stage, latitude, longitude in observed_labels:

                folium.CircleMarker(
                    location=[latitude, longitude],
                    radius=6,
                    color="#f8fafc",
                    weight=2,
                    fill=True,
                    fill_color="#64748b",
                    fill_opacity=1.0,
                    tooltip=f"{stage} observed position",
                    popup=folium.Popup(
                        (
                            f"<b>{stage}</b><br>"
                            f"Observed position<br>"
                            f"Latitude: {latitude:.6f}<br>"
                            f"Longitude: {longitude:.6f}"
                        ),
                        max_width=260,
                    ),
                ).add_to(iceberg_map)

        # --------------------------------------------------------
        # FORECAST PATH
        # --------------------------------------------------------

        if selected_horizon == "All" and current_frame_active:
            forecast_positions = [
                [current_latitude, current_longitude],
            ]
        elif selected_horizon == "All":
            forecast_positions = [
                [current_latitude, current_longitude],
                [forecast_24["latitude"], forecast_24["longitude"]],
                [forecast_48["latitude"], forecast_48["longitude"]],
                [forecast_72["latitude"], forecast_72["longitude"]],
            ]
        else:
            focused_forecast = horizon_lookup[selected_horizon]
            forecast_positions = [
                [current_latitude, current_longitude],
                [
                    focused_forecast["latitude"],
                    focused_forecast["longitude"],
                ],
            ]

        if len(forecast_positions) >= 2:
            folium.PolyLine(
                forecast_positions,
                color="#0ea5e9",
                weight=6,
                opacity=0.95,
                tooltip="PolarGuard predicted trajectory",
            ).add_to(iceberg_map)

        # Current position
        folium.CircleMarker(
            location=[current_latitude, current_longitude],
            radius=9,
            color="#ffffff",
            weight=2,
            fill=True,
            fill_color="#f59e0b",
            fill_opacity=1.0,
            tooltip="Current iceberg position",
            popup=folium.Popup(
                (
                    "<b>Current Position</b><br>"
                    f"Latitude: {current_latitude:.6f}<br>"
                    f"Longitude: {current_longitude:.6f}"
                ),
                max_width=280,
            ),
        ).add_to(iceberg_map)

        # Forecast markers
        forecast_markers = [
            (
                "+24h",
                forecast_24,
                "#16a34a",
            ),
            (
                "+48h",
                forecast_48,
                "#2563eb",
            ),
            (
                "+72h",
                forecast_72,
                "#9333ea",
            ),
        ]

        if selected_horizon == "All" and current_frame_active:
            visible_forecast_markers = []
        elif selected_horizon == "All":
            visible_forecast_markers = forecast_markers
        else:
            visible_forecast_markers = [
                item
                for item in forecast_markers
                if item[0] == selected_horizon
            ]

        for stage, forecast, marker_color in visible_forecast_markers:

            folium.CircleMarker(
                location=[
                    forecast["latitude"],
                    forecast["longitude"],
                ],
                radius=9,
                color="#ffffff",
                weight=2,
                fill=True,
                fill_color=marker_color,
                fill_opacity=1.0,
                tooltip=f"{stage} predicted position",
                popup=folium.Popup(
                    (
                        f"<b>{stage} Forecast</b><br>"
                        f"Latitude: {forecast['latitude']:.6f}<br>"
                        f"Longitude: {forecast['longitude']:.6f}<br>"
                        f"Displacement: "
                        f"{forecast['predicted_displacement_km']:.3f} km"
                    ),
                    max_width=300,
                ),
            ).add_to(iceberg_map)

        # --------------------------------------------------------
        # NAVIGATION PLANNING BUFFERS
        # --------------------------------------------------------

        if show_safety_buffer:
            if selected_horizon == "All" and current_frame_active:
                buffer_targets = []
            elif selected_horizon == "All":
                buffer_targets = forecast_markers
            else:
                buffer_targets = [
                    (
                        selected_horizon,
                        horizon_lookup[selected_horizon],
                        "#ef4444",
                    )
                ]

            for buffer_stage, buffer_forecast, _ in buffer_targets:
                folium.Circle(
                    location=[
                        buffer_forecast["latitude"],
                        buffer_forecast["longitude"],
                    ],
                    radius=safety_buffer_km * 1000.0,
                    color="#ef4444",
                    weight=2,
                    dash_array="6,6",
                    fill=True,
                    fill_color="#ef4444",
                    fill_opacity=0.06,
                    tooltip=(
                        f"{buffer_stage} navigation planning buffer "
                        f"({safety_buffer_km:.0f} km)"
                    ),
                ).add_to(iceberg_map)

        # --------------------------------------------------------
        # MAP PLUGINS
        # --------------------------------------------------------

        Fullscreen(
            position="topright",
            title="Fullscreen",
            title_cancel="Exit fullscreen",
            force_separate_button=True,
        ).add_to(iceberg_map)

        MeasureControl(
            position="topright",
            primary_length_unit="kilometers",
            secondary_length_unit="meters",
            primary_area_unit="sqkilometers",
        ).add_to(iceberg_map)

        if show_coordinate_tool:
            MousePosition(
                position="bottomright",
                separator=" | ",
                prefix="Lat/Lon:",
                num_digits=5,
            ).add_to(iceberg_map)

        folium.LayerControl(
            position="topright",
            collapsed=False,
        ).add_to(iceberg_map)

        # --------------------------------------------------------
        # FIT MAP TO COMPLETE TRAJECTORY
        # --------------------------------------------------------

        if selected_horizon == "All" and current_frame_active:
            # Include one nearby observed point to give Leaflet a stable useful extent.
            fit_points = [
                [lat_tm1, lon_tm1],
                [current_latitude, current_longitude],
            ]
        elif selected_horizon == "All":
            fit_points = [
                [current_latitude, current_longitude],
                [forecast_24["latitude"], forecast_24["longitude"]],
                [forecast_48["latitude"], forecast_48["longitude"]],
                [forecast_72["latitude"], forecast_72["longitude"]],
            ]
        else:
            focused_forecast = horizon_lookup[selected_horizon]
            fit_points = [
                [current_latitude, current_longitude],
                [
                    focused_forecast["latitude"],
                    focused_forecast["longitude"],
                ],
            ]

        if (
            show_observed_history
            and selected_horizon == "All"
            and not current_frame_active
        ):
            fit_points.extend(
                [
                    [lat_tm3, lon_tm3],
                    [lat_tm2, lon_tm2],
                    [lat_tm1, lon_tm1],
                ]
            )

        nav_route_display_for_fit = st.session_state.get(
            "nav_route_display"
        )

        if (
            nav_route_display_for_fit is not None
            and nav_route_display_for_fit.get("success", False)
        ):
            route_coords_for_fit = nav_route_display_for_fit[
                "route"
            ][
                "path_coordinates"
            ]

            alternative_fit = nav_route_display_for_fit.get(
                "alternative_route"
            )

            if (
                alternative_fit is not None
                and alternative_fit.get("success", False)
            ):
                route_coords_for_fit = (
                    list(route_coords_for_fit)
                    + list(
                        alternative_fit["route"]["path_coordinates"]
                    )
                )

            if route_coords_for_fit:
                # Sampling every few route points keeps fit calculations small.
                stride = max(
                    len(route_coords_for_fit) // 20,
                    1,
                )

                fit_points.extend(
                    [
                        [
                            point["latitude"],
                            point["longitude"],
                        ]
                        for point in route_coords_for_fit[::stride]
                    ]
                )

                fit_points.append(
                    [
                        nav_route_display_for_fit["destination"]["latitude"],
                        nav_route_display_for_fit["destination"]["longitude"],
                    ]
                )

        min_lat = min(point[0] for point in fit_points)
        max_lat = max(point[0] for point in fit_points)
        min_lon = min(point[1] for point in fit_points)
        max_lon = max(point[1] for point in fit_points)

        latitude_padding = max(
            (max_lat - min_lat) * 0.18,
            0.008,
        )

        longitude_padding = max(
            (max_lon - min_lon) * 0.18,
            0.008,
        )

        iceberg_map.fit_bounds(
            [
                [
                    min_lat - latitude_padding,
                    min_lon - longitude_padding,
                ],
                [
                    max_lat + latitude_padding,
                    max_lon + longitude_padding,
                ],
            ],
            padding=(40, 40),
        )

        # --------------------------------------------------------
        # DISPLAY MAP
        # --------------------------------------------------------

        _main_map_state = st_folium(
            iceberg_map,
            use_container_width=True,
            height=690,
            returned_objects=[],
            key="polarguard_iceberg_tracker",
        )

        # --------------------------------------------------------
        # ANIMATION DRIVER
        # --------------------------------------------------------
        # Streamlit reruns the script for each frame. Because the horizon
        # radio, sea-ice layer, uncertainty layer, summary cards and map
        # all use selected_horizon, one state change keeps every visual
        # component synchronized.
        if st.session_state.get("sih_animation_playing", False):
            current_frame = st.session_state.get("sih_focus_horizon", "All")

            try:
                current_frame_index = playback_frames.index(current_frame)
            except ValueError:
                current_frame_index = 0

            if current_frame_index < len(playback_frames) - 1:
                time.sleep(float(animation_speed))
                st.session_state["sih_playback_horizon"] = playback_frames[
    current_frame_index + 1
]
                st.rerun()
            else:
                st.session_state["sih_animation_playing"] = False
                st.success(
                    "✅ Forecast playback complete. Press Play to replay or Reset "
                    "to return to Current."
                )

        st.caption(
            "Mouse wheel = zoom • drag = pan • click a marker = forecast details • "
            "fullscreen = presentation mode • ruler = measure distance"
        )

        if selected_horizon == "All" and not current_frame_active:
            st.success(
                "Start at the 🟡 Current position and follow the blue line through "
                "🟢 +24h → 🔵 +48h → 🟣 +72h to understand the predicted movement."
            )
        elif current_frame_active:
            st.success(
                "🟡 Current frame: initialization position with current Member 1 sea-ice context."
            )
        else:
            st.success(
                f"Focused forecast frame: 🟡 Current → {selected_horizon} predicted position."
            )

        if show_full_sic_layer and member1_map_bundle is not None:
            st.markdown(
                """
                <div style="padding:10px 14px;border:1px solid #dbeafe;
                            border-radius:12px;background:#f8fbff;margin:8px 0;">
                  <b>Sea-Ice Concentration</b>&nbsp;&nbsp;
                  <span style="background:#eff6ff;padding:3px 8px;">0-10%</span>
                  <span style="background:#dbeafe;padding:3px 8px;">10-30%</span>
                  <span style="background:#bfdbfe;padding:3px 8px;">30-50%</span>
                  <span style="background:#93c5fd;padding:3px 8px;">50-70%</span>
                  <span style="background:#60a5fa;padding:3px 8px;color:white;">70-90%</span>
                  <span style="background:#2563eb;padding:3px 8px;color:white;">90-100%</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if (
            show_uncertainty_layer
            and member1_map_bundle is not None
            and selected_uncertainty_key is not None
        ):
            st.caption(
                "🟠 Uncertainty shading = historical per-grid-cell RMSE from "
                "2024 validation residuals; it is not a calibrated confidence interval."
            )

        # --------------------------------------------------------
        # LEGEND
        # --------------------------------------------------------

        legend_1, legend_2, legend_3, legend_4, legend_5 = st.columns(5)

        legend_1.markdown("⚪ **Observed**")
        legend_2.markdown("🟡 **Current**")
        legend_3.markdown("🟢 **+24 h**")
        legend_4.markdown("🔵 **+48 h**")
        legend_5.markdown("🟣 **+72 h**")

        st.markdown(
            """
            **Map interpretation:** start at the 🟡 current position and follow the
            blue forecast line. The green, blue and purple markers represent the
            24h, 48h and 72h predicted locations. Dashed red circles are optional
            planning buffers only; they are not calibrated collision probabilities.
            """
        )

        # ========================================================
        # TRAJECTORY SUMMARY
        # ========================================================

        st.divider()

        st.subheader(
            "Trajectory Forecast Summary"
        )

        summary_table = pd.DataFrame(
            [
                {
                    "Position": "Current",
                    "Latitude": f"{current_latitude:.6f}",
                    "Longitude": f"{current_longitude:.6f}",
                    "Displacement": "—",
                },
                {
                    "Position": "+24h",
                    "Latitude": f"{forecast_24['latitude']:.6f}",
                    "Longitude": f"{forecast_24['longitude']:.6f}",
                    "Displacement":
                        f"{forecast_24['predicted_displacement_km']:.3f} km",
                },
                {
                    "Position": "+48h",
                    "Latitude": f"{forecast_48['latitude']:.6f}",
                    "Longitude": f"{forecast_48['longitude']:.6f}",
                    "Displacement":
                        f"{forecast_48['predicted_displacement_km']:.3f} km",
                },
                {
                    "Position": "+72h",
                    "Latitude": f"{forecast_72['latitude']:.6f}",
                    "Longitude": f"{forecast_72['longitude']:.6f}",
                    "Displacement":
                        f"{forecast_72['predicted_displacement_km']:.3f} km",
                },
            ]
        )

        st.dataframe(
            summary_table,
            use_container_width=True,
            hide_index=True,
        )

        export_payload = {
            "system": "PolarGuard",
            "initialization_date": str(initialization_date),
            "current_position": {
                "latitude": float(current_latitude),
                "longitude": float(current_longitude),
            },
            "local_sea_ice": {
                "available": bool(sea_ice_result.get("available", False)),
                "sic": (
                    float(local_sic)
                    if sea_ice_result.get("available", False)
                    else None
                ),
            },
            "environment": {
                "wind_u10_mps": float(wind_u10),
                "wind_v10_mps": float(wind_v10),
                "ocean_uo_mps": float(ocean_uo),
                "ocean_vo_mps": float(ocean_vo),
            },
            "forecast": {
                "24h": forecast_24,
                "48h": forecast_48,
                "72h": forecast_72,
            },
        }

        import json

        download_col1, download_col2 = st.columns(2)

        with download_col1:
            st.download_button(
                "⬇️ Download Forecast JSON",
                data=json.dumps(export_payload, indent=2),
                file_name=(
                    f"polarguard_iceberg_forecast_{initialization_date}.json"
                ),
                mime="application/json",
                use_container_width=True,
            )

        with download_col2:
            st.download_button(
                "⬇️ Download Trajectory CSV",
                data=summary_table.to_csv(index=False),
                file_name=(
                    f"polarguard_trajectory_{initialization_date}.csv"
                ),
                mime="text/csv",
                use_container_width=True,
            )

        st.caption(
            "Downloads contain the displayed forecast and environmental inputs. "
            "They do not retrain or modify the frozen models."
        )

        # ========================================================
        # INDIVIDUAL HORIZON MAPS
        # ========================================================

        st.divider()

        st.subheader(
            "Forecast Horizon Detail"
        )

        tab24, tab48, tab72 = st.tabs(
            [
                "🟢 +24 Hours",
                "🔵 +48 Hours",
                "🟣 +72 Hours",
            ]
        )

        horizon_items = [
            (tab24, "24h", forecast_24, "#16a34a"),
            (tab48, "48h", forecast_48, "#2563eb"),
            (tab72, "72h", forecast_72, "#9333ea"),
        ]

        for (
            horizon_tab,
            horizon_name,
            forecast,
            horizon_color,
        ) in horizon_items:

            with horizon_tab:

                metric_1, metric_2, metric_3 = st.columns(3)

                metric_1.metric(
                    "Predicted Latitude",
                    f"{forecast['latitude']:.6f}"
                )

                metric_2.metric(
                    "Predicted Longitude",
                    f"{forecast['longitude']:.6f}"
                )

                metric_3.metric(
                    "Displacement",
                    f"{forecast['predicted_displacement_km']:.3f} km"
                )

                detail_center_lat = (
                    current_latitude
                    + forecast["latitude"]
                ) / 2

                detail_center_lon = (
                    current_longitude
                    + forecast["longitude"]
                ) / 2

                detail_map = folium.Map(
                    location=[
                        detail_center_lat,
                        detail_center_lon,
                    ],
                    zoom_start=7,
                    tiles=None,
                    control_scale=True,
                    prefer_canvas=True,
                    zoom_control=True,
                    dragging=True,
                    scrollWheelZoom=True,
                    doubleClickZoom=True,
                    min_zoom=3,
                    max_bounds=True,
                )

                folium.TileLayer(
                    tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                    attr="© OpenStreetMap contributors",
                    name="Antarctic Operations Base",
                    max_zoom=19,
                    no_wrap=True,
                    bounds=[[-85.0, -180.0], [-40.0, 180.0]],
                ).add_to(detail_map)

                add_operational_map_style(
                    detail_map,
                    show_sic_legend=False,
                )

                # Local geographic references remain visible while zooming.
                detail_lat_span = max(
                    abs(
                        float(forecast["latitude"])
                        - float(current_latitude)
                    ) * 5.0,
                    0.75,
                )

                detail_lon_span = max(
                    abs(
                        float(forecast["longitude"])
                        - float(current_longitude)
                    ) * 5.0,
                    1.5,
                )

                add_geographic_reference_grid(
                    detail_map,
                    center_lat=detail_center_lat,
                    center_lon=detail_center_lon,
                    latitude_span=detail_lat_span,
                    longitude_span=detail_lon_span,
                    name="Local Coordinate Grid",
                )

                add_position_reference_card(
                    detail_map,
                    forecast["latitude"],
                    forecast["longitude"],
                    title=f"+{horizon_name.upper()} PREDICTED POSITION",
                )

                folium.PolyLine(
                    [
                        [
                            current_latitude,
                            current_longitude,
                        ],
                        [
                            forecast["latitude"],
                            forecast["longitude"],
                        ],
                    ],
                    color=horizon_color,
                    weight=5,
                    opacity=0.95,
                ).add_to(detail_map)

                folium.CircleMarker(
                    location=[
                        current_latitude,
                        current_longitude,
                    ],
                    radius=9,
                    color="#ffffff",
                    weight=2,
                    fill=True,
                    fill_color="#f59e0b",
                    fill_opacity=1,
                    tooltip="Current",
                ).add_to(detail_map)

                folium.CircleMarker(
                    location=[
                        forecast["latitude"],
                        forecast["longitude"],
                    ],
                    radius=9,
                    color="#ffffff",
                    weight=2,
                    fill=True,
                    fill_color=horizon_color,
                    fill_opacity=1,
                    tooltip=f"+{horizon_name}",
                    popup=(
                        f"+{horizon_name}<br>"
                        f"Lat: {forecast['latitude']:.6f}<br>"
                        f"Lon: {forecast['longitude']:.6f}<br>"
                        f"Distance: "
                        f"{forecast['predicted_displacement_km']:.3f} km"
                    ),
                ).add_to(detail_map)

                Fullscreen(
                    position="topright",
                    force_separate_button=True,
                ).add_to(detail_map)

                MeasureControl(
                    position="topright",
                    primary_length_unit="kilometers",
                    secondary_length_unit="meters",
                ).add_to(detail_map)

                MousePosition(
                    position="bottomright",
                    separator=" | ",
                    prefix="Lat/Lon:",
                    num_digits=5,
                ).add_to(detail_map)

                folium.LayerControl(
                    position="topright",
                    collapsed=True,
                ).add_to(detail_map)

                detail_map.fit_bounds(
                    [
                        [
                            min(
                                current_latitude,
                                forecast["latitude"],
                            ) - max(
                                abs(
                                    forecast["latitude"]
                                    - current_latitude
                                ) * 0.30,
                                0.004,
                            ),
                            min(
                                current_longitude,
                                forecast["longitude"],
                            ) - max(
                                abs(
                                    forecast["longitude"]
                                    - current_longitude
                                ) * 0.30,
                                0.008,
                            ),
                        ],
                        [
                            max(
                                current_latitude,
                                forecast["latitude"],
                            ) + max(
                                abs(
                                    forecast["latitude"]
                                    - current_latitude
                                ) * 0.30,
                                0.004,
                            ),
                            max(
                                current_longitude,
                                forecast["longitude"],
                            ) + max(
                                abs(
                                    forecast["longitude"]
                                    - current_longitude
                                ) * 0.30,
                                0.008,
                            ),
                        ],
                    ],
                    padding=(55, 55),
                    max_zoom=12,
                )

                _detail_map_state = st_folium(
                    detail_map,
                    use_container_width=True,
                    height=500,
                    returned_objects=[],
                    key=f"detail_map_{horizon_name}",
                )

                st.caption(
                    f"Current iceberg position → +{horizon_name} predicted position."
                )



# ============================================================
# MODE 5: 2025 VALIDATION
# ============================================================
elif mode == "Polar Updates":
    from tinyfish_polar_updates import render_polar_updates

    render_polar_updates()
elif mode == "2025 Validation":

    render_validation_2025()
# ============================================================
# MODEL EXPLANATION
# ============================================================

st.divider()


with st.expander(
    "How does PolarGuard make the forecast?"
):

    st.markdown(
        """
### Input

The model uses four daily Antarctic SIC maps:

- Current SIC
- SIC one day earlier
- SIC two days earlier
- SIC three days earlier

For every valid grid cell it derives:

1. Current SIC
2. SIC(t-1)
3. SIC(t-2)
4. SIC(t-3)
5. Normalized X coordinate
6. Normalized Y coordinate
7. Seasonal sine value
8. Seasonal cosine value

### Hybrid Forecasting

PolarGuard combines persistence and machine learning.

For stable cells:

**Persistence forecast is used.**

For dynamically changing cells:

**HistGradientBoosting prediction is used.**

The switching signal is:

`abs(SIC(t) - SIC(t-3))`

with a frozen threshold of:

`0.002`

### Outputs

PolarGuard produces:

- +24 hour SIC map
- +48 hour SIC map
- +72 hour SIC map
- spatial uncertainty for each horizon

Each forecast map is:

**332 × 316 grid cells**
"""
    )


# ============================================================
# FOOTER
# ============================================================

st.caption(
    "PolarGuard — Antarctic Sea-Ice Forecasting Module"
)
