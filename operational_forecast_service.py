"""
PolarGuard - Operational Forecast Coordinator
---------------------------------------------

Purpose
-------
Combine the operational components of PolarGuard into one
horizon-aligned data bundle:

    Satellite SIC
         ↓
    Frozen Member 1
         ↓
    CURRENT / +24H / +48H / +72H
         ↓
    Sea-Ice Intelligence
         +
    Genuine current iceberg observations
         +
    Frozen Member 2 where operational history permits
         ↓
    Horizon-aligned hazard bundle

Scientific rules
----------------
- CURRENT iceberg hazards use genuine latest observations.
- Member 2 runs only when four genuine consecutive positions
  ending on the latest operational observation are available.
- Missing iceberg history is never filled by interpolation,
  repetition, or synthetic positions.
- Future Member-1 SIC forecasts are NOT fed into frozen Member 2.
- CURRENT sea ice is observational.
- Forecast uncertainty is RMSE-based, not a confidence interval.
- Future iceberg coverage may legitimately be zero.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from iceberg_history_service import (
    load_operational_history,
    assess_operational_icebergs,
)

from operational_trajectory_service import (
    forecast_operational_iceberg,
)

from sea_ice_intelligence_service import (
    build_intelligence_from_route_bundle,
    format_horizon_display_metrics,
)


# ============================================================
# CONFIGURATION
# ============================================================

HORIZONS = (
    "CURRENT",
    "+24H",
    "+48H",
    "+72H",
)

HORIZON_HOURS = {
    "CURRENT": 0,
    "+24H": 24,
    "+48H": 48,
    "+72H": 72,
}

MEMBER1_SIC_KEYS = {
    "CURRENT":
        "current",

    "+24H":
        "forecast_24h",

    "+48H":
        "forecast_48h",

    "+72H":
        "forecast_72h",
}

MEMBER1_UNCERTAINTY_KEYS = {
    "CURRENT":
        None,

    "+24H":
        "uncertainty_24h",

    "+48H":
        "uncertainty_48h",

    "+72H":
        "uncertainty_72h",
}


# ============================================================
# BASIC HELPERS
# ============================================================

def _normalize_id(
    value: Any,
) -> str:

    if value is None:
        return ""

    return str(
        value
    ).strip().upper()


def _safe_float(
    value: Any,
) -> Optional[float]:

    try:
        if value is None:
            return None

        result = float(
            value
        )

        if not np.isfinite(
            result
        ):
            return None

        return result

    except (
        TypeError,
        ValueError,
    ):
        return None


def _first_present(
    mapping: Dict,
    names,
    default=None,
):

    if not isinstance(
        mapping,
        dict,
    ):
        return default

    for name in names:

        if name not in mapping:
            continue

        value = mapping[
            name
        ]

        if value is not None:
            return value

    return default


def _normalize_horizon(
    horizon: str,
) -> str:

    value = str(
        horizon
    ).strip().upper()

    aliases = {
        "CURRENT":
            "CURRENT",

        "NOW":
            "CURRENT",

        "0":
            "CURRENT",

        "0H":
            "CURRENT",

        "+0H":
            "CURRENT",

        "24":
            "+24H",

        "24H":
            "+24H",

        "+24H":
            "+24H",

        "48":
            "+48H",

        "48H":
            "+48H",

        "+48H":
            "+48H",

        "72":
            "+72H",

        "72H":
            "+72H",

        "+72H":
            "+72H",
    }

    if value not in aliases:

        raise ValueError(
            "Unsupported horizon: "
            f"{horizon}"
        )

    return aliases[
        value
    ]


# ============================================================
# MEMBER-1 BUNDLE
# ============================================================

def load_latest_member1_bundle() -> Dict:
    """
    Load PolarGuard's existing latest satellite route bundle.

    Import is intentionally lazy because app.py is a Streamlit
    application and can emit harmless bare-mode warnings when
    imported from a normal Python terminal.
    """

    from app import (
        get_latest_satellite_route_bundle,
    )

    bundle = (
        get_latest_satellite_route_bundle()
    )

    if not isinstance(
        bundle,
        dict,
    ):
        raise TypeError(
            "get_latest_satellite_route_bundle() "
            "did not return a dictionary."
        )

    required = [
        "current",
        "forecast_24h",
        "forecast_48h",
        "forecast_72h",
    ]

    missing = [
        key
        for key in required
        if key not in bundle
    ]

    if missing:

        raise KeyError(
            "Member-1 operational bundle is missing: "
            + ", ".join(
                missing
            )
        )

    return bundle


# ============================================================
# CURRENT ICEBERG OBSERVATIONS
# ============================================================

def get_latest_operational_icebergs() -> List[Dict]:
    """
    Return one latest genuine stored operational observation
    for every current iceberg.

    No interpolation or synthesis is performed.
    """

    dataframe = (
        load_operational_history()
    )

    if dataframe.empty:
        return []

    dataframe = dataframe.copy()

    dataframe[
        "iceberg_id"
    ] = (
        dataframe[
            "iceberg_id"
        ]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    dataframe[
        "observation_date"
    ] = pd.to_datetime(
        dataframe[
            "observation_date"
        ],
        errors="coerce",
    )

    dataframe = dataframe.dropna(
        subset=[
            "iceberg_id",
            "observation_date",
            "latitude",
            "longitude",
        ]
    )

    dataframe = (
        dataframe.sort_values(
            [
                "iceberg_id",
                "observation_date",
            ]
        )
        .groupby(
            "iceberg_id",
            as_index=False,
        )
        .tail(1)
        .sort_values(
            "iceberg_id"
        )
        .reset_index(
            drop=True
        )
    )

    results = []

    for _, row in (
        dataframe.iterrows()
    ):

        latitude = _safe_float(
            row[
                "latitude"
            ]
        )

        longitude = _safe_float(
            row[
                "longitude"
            ]
        )

        if (
            latitude is None
            or longitude is None
        ):
            continue

        observation_date = (
            pd.Timestamp(
                row[
                    "observation_date"
                ]
            )
        )

        results.append(
            {
                "iceberg_id":
                    _normalize_id(
                        row[
                            "iceberg_id"
                        ]
                    ),

                "latitude":
                    latitude,

                "longitude":
                    longitude,

                "observation_date":
                    observation_date.strftime(
                        "%Y-%m-%d"
                    ),

                "position_type":
                    "CURRENT_OBSERVATION",

                "trajectory_source":
                    "GENUINE_OBSERVATION",

                "horizon":
                    "CURRENT",

                "horizon_hours":
                    0,
            }
        )

    return results


# ============================================================
# MEMBER-2 OPERATIONAL READINESS
# ============================================================

def get_operational_member2_readiness() -> List[Dict]:
    """
    Return operational Member-2 readiness for all current
    icebergs.
    """

    dataframe = (
        assess_operational_icebergs()
    )

    if dataframe.empty:
        return []

    results = []

    for _, row in (
        dataframe.iterrows()
    ):

        results.append(
            {
                "iceberg_id":
                    _normalize_id(
                        row[
                            "iceberg_id"
                        ]
                    ),

                "latest_operational_date":
                    (
                        str(
                            row[
                                "latest_operational_date"
                            ]
                        )
                        if pd.notna(
                            row[
                                "latest_operational_date"
                            ]
                        )
                        else None
                    ),

                "operational_member2_ready":
                    bool(
                        row[
                            "operational_member2_ready"
                        ]
                    ),

                "missing_date":
                    (
                        str(
                            row[
                                "missing_date"
                            ]
                        )
                        if pd.notna(
                            row[
                                "missing_date"
                            ]
                        )
                        else None
                    ),

                "reason":
                    str(
                        row[
                            "reason"
                        ]
                    ),
            }
        )

    return results


# ============================================================
# MEMBER-2 OPERATIONAL FORECASTS
# ============================================================

def build_operational_member2_forecasts(
    readiness: Optional[List[Dict]] = None,
) -> Dict:
    """
    Run frozen Member 2 only for operationally-ready icebergs.

    With the current observation store it is valid for this
    dictionary to contain zero forecasts.
    """

    if readiness is None:

        readiness = (
            get_operational_member2_readiness()
        )

    ready_icebergs = [
        item[
            "iceberg_id"
        ]
        for item in readiness
        if item.get(
            "operational_member2_ready",
            False,
        )
    ]

    forecasts = {}

    failures = {}

    for iceberg_id in (
        ready_icebergs
    ):

        try:

            result = (
                forecast_operational_iceberg(
                    iceberg_id
                )
            )

            forecasts[
                iceberg_id
            ] = result

        except Exception as exc:

            failures[
                iceberg_id
            ] = {
                "error_type":
                    type(
                        exc
                    ).__name__,

                "error":
                    str(
                        exc
                    ),
            }

    return {
        "ready_iceberg_ids":
            ready_icebergs,

        "ready_count":
            int(
                len(
                    ready_icebergs
                )
            ),

        "forecasts":
            forecasts,

        "forecast_success_count":
            int(
                len(
                    forecasts
                )
            ),

        "failures":
            failures,

        "forecast_failure_count":
            int(
                len(
                    failures
                )
            ),
    }


# ============================================================
# HORIZON-MATCHED ICEBERG POSITIONS
# ============================================================

def build_horizon_iceberg_positions(
    *,
    current_positions: List[Dict],
    member2_forecasts: Dict,
) -> Dict:
    """
    Build iceberg hazard positions for each time horizon.

    CURRENT
    -------
    All genuine latest observations.

    FUTURE
    ------
    Only genuine Member-2 predictions from operationally-ready
    icebergs.

    Current positions are NEVER copied forward to simulate
    future positions.
    """

    horizons = {
        "CURRENT":
            list(
                current_positions
            ),

        "+24H":
            [],

        "+48H":
            [],

        "+72H":
            [],
    }

    forecasts = member2_forecasts.get(
        "forecasts",
        {},
    )

    for iceberg_id, result in (
        forecasts.items()
    ):

        if not isinstance(
            result,
            dict,
        ):
            continue

        positions = result.get(
            "positions",
            {},
        )

        if not isinstance(
            positions,
            dict,
        ):
            continue

        for horizon in (
            "+24H",
            "+48H",
            "+72H",
        ):

            item = positions.get(
                horizon
            )

            if not isinstance(
                item,
                dict,
            ):
                continue

            latitude = _safe_float(
                item.get(
                    "latitude"
                )
            )

            longitude = _safe_float(
                item.get(
                    "longitude"
                )
            )

            if (
                latitude is None
                or longitude is None
            ):
                continue

            hazard = {
                "iceberg_id":
                    _normalize_id(
                        iceberg_id
                    ),

                "latitude":
                    latitude,

                "longitude":
                    longitude,

                "horizon":
                    horizon,

                "horizon_hours":
                    HORIZON_HOURS[
                        horizon
                    ],

                "position_type":
                    "MEMBER2_PREDICTED",

                "trajectory_source":
                    "FROZEN_MEMBER2",

                "forecast_date":
                    item.get(
                        "forecast_date"
                    ),

                "initialization_date":
                    item.get(
                        "initialization_date"
                    ),
            }

            if (
                "predicted_displacement_km"
                in item
            ):
                hazard[
                    "predicted_displacement_km"
                ] = item[
                    "predicted_displacement_km"
                ]

            horizons[
                horizon
            ].append(
                hazard
            )

    return horizons


# ============================================================
# TRAJECTORY COVERAGE
# ============================================================

def build_trajectory_coverage(
    *,
    current_positions: List[Dict],
    readiness: List[Dict],
    horizon_positions: Dict,
) -> Dict:
    """
    Report actual Member-2 coverage rather than implying that
    every current iceberg has a future trajectory.
    """

    current_count = int(
        len(
            current_positions
        )
    )

    ready_count = int(
        sum(
            1
            for item in readiness
            if item.get(
                "operational_member2_ready",
                False,
            )
        )
    )

    future_coverage_percent = (
        (
            ready_count
            / current_count
            * 100.0
        )
        if current_count
        > 0
        else 0.0
    )

    return {
        "current_observed_iceberg_count":
            current_count,

        "operational_member2_ready_count":
            ready_count,

        "current_only_count":
            int(
                current_count
                - ready_count
            ),

        "future_trajectory_coverage_percent":
            float(
                future_coverage_percent
            ),

        "hazard_count_by_horizon": {
            horizon:
                int(
                    len(
                        horizon_positions.get(
                            horizon,
                            [],
                        )
                    )
                )
            for horizon in HORIZONS
        },

        "interpretation":
            (
                "CURRENT uses genuine observed iceberg "
                "positions. Future horizons contain only "
                "icebergs with genuine Member-2 trajectory "
                "availability."
            ),
    }


# ============================================================
# SEA-ICE HORIZON DATA
# ============================================================

def build_sea_ice_horizon_bundle(
    member1_bundle: Dict,
    intelligence: Dict,
) -> Dict:
    """
    Align SIC grids, uncertainty grids and intelligence metrics
    to the four PolarGuard horizons.
    """

    result = {}

    for horizon in HORIZONS:

        sic_key = (
            MEMBER1_SIC_KEYS[
                horizon
            ]
        )

        uncertainty_key = (
            MEMBER1_UNCERTAINTY_KEYS[
                horizon
            ]
        )

        sic = member1_bundle[
            sic_key
        ]

        uncertainty = (
            member1_bundle.get(
                uncertainty_key
            )
            if uncertainty_key
            is not None
            else None
        )

        result[
            horizon
        ] = {
            "horizon":
                horizon,

            "horizon_hours":
                HORIZON_HOURS[
                    horizon
                ],

            "sic":
                sic,

            "uncertainty":
                uncertainty,

            "metrics":
                format_horizon_display_metrics(
                    intelligence,
                    horizon,
                ),

            "intelligence":
                intelligence[
                    horizon
                ],
        }

    return result


# ============================================================
# COMPLETE OPERATIONAL COORDINATOR
# ============================================================

def build_operational_forecast_bundle(
    *,
    member1_bundle: Optional[Dict] = None,
    run_member2: bool = True,
) -> Dict:
    """
    Build the complete operational PolarGuard forecast bundle.

    Parameters
    ----------
    member1_bundle:
        Optional preloaded Member-1 bundle. Supplying it avoids
        importing app.py again.

    run_member2:
        If True, run Member 2 for operationally-ready icebergs.
        If none are ready, no Member-2 model execution occurs.
    """

    # --------------------------------------------------------
    # MEMBER 1
    # --------------------------------------------------------

    if member1_bundle is None:

        member1_bundle = (
            load_latest_member1_bundle()
        )

    sea_ice_intelligence = (
        build_intelligence_from_route_bundle(
            member1_bundle
        )
    )

    sea_ice = (
        build_sea_ice_horizon_bundle(
            member1_bundle,
            sea_ice_intelligence,
        )
    )

    # --------------------------------------------------------
    # CURRENT ICEBERGS
    # --------------------------------------------------------

    current_icebergs = (
        get_latest_operational_icebergs()
    )

    readiness = (
        get_operational_member2_readiness()
    )

    # --------------------------------------------------------
    # MEMBER 2
    # --------------------------------------------------------

    if run_member2:

        member2 = (
            build_operational_member2_forecasts(
                readiness
            )
        )

    else:

        ready_ids = [
            item[
                "iceberg_id"
            ]
            for item in readiness
            if item.get(
                "operational_member2_ready",
                False,
            )
        ]

        member2 = {
            "ready_iceberg_ids":
                ready_ids,

            "ready_count":
                len(
                    ready_ids
                ),

            "forecasts":
                {},

            "forecast_success_count":
                0,

            "failures":
                {},

            "forecast_failure_count":
                0,

            "execution_skipped":
                True,
        }

    # --------------------------------------------------------
    # HORIZON ICEBERGS
    # --------------------------------------------------------

    iceberg_positions = (
        build_horizon_iceberg_positions(
            current_positions=
                current_icebergs,

            member2_forecasts=
                member2,
        )
    )

    coverage = (
        build_trajectory_coverage(
            current_positions=
                current_icebergs,

            readiness=
                readiness,

            horizon_positions=
                iceberg_positions,
        )
    )

    # --------------------------------------------------------
    # SOURCE / GRID METADATA
    # --------------------------------------------------------

    x_coords = _first_present(
        member1_bundle,
        [
            "x",
            "x_coords",
            "grid_x",
        ],
        default=None,
    )

    y_coords = _first_present(
        member1_bundle,
        [
            "y",
            "y_coords",
            "grid_y",
        ],
        default=None,
    )

    current_date = _first_present(
        member1_bundle,
        [
            "current_date",
            "date",
            "source_date",
            "latest_date",
        ],
        default=None,
    )

    # --------------------------------------------------------
    # COMPLETE BUNDLE
    # --------------------------------------------------------

    return {
        "mode":
            "OPERATIONAL",

        "system":
            "PolarGuard",

        "current_date":
            (
                str(
                    current_date
                )
                if current_date
                is not None
                else None
            ),

        "horizons":
            list(
                HORIZONS
            ),

        "grid": {
            "x":
                x_coords,

            "y":
                y_coords,
        },

        "sea_ice":
            sea_ice,

        "sea_ice_intelligence":
            sea_ice_intelligence,

        "current_icebergs":
            current_icebergs,

        "member2_readiness":
            readiness,

        "member2":
            member2,

        "iceberg_positions_by_horizon":
            iceberg_positions,

        "trajectory_coverage":
            coverage,

        "scientific_status": {
            "current_sea_ice":
                "OBSERVED",

            "future_sea_ice":
                "FROZEN_MEMBER1_FORECAST",

            "future_sea_ice_uncertainty":
                "RMSE_BASED",

            "current_icebergs":
                "GENUINE_OBSERVATIONS",

            "future_icebergs":
                (
                    "FROZEN_MEMBER2_WHERE_READY"
                ),

            "synthetic_iceberg_positions":
                False,

            "future_member1_sic_fed_to_member2":
                False,
        },
    }


# ============================================================
# HORIZON ACCESSOR
# ============================================================

def get_operational_horizon(
    bundle: Dict,
    horizon: str,
) -> Dict:
    """
    Return the complete operational data required by the UI or
    navigation service for one horizon.
    """

    horizon = _normalize_horizon(
        horizon
    )

    sea_ice = bundle[
        "sea_ice"
    ][
        horizon
    ]

    icebergs = bundle[
        "iceberg_positions_by_horizon"
    ].get(
        horizon,
        [],
    )

    return {
        "horizon":
            horizon,

        "horizon_hours":
            HORIZON_HOURS[
                horizon
            ],

        "sic":
            sea_ice[
                "sic"
            ],

        "uncertainty":
            sea_ice[
                "uncertainty"
            ],

        "sea_ice_metrics":
            sea_ice[
                "metrics"
            ],

        "iceberg_positions":
            icebergs,

        "iceberg_hazard_count":
            int(
                len(
                    icebergs
                )
            ),

        "trajectory_coverage":
            bundle[
                "trajectory_coverage"
            ],
    }


# ============================================================
# TERMINAL SUMMARY
# ============================================================

def print_operational_summary(
    bundle: Dict,
):
    """
    Compact terminal summary for validation.
    """

    print()
    print("=" * 78)
    print(
        "POLARGUARD - COMPLETE OPERATIONAL FORECAST"
    )
    print("=" * 78)

    print()
    print(
        f"Current sea-ice date: "
        f"{bundle.get('current_date')}"
    )

    coverage = bundle[
        "trajectory_coverage"
    ]

    print()
    print(
        "ICEBERG COVERAGE"
    )
    print("-" * 78)

    print(
        "Current observed icebergs: "
        f"{coverage['current_observed_iceberg_count']}"
    )

    print(
        "Member-2 ready icebergs: "
        f"{coverage['operational_member2_ready_count']}"
    )

    print(
        "Current-only icebergs: "
        f"{coverage['current_only_count']}"
    )

    print(
        "Future trajectory coverage: "
        f"{coverage['future_trajectory_coverage_percent']:.1f}%"
    )

    print()
    print(
        "HORIZON STATUS"
    )
    print("-" * 78)

    for horizon in HORIZONS:

        item = (
            get_operational_horizon(
                bundle,
                horizon,
            )
        )

        metrics = item[
            "sea_ice_metrics"
        ]

        print()
        print(
            horizon
        )

        print(
            f"  Mean SIC: "
            f"{metrics['mean_sic']}"
        )

        print(
            f"  Ice-covered grid: "
            f"{metrics['ice_covered_grid']}"
        )

        print(
            f"  Uncertainty: "
            f"{metrics['uncertainty']}"
        )

        print(
            f"  Iceberg hazards: "
            f"{item['iceberg_hazard_count']}"
        )

    print()
    print(
        "SCIENTIFIC SAFETY"
    )
    print("-" * 78)

    print(
        "Synthetic iceberg positions: NO"
    )

    print(
        "Future Member-1 SIC fed to Member 2: NO"
    )

    print(
        "Future uncertainty type: RMSE-BASED"
    )

    print()
    print("=" * 78)
    print(
        "Operational forecast coordinator: READY"
    )
    print("=" * 78)
    print()


# ============================================================
# SELF / OPERATIONAL TEST
# ============================================================

def main():

    bundle = (
        build_operational_forecast_bundle()
    )

    print_operational_summary(
        bundle
    )


if __name__ == "__main__":
    main()