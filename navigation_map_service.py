from __future__ import annotations

from typing import Any

import numpy as np

from sea_ice_service import (
    predict_sea_ice,
    load_uncertainty,
)

from satellite_data_service import (
    load_latest_satellite_input,
)

from current_iceberg_service import (
    load_current_icebergs,
)

from risk_engine import (
    build_risk_grid,
)

from vessel_constraints import (
    build_navigation_mask,
)

from pyproj import Transformer


# ============================================================
# PROTOTYPE VESSEL PROFILES
# ============================================================

VESSEL_PROFILES = {
    "LOW": {
        "name": "LOW_ICE_CAPABILITY",
        "label": "Low Ice Capability",
        "max_sic": 0.30,
        "iceberg_exclusion_risk": 0.60,
        "uncertainty_limit": 0.70,
    },

    "MEDIUM": {
        "name": "MEDIUM_ICE_CAPABILITY",
        "label": "Medium Ice Capability",
        "max_sic": 0.55,
        "iceberg_exclusion_risk": 0.75,
        "uncertainty_limit": 0.85,
    },

    "HIGH": {
        "name": "HIGH_ICE_CAPABILITY",
        "label": "High Ice Capability",
        "max_sic": 0.80,
        "iceberg_exclusion_risk": 0.90,
        "uncertainty_limit": 1.00,
    },
}


# ============================================================
# JSON SAFETY
# ============================================================

def json_safe(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, np.ndarray):
        return json_safe(
            value.tolist()
        )

    if isinstance(value, np.generic):
        return json_safe(
            value.item()
        )

    if isinstance(value, float):
        if not np.isfinite(value):
            return None

        return value

    if isinstance(value, dict):
        return {
            str(key): json_safe(item)
            for key, item in value.items()
        }

    if isinstance(
        value,
        (list, tuple),
    ):
        return [
            json_safe(item)
            for item in value
        ]

    return value


# ============================================================
# GRID → WGS84
# ============================================================

