import numpy as np


def classify_hazard_level(value):
    """
    Convert normalized hazard value into a readable level.
    """

    if not np.isfinite(value):
        return "UNKNOWN"

    if value < 0.25:
        return "LOW"

    if value < 0.50:
        return "MODERATE"

    if value < 0.75:
        return "HIGH"

    return "CRITICAL"


def build_hazard_zones(
    sic,
    uncertainty_risk,
    iceberg_risk,
    vessel_max_sic,
    iceberg_exclusion_risk,
):
    """
    Build explainable PolarGuard hazard masks.

    IMPORTANT:
    These are prototype decision-support zones,
    not calibrated collision probabilities.
    """

    sic = np.asarray(
        sic,
        dtype=float
    )

    uncertainty_risk = np.asarray(
        uncertainty_risk,
        dtype=float
    )

    iceberg_risk = np.asarray(
        iceberg_risk,
        dtype=float
    )

    if (
        sic.shape != uncertainty_risk.shape
        or
        sic.shape != iceberg_risk.shape
    ):
        raise ValueError(
            "SIC, uncertainty risk and iceberg risk "
            "must have matching shapes."
        )

    # --------------------------------------------------------
    # SEA-ICE HAZARD
    # --------------------------------------------------------

    sea_ice_warning = (
        np.isfinite(sic)
        &
        (sic >= vessel_max_sic * 0.75)
        &
        (sic < vessel_max_sic)
    )

    sea_ice_blocked = (
        np.isfinite(sic)
        &
        (sic >= vessel_max_sic)
    )

    # --------------------------------------------------------
    # ICEBERG HAZARD
    # --------------------------------------------------------

    iceberg_warning = (
        np.isfinite(iceberg_risk)
        &
        (iceberg_risk >= 0.30)
        &
        (
            iceberg_risk
            <
            iceberg_exclusion_risk
        )
    )

    iceberg_blocked = (
        np.isfinite(iceberg_risk)
        &
        (
            iceberg_risk
            >=
            iceberg_exclusion_risk
        )
    )

    # --------------------------------------------------------
    # UNCERTAINTY HAZARD
    # --------------------------------------------------------

    uncertainty_warning = (
        np.isfinite(uncertainty_risk)
        &
        (uncertainty_risk >= 0.50)
    )

    uncertainty_high = (
        np.isfinite(uncertainty_risk)
        &
        (uncertainty_risk >= 0.75)
    )

    # --------------------------------------------------------
    # COMBINED HAZARD SCORE
    # --------------------------------------------------------

    sic_normalized = np.clip(
        sic,
        0.0,
        1.0
    )

    combined_hazard = np.maximum.reduce(
        [
            sic_normalized,
            iceberg_risk,
            uncertainty_risk,
        ]
    )

    invalid = (
        ~np.isfinite(sic)
    )

    combined_hazard[
        invalid
    ] = np.nan

    critical_zone = (
        sea_ice_blocked
        |
        iceberg_blocked
        |
        uncertainty_high
    )

    warning_zone = (
        (
            sea_ice_warning
            |
            iceberg_warning
            |
            uncertainty_warning
        )
        &
        ~critical_zone
    )

    return {
        "sea_ice_warning":
            sea_ice_warning,

        "sea_ice_blocked":
            sea_ice_blocked,

        "iceberg_warning":
            iceberg_warning,

        "iceberg_blocked":
            iceberg_blocked,

        "uncertainty_warning":
            uncertainty_warning,

        "uncertainty_high":
            uncertainty_high,

        "warning_zone":
            warning_zone,

        "critical_zone":
            critical_zone,

        "combined_hazard":
            combined_hazard,
    }


