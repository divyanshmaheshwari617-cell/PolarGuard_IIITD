from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent.parent

if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

import numpy as np
import pandas as pd
import xarray as xr

from pyproj import Transformer

from sea_ice_service import (
    predict_sea_ice,
    load_uncertainty,
)

from risk_engine import (
    build_risk_grid,
)

from vessel_constraints import (
    build_navigation_mask,
)

from routing_engine import (
    nearest_grid_cell,
)


# ============================================================
# PATHS
# ============================================================

SEA_ICE_HISTORY_FILE = (
    BASE
    / "data"
    / "processed"
    / "sea_ice_2019_2025.nc"
)

TEST_FILE = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps124_validation"
    / "selected_cases"
    / "ps124_selected_case_definitions.csv"
)

MEMBER2_FILE = (
    BASE
    / "iceberg"
    / "data"
    / "processed"
    / "iceberg_features_environment_ml_ready_2019_2025.csv"
)


# ============================================================
# SETTINGS
# ============================================================

VESSEL_PROFILE = "MEDIUM_ICE_CAPABILITY"

SAFETY_RADIUS_KM = 10.0
INFLUENCE_RADIUS_KM = 30.0


# ============================================================
# MEMBER 1 HISTORICAL BUNDLE
# ============================================================

def load_member1_bundle(
    initialization_date,
):
    """
    Load historical sea-ice state and generate the
    24h / 48h / 72h Member-1 forecasts.
    """

    ds = xr.open_dataarray(
        SEA_ICE_HISTORY_FILE
    )

    target_date = np.datetime64(
        initialization_date,
        "D",
    )

    dates = ds.time.values.astype(
        "datetime64[D]"
    )

    matches = np.where(
        dates == target_date
    )[0]

    if len(matches) == 0:

        raise RuntimeError(
            f"No sea-ice history for "
            f"{initialization_date}"
        )

    idx = int(
        matches[0]
    )

    if idx < 3:

        raise RuntimeError(
            "At least three prior sea-ice "
            "maps are required."
        )

    current = np.asarray(
        ds.values[idx],
        dtype=np.float32,
    )

    lag1 = np.asarray(
        ds.values[idx - 1],
        dtype=np.float32,
    )

    lag2 = np.asarray(
        ds.values[idx - 2],
        dtype=np.float32,
    )

    lag3 = np.asarray(
        ds.values[idx - 3],
        dtype=np.float32,
    )

    x = np.asarray(
        ds.x.values
    )

    y = np.asarray(
        ds.y.values
    )

    forecasts = predict_sea_ice(
        current=current,
        lag1=lag1,
        lag2=lag2,
        lag3=lag3,
        x_coords=x,
        y_coords=y,
        date=target_date,
    )

    uncertainty = load_uncertainty()

    return {
        "24":
            np.asarray(
                forecasts["24h"]
            ),

        "48":
            np.asarray(
                forecasts["48h"]
            ),

        "72":
            np.asarray(
                forecasts["72h"]
            ),

        "uncertainty_24":
            np.asarray(
                uncertainty["24h"]
            ),

        "uncertainty_48":
            np.asarray(
                uncertainty["48h"]
            ),

        "uncertainty_72":
            np.asarray(
                uncertainty["72h"]
            ),

        "x":
            x,

        "y":
            y,
    }


# ============================================================
# GRID CONVERSION
# ============================================================