def projected_grid_to_latlon(
    x_coords: np.ndarray,
    y_coords: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:

    x_grid, y_grid = np.meshgrid(
        np.asarray(
            x_coords,
            dtype=float,
        ),
        np.asarray(
            y_coords,
            dtype=float,
        ),
    )

    transformer = (
        Transformer.from_crs(
            "EPSG:3412",
            "EPSG:4326",
            always_xy=True,
        )
    )

    grid_lon, grid_lat = (
        transformer.transform(
            x_grid,
            y_grid,
        )
    )

    return (
        np.asarray(
            grid_lat,
            dtype=float,
        ),
        np.asarray(
            grid_lon,
            dtype=float,
        ),
    )


# ============================================================
# CURRENT ICEBERGS
# ============================================================

def load_current_iceberg_records():
    bundle = (
        load_current_icebergs()
    )

    dataframe = (
        bundle.get(
            "dataframe"
        )
    )

    if dataframe is None:
        return []

    records = []

    for _, row in dataframe.iterrows():
        try:
            latitude = float(
                row["latitude"]
            )

            longitude = float(
                row["longitude"]
            )
        except Exception:
            continue

        if not (
            np.isfinite(latitude)
            and
            np.isfinite(longitude)
        ):
            continue

        age_value = (
            row.get(
                "age_days"
            )
        )

        try:
            age_days = (
                int(age_value)
                if age_value is not None
                and np.isfinite(
                    float(
                        age_value
                    )
                )
                else None
            )
        except Exception:
            age_days = None

        records.append(
            {
                "iceberg_id": str(
                    row.get(
                        "iceberg_id",
                        "UNKNOWN",
                    )
                ).upper(),

                "latitude":
                    latitude,

                "longitude":
                    longitude,

                "observation_date":
                    str(
                        row.get(
                            "observation_date",
                            "",
                        )
                    ),

                "age_days":
                    age_days,

                "freshness_status":
                    str(
                        row.get(
                            "freshness_status",
                            "UNKNOWN",
                        )
                    ),
            }
        )

    return records


# ============================================================
# LATEST MEMBER-1 FORECAST BUNDLE
# ============================================================

def build_latest_forecast_bundle():
    satellite = (
        load_latest_satellite_input()
    )

    current = np.asarray(
        satellite["current"],
        dtype=np.float32,
    )

    lag1 = np.asarray(
        satellite["lag1"],
        dtype=np.float32,
    )

    lag2 = np.asarray(
        satellite["lag2"],
        dtype=np.float32,
    )

    lag3 = np.asarray(
        satellite["lag3"],
        dtype=np.float32,
    )

    x_coords = np.asarray(
        satellite["x"],
        dtype=float,
    )

    y_coords = np.asarray(
        satellite["y"],
        dtype=float,
    )

    initialization_date = (
        np.datetime64(
            satellite["date"],
            "D",
        )
    )

    forecasts = predict_sea_ice(
        current=current,
        lag1=lag1,
        lag2=lag2,
        lag3=lag3,
        x_coords=x_coords,
        y_coords=y_coords,
        date=initialization_date,
    )

    uncertainty = (
        load_uncertainty()
    )

    return {
        "date":
            str(
                initialization_date
            ),

        "provider_lag_days":
            satellite.get(
                "provider_lag_days"
            ),

        "current":
            current,

        "forecast_24h":
            np.asarray(
                forecasts["24h"],
                dtype=np.float32,
            ),

        "forecast_48h":
            np.asarray(
                forecasts["48h"],
                dtype=np.float32,
            ),

        "forecast_72h":
            np.asarray(
                forecasts["72h"],
                dtype=np.float32,
            ),

        "uncertainty_24h":
            np.asarray(
                uncertainty["24h"],
                dtype=np.float32,
            ),

        "uncertainty_48h":
            np.asarray(
                uncertainty["48h"],
                dtype=np.float32,
            ),

        "uncertainty_72h":
            np.asarray(
                uncertainty["72h"],
                dtype=np.float32,
            ),

        "x":
            x_coords,

        "y":
            y_coords,
    }


# ============================================================
# MAP DATA
# ============================================================

def build_navigation_map_data(
    horizon: str = "CURRENT",
    vessel_profile: str = "MEDIUM",
    safety_radius_km: float = 8.0,
    influence_radius_km: float = 24.0,
    sample_step: int = 5,
) -> dict[str, Any]:

    # --------------------------------------------------------
    # NORMALIZE HORIZON
    # --------------------------------------------------------

    horizon = (
        str(horizon)
        .strip()
        .upper()
    )

    valid_horizons = {
        "CURRENT",
        "+24H",
        "+48H",
        "+72H",
    }

    if horizon not in valid_horizons:
        horizon = "CURRENT"


    # --------------------------------------------------------
    # NORMALIZE PROFILE
    # --------------------------------------------------------

    profile_key = (
        str(vessel_profile)
        .strip()
        .upper()
    )

    if profile_key not in VESSEL_PROFILES:
        profile_key = "MEDIUM"

    profile = (
        VESSEL_PROFILES[
            profile_key
        ]
    )


    # --------------------------------------------------------
    # MEMBER-1
    # --------------------------------------------------------

    bundle = (
        build_latest_forecast_bundle()
    )


    sic_lookup = {
        "CURRENT":
            "current",

        "+24H":
            "forecast_24h",

        "+48H":
            "forecast_48h",

        "+72H":
            "forecast_72h",
    }

    uncertainty_lookup = {
        "+24H":
            "uncertainty_24h",

        "+48H":
            "uncertainty_48h",

        "+72H":
            "uncertainty_72h",
    }


    sic = np.asarray(
        bundle[
            sic_lookup[
                horizon
            ]
        ],
        dtype=np.float32,
    )


    # CURRENT is an observation,
    # not a forecast.
    if horizon == "CURRENT":

        uncertainty = np.where(
            np.isfinite(sic),
            0.0,
            np.nan,
        ).astype(
            np.float32
        )

        uncertainty_available = False

    else:

        uncertainty = np.asarray(
            bundle[
                uncertainty_lookup[
                    horizon
                ]
            ],
            dtype=np.float32,
        )

        uncertainty_available = True


    # --------------------------------------------------------
    # LAT / LON
    # --------------------------------------------------------

    grid_lat, grid_lon = (
        projected_grid_to_latlon(
            bundle["x"],
            bundle["y"],
        )
    )


    # --------------------------------------------------------
    # ICEBERGS
    # --------------------------------------------------------

    icebergs = (
        load_current_iceberg_records()
    )

    iceberg_positions = [
        {
            "latitude":
                item["latitude"],

            "longitude":
                item["longitude"],
        }

        for item in icebergs
    ]


    # --------------------------------------------------------
    # RISK
    # --------------------------------------------------------

    risk = build_risk_grid(
        sic=sic,
        uncertainty=uncertainty,
        grid_lat=grid_lat,
        grid_lon=grid_lon,
        iceberg_positions=iceberg_positions,
        safety_radius_km=float(
            safety_radius_km
        ),
        influence_radius_km=float(
            influence_radius_km
        ),
    )


    # --------------------------------------------------------
    # VESSEL NAVIGATION MASK
    # --------------------------------------------------------

    nav_mask = (
        build_navigation_mask(
            sic=sic,

            iceberg_risk=
                risk[
                    "iceberg_risk"
                ],

            uncertainty_risk=
                risk[
                    "uncertainty_risk"
                ],

            blocked_mask=
                risk[
                    "blocked_mask"
                ],

            profile_name=
                profile[
                    "name"
                ],
        )
    )


    # --------------------------------------------------------
    # MAP SAMPLING
    #
    # Routing still uses the full grid.
    # Sampling is visualization-only.
    # --------------------------------------------------------

    step = max(
        int(sample_step),
        1,
    )

    cells = []

    rows, cols = (
        sic.shape
    )

    for row in range(
        0,
        rows,
        step,
    ):

        for col in range(
            0,
            cols,
            step,
        ):

            latitude = (
                grid_lat[
                    row,
                    col,
                ]
            )

            longitude = (
                grid_lon[
                    row,
                    col,
                ]
            )

            sic_value = (
                sic[
                    row,
                    col,
                ]
            )

            if not (
                np.isfinite(
                    latitude
                )
                and
                np.isfinite(
                    longitude
                )
                and
                np.isfinite(
                    sic_value
                )
            ):
                continue

            if (
                latitude > -40.0
                or
                latitude < -90.0
            ):
                continue


            combined_risk = (
                risk[
                    "combined_risk"
                ][
                    row,
                    col,
                ]
            )

            sea_ice_risk = (
                risk[
                    "sea_ice_risk"
                ][
                    row,
                    col,
                ]
            )

            iceberg_risk = (
                risk[
                    "iceberg_risk"
                ][
                    row,
                    col,
                ]
            )

            uncertainty_risk = (
                risk[
                    "uncertainty_risk"
                ][
                    row,
                    col,
                ]
            )

            uncertainty_value = (
                uncertainty[
                    row,
                    col,
                ]
            )


            blocked = bool(
                nav_mask[
                    "blocked_mask"
                ][
                    row,
                    col,
                ]
            )

            blocked_by_sic = bool(
                nav_mask[
                    "blocked_by_sic"
                ][
                    row,
                    col,
                ]
            )

            blocked_by_iceberg = bool(
                nav_mask[
                    "blocked_by_iceberg"
                ][
                    row,
                    col,
                ]
            )

            blocked_by_uncertainty = bool(
                nav_mask[
                    "blocked_by_uncertainty"
                ][
                    row,
                    col,
                ]
            )


            if not np.isfinite(
                combined_risk
            ):
                combined_risk_value = None
            else:
                combined_risk_value = float(
                    combined_risk
                )


            if not np.isfinite(
                sea_ice_risk
            ):
                sea_ice_risk_value = None
            else:
                sea_ice_risk_value = float(
                    sea_ice_risk
                )


            if not np.isfinite(
                iceberg_risk
            ):
                iceberg_risk_value = None
            else:
                iceberg_risk_value = float(
                    iceberg_risk
                )


            if not np.isfinite(
                uncertainty_risk
            ):
                uncertainty_risk_value = None
            else:
                uncertainty_risk_value = float(
                    uncertainty_risk
                )


            if not np.isfinite(
                uncertainty_value
            ):
                uncertainty_value_json = None
            else:
                uncertainty_value_json = float(
                    uncertainty_value
                )


            if blocked:

                if blocked_by_sic:
                    block_reason = (
                        "SIC exceeds vessel limit"
                    )

                elif blocked_by_iceberg:
                    block_reason = (
                        "Iceberg exclusion risk"
                    )

                elif blocked_by_uncertainty:
                    block_reason = (
                        "Forecast uncertainty exceeds limit"
                    )

                else:
                    block_reason = (
                        "Environmental / combined constraint"
                    )

            else:
                block_reason = None


            cells.append(
                {
                    "row":
                        int(
                            row
                        ),

                    "col":
                        int(
                            col
                        ),

                    "latitude":
                        float(
                            latitude
                        ),

                    "longitude":
                        float(
                            longitude
                        ),

                    "sic":
                        float(
                            np.clip(
                                sic_value,
                                0.0,
                                1.0,
                            )
                        ),

                    "uncertainty":
                        (
                            uncertainty_value_json
                        ),

                    "sea_ice_risk":
                        sea_ice_risk_value,

                    "iceberg_risk":
                        iceberg_risk_value,

                    "uncertainty_risk":
                        uncertainty_risk_value,

                    "combined_risk":
                        combined_risk_value,

                    "blocked":
                        blocked,

                    "blocked_by_sic":
                        blocked_by_sic,

                    "blocked_by_iceberg":
                        blocked_by_iceberg,

                    "blocked_by_uncertainty":
                        blocked_by_uncertainty,

                    "block_reason":
                        block_reason,
                }
            )


    # --------------------------------------------------------
    # TRAJECTORY STATUS
    # --------------------------------------------------------

    trajectory = {
        "available":
            False,

        "status":
            (
                "WAITING_FOR_4_REAL_DAILY_POSITIONS"
            ),

        "points":
            [],

        "note":
            (
                "The current BYU feed provides latest "
                "observed iceberg hazards. "
                "Future Member-2 trajectory forecasting "
                "requires four consecutive real daily "
                "positions for the same iceberg."
            ),
    }


    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    finite_sic = (
        sic[
            np.isfinite(
                sic
            )
        ]
    )

    if finite_sic.size:

        mean_sic = float(
            np.mean(
                finite_sic
            )
        )

        max_sic = float(
            np.max(
                finite_sic
            )
        )

    else:

        mean_sic = None
        max_sic = None


    response = {
        "ok":
            True,

        "mode":
            "LATEST_AVAILABLE",

        "horizon":
            horizon,

        "initialization_date":
            bundle["date"],

        "provider_lag_days":
            bundle[
                "provider_lag_days"
            ],

        "vessel_profile":
            profile,

        "safety_radius_km":
            float(
                safety_radius_km
            ),

        "influence_radius_km":
            float(
                influence_radius_km
            ),

        "uncertainty_available":
            uncertainty_available,

        "grid": {
            "rows":
                int(
                    rows
                ),

            "cols":
                int(
                    cols
                ),

            "sample_step":
                step,

            "sampled_cells":
                len(
                    cells
                ),

            "crs":
                "EPSG:3412",
        },

        "summary": {
            "mean_sic":
                mean_sic,

            "max_sic":
                max_sic,

            "blocked_cells":
                int(
                    np.sum(
                        nav_mask[
                            "blocked_mask"
                        ]
                    )
                ),

            "blocked_by_sic":
                int(
                    np.sum(
                        nav_mask[
                            "blocked_by_sic"
                        ]
                    )
                ),

            "blocked_by_iceberg":
                int(
                    np.sum(
                        nav_mask[
                            "blocked_by_iceberg"
                        ]
                    )
                ),

            "blocked_by_uncertainty":
                int(
                    np.sum(
                        nav_mask[
                            "blocked_by_uncertainty"
                        ]
                    )
                ),
        },

        "cells":
            cells,

        "icebergs":
            icebergs,

        "trajectory":
            trajectory,

        "scientific_note":
            (
                "Sea-ice forecast uncertainty is the "
                "historical per-grid-cell RMSE derived "
                "from 2024 validation residuals. "
                "It is not a calibrated confidence interval. "
                "CURRENT SIC is an observation, so forecast "
                "uncertainty is not applied to CURRENT routing."
            ),
    }

    return json_safe(
        response
    )