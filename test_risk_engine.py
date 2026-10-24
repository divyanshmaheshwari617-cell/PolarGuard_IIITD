import numpy as np

from risk_engine import (
    build_risk_grid,
    classify_risk
)


# ============================================================
# CREATE TEST GRID
# ============================================================

rows = 30
cols = 30

# Normal sea ice = 30%
sic = np.full(
    (rows, cols),
    0.30,
    dtype=float
)

# Add a heavier sea-ice region = 75%
sic[5:15, 15:25] = 0.75


# ============================================================
# UNCERTAINTY
# ============================================================

# 3 percentage-point historical RMSE
uncertainty = np.full(
    (rows, cols),
    0.03,
    dtype=float
)


# ============================================================
# LATITUDE / LONGITUDE GRID
# ============================================================

latitudes = np.linspace(
    -76.0,
    -75.0,
    rows
)

longitudes = np.linspace(
    -42.0,
    -40.0,
    cols
)

grid_lon, grid_lat = np.meshgrid(
    longitudes,
    latitudes
)


# ============================================================
# TEST ICEBERG
# ============================================================

iceberg_positions = [
    {
        "latitude": -75.50,
        "longitude": -41.00
    }
]


# ============================================================
# BUILD RISK GRID
# ============================================================

result = build_risk_grid(
    sic=sic,
    uncertainty=uncertainty,
    grid_lat=grid_lat,
    grid_lon=grid_lon,
    iceberg_positions=iceberg_positions,
    safety_radius_km=10.0,
    influence_radius_km=30.0
)


# ============================================================
# GET OUTPUTS
# ============================================================

sea_ice_risk = result["sea_ice_risk"]

iceberg_risk = result["iceberg_risk"]

uncertainty_risk = result["uncertainty_risk"]

combined_risk = result["combined_risk"]

routing_cost = result["routing_cost"]


# ============================================================
# PRINT RESULTS
# ============================================================

print()
print("POLARGUARD RISK ENGINE TEST")
print("===========================")
print()

print(
    "Sea-ice risk range:",
    np.nanmin(sea_ice_risk),
    "to",
    np.nanmax(sea_ice_risk)
)

print(
    "Iceberg risk range:",
    np.nanmin(iceberg_risk),
    "to",
    np.nanmax(iceberg_risk)
)

print(
    "Uncertainty risk range:",
    np.nanmin(uncertainty_risk),
    "to",
    np.nanmax(uncertainty_risk)
)

print(
    "Combined risk range:",
    np.nanmin(combined_risk),
    "to",
    np.nanmax(combined_risk)
)


# Only finite routing cells
finite_cost = routing_cost[
    np.isfinite(routing_cost)
]

print(
    "Routing cost range:",
    np.min(finite_cost),
    "to",
    np.max(finite_cost)
)


# ============================================================
# CHECK CENTER CELL
# ============================================================

center_row = rows // 2
center_col = cols // 2

center_risk = combined_risk[
    center_row,
    center_col
]

print()
print(
    "Center-cell risk:",
    center_risk
)

print(
    "Center-cell classification:",
    classify_risk(center_risk)
)


# ============================================================
# BASIC AUTOMATIC CHECKS
# ============================================================

assert sea_ice_risk.shape == (rows, cols)
assert iceberg_risk.shape == (rows, cols)
assert uncertainty_risk.shape == (rows, cols)
assert combined_risk.shape == (rows, cols)
assert routing_cost.shape == (rows, cols)

assert np.nanmin(sea_ice_risk) >= 0.0
assert np.nanmax(sea_ice_risk) <= 1.0

assert np.nanmin(iceberg_risk) >= 0.0
assert np.nanmax(iceberg_risk) <= 1.0

assert np.nanmin(uncertainty_risk) >= 0.0
assert np.nanmax(uncertainty_risk) <= 1.0


print()
print("ALL BASIC CHECKS PASSED")
print("RISK ENGINE TEST COMPLETE")