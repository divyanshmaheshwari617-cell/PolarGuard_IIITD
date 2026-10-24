from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# PATHS
# ============================================================

BASE = Path(__file__).resolve().parent.parent

AIS_FILE = (
    BASE
    / "data"
    / "ais"
    / "polarstern_ps124_2021"
    / "analysis"
    / "polarstern_ps124_cleaned_track.csv"
)

OUTPUT_DIR = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps124_validation"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# VALIDATION CONFIGURATION
# ============================================================

INITIALIZATION_TIME = pd.Timestamp(
    "2021-03-01T12:00:00Z"
)

INITIALIZATION_DATE = "2021-03-01"

HORIZONS = [
    24,
    48,
    72,
]

EARTH_RADIUS_KM = 6371.0088


# ============================================================
# HAVERSINE DISTANCE
# ============================================================

def haversine_km(
    lat1,
    lon1,
    lat2,
    lon2,
):

    lat1 = np.radians(
        np.asarray(
            lat1,
            dtype=float,
        )
    )

    lon1 = np.radians(
        np.asarray(
            lon1,
            dtype=float,
        )
    )

    lat2 = np.radians(
        np.asarray(
            lat2,
            dtype=float,
        )
    )

    lon2 = np.radians(
        np.asarray(
            lon2,
            dtype=float,
        )
    )

    dlat = lat2 - lat1

    dlon = (
        lon2
        - lon1
        + np.pi
    ) % (
        2.0 * np.pi
    ) - np.pi

    a = (
        np.sin(
            dlat / 2.0
        ) ** 2
        +
        np.cos(lat1)
        *
        np.cos(lat2)
        *
        np.sin(
            dlon / 2.0
        ) ** 2
    )

    a = np.clip(
        a,
        0.0,
        1.0,
    )

    return (
        2.0
        *
        EARTH_RADIUS_KM
        *
        np.arcsin(
            np.sqrt(a)
        )
    )


# ============================================================
# ROUTE DISTANCE
# ============================================================

