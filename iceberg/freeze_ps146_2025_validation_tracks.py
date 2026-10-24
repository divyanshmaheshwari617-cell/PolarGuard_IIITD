from pathlib import Path
import pandas as pd
import numpy as np


BASE = Path(__file__).resolve().parent.parent

TRACK_FILE = (
    BASE
    / "data"
    / "ais"
    / "polarstern_ps146_2025"
    / "analysis"
    / "polarstern_ps146_2025_cleaned_track.csv"
)

SELECTED_CASES_FILE = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps146_2025_validation"
    / "ps146_2025_selected_validation_windows.csv"
)

OUTPUT_DIR = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps146_2025_validation"
    / "selected_cases"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

SUMMARY_FILE = (
    OUTPUT_DIR
    / "ps146_2025_frozen_case_definitions.csv"
)


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
# ROUTE DISTANCE
# ============================================================

def route_distance_km(
    segment,
):
    if len(segment) < 2:
        return 0.0

    lat = (
        segment["lat"]
        .to_numpy(
            dtype=float
        )
    )

    lon = (
        segment["lon"]
        .to_numpy(
            dtype=float
        )
    )

    d = haversine_km(
        lat[:-1],
        lon[:-1],
        lat[1:],
        lon[1:],
    )

    return float(
        np.nansum(d)
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 110)
    print("POLARGUARD")
    print("FREEZE PS146 2025 SELECTED VALIDATION TRACKS")
    print("=" * 110)

    # --------------------------------------------------------
    # LOAD TRACK
    # --------------------------------------------------------

    track = pd.read_csv(
        TRACK_FILE
    )

    track["timestamp"] = pd.to_datetime(
        track["timestamp"],
        utc=True,
        errors="coerce",
    )

    track["lat"] = pd.to_numeric(
        track["lat"],
        errors="coerce",
    )

    track["lon"] = pd.to_numeric(
        track["lon"],
        errors="coerce",
    )

    track = (
        track
        .dropna(
            subset=[
                "timestamp",
                "lat",
                "lon",
            ]
        )
        .sort_values(
            "timestamp"
        )
        .reset_index(
            drop=True
        )
    )

    # --------------------------------------------------------
    # LOAD SELECTED CASES
    # --------------------------------------------------------

    selected = pd.read_csv(
        SELECTED_CASES_FILE
    )

    datetime_columns = [
        "actual_start_time",
        "actual_end_time",
        "start_time",
        "end_time",
    ]

    for col in datetime_columns:
        if col in selected.columns:
            selected[col] = pd.to_datetime(
                selected[col],
                utc=True,
                errors="coerce",
            )

    selected["horizon_hours"] = pd.to_numeric(
        selected["horizon_hours"],
        errors="coerce",
    )

    selected["selection_rank"] = pd.to_numeric(
        selected["selection_rank"],
        errors="coerce",
    )

    frozen_rows = []

    # ========================================================
    # FREEZE EACH CASE
    # ========================================================

    for _, case in selected.iterrows():

        case_id = str(
            case["case_id"]
        )

        horizon = int(
            case["horizon_hours"]
        )

        requested_start = pd.Timestamp(
            case["actual_start_time"]
        )

        requested_end = pd.Timestamp(
            case["actual_end_time"]
        )

        print()
        print("=" * 110)
        print(case_id)
        print("=" * 110)

        # ----------------------------------------------------
        # EXACT TRACK SEGMENT
        # ----------------------------------------------------

        segment = track[
            (
                track["timestamp"]
                >=
                requested_start
            )
            &
            (
                track["timestamp"]
                <=
                requested_end
            )
        ].copy()

        segment = (
            segment
            .sort_values(
                "timestamp"
            )
            .reset_index(
                drop=True
            )
        )

        if segment.empty:
            print(
                "SKIPPED: no AIS rows found."
            )
            continue

        # ----------------------------------------------------
        # ACTUAL FROZEN BOUNDS
        # ----------------------------------------------------

        actual_start = pd.Timestamp(
            segment.iloc[0][
                "timestamp"
            ]
        )

        actual_end = pd.Timestamp(
            segment.iloc[-1][
                "timestamp"
            ]
        )

        start_lat = float(
            segment.iloc[0][
                "lat"
            ]
        )

        start_lon = float(
            segment.iloc[0][
                "lon"
            ]
        )

        destination_lat = float(
            segment.iloc[-1][
                "lat"
            ]
        )

        destination_lon = float(
            segment.iloc[-1][
                "lon"
            ]
        )

        ais_distance = (
            route_distance_km(
                segment
            )
        )

        direct_distance = float(
            haversine_km(
                start_lat,
                start_lon,
                destination_lat,
                destination_lon,
            )
        )

        geometric_efficiency = (
            direct_distance
            /
            ais_distance
            *
            100.0
            if ais_distance > 0
            else np.nan
        )

        effective_hours = (
            (
                actual_end
                -
                actual_start
            )
            .total_seconds()
            /
            3600.0
        )

        # ----------------------------------------------------
        # SAVE TRACK FILE
        # ----------------------------------------------------

        route_file = (
            OUTPUT_DIR
            /
            f"{case_id}_actual_ais.csv"
        )

        segment.to_csv(
            route_file,
            index=False,
        )

        # ----------------------------------------------------
        # PRINT
        # ----------------------------------------------------

        print(
            "Horizon:",
            f"{horizon}h",
        )

        print(
            "Initialization:",
            case[
                "initialization_date"
            ],
        )

        print(
            "Actual start:",
            actual_start,
        )

        print(
            "Actual end:",
            actual_end,
        )

        print(
            f"Effective duration: "
            f"{effective_hours:.3f} h"
        )

        print(
            "AIS points:",
            len(
                segment
            ),
        )

        print(
            f"AIS distance: "
            f"{ais_distance:.2f} km"
        )

        print(
            f"Direct distance: "
            f"{direct_distance:.2f} km"
        )

        print(
            f"Geometric efficiency: "
            f"{geometric_efficiency:.2f}%"
        )

        print(
            f"Start: "
            f"{start_lat:.6f}, "
            f"{start_lon:.6f}"
        )

        print(
            f"Destination: "
            f"{destination_lat:.6f}, "
            f"{destination_lon:.6f}"
        )

        print(
            "Saved:",
            route_file,
        )

        # ----------------------------------------------------
        # SUMMARY ROW
        # ----------------------------------------------------

        frozen_rows.append(
            {
                "case_id":
                    case_id,

                "horizon_hours":
                    horizon,

                "selection_rank":
                    int(
                        case[
                            "selection_rank"
                        ]
                    ),

                "initialization_date":
                    case[
                        "initialization_date"
                    ],

                "target_date":
                    case[
                        "target_date"
                    ],

                "actual_start_time":
                    actual_start,

                "actual_end_time":
                    actual_end,

                "effective_duration_hours":
                    effective_hours,

                "start_latitude":
                    start_lat,

                "start_longitude":
                    start_lon,

                "destination_latitude":
                    destination_lat,

                "destination_longitude":
                    destination_lon,

                "ais_points":
                    len(
                        segment
                    ),

                "ais_distance_km":
                    ais_distance,

                "direct_distance_km":
                    direct_distance,

                "geometric_efficiency_pct":
                    geometric_efficiency,

                "actual_mean_sic_pct":
                    case[
                        "actual_mean_sic_pct"
                    ],

                "actual_max_sic_pct":
                    case[
                        "actual_max_sic_pct"
                    ],

                "predicted_mean_sic_pct":
                    case[
                        "predicted_mean_sic_pct"
                    ],

                "route_sic_mae_pct":
                    case[
                        "route_sic_mae_pct"
                    ],

                "map_mae_pct":
                    case[
                        "map_mae_pct"
                    ],

                "map_correlation":
                    case[
                        "map_correlation"
                    ],

                "route_file":
                    str(
                        route_file
                    ),
            }
        )

    # ========================================================
    # SAVE SUMMARY
    # ========================================================

    frozen = pd.DataFrame(
        frozen_rows
    )

    if frozen.empty:
        raise RuntimeError(
            "No PS146 validation tracks were frozen."
        )

    frozen = (
        frozen
        .sort_values(
            [
                "horizon_hours",
                "selection_rank",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    frozen.to_csv(
        SUMMARY_FILE,
        index=False,
    )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print()
    print("=" * 110)
    print("FINAL FROZEN PS146 2025 CASE MATRIX")
    print("=" * 110)

    display_columns = [
        "case_id",
        "horizon_hours",
        "initialization_date",
        "actual_start_time",
        "actual_end_time",
        "ais_points",
        "ais_distance_km",
        "direct_distance_km",
        "geometric_efficiency_pct",
        "actual_mean_sic_pct",
        "predicted_mean_sic_pct",
        "route_sic_mae_pct",
    ]

    print()

    print(
        frozen[
            display_columns
        ]
        .round(3)
        .to_string(
            index=False
        )
    )

    print()
    print("=" * 110)
    print("FREEZE SUMMARY")
    print("=" * 110)

    print(
        "Frozen cases:",
        len(
            frozen
        ),
    )

    for horizon in [
        24,
        48,
        72,
    ]:

        count = int(
            (
                frozen[
                    "horizon_hours"
                ]
                ==
                horizon
            ).sum()
        )

        print(
            f"{horizon}H cases:",
            count,
        )

    print()
    print("=" * 110)
    print("OUTPUT")
    print("=" * 110)

    print(
        SUMMARY_FILE
    )

    print()
    print("=" * 110)
    print(
        "PS146 2025 VALIDATION TRACK FREEZE COMPLETE"
    )
    print("=" * 110)


if __name__ == "__main__":
    main()