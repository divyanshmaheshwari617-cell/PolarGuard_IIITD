import numpy as np


# ============================================================
# POLARGUARD PROTOTYPE VESSEL PROFILES
# ============================================================

VESSEL_PROFILES = {
    "LOW_ICE_CAPABILITY": {
        "name": "Low Ice Capability",
        "max_sic": 0.30,
        "iceberg_exclusion_risk": 0.60,
        "uncertainty_limit": 0.70,
    },

    "MEDIUM_ICE_CAPABILITY": {
        "name": "Medium Ice Capability",
        "max_sic": 0.55,
        "iceberg_exclusion_risk": 0.75,
        "uncertainty_limit": 0.85,
    },

    "HIGH_ICE_CAPABILITY": {
        "name": "High Ice Capability",
        "max_sic": 0.80,
        "iceberg_exclusion_risk": 0.90,
        "uncertainty_limit": 1.00,
    },
}


def get_vessel_profile(profile_name):
    """
    Return one PolarGuard prototype vessel profile.
    """

    if profile_name not in VESSEL_PROFILES:

        raise ValueError(
            f"Unknown vessel profile: {profile_name}"
        )

    return VESSEL_PROFILES[
        profile_name
    ].copy()


def build_navigation_mask(
    sic,
    iceberg_risk,
    uncertainty_risk,
    blocked_mask=None,
    profile_name="MEDIUM_ICE_CAPABILITY"
):
    """
    Build hard navigation constraints for a vessel.

    A cell becomes blocked if:

    1. SIC exceeds vessel maximum
    2. iceberg risk exceeds exclusion threshold
    3. uncertainty exceeds prototype limit
    4. source grid already marks cell blocked

    IMPORTANT:
    These are prototype decision-support parameters.
    They are not certified vessel-operating limits.
    """

    sic = np.asarray(
        sic,
        dtype=float
    )

    iceberg_risk = np.asarray(
        iceberg_risk,
        dtype=float
    )

    uncertainty_risk = np.asarray(
        uncertainty_risk,
        dtype=float
    )

    if (
        sic.shape != iceberg_risk.shape
        or
        sic.shape != uncertainty_risk.shape
    ):
        raise ValueError(
            "SIC, iceberg risk and uncertainty risk "
            "must have matching shapes."
        )

    profile = get_vessel_profile(
        profile_name
    )

    blocked_by_sic = (
        sic
        >
        profile["max_sic"]
    )

    blocked_by_iceberg = (
        iceberg_risk
        >=
        profile[
            "iceberg_exclusion_risk"
        ]
    )

    blocked_by_uncertainty = (
        uncertainty_risk
        >
        profile[
            "uncertainty_limit"
        ]
    )

    invalid = (
        ~np.isfinite(sic)
        |
        ~np.isfinite(iceberg_risk)
        |
        ~np.isfinite(uncertainty_risk)
    )

    final_blocked = (
        blocked_by_sic
        |
        blocked_by_iceberg
        |
        blocked_by_uncertainty
        |
        invalid
    )

    if blocked_mask is not None:

        blocked_mask = np.asarray(
            blocked_mask,
            dtype=bool
        )

        if blocked_mask.shape != sic.shape:

            raise ValueError(
                "blocked_mask must match SIC shape."
            )

        final_blocked |= (
            blocked_mask
        )

    return {
        "profile":
            profile,

        "blocked_mask":
            final_blocked,

        "blocked_by_sic":
            blocked_by_sic,

        "blocked_by_iceberg":
            blocked_by_iceberg,

        "blocked_by_uncertainty":
            blocked_by_uncertainty,
    }


def apply_navigation_constraints(
    routing_cost,
    navigation_mask
):
    """
    Apply hard vessel constraints to routing cost.

    Blocked cells become infinity so A* cannot
    pass through them.
    """

    routing_cost = np.asarray(
        routing_cost,
        dtype=float
    ).copy()

    blocked_mask = np.asarray(
        navigation_mask[
            "blocked_mask"
        ],
        dtype=bool
    )

    if (
        routing_cost.shape
        !=
        blocked_mask.shape
    ):
        raise ValueError(
            "routing_cost and blocked mask "
            "must have matching shapes."
        )

    routing_cost[
        blocked_mask
    ] = np.inf

    return routing_cost


def summarize_navigation_constraints(
    navigation_mask
):
    """
    Return statistics describing blocked cells.
    """

    blocked = navigation_mask[
        "blocked_mask"
    ]

    total_cells = (
        blocked.size
    )

    blocked_cells = int(
        np.count_nonzero(
            blocked
        )
    )

    blocked_by_sic = int(
        np.count_nonzero(
            navigation_mask[
                "blocked_by_sic"
            ]
        )
    )

    blocked_by_iceberg = int(
        np.count_nonzero(
            navigation_mask[
                "blocked_by_iceberg"
            ]
        )
    )

    blocked_by_uncertainty = int(
        np.count_nonzero(
            navigation_mask[
                "blocked_by_uncertainty"
            ]
        )
    )

    blocked_percent = (
        100.0
        *
        blocked_cells
        /
        total_cells
    )

    return {
        "total_cells":
            total_cells,

        "blocked_cells":
            blocked_cells,

        "blocked_percent":
            blocked_percent,

        "blocked_by_sic":
            blocked_by_sic,

        "blocked_by_iceberg":
            blocked_by_iceberg,

        "blocked_by_uncertainty":
            blocked_by_uncertainty,
    }