def projected_grid_to_latlon(
    x_coords,
    y_coords,
):
    """
    Convert Member-1 EPSG:3412 coordinates to WGS84.
    """

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

    transformer = Transformer.from_crs(
        "EPSG:3412",
        "EPSG:4326",
        always_xy=True,
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
# MEMBER 2 HISTORICAL ICEBERGS
# ============================================================

def load_member2_rows(
    initialization_date,
):
    """
    Load Member-2 historical rows for one initialization date.
    """

    df = pd.read_csv(
        MEMBER2_FILE
    )

    dates = pd.to_datetime(
        df["init_date"],
        errors="coerce",
    )

    rows = df[
        dates.dt.strftime(
            "%Y-%m-%d"
        )
        ==
        initialization_date
    ].copy()

    return rows


def build_iceberg_positions(
    rows,
    horizon,
):
    """
    Extract the historical future iceberg positions
    used by the routing-validation experiment.
    """

    lat_col = (
        f"true_lat_{horizon}h"
    )

    lon_col = (
        f"true_lon_{horizon}h"
    )

    positions = []

    for _, row in rows.iterrows():

        lat = row[
            lat_col
        ]

        lon = row[
            lon_col
        ]

        if (
            np.isfinite(lat)
            and
            np.isfinite(lon)
        ):

            positions.append(
                {
                    "latitude":
                        float(lat),

                    "longitude":
                        float(lon),
                }
            )

    return positions


# ============================================================
# SAFE VALUE FORMATTER
# ============================================================

def format_value(
    value,
    multiplier=1.0,
    decimals=4,
):
    """
    Format finite values safely for console output.
    """

    if not np.isfinite(value):
        return "INVALID / NaN"

    return (
        f"{value * multiplier:.{decimals}f}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 105)
    print("POLARGUARD")
    print("PS124 START-CELL BLOCK DIAGNOSTIC")
    print("=" * 105)

    tests = pd.read_csv(
        TEST_FILE
    )

    # --------------------------------------------------------
    # CHECK REQUIRED TEST COLUMNS
    # --------------------------------------------------------

    required_columns = [
        "horizon_hours",
        "initialization_date",
        "start_latitude",
        "start_longitude",
    ]

    missing = [
        column
        for column in required_columns
        if column not in tests.columns
    ]

    if missing:

        raise RuntimeError(
            "Missing test columns: "
            +
            ", ".join(missing)
        )

    # ========================================================
    # CHECK EVERY FROZEN PS124 CASE
    # ========================================================

    for _, test in tests.iterrows():

        horizon = int(
            test[
                "horizon_hours"
            ]
        )

        initialization_date = str(
            test[
                "initialization_date"
            ]
        )

        start_lat = float(
            test[
                "start_latitude"
            ]
        )

        start_lon = float(
            test[
                "start_longitude"
            ]
        )

        print()
        print("=" * 105)
        print(
            f"{horizon}H START-CELL DIAGNOSTIC"
        )
        print("=" * 105)

        print(
            "Initialization:",
            initialization_date,
        )

        print(
            "Vessel profile:",
            VESSEL_PROFILE,
        )

        print(
            "Start:",
            start_lat,
            start_lon,
        )

        # ====================================================
        # LOAD MEMBER 1
        # ====================================================

        member1 = load_member1_bundle(
            initialization_date
        )

        grid_lat, grid_lon = (
            projected_grid_to_latlon(
                member1["x"],
                member1["y"],
            )
        )

        sic = member1[
            str(horizon)
        ]

        uncertainty = member1[
            f"uncertainty_{horizon}"
        ]

        # ====================================================
        # LOAD MEMBER 2
        # ====================================================

        member2_rows = (
            load_member2_rows(
                initialization_date
            )
        )

        iceberg_positions = (
            build_iceberg_positions(
                member2_rows,
                horizon,
            )
        )

        # ====================================================
        # BUILD SAME RISK GRID USED BY NAVIGATION SERVICE
        # ====================================================

        risk = build_risk_grid(
            sic=sic,
            uncertainty=uncertainty,
            grid_lat=grid_lat,
            grid_lon=grid_lon,
            iceberg_positions=
                iceberg_positions,
            safety_radius_km=
                SAFETY_RADIUS_KM,
            influence_radius_km=
                INFLUENCE_RADIUS_KM,
        )

        # ====================================================
        # BUILD SAME VESSEL NAVIGATION MASK
        # ====================================================

        navigation_mask = (
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
                    VESSEL_PROFILE,
            )
        )

        # ====================================================
        # FIND ROUTING GRID CELL NEAREST REAL AIS START
        # ====================================================

        row, col = nearest_grid_cell(
            grid_lat,
            grid_lon,
            start_lat,
            start_lon,
        )

        # ====================================================
        # ENVIRONMENT AT START CELL
        # ====================================================

        sic_value = float(
            sic[
                row,
                col
            ]
        )

        iceberg_risk_value = float(
            risk[
                "iceberg_risk"
            ][
                row,
                col
            ]
        )

        uncertainty_risk_value = float(
            risk[
                "uncertainty_risk"
            ][
                row,
                col
            ]
        )

        combined_risk_value = float(
            risk[
                "combined_risk"
            ][
                row,
                col
            ]
        )

        routing_cost_value = float(
            risk[
                "routing_cost"
            ][
                row,
                col
            ]
        )

        # ====================================================
        # BLOCKING CAUSES
        # ====================================================

        source_blocked = bool(
            risk[
                "blocked_mask"
            ][
                row,
                col
            ]
        )

        blocked_by_sic = bool(
            navigation_mask[
                "blocked_by_sic"
            ][
                row,
                col
            ]
        )

        blocked_by_iceberg = bool(
            navigation_mask[
                "blocked_by_iceberg"
            ][
                row,
                col
            ]
        )

        blocked_by_uncertainty = bool(
            navigation_mask[
                "blocked_by_uncertainty"
            ][
                row,
                col
            ]
        )

        final_blocked = bool(
            navigation_mask[
                "blocked_mask"
            ][
                row,
                col
            ]
        )

        # ====================================================
        # VESSEL PROFILE LIMITS
        # ====================================================

        profile = navigation_mask[
            "profile"
        ]

        max_sic = float(
            profile[
                "max_sic"
            ]
        )

        iceberg_limit = float(
            profile[
                "iceberg_exclusion_risk"
            ]
        )

        uncertainty_limit = float(
            profile[
                "uncertainty_limit"
            ]
        )

        # ====================================================
        # PRINT GRID CELL
        # ====================================================

        print()
        print("GRID CELL")
        print("-" * 105)

        print(
            "Row:",
            row,
        )

        print(
            "Col:",
            col,
        )

        print(
            "Grid latitude :",
            grid_lat[
                row,
                col
            ],
        )

        print(
            "Grid longitude:",
            grid_lon[
                row,
                col
            ],
        )

        # ====================================================
        # PRINT ENVIRONMENT
        # ====================================================

        print()
        print("ENVIRONMENT AT START")
        print("-" * 105)

        if np.isfinite(
            sic_value
        ):

            print(
                f"SIC                    : "
                f"{sic_value:.4f} "
                f"({sic_value * 100.0:.2f}%)"
            )

        else:

            print(
                "SIC                    : "
                "INVALID / NaN"
            )

        print(
            "Iceberg risk           :",
            format_value(
                iceberg_risk_value,
                decimals=4,
            ),
        )

        print(
            "Uncertainty risk       :",
            format_value(
                uncertainty_risk_value,
                decimals=4,
            ),
        )

        print(
            "Combined risk          :",
            format_value(
                combined_risk_value,
                decimals=4,
            ),
        )

        print(
            "Raw routing cost       :",
            format_value(
                routing_cost_value,
                decimals=4,
            ),
        )

        # ====================================================
        # PRINT PROFILE LIMITS
        # ====================================================

        print()
        print("VESSEL PROFILE LIMITS")
        print("-" * 105)

        print(
            f"Maximum SIC allowed    : "
            f"{max_sic:.4f} "
            f"({max_sic * 100.0:.1f}%)"
        )

        print(
            f"Iceberg exclusion risk : "
            f"{iceberg_limit:.4f}"
        )

        print(
            f"Uncertainty limit      : "
            f"{uncertainty_limit:.4f}"
        )

        # ====================================================
        # PRINT BLOCKING CAUSES
        # ====================================================

        print()
        print("BLOCKING TEST")
        print("-" * 105)

        print(
            "Blocked by SIC         :",
            blocked_by_sic,
        )

        print(
            "Blocked by iceberg     :",
            blocked_by_iceberg,
        )

        print(
            "Blocked by uncertainty :",
            blocked_by_uncertainty,
        )

        print(
            "Source/invalid blocked :",
            source_blocked,
        )

        print(
            "FINAL BLOCKED          :",
            final_blocked,
        )

        # ====================================================
        # HUMAN-READABLE DIAGNOSIS
        # ====================================================

        reasons = []

        if blocked_by_sic:

            reasons.append(
                "SIC exceeds vessel maximum"
            )

        if blocked_by_iceberg:

            reasons.append(
                "iceberg risk exceeds vessel exclusion threshold"
            )

        if blocked_by_uncertainty:

            reasons.append(
                "uncertainty exceeds vessel limit"
            )

        if source_blocked:

            reasons.append(
                "underlying environmental/source grid is blocked"
            )

        print()
        print("DIAGNOSIS")
        print("-" * 105)

        if final_blocked:

            if reasons:

                for number, reason in enumerate(
                    reasons,
                    start=1,
                ):

                    print(
                        f"{number}. {reason}"
                    )

            else:

                print(
                    "Cell is blocked, but no individual "
                    "cause was identified."
                )

        else:

            print(
                "Start cell is navigable under the "
                "selected vessel profile."
            )

        print()
        print(
            "Historical iceberg hazards:",
            len(
                iceberg_positions
            ),
        )

    print()
    print("=" * 105)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 105)


if __name__ == "__main__":
    main()