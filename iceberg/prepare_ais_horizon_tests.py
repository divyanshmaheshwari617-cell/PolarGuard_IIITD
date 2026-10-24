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
    / "oceannova_2024"
    / "analysis"
    / "oceannova_cleaned_track.csv"
)

OUTPUT_DIR = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# SETTINGS
# ============================================================

INITIALIZATION_TIME = pd.Timestamp(
    "2024-11-29T00:00:00Z"
)

HORIZONS = [
    24,
    48,
    72,
]

EARTH_RADIUS_KM = 6371.0088


# ============================================================
# DISTANCE
# ============================================================

def haversine_km(
    lat1,
    lon1,
    lat2,
    lon2,
):

    lat1 = np.radians(
        np.asarray(lat1, dtype=float)
    )

    lon1 = np.radians(
        np.asarray(lon1, dtype=float)
    )

    lat2 = np.radians(
        np.asarray(lat2, dtype=float)
    )

    lon2 = np.radians(
        np.asarray(lon2, dtype=float)
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    dlon = (
        dlon
        + np.pi
    ) % (
        2.0 * np.pi
    ) - np.pi

    a = (
        np.sin(dlat / 2.0) ** 2
        +
        np.cos(lat1)
        * np.cos(lat2)
        * np.sin(dlon / 2.0) ** 2
    )

    a = np.clip(
        a,
        0.0,
        1.0,
    )

    return (
        2.0
        * EARTH_RADIUS_KM
        * np.arcsin(
            np.sqrt(a)
        )
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 90)
    print("POLARGUARD")
    print("OCEANNOVA 24H / 48H / 72H AIS TEST PREPARATION")
    print("=" * 90)

    df = pd.read_csv(
        AIS_FILE
    )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        utc=True,
    )

    df = (
        df
        .sort_values(
            "timestamp"
        )
        .reset_index(
            drop=True
        )
    )

    # --------------------------------------------------------
    # INITIAL AIS POSITION
    # --------------------------------------------------------

    initial_index = (
        (
            df["timestamp"]
            - INITIALIZATION_TIME
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

    print()
    print("INITIALIZATION")
    print("-" * 90)

    print(
        "Requested:",
        INITIALIZATION_TIME,
    )

    print(
        "AIS point:",
        actual_initial_time,
    )

    print(
        f"Start latitude : "
        f"{start_lat:.6f}"
    )

    print(
        f"Start longitude: "
        f"{start_lon:.6f}"
    )


    # ========================================================
    # BUILD HORIZON TESTS
    # ========================================================

    summary_rows = []

    for horizon in HORIZONS:

        target_time = (
            INITIALIZATION_TIME
            +
            pd.Timedelta(
                hours=horizon
            )
        )

        # ----------------------------------------------------
        # FIND AIS POINT CLOSEST TO EXACT HORIZON
        # ----------------------------------------------------

        target_index = (
            (
                df["timestamp"]
                - target_time
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

        time_difference_minutes = (
            abs(
                (
                    actual_target_time
                    - target_time
                )
                .total_seconds()
            )
            / 60.0
        )

        # ----------------------------------------------------
        # AIS SEGMENT
        # ----------------------------------------------------

        segment = df[
            (
                df["timestamp"]
                >= actual_initial_time
            )
            &
            (
                df["timestamp"]
                <= actual_target_time
            )
        ].copy()

        segment = (
            segment
            .reset_index(
                drop=True
            )
        )

        # ----------------------------------------------------
        # DISTANCE ALONG REAL AIS ROUTE
        # ----------------------------------------------------

        segment[
            "previous_lat"
        ] = (
            segment[
                "lat"
            ]
            .shift(1)
        )

        segment[
            "previous_lon"
        ] = (
            segment[
                "lon"
            ]
            .shift(1)
        )

        segment[
            "step_distance_km"
        ] = haversine_km(
            segment[
                "previous_lat"
            ],
            segment[
                "previous_lon"
            ],
            segment["lat"],
            segment["lon"],
        )

        actual_route_distance = float(
            segment[
                "step_distance_km"
            ]
            .fillna(0.0)
            .sum()
        )

        destination_lat = float(
            target["lat"]
        )

        destination_lon = float(
            target["lon"]
        )

        direct_distance = float(
            haversine_km(
                start_lat,
                start_lon,
                destination_lat,
                destination_lon,
            )
        )

        efficiency = (
            direct_distance
            /
            actual_route_distance
            *
            100.0
            if actual_route_distance > 0
            else np.nan
        )

        # ----------------------------------------------------
        # PRINT
        # ----------------------------------------------------

        print()
        print("=" * 90)

        print(
            f"{horizon}H ACTUAL AIS TEST"
        )

        print("=" * 90)

        print(
            "Requested target:",
            target_time,
        )

        print(
            "Closest AIS point:",
            actual_target_time,
        )

        print(
            f"Time mismatch: "
            f"{time_difference_minutes:.2f} minutes"
        )

        print(
            f"AIS points: "
            f"{len(segment):,}"
        )

        print(
            f"Destination latitude : "
            f"{destination_lat:.6f}"
        )

        print(
            f"Destination longitude: "
            f"{destination_lon:.6f}"
        )

        print(
            f"Actual AIS distance   : "
            f"{actual_route_distance:.2f} km"
        )

        print(
            f"Direct distance       : "
            f"{direct_distance:.2f} km"
        )

        print(
            f"Geometric efficiency  : "
            f"{efficiency:.2f}%"
        )

        # ----------------------------------------------------
        # SAVE SEGMENT
        # ----------------------------------------------------

        segment_file = (
            OUTPUT_DIR
            /
            f"oceannova_actual_{horizon}h.csv"
        )

        segment.to_csv(
            segment_file,
            index=False,
        )

        summary_rows.append(
            {
                "horizon_hours":
                    horizon,

                "initialization_time":
                    actual_initial_time,

                "requested_target_time":
                    target_time,

                "actual_target_time":
                    actual_target_time,

                "target_time_difference_minutes":
                    time_difference_minutes,

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
                    actual_route_distance,

                "direct_distance_km":
                    direct_distance,

                "geometric_efficiency_pct":
                    efficiency,

                "segment_file":
                    str(segment_file),
            }
        )


    # ========================================================
    # SAVE SUMMARY
    # ========================================================

    summary = pd.DataFrame(
        summary_rows
    )

    summary_file = (
        OUTPUT_DIR
        /
        "oceannova_horizon_test_definitions.csv"
    )

    summary.to_csv(
        summary_file,
        index=False,
    )


    print()
    print("=" * 90)
    print("FINAL HORIZON TEST MATRIX")
    print("=" * 90)

    print()

    print(
        summary[
            [
                "horizon_hours",
                "actual_target_time",
                "target_time_difference_minutes",
                "destination_latitude",
                "destination_longitude",
                "ais_points",
                "actual_route_distance_km",
                "direct_distance_km",
                "geometric_efficiency_pct",
            ]
        ]
        .round(3)
        .to_string(
            index=False
        )
    )

    print()
    print("=" * 90)
    print("OUTPUT")
    print("=" * 90)

    print(
        summary_file
    )

    print()
    print(
        "2024 AIS horizon tests are now frozen."
    )

    print()
    print("=" * 90)
    print("STAGE 2 COMPLETE")
    print("=" * 90)


if __name__ == "__main__":
    main()