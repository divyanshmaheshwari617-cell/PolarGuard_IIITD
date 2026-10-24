from pathlib import Path

import numpy as np
import pandas as pd


BASE = Path(__file__).resolve().parent.parent

AIS_FILE = (
    BASE
    / "data"
    / "ais"
    / "oceannova_2024"
    / "track-data-2024-11-29,2024-12-31.csv"
)

OUTPUT_DIR = (
    BASE
    / "data"
    / "ais"
    / "oceannova_2024"
    / "analysis"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


EARTH_RADIUS_KM = 6371.0088


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

    a = np.clip(a, 0, 1)

    return (
        2.0
        * EARTH_RADIUS_KM
        * np.arcsin(np.sqrt(a))
    )


def main():

    print("=" * 80)
    print("POLARGUARD")
    print("OCEANNOVA AIS TRACK ANALYSIS")
    print("=" * 80)

    df = pd.read_csv(AIS_FILE)

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        utc=True
    )

    df = (
        df
        .sort_values("timestamp")
        .drop_duplicates(
            subset=["timestamp", "lat", "lon"]
        )
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # Consecutive-point movement
    # --------------------------------------------------------

    df["previous_lat"] = df["lat"].shift(1)
    df["previous_lon"] = df["lon"].shift(1)
    df["previous_time"] = df["timestamp"].shift(1)

    df["step_distance_km"] = haversine_km(
        df["previous_lat"],
        df["previous_lon"],
        df["lat"],
        df["lon"],
    )

    df["time_gap_hours"] = (
        (
            df["timestamp"]
            - df["previous_time"]
        )
        .dt.total_seconds()
        / 3600.0
    )

    # --------------------------------------------------------
    # Daily summary
    # --------------------------------------------------------

    df["date"] = (
        df["timestamp"]
        .dt.date
    )

    daily_rows = []

    for date, group in df.groupby("date"):

        group = group.sort_values(
            "timestamp"
        )

        distance = float(
            group["step_distance_km"]
            .fillna(0)
            .sum()
        )

        moving = group[
            group["speed"] >= 2.0
        ]

        daily_rows.append(
            {
                "date": date,

                "points":
                    len(group),

                "start_time":
                    group[
                        "timestamp"
                    ].iloc[0],

                "end_time":
                    group[
                        "timestamp"
                    ].iloc[-1],

                "start_lat":
                    group["lat"].iloc[0],

                "start_lon":
                    group["lon"].iloc[0],

                "end_lat":
                    group["lat"].iloc[-1],

                "end_lon":
                    group["lon"].iloc[-1],

                "distance_km":
                    distance,

                "mean_speed":
                    float(
                        group["speed"].mean()
                    ),

                "max_speed":
                    float(
                        group["speed"].max()
                    ),

                "moving_points":
                    len(moving),

                "min_lat":
                    float(
                        group["lat"].min()
                    ),

                "max_lat":
                    float(
                        group["lat"].max()
                    ),

                "min_lon":
                    float(
                        group["lon"].min()
                    ),

                "max_lon":
                    float(
                        group["lon"].max()
                    ),
            }
        )

    daily = pd.DataFrame(
        daily_rows
    )

    # --------------------------------------------------------
    # Detect large temporal gaps
    # --------------------------------------------------------

    gaps = df[
        df["time_gap_hours"] >= 3
    ][
        [
            "previous_time",
            "timestamp",
            "time_gap_hours",
            "previous_lat",
            "previous_lon",
            "lat",
            "lon",
        ]
    ].copy()

    # --------------------------------------------------------
    # Candidate route periods
    #
    # These are days with substantial movement.
    # --------------------------------------------------------

    candidates = daily[
        (daily["distance_km"] >= 100)
        &
        (daily["moving_points"] >= 5)
    ].copy()

    candidates = candidates.sort_values(
        "distance_km",
        ascending=False
    )

    # --------------------------------------------------------
    # Overall statistics
    # --------------------------------------------------------

    total_distance = float(
        df["step_distance_km"]
        .fillna(0)
        .sum()
    )

    print()
    print("AIS FILE:")
    print(AIS_FILE)

    print()
    print(f"Rows: {len(df):,}")

    print(
        "Time range:",
        df["timestamp"].min(),
        "to",
        df["timestamp"].max()
    )

    print(
        "Unique segments:",
        df["seg_id"].nunique()
    )

    print(
        f"Total point-to-point distance: "
        f"{total_distance:,.2f} km"
    )

    print()
    print("Geographic extent:")

    print(
        f"Latitude : "
        f"{df['lat'].min():.4f} "
        f"to "
        f"{df['lat'].max():.4f}"
    )

    print(
        f"Longitude: "
        f"{df['lon'].min():.4f} "
        f"to "
        f"{df['lon'].max():.4f}"
    )

    print()
    print("=" * 80)
    print("DAILY MOVEMENT")
    print("=" * 80)

    print()

    print(
        daily[
            [
                "date",
                "points",
                "start_lat",
                "start_lon",
                "end_lat",
                "end_lon",
                "distance_km",
                "mean_speed",
                "max_speed",
            ]
        ]
        .round(3)
        .to_string(index=False)
    )

    print()
    print("=" * 80)
    print("CANDIDATE ROUTE DAYS >= 100 KM")
    print("=" * 80)

    print()

    if len(candidates):

        print(
            candidates[
                [
                    "date",
                    "points",
                    "start_lat",
                    "start_lon",
                    "end_lat",
                    "end_lon",
                    "distance_km",
                    "mean_speed",
                    "max_speed",
                ]
            ]
            .head(15)
            .round(3)
            .to_string(index=False)
        )

    else:

        print(
            "No candidate days found."
        )

    print()
    print("=" * 80)
    print("AIS GAPS >= 3 HOURS")
    print("=" * 80)

    print()

    if len(gaps):

        print(
            gaps
            .head(20)
            .to_string(index=False)
        )

    else:

        print(
            "No >=3 hour gaps detected."
        )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    cleaned_file = (
        OUTPUT_DIR
        / "oceannova_cleaned_track.csv"
    )

    daily_file = (
        OUTPUT_DIR
        / "oceannova_daily_summary.csv"
    )

    candidates_file = (
        OUTPUT_DIR
        / "oceannova_candidate_route_days.csv"
    )

    gaps_file = (
        OUTPUT_DIR
        / "oceannova_ais_gaps.csv"
    )

    df.to_csv(
        cleaned_file,
        index=False
    )

    daily.to_csv(
        daily_file,
        index=False
    )

    candidates.to_csv(
        candidates_file,
        index=False
    )

    gaps.to_csv(
        gaps_file,
        index=False
    )

    print()
    print("=" * 80)
    print("FILES CREATED")
    print("=" * 80)

    print(cleaned_file)
    print(daily_file)
    print(candidates_file)
    print(gaps_file)

    print()
    print("=" * 80)
    print("AIS ANALYSIS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()