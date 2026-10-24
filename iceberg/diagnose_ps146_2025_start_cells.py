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

ACTUAL_2025_FILE = (
    BASE
    / "data"
    / "processed"
    / "test_2025.nc"
)

FROZEN_CASES_FILE = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps146_2025_validation"
    / "selected_cases"
    / "ps146_2025_frozen_case_definitions.csv"
)

ROUTING_SUMMARY_FILE = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps146_2025_validation"
    / "polarguard_results"
    / "ps146_2025_ais_vs_polarguard_summary.csv"
)

MEMBER2_FILE = (
    BASE
    / "iceberg"
    / "data"
    / "processed"
    / "iceberg_features_environment_ml_ready_2019_2025.csv"
)

OUTPUT_DIR = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps146_2025_validation"
    / "start_cell_diagnostic"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

SUMMARY_FILE = (
    OUTPUT_DIR
    / "ps146_2025_failed_start_cell_summary.csv"
)

NEARBY_FILE = (
    OUTPUT_DIR
    / "ps146_2025_failed_start_nearby_cells.csv"
)


# ============================================================
# SETTINGS
# ============================================================

VESSEL_PROFILE = "HIGH_ICE_CAPABILITY"

SAFETY_RADIUS_KM = 10.0
INFLUENCE_RADIUS_KM = 30.0

# Search +/- 4 routing cells around the snapped start.
NEARBY_SEARCH_RADIUS_CELLS = 4


# ============================================================
# HAVERSINE
# ============================================================

def haversine_km(
    lat1,
    lon1,
    lat2,
    lon2,
):

    R = 6371.0088

    lat1 = np.radians(lat1)
    lon1 = np.radians(lon1)

    lat2 = np.radians(lat2)
    lon2 = np.radians(lon2)

    dlat = lat2 - lat1

    dlon = (
        lon2
        -
        lon1
        +
        np.pi
    ) % (2.0 * np.pi) - np.pi

    a = (
        np.sin(dlat / 2.0) ** 2
        +
        np.cos(lat1)
        *
        np.cos(lat2)
        *
        np.sin(dlon / 2.0) ** 2
    )

    a = np.clip(
        a,
        0.0,
        1.0,
    )

    return (
        2.0
        *
        R
        *
        np.arcsin(
            np.sqrt(a)
        )
    )


# ============================================================
# MEMBER 1
# ============================================================

