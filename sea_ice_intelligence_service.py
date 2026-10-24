"""
PolarGuard - Sea-Ice Intelligence Service
------------------------------------------

Converts Member-1 sea-ice grids into UI/navigation-ready
intelligence for:

    CURRENT
    +24H
    +48H
    +72H

Outputs include:
- Mean sea-ice concentration (%)
- Maximum sea-ice concentration (%)
- Ice-covered grid fraction (%), using SIC >= 15%
- Valid grid-cell count
- RMSE-based uncertainty for forecast horizons
- Horizon metadata

Scientific rules
----------------
- Statistics are calculated from the actual SIC grid.
- No hard-coded SIC percentages are used.
- CURRENT is an observation, so model forecast uncertainty is
  not attached to CURRENT.
- Future uncertainty is RMSE-based uncertainty, NOT a
  confidence interval.
- SIC values are expected on the 0-1 fractional scale.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np


# ============================================================
# CONFIGURATION
# ============================================================

ICE_COVERED_SIC_THRESHOLD = 0.15

SUPPORTED_HORIZONS = (
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


# ============================================================
# HELPERS
# ============================================================

def _to_numpy(
    value: Any,
) -> np.ndarray:
    """
    Convert numpy/xarray-like data into a float numpy array.
    """

    if value is None:
        return np.asarray(
            [],
            dtype=float,
        )

    if hasattr(
        value,
        "values",
    ):
        value = value.values

    return np.asarray(
        value,
        dtype=float,
    )


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
    """
    Return the first non-None value found in a dictionary
    from a sequence of possible key names.
    """

    if not isinstance(mapping, dict):
        return default

    for name in names:
        if name in mapping:
            value = mapping[name]

            if value is not None:
                return value

    return default


def _normalize_horizon(
    horizon: str,
) -> str:
    """
    Normalize common horizon labels to the PolarGuard format.
    """

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

        "FORECAST_24H":
            "+24H",

        "48":
            "+48H",

        "48H":
            "+48H",

        "+48H":
            "+48H",

        "FORECAST_48H":
            "+48H",

        "72":
            "+72H",

        "72H":
            "+72H",

        "+72H":
            "+72H",

        "FORECAST_72H":
            "+72H",
    }

    if value not in aliases:
        raise ValueError(
            "Unsupported sea-ice horizon: "
            f"{horizon}. "
            "Expected CURRENT, +24H, +48H or +72H."
        )

    return aliases[
        value
    ]


# ============================================================
# SIC GRID VALIDATION
# ============================================================

def prepare_sic_grid(
    sic: Any,
) -> np.ndarray:
    """
    Prepare a SIC grid for statistics.

    Invalid/non-finite values become NaN.

    Small numerical excursions outside 0-1 are clipped to the
    physical SIC range.
    """

    grid = _to_numpy(
        sic
    ).copy()

    if grid.size == 0:
        raise ValueError(
            "Sea-ice concentration grid is empty."
        )

    grid[
        ~np.isfinite(
            grid
        )
    ] = np.nan

    finite = np.isfinite(
        grid
    )

    if not np.any(
        finite
    ):
        raise ValueError(
            "Sea-ice concentration grid contains no "
            "finite values."
        )

    grid[
        finite
    ] = np.clip(
        grid[
            finite
        ],
        0.0,
        1.0,
    )

    return grid


# ============================================================
# SIC STATISTICS
# ============================================================

def calculate_sic_statistics(
    sic: Any,
    *,
    ice_threshold: float = ICE_COVERED_SIC_THRESHOLD,
) -> Dict:
    """
    Calculate statistics from one actual SIC grid.

    Mean SIC %
    ----------
    Average sea-ice concentration across valid grid cells.

    Ice-covered grid %
    ------------------
    Percentage of valid grid cells with SIC >= threshold.

    This is a grid-cell fraction and should not be described
    as physical Antarctic sea-ice area.
    """

    grid = prepare_sic_grid(
        sic
    )

    valid_mask = np.isfinite(
        grid
    )

    valid_values = grid[
        valid_mask
    ]

    valid_count = int(
        valid_values.size
    )

    if valid_count == 0:
        raise ValueError(
            "No valid SIC cells are available."
        )

    threshold = float(
        ice_threshold
    )

    if not (
        0.0
        <= threshold
        <= 1.0
    ):
        raise ValueError(
            "ice_threshold must be between 0 and 1."
        )

    mean_sic = float(
        np.mean(
            valid_values
        )
    )

    maximum_sic = float(
        np.max(
            valid_values
        )
    )

    minimum_sic = float(
        np.min(
            valid_values
        )
    )

    ice_covered_count = int(
        np.count_nonzero(
            valid_values
            >= threshold
        )
    )

    ice_covered_grid_fraction = (
        ice_covered_count
        / valid_count
    )

    return {
        "mean_sic":
            mean_sic,

        "mean_sic_percent":
            mean_sic
            * 100.0,

        "maximum_sic":
            maximum_sic,

        "maximum_sic_percent":
            maximum_sic
            * 100.0,

        "minimum_sic":
            minimum_sic,

        "minimum_sic_percent":
            minimum_sic
            * 100.0,

        "ice_threshold":
            threshold,

        "ice_threshold_percent":
            threshold
            * 100.0,

        "ice_covered_grid_fraction":
            float(
                ice_covered_grid_fraction
            ),

        "ice_covered_grid_percent":
            float(
                ice_covered_grid_fraction
                * 100.0
            ),

        "ice_covered_grid_cell_count":
            ice_covered_count,

        "valid_grid_cell_count":
            valid_count,

        "total_grid_cell_count":
            int(
                grid.size
            ),

        "invalid_grid_cell_count":
            int(
                grid.size
                - valid_count
            ),
    }


# ============================================================
# UNCERTAINTY STATISTICS
# ============================================================

def calculate_uncertainty_statistics(
    uncertainty: Any,
) -> Optional[Dict]:
    """
    Summarize a Member-1 RMSE-based uncertainty grid.

    The values are expected on the SIC 0-1 scale.

    Returned percentage values are percentage points of SIC.

    This is NOT a calibrated confidence interval.
    """

    if uncertainty is None:
        return None

    grid = _to_numpy(
        uncertainty
    )

    if grid.size == 0:
        return None

    valid = (
        np.isfinite(
            grid
        )
        & (
            grid
            >= 0.0
        )
    )

    if not np.any(
        valid
    ):
        return None

    values = grid[
        valid
    ]

    mean_rmse = float(
        np.mean(
            values
        )
    )

    median_rmse = float(
        np.median(
            values
        )
    )

    maximum_rmse = float(
        np.max(
            values
        )
    )

    return {
        "type":
            "RMSE_BASED",

        "label":
            "RMSE-based uncertainty",

        "is_confidence_interval":
            False,

        "mean_rmse_sic":
            mean_rmse,

        "mean_rmse_percentage_points":
            mean_rmse
            * 100.0,

        "median_rmse_sic":
            median_rmse,

        "median_rmse_percentage_points":
            median_rmse
            * 100.0,

        "maximum_rmse_sic":
            maximum_rmse,

        "maximum_rmse_percentage_points":
            maximum_rmse
            * 100.0,

        "valid_uncertainty_cell_count":
            int(
                values.size
            ),
    }


# ============================================================
# ONE-HORIZON INTELLIGENCE
# ============================================================

def build_horizon_intelligence(
    *,
    horizon: str,
    sic: Any,
    uncertainty: Any = None,
    source_date: Any = None,
) -> Dict:
    """
    Build UI-ready intelligence for one horizon.
    """

    horizon = _normalize_horizon(
        horizon
    )

    statistics = (
        calculate_sic_statistics(
            sic
        )
    )

    if horizon == "CURRENT":
        uncertainty_statistics = None
        uncertainty_status = (
            "OBSERVED"
        )

    else:
        uncertainty_statistics = (
            calculate_uncertainty_statistics(
                uncertainty
            )
        )

        uncertainty_status = (
            "RMSE_BASED"
            if uncertainty_statistics
            is not None
            else
            "UNAVAILABLE"
        )

    return {
        "horizon":
            horizon,

        "horizon_hours":
            HORIZON_HOURS[
                horizon
            ],

        "source_date":
            (
                str(
                    source_date
                )
                if source_date
                is not None
                else None
            ),

        "statistics":
            statistics,

        "mean_sic_percent":
            statistics[
                "mean_sic_percent"
            ],

        "maximum_sic_percent":
            statistics[
                "maximum_sic_percent"
            ],

        "ice_covered_grid_percent":
            statistics[
                "ice_covered_grid_percent"
            ],

        "ice_threshold_percent":
            statistics[
                "ice_threshold_percent"
            ],

        "uncertainty_status":
            uncertainty_status,

        "uncertainty":
            uncertainty_statistics,
    }


# ============================================================
# COMPLETE 4-HORIZON INTELLIGENCE
# ============================================================

def build_sea_ice_intelligence(
    *,
    current_sic: Any,
    forecast_24h: Any,
    forecast_48h: Any,
    forecast_72h: Any,
    uncertainty_24h: Any = None,
    uncertainty_48h: Any = None,
    uncertainty_72h: Any = None,
    current_date: Any = None,
) -> Dict:
    """
    Build the complete PolarGuard sea-ice intelligence bundle.
    """

    current = build_horizon_intelligence(
        horizon=
            "CURRENT",

        sic=
            current_sic,

        uncertainty=
            None,

        source_date=
            current_date,
    )

    horizon_24 = (
        build_horizon_intelligence(
            horizon=
                "+24H",

            sic=
                forecast_24h,

            uncertainty=
                uncertainty_24h,

            source_date=
                current_date,
        )
    )

    horizon_48 = (
        build_horizon_intelligence(
            horizon=
                "+48H",

            sic=
                forecast_48h,

            uncertainty=
                uncertainty_48h,

            source_date=
                current_date,
        )
    )

    horizon_72 = (
        build_horizon_intelligence(
            horizon=
                "+72H",

            sic=
                forecast_72h,

            uncertainty=
                uncertainty_72h,

            source_date=
                current_date,
        )
    )

    return {
        "CURRENT":
            current,

        "+24H":
            horizon_24,

        "+48H":
            horizon_48,

        "+72H":
            horizon_72,

        "metadata": {
            "ice_covered_grid_definition":
                (
                    "Percentage of valid grid cells "
                    "with SIC >= 15%."
                ),

            "mean_sic_definition":
                (
                    "Mean concentration across valid "
                    "SIC grid cells."
                ),

            "uncertainty_definition":
                (
                    "Forecast uncertainty is summarized "
                    "from the Member-1 RMSE-based "
                    "uncertainty grid. It is not a "
                    "confidence interval."
                ),

            "sic_scale":
                "0-1 internally; percentages in UI",

            "horizons":
                list(
                    SUPPORTED_HORIZONS
                ),
        },
    }


# ============================================================
# EXISTING MEMBER-1 BUNDLE ADAPTER
# ============================================================

def build_intelligence_from_route_bundle(
    bundle: Dict,
) -> Dict:
    """
    Adapter for the existing PolarGuard Member-1 route bundle.

    Expected SIC keys:
        current
        forecast_24h
        forecast_48h
        forecast_72h

    Expected uncertainty keys:
        uncertainty_24h
        uncertainty_48h
        uncertainty_72h

    A few safe aliases are supported.
    """

    if not isinstance(
        bundle,
        dict,
    ):
        raise TypeError(
            "Member-1 bundle must be a dictionary."
        )

    current_sic = _first_present(
        bundle,
        [
            "current",
            "current_sic",
            "sic_current",
        ],
    )

    forecast_24h = _first_present(
        bundle,
        [
            "forecast_24h",
            "sic_24h",
            "forecast24",
        ],
    )

    forecast_48h = _first_present(
        bundle,
        [
            "forecast_48h",
            "sic_48h",
            "forecast48",
        ],
    )

    forecast_72h = _first_present(
        bundle,
        [
            "forecast_72h",
            "sic_72h",
            "forecast72",
        ],
    )

    missing = []

    if current_sic is None:
        missing.append(
            "current"
        )

    if forecast_24h is None:
        missing.append(
            "forecast_24h"
        )

    if forecast_48h is None:
        missing.append(
            "forecast_48h"
        )

    if forecast_72h is None:
        missing.append(
            "forecast_72h"
        )

    if missing:
        raise KeyError(
            "Member-1 route bundle is missing SIC fields: "
            + ", ".join(
                missing
            )
        )

    uncertainty_24h = _first_present(
        bundle,
        [
            "uncertainty_24h",
            "uncertainty_24",
            "rmse_24h",
        ],
    )

    uncertainty_48h = _first_present(
        bundle,
        [
            "uncertainty_48h",
            "uncertainty_48",
            "rmse_48h",
        ],
    )

    uncertainty_72h = _first_present(
        bundle,
        [
            "uncertainty_72h",
            "uncertainty_72",
            "rmse_72h",
        ],
    )

    current_date = _first_present(
        bundle,
        [
            "current_date",
            "date",
            "source_date",
            "latest_date",
        ],
        default=None,
    )

    return build_sea_ice_intelligence(
        current_sic=
            current_sic,

        forecast_24h=
            forecast_24h,

        forecast_48h=
            forecast_48h,

        forecast_72h=
            forecast_72h,

        uncertainty_24h=
            uncertainty_24h,

        uncertainty_48h=
            uncertainty_48h,

        uncertainty_72h=
            uncertainty_72h,

        current_date=
            current_date,
    )


# ============================================================
# UI HELPERS
# ============================================================

def get_horizon_display_metrics(
    intelligence: Dict,
    horizon: str,
) -> Dict:
    """
    Return compact metrics suitable for Streamlit cards.
    """

    horizon = _normalize_horizon(
        horizon
    )

    if horizon not in intelligence:
        raise KeyError(
            f"Horizon {horizon} is not present "
            "in the intelligence bundle."
        )

    item = intelligence[
        horizon
    ]

    uncertainty = item.get(
        "uncertainty"
    )

    return {
        "horizon":
            horizon,

        "mean_sic_percent":
            float(
                item[
                    "mean_sic_percent"
                ]
            ),

        "maximum_sic_percent":
            float(
                item[
                    "maximum_sic_percent"
                ]
            ),

        "ice_covered_grid_percent":
            float(
                item[
                    "ice_covered_grid_percent"
                ]
            ),

        "ice_threshold_percent":
            float(
                item[
                    "ice_threshold_percent"
                ]
            ),

        "rmse_uncertainty_percentage_points":
            (
                float(
                    uncertainty[
                        "mean_rmse_percentage_points"
                    ]
                )
                if uncertainty
                is not None
                else None
            ),

        "uncertainty_status":
            item[
                "uncertainty_status"
            ],
    }


def format_horizon_display_metrics(
    intelligence: Dict,
    horizon: str,
) -> Dict:
    """
    Return formatted strings for the UI.
    """

    metrics = (
        get_horizon_display_metrics(
            intelligence,
            horizon,
        )
    )

    uncertainty = metrics[
        "rmse_uncertainty_percentage_points"
    ]

    return {
        "horizon":
            metrics[
                "horizon"
            ],

        "mean_sic":
            (
                f"{metrics['mean_sic_percent']:.1f}%"
            ),

        "maximum_sic":
            (
                f"{metrics['maximum_sic_percent']:.1f}%"
            ),

        "ice_covered_grid":
            (
                f"{metrics['ice_covered_grid_percent']:.1f}%"
            ),

        "ice_covered_grid_label":
            (
                "Grid cells with SIC ≥ "
                f"{metrics['ice_threshold_percent']:.0f}%"
            ),

        "uncertainty":
            (
                "Observed"
                if metrics[
                    "horizon"
                ]
                == "CURRENT"
                else (
                    f"{uncertainty:.2f} pp RMSE"
                    if uncertainty
                    is not None
                    else
                    "Unavailable"
                )
            ),
    }


# ============================================================
# SELF TEST
# ============================================================

def _self_test():
    """
    Small synthetic unit test.

    This tests only the intelligence calculations.
    It does NOT test Member 1 itself.
    """

    current = np.asarray(
        [
            [0.00, 0.10, 0.20],
            [0.30, 0.50, 1.00],
            [np.nan, 0.00, 0.40],
        ],
        dtype=float,
    )

    forecast_24h = np.clip(
        current
        + 0.02,
        0.0,
        1.0,
    )

    forecast_48h = np.clip(
        current
        + 0.04,
        0.0,
        1.0,
    )

    forecast_72h = np.clip(
        current
        + 0.06,
        0.0,
        1.0,
    )

    uncertainty_24h = np.full(
        current.shape,
        0.02,
    )

    uncertainty_48h = np.full(
        current.shape,
        0.03,
    )

    uncertainty_72h = np.full(
        current.shape,
        0.04,
    )

    intelligence = (
        build_sea_ice_intelligence(
            current_sic=
                current,

            forecast_24h=
                forecast_24h,

            forecast_48h=
                forecast_48h,

            forecast_72h=
                forecast_72h,

            uncertainty_24h=
                uncertainty_24h,

            uncertainty_48h=
                uncertainty_48h,

            uncertainty_72h=
                uncertainty_72h,

            current_date=
                "SELF_TEST",
        )
    )

    print()
    print("=" * 76)
    print(
        "POLARGUARD - SEA-ICE INTELLIGENCE SERVICE"
    )
    print("=" * 76)

    for horizon in (
        SUPPORTED_HORIZONS
    ):

        metrics = (
            format_horizon_display_metrics(
                intelligence,
                horizon,
            )
        )

        print()
        print(
            horizon
        )

        print(
            f"  Mean SIC: "
            f"{metrics['mean_sic']}"
        )

        print(
            f"  Maximum SIC: "
            f"{metrics['maximum_sic']}"
        )

        print(
            f"  Ice-covered grid: "
            f"{metrics['ice_covered_grid']}"
        )

        print(
            f"  Uncertainty: "
            f"{metrics['uncertainty']}"
        )

    assert (
        intelligence[
            "CURRENT"
        ][
            "uncertainty"
        ]
        is None
    )

    assert (
        intelligence[
            "+24H"
        ][
            "uncertainty"
        ][
            "type"
        ]
        == "RMSE_BASED"
    )

    assert (
        set(
            key
            for key
            in intelligence.keys()
            if key
            != "metadata"
        )
        == {
            "CURRENT",
            "+24H",
            "+48H",
            "+72H",
        }
    )

    print()
    print("=" * 76)
    print(
        "Sea-ice intelligence service: READY"
    )
    print("=" * 76)
    print()


if __name__ == "__main__":
    _self_test()