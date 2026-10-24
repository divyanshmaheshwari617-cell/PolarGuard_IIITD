from pathlib import Path

import numpy as np
import pandas as pd


BASE = Path(__file__).resolve().parent.parent

TRACK_FILE = (
    BASE
    / "data"
    / "ais"
    / "polarstern_ps124_2021"
    / "analysis"
    / "polarstern_ps124_cleaned_track.csv"
)

SELECTED_FILE = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps124_validation"
    / "ps124_selected_route_validation_windows.csv"
)

OUTPUT_DIR = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps124_validation"
    / "selected_cases"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1, lon1, lat2, lon2):

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

    dlon = (
        lon2
        - lon1
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


def route_distance_km(segment):

    if len(segment) < 2:
        return 0.0

    lat = segment[
        "lat"
    ].to_numpy(dtype=float)

    lon = segment[
        "lon"
    ].to_numpy(dtype=float)

    return float(
        np.nansum(
            haversine_km(
                lat[:-1],
                lon[:-1],
                lat[1:],
                lon[1:],
            )
        )
    )


def main():

    print("=" * 100)
    print("POLARGUARD")
    print("FREEZE SELECTED PS124 VALIDATION WINDOWS - CORRECTED")
    print("=" * 100)

    track = pd.read_csv(
        TRACK_FILE
    )

    track["timestamp"] = pd.to_datetime(
        track["timestamp"],
        utc=True,
    )

    track = (
        track
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    selected = pd.read_csv(
        SELECTED_FILE
    )

    selected["start_time"] = pd.to_datetime(
        selected["start_time"],
        utc=True,
    )

    summary_rows = []

    for _, case in selected.iterrows():

        horizon = int(
            case["horizon_hours"]
        )

        requested_start = case[
            "start_time"
        ]

        requested_end = (
            requested_start
            +
            pd.Timedelta(hours=horizon)
        )

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # Use only points INSIDE the requested window.
        # Never extend the route beyond the target time.
        # ----------------------------------------------------

        segment = track[
            (
                track["timestamp"]
                >= requested_start
            )
            &
            (
                track["timestamp"]
                <= requested_end
            )
        ].copy()

        segment = (
            segment
            .sort_values("timestamp")
            .reset_index(drop=True)
        )

        if len(segment) < 2:
            raise RuntimeError(
                f"Not enough AIS points for {horizon}h case."
            )

        actual_start = segment.iloc[0]
        actual_end = segment.iloc[-1]

        actual_start_time = actual_start[
            "timestamp"
        ]

        actual_end_time = actual_end[
            "timestamp"
        ]

        start_error_minutes = (
            (
                actual_start_time
                -
                requested_start
            )
            .total_seconds()
            /
            60.0
        )

        end_shortfall_minutes = (
            (
                requested_end
                -
                actual_end_time
            )
            .total_seconds()
            /
            60.0
        )

        effective_duration_hours = (
            (
                actual_end_time
                -
                actual_start_time
            )
            .total_seconds()
            /
            3600.0
        )

        actual_distance = (
            route_distance_km(
                segment
            )
        )

        direct_distance = float(
            haversine_km(
                actual_start["lat"],
                actual_start["lon"],
                actual_end["lat"],
                actual_end["lon"],
            )
        )

        efficiency = (
            direct_distance
            /
            actual_distance
            *
            100.0
            if actual_distance > 0
            else np.nan
        )

        output_file = (
            OUTPUT_DIR
            /
            f"ps124_selected_{horizon}h_actual.csv"
        )

        segment.to_csv(
            output_file,
            index=False,
        )

        print()
        print("=" * 100)
        print(
            f"{horizon}H SELECTED CASE"
        )
        print("=" * 100)

        print(
            "Requested start :",
            requested_start,
        )

        print(
            "Actual start    :",
            actual_start_time,
        )

        print(
            f"Start delay     : "
            f"{start_error_minutes:.2f} min"
        )

        print()

        print(
            "Requested end   :",
            requested_end,
        )

        print(
            "Actual last AIS :",
            actual_end_time,
        )

        print(
            f"End shortfall   : "
            f"{end_shortfall_minutes:.2f} min"
        )

        print(
            f"Effective hours : "
            f"{effective_duration_hours:.2f} h"
        )

        print()

        print(
            f"Start position  : "
            f"{float(actual_start['lat']):.6f}, "
            f"{float(actual_start['lon']):.6f}"
        )

        print(
            f"Destination     : "
            f"{float(actual_end['lat']):.6f}, "
            f"{float(actual_end['lon']):.6f}"
        )

        print()

        print(
            f"AIS points      : "
            f"{len(segment):,}"
        )

        print(
            f"AIS distance    : "
            f"{actual_distance:.2f} km"
        )

        print(
            f"Direct distance : "
            f"{direct_distance:.2f} km"
        )

        print(
            f"Efficiency      : "
            f"{efficiency:.2f}%"
        )

        print(
            "Saved:",
            output_file,
        )

        summary_rows.append(
            {
                "horizon_hours":
                    horizon,

                "requested_start_time":
                    requested_start,

                "actual_start_time":
                    actual_start_time,

                "start_delay_minutes":
                    start_error_minutes,

                "requested_end_time":
                    requested_end,

                "actual_end_time":
                    actual_end_time,

                "end_shortfall_minutes":
                    end_shortfall_minutes,

                "effective_duration_hours":
                    effective_duration_hours,

                "initialization_date":
                    requested_start.strftime(
                        "%Y-%m-%d"
                    ),

                "start_latitude":
                    float(
                        actual_start["lat"]
                    ),

                "start_longitude":
                    float(
                        actual_start["lon"]
                    ),

                "destination_latitude":
                    float(
                        actual_end["lat"]
                    ),

                "destination_longitude":
                    float(
                        actual_end["lon"]
                    ),

                "ais_points":
                    len(segment),

                "actual_route_distance_km":
                    actual_distance,

                "direct_distance_km":
                    direct_distance,

                "geometric_efficiency_pct":
                    efficiency,

                "scan_mean_sic_pct":
                    float(
                        case["mean_sic_pct"]
                    ),

                "scan_max_sic_pct":
                    float(
                        case["max_sic_pct"]
                    ),

                "scan_points_in_ice_ge_15_pct":
                    float(
                        case[
                            "points_in_ice_ge_15_pct"
                        ]
                    ),

                "valid_sic_coverage_pct":
                    float(
                        case[
                            "valid_sic_coverage_pct"
                        ]
                    ),

                "segment_file":
                    str(output_file),
            }
        )

    summary = (
        pd.DataFrame(summary_rows)
        .sort_values("horizon_hours")
    )

    summary_file = (
        OUTPUT_DIR
        /
        "ps124_selected_case_definitions.csv"
    )

    summary.to_csv(
        summary_file,
        index=False,
    )

    print()
    print("=" * 100)
    print("CORRECTED SELECTED CASE MATRIX")
    print("=" * 100)

    display = summary[
        [
            "horizon_hours",
            "actual_start_time",
            "actual_end_time",
            "end_shortfall_minutes",
            "effective_duration_hours",
            "start_latitude",
            "start_longitude",
            "destination_latitude",
            "destination_longitude",
            "ais_points",
            "actual_route_distance_km",
            "direct_distance_km",
            "geometric_efficiency_pct",
            "scan_mean_sic_pct",
            "scan_max_sic_pct",
        ]
    ].copy()

    numeric = [
        "end_shortfall_minutes",
        "effective_duration_hours",
        "start_latitude",
        "start_longitude",
        "destination_latitude",
        "destination_longitude",
        "actual_route_distance_km",
        "direct_distance_km",
        "geometric_efficiency_pct",
        "scan_mean_sic_pct",
        "scan_max_sic_pct",
    ]

    display[numeric] = (
        display[numeric]
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
    print("OUTPUT")
    print("=" * 100)

    print(summary_file)

    print()
    print("=" * 100)
    print("CORRECTED PS124 CASES FROZEN")
    print("=" * 100)


if __name__ == "__main__":
    main()