def load_member1_bundle(
    initialization_date,
):

    ds = xr.open_dataarray(
        SEA_ICE_HISTORY_FILE
    )

    target_date = np.datetime64(
        initialization_date,
        "D",
    )

    dates = (
        ds.time.values
        .astype(
            "datetime64[D]"
        )
    )

    matches = np.where(
        dates
        ==
        target_date
    )[0]

    if len(matches) == 0:

        ds.close()

        raise RuntimeError(
            f"No SIC history for {initialization_date}"
        )

    idx = int(
        matches[0]
    )

    if idx < 3:

        ds.close()

        raise RuntimeError(
            "Three previous SIC maps are required."
        )

    current = np.asarray(
        ds.isel(
            time=idx
        ).values,
        dtype=np.float32,
    )

    lag1 = np.asarray(
        ds.isel(
            time=idx - 1
        ).values,
        dtype=np.float32,
    )

    lag2 = np.asarray(
        ds.isel(
            time=idx - 2
        ).values,
        dtype=np.float32,
    )

    lag3 = np.asarray(
        ds.isel(
            time=idx - 3
        ).values,
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

    result = {
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

    ds.close()

    return result


# ============================================================
# ACTUAL 2025 SIC
# ============================================================

def load_actual_sic(
    actual_da,
    target_date,
):

    target_date = np.datetime64(
        str(target_date),
        "D",
    )

    dates = (
        actual_da.time.values
        .astype(
            "datetime64[D]"
        )
    )

    matches = np.where(
        dates == target_date
    )[0]

    if len(matches) == 0:
        return None

    return np.asarray(
        actual_da.isel(
            time=int(
                matches[0]
            )
        ).values,
        dtype=np.float32,
    )


# ============================================================
# GRID CONVERSION
# ============================================================

def projected_grid_to_latlon(
    x_coords,
    y_coords,
):

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

    grid_lon, grid_lat = transformer.transform(
        x_grid,
        y_grid,
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
# MEMBER 2
# ============================================================

def load_member2_rows(
    initialization_date,
):

    df = pd.read_csv(
        MEMBER2_FILE
    )

    dates = pd.to_datetime(
        df["init_date"],
        errors="coerce",
    )

    return df[
        dates.dt.strftime(
            "%Y-%m-%d"
        )
        ==
        initialization_date
    ].copy()


def build_iceberg_positions(
    rows,
    horizon,
):

    if rows.empty:
        return []

    lat_col = (
        f"true_lat_{horizon}h"
    )

    lon_col = (
        f"true_lon_{horizon}h"
    )

    if (
        lat_col not in rows.columns
        or
        lon_col not in rows.columns
    ):
        return []

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
# SAFE NUMBER
# ============================================================

def safe_float(
    value,
):

    try:

        value = float(
            value
        )

        if np.isfinite(
            value
        ):
            return value

    except Exception:
        pass

    return np.nan


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 115)
    print("POLARGUARD")
    print(
        "PS146 2025 FAILED START-CELL DIAGNOSTIC"
    )
    print("=" * 115)

    frozen = pd.read_csv(
        FROZEN_CASES_FILE
    )

    routing = pd.read_csv(
        ROUTING_SUMMARY_FILE
    )

    actual_ds = xr.open_dataset(
        ACTUAL_2025_FILE
    )

    actual_da = actual_ds[
        "sea_ice_concentration"
    ]

    # --------------------------------------------------------
    # NORMALIZE ROUTING SUCCESS
    # --------------------------------------------------------

    routing[
        "success_bool"
    ] = (
        routing[
            "success"
        ]
        .astype(
            str
        )
        .str.lower()
        .map(
            {
                "true": True,
                "false": False,
            }
        )
        .fillna(
            False
        )
    )

    failed = routing[
        routing[
            "success_bool"
        ]
        ==
        False
    ].copy()

    print()
    print(
        "Failed/rejected cases:",
        len(
            failed
        ),
    )

    summary_rows = []
    nearby_rows = []

    bundle_cache = {}

    # ========================================================
    # EACH FAILED CASE
    # ========================================================

    for _, routing_case in failed.iterrows():

        case_id = str(
            routing_case[
                "case_id"
            ]
        )

        match = frozen[
            frozen[
                "case_id"
            ]
            ==
            case_id
        ]

        if match.empty:

            print()
            print(
                "Missing frozen definition:",
                case_id,
            )

            continue

        test = match.iloc[0]

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

        target_date = str(
            test[
                "target_date"
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
        print("=" * 115)
        print(case_id)
        print("=" * 115)

        print(
            "Horizon:",
            f"{horizon}h",
        )

        print(
            "Initialization:",
            initialization_date,
        )

        print(
            "Target date:",
            target_date,
        )

        print(
            "Vessel profile:",
            VESSEL_PROFILE,
        )

        print(
            "Exact AIS start:",
            start_lat,
            start_lon,
        )

        # ====================================================
        # MEMBER 1
        # ====================================================

        if initialization_date not in bundle_cache:

            bundle_cache[
                initialization_date
            ] = load_member1_bundle(
                initialization_date
            )

        member1 = bundle_cache[
            initialization_date
        ]

        sic = member1[
            str(
                horizon
            )
        ]

        uncertainty = member1[
            f"uncertainty_{horizon}"
        ]

        grid_lat, grid_lon = (
            projected_grid_to_latlon(
                member1[
                    "x"
                ],
                member1[
                    "y"
                ],
            )
        )

        # ====================================================
        # MEMBER 2
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
        # RISK
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
        # NEAREST CELL
        # ====================================================

        row, col = nearest_grid_cell(
            grid_lat,
            grid_lon,
            start_lat,
            start_lon,
        )

        cell_lat = float(
            grid_lat[
                row,
                col
            ]
        )

        cell_lon = float(
            grid_lon[
                row,
                col
            ]
        )

        snap_distance = float(
            haversine_km(
                start_lat,
                start_lon,
                cell_lat,
                cell_lon,
            )
        )

        sic_value = safe_float(
            sic[
                row,
                col
            ]
        )

        iceberg_risk = safe_float(
            risk[
                "iceberg_risk"
            ][
                row,
                col
            ]
        )

        uncertainty_risk = safe_float(
            risk[
                "uncertainty_risk"
            ][
                row,
                col
            ]
        )

        combined_risk = safe_float(
            risk[
                "combined_risk"
            ][
                row,
                col
            ]
        )

        routing_cost = safe_float(
            risk[
                "routing_cost"
            ][
                row,
                col
            ]
        )

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
        # ACTUAL 2025 SIC FOR CONTEXT
        # ====================================================

        actual_sic = load_actual_sic(
            actual_da,
            target_date,
        )

        if actual_sic is None:

            actual_sic_value = np.nan

        else:

            actual_sic_value = safe_float(
                actual_sic[
                    row,
                    col
                ]
            )

        # ====================================================
        # PRINT START CELL
        # ====================================================

        print()
        print("NEAREST ROUTING GRID CELL")
        print("-" * 115)

        print(
            "Row:",
            row,
        )

        print(
            "Col:",
            col,
        )

        print(
            f"Grid position: "
            f"{cell_lat:.6f}, "
            f"{cell_lon:.6f}"
        )

        print(
            f"Grid snap distance: "
            f"{snap_distance:.2f} km"
        )

        print()
        print("ENVIRONMENT AT SNAPPED START CELL")
        print("-" * 115)

        print(
            f"Predicted SIC          : "
            f"{sic_value * 100.0:.2f}%"
            if np.isfinite(
                sic_value
            )
            else
            "Predicted SIC          : NaN"
        )

        print(
            f"Observed target SIC    : "
            f"{actual_sic_value * 100.0:.2f}%"
            if np.isfinite(
                actual_sic_value
            )
            else
            "Observed target SIC    : NaN"
        )

        print(
            f"Iceberg risk           : "
            f"{iceberg_risk:.4f}"
        )

        print(
            f"Uncertainty risk       : "
            f"{uncertainty_risk:.4f}"
        )

        print(
            f"Combined risk          : "
            f"{combined_risk:.4f}"
        )

        print(
            f"Routing cost           : "
            f"{routing_cost:.4f}"
        )

        print()
        print("HIGH-ICE VESSEL LIMITS")
        print("-" * 115)

        print(
            f"Maximum SIC            : "
            f"{max_sic * 100.0:.1f}%"
        )

        print(
            f"Iceberg exclusion risk : "
            f"{iceberg_limit:.4f}"
        )

        print(
            f"Uncertainty limit      : "
            f"{uncertainty_limit:.4f}"
        )

        print()
        print("BLOCKING TEST")
        print("-" * 115)

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
        # HUMAN DIAGNOSIS
        # ====================================================

        reasons = []

        if blocked_by_sic:

            reasons.append(
                "SIC exceeds HIGH_ICE_CAPABILITY limit"
            )

        if blocked_by_iceberg:

            reasons.append(
                "Iceberg risk exceeds exclusion threshold"
            )

        if blocked_by_uncertainty:

            reasons.append(
                "Uncertainty exceeds vessel limit"
            )

        if source_blocked:

            reasons.append(
                "Risk engine/source grid blocked"
            )

        if not reasons:

            reasons.append(
                "No explicit blocking cause found"
            )

        print()
        print("PRIMARY DIAGNOSIS")
        print("-" * 115)

        for number, reason in enumerate(
            reasons,
            start=1,
        ):

            print(
                f"{number}. {reason}"
            )

        # ====================================================
        # NEARBY GRID SEARCH
        # ====================================================

        nearby_candidates = []

        row_min = max(
            0,
            row
            -
            NEARBY_SEARCH_RADIUS_CELLS,
        )

        row_max = min(
            grid_lat.shape[
                0
            ]
            -
            1,
            row
            +
            NEARBY_SEARCH_RADIUS_CELLS,
        )

        col_min = max(
            0,
            col
            -
            NEARBY_SEARCH_RADIUS_CELLS,
        )

        col_max = min(
            grid_lat.shape[
                1
            ]
            -
            1,
            col
            +
            NEARBY_SEARCH_RADIUS_CELLS,
        )

        for rr in range(
            row_min,
            row_max + 1,
        ):

            for cc in range(
                col_min,
                col_max + 1,
            ):

                candidate_lat = safe_float(
                    grid_lat[
                        rr,
                        cc
                    ]
                )

                candidate_lon = safe_float(
                    grid_lon[
                        rr,
                        cc
                    ]
                )

                if (
                    not np.isfinite(
                        candidate_lat
                    )
                    or
                    not np.isfinite(
                        candidate_lon
                    )
                ):
                    continue

                distance = float(
                    haversine_km(
                        start_lat,
                        start_lon,
                        candidate_lat,
                        candidate_lon,
                    )
                )

                candidate_sic = safe_float(
                    sic[
                        rr,
                        cc
                    ]
                )

                candidate_iceberg = safe_float(
                    risk[
                        "iceberg_risk"
                    ][
                        rr,
                        cc
                    ]
                )

                candidate_uncertainty = safe_float(
                    risk[
                        "uncertainty_risk"
                    ][
                        rr,
                        cc
                    ]
                )

                candidate_final_blocked = bool(
                    navigation_mask[
                        "blocked_mask"
                    ][
                        rr,
                        cc
                    ]
                )

                candidate_sic_blocked = bool(
                    navigation_mask[
                        "blocked_by_sic"
                    ][
                        rr,
                        cc
                    ]
                )

                candidate_iceberg_blocked = bool(
                    navigation_mask[
                        "blocked_by_iceberg"
                    ][
                        rr,
                        cc
                    ]
                )

                candidate_uncertainty_blocked = bool(
                    navigation_mask[
                        "blocked_by_uncertainty"
                    ][
                        rr,
                        cc
                    ]
                )

                nearby_candidates.append(
                    {
                        "case_id":
                            case_id,

                        "horizon_hours":
                            horizon,

                        "row":
                            rr,

                        "col":
                            cc,

                        "latitude":
                            candidate_lat,

                        "longitude":
                            candidate_lon,

                        "distance_from_exact_start_km":
                            distance,

                        "predicted_sic_pct":
                            (
                                candidate_sic
                                *
                                100.0
                            ),

                        "iceberg_risk":
                            candidate_iceberg,

                        "uncertainty_risk":
                            candidate_uncertainty,

                        "blocked_by_sic":
                            candidate_sic_blocked,

                        "blocked_by_iceberg":
                            candidate_iceberg_blocked,

                        "blocked_by_uncertainty":
                            candidate_uncertainty_blocked,

                        "final_blocked":
                            candidate_final_blocked,
                    }
                )

        nearby_df = pd.DataFrame(
            nearby_candidates
        )

        nearby_df = (
            nearby_df
            .sort_values(
                "distance_from_exact_start_km"
            )
            .reset_index(
                drop=True
            )
        )

        nearby_rows.extend(
            nearby_df.to_dict(
                orient="records"
            )
        )

        feasible_nearby = nearby_df[
            nearby_df[
                "final_blocked"
            ]
            ==
            False
        ].copy()

        if feasible_nearby.empty:

            nearest_feasible_distance = np.nan
            nearest_feasible_sic = np.nan
            nearest_feasible_row = np.nan
            nearest_feasible_col = np.nan

            grid_artifact_suspected = False

            print()
            print("NEARBY FEASIBLE CELL SEARCH")
            print("-" * 115)

            print(
                "No feasible grid cell found within "
                f"+/-{NEARBY_SEARCH_RADIUS_CELLS} cells."
            )

        else:

            nearest_feasible = (
                feasible_nearby.iloc[
                    0
                ]
            )

            nearest_feasible_distance = float(
                nearest_feasible[
                    "distance_from_exact_start_km"
                ]
            )

            nearest_feasible_sic = float(
                nearest_feasible[
                    "predicted_sic_pct"
                ]
            )

            nearest_feasible_row = int(
                nearest_feasible[
                    "row"
                ]
            )

            nearest_feasible_col = int(
                nearest_feasible[
                    "col"
                ]
            )

            # Heuristic:
            # if snapped cell is blocked but there is an
            # unblocked neighboring cell within roughly
            # one grid spacing (~30 km), snapping may matter.
            grid_artifact_suspected = (
                final_blocked
                and
                nearest_feasible_distance
                <=
                30.0
            )

            print()
            print("NEARBY FEASIBLE CELL SEARCH")
            print("-" * 115)

            print(
                f"Nearest feasible cell: "
                f"row={nearest_feasible_row}, "
                f"col={nearest_feasible_col}"
            )

            print(
                f"Distance from exact AIS start: "
                f"{nearest_feasible_distance:.2f} km"
            )

            print(
                f"Predicted SIC there: "
                f"{nearest_feasible_sic:.2f}%"
            )

            print(
                "Potential grid-snap artifact:",
                grid_artifact_suspected,
            )

        # ====================================================
        # CLASSIFICATION
        # ====================================================

        if (
            blocked_by_sic
            and
            np.isfinite(
                actual_sic_value
            )
            and
            actual_sic_value
            >
            max_sic
        ):

            classification = (
                "LIKELY GENUINE HIGH-ICE REJECTION"
            )

        elif (
            final_blocked
            and
            grid_artifact_suspected
        ):

            classification = (
                "POSSIBLE GRID-SNAP ARTIFACT"
            )

        elif final_blocked:

            classification = (
                "MODEL/RISK-BASED REJECTION"
            )

        else:

            classification = (
                "UNEXPECTED: START CELL NOT BLOCKED"
            )

        print()
        print("FINAL CLASSIFICATION")
        print("-" * 115)

        print(
            classification
        )

        # ====================================================
        # SAVE SUMMARY
        # ====================================================

        summary_rows.append(
            {
                "case_id":
                    case_id,

                "horizon_hours":
                    horizon,

                "initialization_date":
                    initialization_date,

                "target_date":
                    target_date,

                "exact_start_latitude":
                    start_lat,

                "exact_start_longitude":
                    start_lon,

                "grid_row":
                    row,

                "grid_col":
                    col,

                "grid_latitude":
                    cell_lat,

                "grid_longitude":
                    cell_lon,

                "grid_snap_distance_km":
                    snap_distance,

                "predicted_start_sic_pct":
                    (
                        sic_value
                        *
                        100.0
                    ),

                "observed_target_sic_pct":
                    (
                        actual_sic_value
                        *
                        100.0
                    ),

                "iceberg_risk":
                    iceberg_risk,

                "uncertainty_risk":
                    uncertainty_risk,

                "combined_risk":
                    combined_risk,

                "routing_cost":
                    routing_cost,

                "vessel_max_sic_pct":
                    (
                        max_sic
                        *
                        100.0
                    ),

                "blocked_by_sic":
                    blocked_by_sic,

                "blocked_by_iceberg":
                    blocked_by_iceberg,

                "blocked_by_uncertainty":
                    blocked_by_uncertainty,

                "source_blocked":
                    source_blocked,

                "final_blocked":
                    final_blocked,

                "nearest_feasible_distance_km":
                    nearest_feasible_distance,

                "nearest_feasible_sic_pct":
                    nearest_feasible_sic,

                "grid_artifact_suspected":
                    grid_artifact_suspected,

                "classification":
                    classification,

                "diagnosis":
                    "; ".join(
                        reasons
                    ),
            }
        )

    # ========================================================
    # SAVE OUTPUTS
    # ========================================================

    summary_df = pd.DataFrame(
        summary_rows
    )

    nearby_df = pd.DataFrame(
        nearby_rows
    )

    summary_df.to_csv(
        SUMMARY_FILE,
        index=False,
    )

    nearby_df.to_csv(
        NEARBY_FILE,
        index=False,
    )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print()
    print("=" * 115)
    print("FINAL FAILED-START DIAGNOSTIC SUMMARY")
    print("=" * 115)

    if summary_df.empty:

        print(
            "No failed cases diagnosed."
        )

    else:

        display_columns = [
            "case_id",
            "horizon_hours",
            "grid_snap_distance_km",
            "predicted_start_sic_pct",
            "observed_target_sic_pct",
            "blocked_by_sic",
            "blocked_by_iceberg",
            "blocked_by_uncertainty",
            "nearest_feasible_distance_km",
            "grid_artifact_suspected",
            "classification",
        ]

        print()

        print(
            summary_df[
                display_columns
            ]
            .round(
                3
            )
            .to_string(
                index=False
            )
        )

    print()
    print("=" * 115)
    print("OUTPUT")
    print("=" * 115)

    print(
        SUMMARY_FILE
    )

    print(
        NEARBY_FILE
    )

    print()
    print("=" * 115)
    print(
        "PS146 2025 START-CELL DIAGNOSTIC COMPLETE"
    )
    print("=" * 115)

    actual_ds.close()


if __name__ == "__main__":
    main()