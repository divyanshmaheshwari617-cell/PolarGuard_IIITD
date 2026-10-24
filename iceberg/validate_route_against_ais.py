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
# TEST CONFIGURATION
# ============================================================

# First clean southbound Drake Passage / Antarctic test.
TEST_START = "2024-11-29 00:00:00+00:00"
TEST_END = "2024-12-02 23:59:59+00:00"

# This is the historical initialization date that will later
# be passed to PolarGuard Member 1.
INITIALIZATION_DATE = "2024-11-29"


EARTH_RADIUS_KM = 6371.0088


# ============================================================
# DISTANCE
# ============================================================

def haversine_km(lat1, lon1, lat2, lon2):

    lat1 = np.radians(lat1)
    lon1 = np.radians(lon1)

    lat2 = np.radians(lat2)
    lon2 = np.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        np.sin(dlat / 2.0) ** 2
        +
        np.cos(lat1)
        * np.cos(lat2)
        * np.sin(dlon / 2.0) ** 2
    )

    a = np.clip(a, 0.0, 1.0)

    return (
        2.0
        * EARTH_RADIUS_KM
        * np.arcsin(np.sqrt(a))
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 90)
    print("POLARGUARD")
    print("OCEANNOVA HISTORICAL AIS ROUTE VALIDATION")
    print("=" * 90)

    # --------------------------------------------------------
    # LOAD REAL AIS
    # --------------------------------------------------------

    df = pd.read_csv(AIS_FILE)

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        utc=True,
    )

    df = (
        df
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    start_time = pd.Timestamp(TEST_START)
    end_time = pd.Timestamp(TEST_END)

    voyage = df[
        (df["timestamp"] >= start_time)
        &
        (df["timestamp"] <= end_time)
    ].copy()

    voyage = voyage.reset_index(drop=True)

    if len(voyage) < 2:
        raise RuntimeError(
            "Not enough AIS points in selected voyage."
        )

    # --------------------------------------------------------
    # CALCULATE REAL ROUTE DISTANCE
    # --------------------------------------------------------

    voyage["previous_lat"] = voyage["lat"].shift(1)
    voyage["previous_lon"] = voyage["lon"].shift(1)

    voyage["step_distance_km"] = haversine_km(
        voyage["previous_lat"],
        voyage["previous_lon"],
        voyage["lat"],
        voyage["lon"],
    )

    actual_distance_km = float(
        voyage["step_distance_km"]
        .fillna(0.0)
        .sum()
    )

    # --------------------------------------------------------
    # START / END
    # --------------------------------------------------------

    start = voyage.iloc[0]
    destination = voyage.iloc[-1]

    direct_distance_km = float(
        haversine_km(
            start["lat"],
            start["lon"],
            destination["lat"],
            destination["lon"],
        )
    )

    route_efficiency = (
        direct_distance_km
        / actual_distance_km
        * 100.0
        if actual_distance_km > 0
        else np.nan
    )

    # --------------------------------------------------------
    # PRINT TEST CASE
    # --------------------------------------------------------

    print()
    print("AIS SOURCE:")
    print(AIS_FILE)

    print()
    print("TEST PERIOD")
    print("-" * 90)

    print(
        "Start:",
        voyage["timestamp"].iloc[0],
    )

    print(
        "End  :",
        voyage["timestamp"].iloc[-1],
    )

    print(
        f"AIS observations: {len(voyage):,}"
    )

    print()
    print("START POSITION")
    print("-" * 90)

    print(
        f"Latitude : {start['lat']:.6f}"
    )

    print(
        f"Longitude: {start['lon']:.6f}"
    )

    print()
    print("DESTINATION POSITION")
    print("-" * 90)

    print(
        f"Latitude : {destination['lat']:.6f}"
    )

    print(
        f"Longitude: {destination['lon']:.6f}"
    )

    print()
    print("ACTUAL AIS ROUTE")
    print("-" * 90)

    print(
        f"Actual travelled distance : "
        f"{actual_distance_km:.2f} km"
    )

    print(
        f"Straight-line distance    : "
        f"{direct_distance_km:.2f} km"
    )

    print(
        f"Geometric route efficiency: "
        f"{route_efficiency:.2f}%"
    )

    print()
    print("POLARGUARD HISTORICAL INITIALIZATION")
    print("-" * 90)

    print(
        "Member 1 initialization date:",
        INITIALIZATION_DATE,
    )

    # --------------------------------------------------------
    # SAVE EXACT TEST SEGMENT
    # --------------------------------------------------------

    output_file = (
        OUTPUT_DIR
        / "oceannova_actual_route_test1.csv"
    )

    voyage.to_csv(
        output_file,
        index=False,
    )

    test_definition = pd.DataFrame(
        [
            {
                "test_name":
                    "oceannova_southbound_test1",

                "initialization_date":
                    INITIALIZATION_DATE,

                "start_timestamp":
                    voyage["timestamp"].iloc[0],

                "end_timestamp":
                    voyage["timestamp"].iloc[-1],

                "start_latitude":
                    float(start["lat"]),

                "start_longitude":
                    float(start["lon"]),

                "destination_latitude":
                    float(destination["lat"]),

                "destination_longitude":
                    float(destination["lon"]),

                "ais_points":
                    len(voyage),

                "actual_route_distance_km":
                    actual_distance_km,

                "direct_distance_km":
                    direct_distance_km,

                "geometric_efficiency_pct":
                    route_efficiency,
            }
        ]
    )

    definition_file = (
        OUTPUT_DIR
        / "oceannova_test1_definition.csv"
    )

    test_definition.to_csv(
        definition_file,
        index=False,
    )

    print()
    print("=" * 90)
    print("FILES CREATED")
    print("=" * 90)

    print(output_file)
    print(definition_file)

    print()
    print("=" * 90)
    print("STAGE 1 COMPLETE")
    print("=" * 90)

    print()
    print(
        "The real AIS test case is now frozen."
    )

    print(
        "Next stage: run the existing PolarGuard historical "
        "routing pipeline for this exact test case."
    )


if __name__ == "__main__":
    main()