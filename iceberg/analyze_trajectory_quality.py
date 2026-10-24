from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# PATHS
# ============================================================

INPUT_FILE = Path(
    "iceberg/data/processed/byu_trajectories_2019_2025.csv"
)

OUTPUT_DIR = Path(
    "iceberg/data/processed"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# HAVERSINE DISTANCE
# ============================================================

def haversine_km(lat1, lon1, lat2, lon2):
    """
    Great-circle distance between two latitude/longitude points.

    Handles the ±180 degree dateline correctly.
    """

    lat1 = np.radians(lat1)
    lat2 = np.radians(lat2)

    lon1 = np.radians(lon1)
    lon2 = np.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    # Normalize longitude difference to [-pi, pi]
    dlon = (
        dlon + np.pi
    ) % (2 * np.pi) - np.pi

    a = (
        np.sin(dlat / 2.0) ** 2
        +
        np.cos(lat1)
        * np.cos(lat2)
        * np.sin(dlon / 2.0) ** 2
    )

    c = 2 * np.arctan2(
        np.sqrt(a),
        np.sqrt(1 - a)
    )

    earth_radius_km = 6371.0088

    return earth_radius_km * c


# ============================================================
# LOAD DATA
# ============================================================

print("=" * 75)
print("ICEBERG TRAJECTORY QUALITY ANALYSIS")
print("=" * 75)

df = pd.read_csv(
    INPUT_FILE,
    parse_dates=["date"]
)

df = df.sort_values(
    [
        "iceberg_id",
        "date",
    ]
).reset_index(drop=True)

print(
    f"\nObservations loaded: {len(df):,}"
)

print(
    f"Unique icebergs: {df['iceberg_id'].nunique():,}"
)

print(
    f"Date range: "
    f"{df['date'].min()} to {df['date'].max()}"
)


# ============================================================
# PREVIOUS OBSERVATION
# ============================================================

grouped = df.groupby(
    "iceberg_id",
    group_keys=False
)

df["prev_date"] = grouped["date"].shift(1)

df["prev_latitude"] = grouped[
    "latitude"
].shift(1)

df["prev_longitude"] = grouped[
    "longitude"
].shift(1)


# ============================================================
# TIME GAP
# ============================================================

df["gap_days"] = (
    df["date"]
    - df["prev_date"]
).dt.total_seconds() / 86400.0


# ============================================================
# DISTANCE BETWEEN OBSERVATIONS
# ============================================================

valid_previous = (
    df["prev_latitude"].notna()
    &
    df["prev_longitude"].notna()
    &
    df["gap_days"].notna()
    &
    (df["gap_days"] > 0)
)

df["distance_km"] = np.nan

df.loc[
    valid_previous,
    "distance_km"
] = haversine_km(
    df.loc[valid_previous, "prev_latitude"].to_numpy(),
    df.loc[valid_previous, "prev_longitude"].to_numpy(),
    df.loc[valid_previous, "latitude"].to_numpy(),
    df.loc[valid_previous, "longitude"].to_numpy(),
)


# ============================================================
# SPEED
# ============================================================

df["speed_km_per_day"] = (
    df["distance_km"]
    /
    df["gap_days"]
)

df["speed_m_per_s"] = (
    df["speed_km_per_day"]
    * 1000
    / 86400
)


# ============================================================
# DATE GAP ANALYSIS
# ============================================================

gap_data = df[
    df["gap_days"].notna()
].copy()

print("\n" + "=" * 75)
print("TIME GAP ANALYSIS")
print("=" * 75)

print(
    f"Observation transitions: {len(gap_data):,}"
)

daily = (
    gap_data["gap_days"] == 1
).sum()

print(
    f"Exactly 1-day gaps: {daily:,}"
)

print(
    f"Percentage exactly daily: "
    f"{100 * daily / len(gap_data):.2f}%"
)

print("\nMost common gaps:")

print(
    gap_data["gap_days"]
    .value_counts()
    .sort_index()
    .head(20)
)


# ============================================================
# SPEED DISTRIBUTION
# ============================================================

speed = df[
    (df["gap_days"] == 1)
    &
    df["speed_km_per_day"].notna()
]["speed_km_per_day"]

print("\n" + "=" * 75)
print("DAILY SPEED DISTRIBUTION")
print("=" * 75)

percentiles = [
    0,
    1,
    5,
    25,
    50,
    75,
    90,
    95,
    99,
    99.5,
    99.9,
    100,
]

for p in percentiles:

    value = np.percentile(
        speed,
        p
    )

    print(
        f"{p:>5}% : "
        f"{value:10.3f} km/day"
    )


# ============================================================
# ZERO-MOVEMENT ANALYSIS
# ============================================================

zero_movement = (
    speed < 0.001
).sum()

print("\nZero / near-zero daily movement:")

print(
    f"{zero_movement:,} transitions "
    f"({100 * zero_movement / len(speed):.2f}%)"
)


# ============================================================
# LARGE JUMP COUNTS
# ============================================================

print("\n" + "=" * 75)
print("LARGE DAILY MOVEMENT COUNTS")
print("=" * 75)

thresholds = [
    25,
    50,
    100,
    150,
    200,
    300,
    500,
    1000,
]

for threshold in thresholds:

    count = (
        speed > threshold
    ).sum()

    percentage = (
        100 * count / len(speed)
    )

    print(
        f"> {threshold:4} km/day : "
        f"{count:6,} "
        f"({percentage:.4f}%)"
    )


# ============================================================
# BUILD DATE LOOKUP
# ============================================================

print("\n" + "=" * 75)
print("CHECKING 7-DAY TRAJECTORY WINDOWS")
print("=" * 75)

date_sets = {}

for iceberg_id, group in df.groupby(
    "iceberg_id"
):

    date_sets[iceberg_id] = set(
        group["date"]
    )


# ============================================================
# COUNT VALID FORECAST WINDOWS
# ============================================================

valid_windows = []

for iceberg_id, group in df.groupby(
    "iceberg_id"
):

    available_dates = date_sets[
        iceberg_id
    ]

    for _, row in group.iterrows():

        current_date = row["date"]

        required_dates = [
            current_date - pd.Timedelta(days=3),
            current_date - pd.Timedelta(days=2),
            current_date - pd.Timedelta(days=1),
            current_date,
            current_date + pd.Timedelta(days=1),
            current_date + pd.Timedelta(days=2),
            current_date + pd.Timedelta(days=3),
        ]

        if all(
            required_date in available_dates
            for required_date in required_dates
        ):

            valid_windows.append(
                {
                    "iceberg_id": iceberg_id,
                    "init_date": current_date,
                }
            )


windows = pd.DataFrame(
    valid_windows
)


# ============================================================
# WINDOW SUMMARY
# ============================================================

print(
    f"\nComplete 7-day windows: "
    f"{len(windows):,}"
)

if len(windows) > 0:

    print(
        f"Unique icebergs with valid windows: "
        f"{windows['iceberg_id'].nunique():,}"
    )

    print("\nWindows by year:")

    print(
        windows["init_date"]
        .dt.year
        .value_counts()
        .sort_index()
    )

    print("\nTop 20 icebergs by valid windows:")

    print(
        windows["iceberg_id"]
        .value_counts()
        .head(20)
    )


# ============================================================
# TRAIN / VALIDATION / TEST POSSIBILITY
# ============================================================

if len(windows) > 0:

    train = windows[
        windows["init_date"].dt.year
        <= 2023
    ]

    validation = windows[
        windows["init_date"].dt.year
        == 2024
    ]

    test = windows[
        windows["init_date"].dt.year
        == 2025
    ]

    print("\n" + "=" * 75)
    print("POSSIBLE CHRONOLOGICAL SPLIT")
    print("=" * 75)

    print(
        f"Train 2019-2023 : {len(train):,}"
    )

    print(
        f"Validation 2024 : {len(validation):,}"
    )

    print(
        f"Test 2025       : {len(test):,}"
    )


# ============================================================
# SAVE ANALYSIS
# ============================================================

quality_output = (
    OUTPUT_DIR
    / "trajectory_quality_2019_2025.csv"
)

df.to_csv(
    quality_output,
    index=False
)


windows_output = (
    OUTPUT_DIR
    / "valid_7day_windows_2019_2025.csv"
)

windows.to_csv(
    windows_output,
    index=False
)


print("\n" + "=" * 75)
print("FILES SAVED")
print("=" * 75)

print(quality_output)
print(windows_output)


print("\n" + "=" * 75)
print("TRAJECTORY QUALITY ANALYSIS COMPLETE")
print("=" * 75)