def calculate_route_distance(
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

    distances = haversine_km(
        lat[:-1],
        lon[:-1],
        lat[1:],
        lon[1:],
    )

    return float(
        np.nansum(
            distances
        )
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 100)
    print("POLARGUARD")
    print("POLARSTERN PS124 VALIDATION CASE PREPARATION")
    print("=" * 100)

    # --------------------------------------------------------
    # LOAD TRACK
    # --------------------------------------------------------

    df = pd.read_csv(
        AIS_FILE
    )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        utc=True,
        errors="coerce",
    )

    df = (
        df
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

    print()
    print(
        "Track rows:",
        f"{len(df):,}",
    )

    print(
        "Track start:",
        df["timestamp"].min(),
    )

    print(
        "Track end  :",
        df["timestamp"].max(),
    )

    # --------------------------------------------------------
    # FIND REAL AIS INITIALIZATION POINT
    # --------------------------------------------------------

    initial_index = (
        (
            df["timestamp"]
            -
            INITIALIZATION_TIME
        )
        .abs()
        .idxmin()
    )

    initial = df.loc[
        initial_index
    ]

    actual_initial_time = (
        initial["timestamp"]
    )

    start_lat = float(
        initial["lat"]
    )

    start_lon = float(
        initial["lon"]
    )

    initialization_error_minutes = (
        abs(
            (
                actual_initial_time
                -
                INITIALIZATION_TIME
            )
            .total_seconds()
        )
        /
        60.0
    )

    print()
    print("=" * 100)
    print("INITIALIZATION")
    print("=" * 100)

    print(
        "Requested time :",
        INITIALIZATION_TIME,
    )

    print(
        "Nearest AIS time:",
        actual_initial_time,
    )

    print(
        f"Time mismatch  : "
        f"{initialization_error_minutes:.2f} minutes"
    )

    print(
        f"Start latitude : "
        f"{start_lat:.6f}"
    )

    print(
        f"Start longitude: "
        f"{start_lon:.6f}"
    )

    # --------------------------------------------------------
    # BUILD 24 / 48 / 72 HOUR CASES
    # --------------------------------------------------------

    summary_rows = []

    for horizon in HORIZONS:

        requested_target_time = (
            INITIALIZATION_TIME
            +
            pd.Timedelta(
                hours=horizon
            )
        )

        target_index = (
            (
                df["timestamp"]
                -
                requested_target_time
            )
            .abs()
            .idxmin()
        )

        target = df.loc[
            target_index
        ]

        actual_target_time = (
            target["timestamp"]
        )

        target_time_error_minutes = (
            abs(
                (
                    actual_target_time
                    -
                    requested_target_time
                )
                .total_seconds()
            )
            /
            60.0
        )

        # ----------------------------------------------------
        # REAL AIS SEGMENT
        # ----------------------------------------------------

        segment = df[
            (
                df["timestamp"]
                >=
                actual_initial_time
            )
            &
            (
                df["timestamp"]
                <=
                actual_target_time
            )
        ].copy()

        segment = (
            segment
            .reset_index(
                drop=True
            )
        )

        if len(segment) < 2:
            raise RuntimeError(
                f"Not enough AIS points "
                f"for {horizon}h test."
            )

        destination_lat = float(
            target["lat"]
        )

        destination_lon = float(
            target["lon"]
        )

        actual_distance_km = (
            calculate_route_distance(
                segment
            )
        )

        direct_distance_km = float(
            haversine_km(
                start_lat,
                start_lon,
                destination_lat,
                destination_lon,
            )
        )

        geometric_efficiency_pct = (
            direct_distance_km
            /
            actual_distance_km
            *
            100.0
            if actual_distance_km > 0
            else np.nan
        )

        # ----------------------------------------------------
        # SAVE EXACT AIS SEGMENT
        # ----------------------------------------------------

        segment_file = (
            OUTPUT_DIR
            /
            f"polarstern_ps124_actual_{horizon}h.csv"
        )

        segment.to_csv(
            segment_file,
            index=False,
        )

        # ----------------------------------------------------
        # PRINT
        # ----------------------------------------------------

        print()
        print("=" * 100)
        print(
            f"{horizon}H ACTUAL POLARSTERN TEST"
        )
        print("=" * 100)

        print(
            "Requested target:",
            requested_target_time,
        )

        print(
            "Nearest AIS time:",
            actual_target_time,
        )

        print(
            f"Target time mismatch: "
            f"{target_time_error_minutes:.2f} minutes"
        )

        print(
            f"AIS observations: "
            f"{len(segment):,}"
        )

        print()
        print(
            f"Destination latitude : "
            f"{destination_lat:.6f}"
        )

        print(
            f"Destination longitude: "
            f"{destination_lon:.6f}"
        )

        print()
        print(
            f"Actual AIS distance : "
            f"{actual_distance_km:.2f} km"
        )

        print(
            f"Direct distance     : "
            f"{direct_distance_km:.2f} km"
        )

        print(
            f"Geometric efficiency: "
            f"{geometric_efficiency_pct:.2f}%"
        )

        print(
            "Saved:",
            segment_file,
        )

        summary_rows.append(
            {
                "test_name":
                    f"ps124_{horizon}h",

                "initialization_date":
                    INITIALIZATION_DATE,

                "requested_initialization_time":
                    INITIALIZATION_TIME,

                "actual_initialization_time":
                    actual_initial_time,

                "initialization_time_error_minutes":
                    initialization_error_minutes,

                "horizon_hours":
                    horizon,

                "requested_target_time":
                    requested_target_time,

                "actual_target_time":
                    actual_target_time,

                "target_time_error_minutes":
                    target_time_error_minutes,

                "start_latitude":
                    start_lat,

                "start_longitude":
                    start_lon,

                "destination_latitude":
                    destination_lat,

                "destination_longitude":
                    destination_lon,

                "ais_points":
                    len(segment),

                "actual_route_distance_km":
                    actual_distance_km,

                "direct_distance_km":
                    direct_distance_km,

                "geometric_efficiency_pct":
                    geometric_efficiency_pct,

                "segment_file":
                    str(
                        segment_file
                    ),
            }
        )

    # ========================================================
    # SAVE TEST MATRIX
    # ========================================================

    summary = pd.DataFrame(
        summary_rows
    )

    summary_file = (
        OUTPUT_DIR
        /
        "ps124_validation_test_definitions.csv"
    )

    summary.to_csv(
        summary_file,
        index=False,
    )

    print()
    print("=" * 100)
    print("FINAL PS124 VALIDATION MATRIX")
    print("=" * 100)

    display_columns = [
        "horizon_hours",
        "actual_target_time",
        "target_time_error_minutes",
        "destination_latitude",
        "destination_longitude",
        "ais_points",
        "actual_route_distance_km",
        "direct_distance_km",
        "geometric_efficiency_pct",
    ]

    display = (
        summary[
            display_columns
        ]
        .copy()
    )

    numeric_columns = [
        "target_time_error_minutes",
        "destination_latitude",
        "destination_longitude",
        "actual_route_distance_km",
        "direct_distance_km",
        "geometric_efficiency_pct",
    ]

    display[
        numeric_columns
    ] = (
        display[
            numeric_columns
        ]
        .round(3)
    )

    print()
    print(
        display.to_string(
            index=False
        )
    )

    print()
    print("=" * 100)
    print("FILES CREATED")
    print("=" * 100)

    print(summary_file)

    for horizon in HORIZONS:
        print(
            OUTPUT_DIR
            /
            f"polarstern_ps124_actual_{horizon}h.csv"
        )

    print()
    print("=" * 100)
    print("PS124 VALIDATION CASE FROZEN")
    print("=" * 100)

    print()
    print(
        "Next stage: run the existing "
        "PolarGuard historical routing pipeline "
        "against these exact 24h / 48h / 72h "
        "Polarstern endpoints."
    )


if __name__ == "__main__":
    main()