def analyze_route_hazards(
    path_indices,
    sic,
    uncertainty_risk,
    iceberg_risk,
    combined_hazard,
):
    """
    Analyze environmental conditions encountered
    along a calculated route.
    """

    if not path_indices:

        return {
            "route_cells": 0,
            "max_sic": np.nan,
            "max_uncertainty_risk": np.nan,
            "max_iceberg_risk": np.nan,
            "max_combined_hazard": np.nan,
            "hazard_level": "NO ROUTE",
        }

    sic_values = []
    uncertainty_values = []
    iceberg_values = []
    combined_values = []

    for row, col in path_indices:

        sic_values.append(
            sic[row, col]
        )

        uncertainty_values.append(
            uncertainty_risk[
                row,
                col
            ]
        )

        iceberg_values.append(
            iceberg_risk[
                row,
                col
            ]
        )

        combined_values.append(
            combined_hazard[
                row,
                col
            ]
        )

    max_sic = float(
        np.nanmax(
            sic_values
        )
    )

    max_uncertainty = float(
        np.nanmax(
            uncertainty_values
        )
    )

    max_iceberg = float(
        np.nanmax(
            iceberg_values
        )
    )

    max_combined = float(
        np.nanmax(
            combined_values
        )
    )

    return {
        "route_cells":
            len(path_indices),

        "max_sic":
            max_sic,

        "max_uncertainty_risk":
            max_uncertainty,

        "max_iceberg_risk":
            max_iceberg,

        "max_combined_hazard":
            max_combined,

        "hazard_level":
            classify_hazard_level(
                max_combined
            ),
    }


def generate_route_alerts(
    route_hazard_summary,
    vessel_max_sic,
    iceberg_exclusion_risk,
):
    """
    Generate human-readable route alerts.
    """

    alerts = []

    if (
        route_hazard_summary[
            "route_cells"
        ]
        == 0
    ):

        alerts.append(
            {
                "severity": "CRITICAL",
                "message": "No navigable route is currently available."
            }
        )

        return alerts

    max_sic = route_hazard_summary[
        "max_sic"
    ]

    max_iceberg = route_hazard_summary[
        "max_iceberg_risk"
    ]

    max_uncertainty = route_hazard_summary[
        "max_uncertainty_risk"
    ]

    # --------------------------------------------------------
    # SEA ICE
    # --------------------------------------------------------

    if max_sic >= vessel_max_sic:

        alerts.append(
            {
                "severity": "CRITICAL",
                "message":
                    "Route reaches or exceeds the selected "
                    "vessel sea-ice limit."
            }
        )

    elif (
        max_sic
        >=
        vessel_max_sic * 0.75
    ):

        alerts.append(
            {
                "severity": "WARNING",
                "message":
                    "Route approaches the selected vessel "
                    "sea-ice limit."
            }
        )

    # --------------------------------------------------------
    # ICEBERG
    # --------------------------------------------------------

    if (
        max_iceberg
        >=
        iceberg_exclusion_risk
    ):

        alerts.append(
            {
                "severity": "CRITICAL",
                "message":
                    "Route intersects the selected iceberg "
                    "exclusion threshold."
            }
        )

    elif max_iceberg >= 0.30:

        alerts.append(
            {
                "severity": "WARNING",
                "message":
                    "Route passes through an iceberg "
                    "influence region."
            }
        )

    # --------------------------------------------------------
    # UNCERTAINTY
    # --------------------------------------------------------

    if max_uncertainty >= 0.75:

        alerts.append(
            {
                "severity": "WARNING",
                "message":
                    "Part of the route crosses a region with "
                    "high historical forecast-error uncertainty."
            }
        )

    elif max_uncertainty >= 0.50:

        alerts.append(
            {
                "severity": "INFO",
                "message":
                    "Moderate forecast uncertainty exists "
                    "along part of the route."
            }
        )

    if not alerts:

        alerts.append(
            {
                "severity": "SAFE",
                "message":
                    "No major forecast hazard threshold is "
                    "encountered along the recommended route."
            }
        )

    return alerts


def summarize_hazard_grid(
    hazard_result
):
    """
    Summarize complete hazard grid.
    """

    critical = hazard_result[
        "critical_zone"
    ]

    warning = hazard_result[
        "warning_zone"
    ]

    total_cells = (
        critical.size
    )

    critical_cells = int(
        np.count_nonzero(
            critical
        )
    )

    warning_cells = int(
        np.count_nonzero(
            warning
        )
    )

    return {
        "total_cells":
            total_cells,

        "critical_cells":
            critical_cells,

        "warning_cells":
            warning_cells,

        "critical_percent":
            100.0
            *
            critical_cells
            /
            total_cells,

        "warning_percent":
            100.0
            *
            warning_cells
            /
            total_cells,
    }