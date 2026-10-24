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

OUTPUT_FILE = (
    OUTPUT_DIR
    / "iceberg_trajectory_features_2019_2025.csv"
)


# ============================================================
# SETTINGS
# ============================================================

MAX_DAILY_SPEED_KM = 100.0

EARTH_RADIUS_KM = 6371.0088


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def wrapped_lon_difference(lon2, lon1):
    """
    Return longitude difference in degrees,
    safely handling the ±180° dateline.
    """

    return (
        (lon2 - lon1 + 180.0) % 360.0
    ) - 180.0


def displacement_east_north_km(
    lat1,
    lon1,
    lat2,
    lon2
):
    """
    Approximate local east/north displacement
    between two nearby geographic coordinates.

    Returns:
        dx_km : east-west displacement
        dy_km : north-south displacement

    Positive dx = eastward
    Negative dx = westward

    Positive dy = northward
    Negative dy = southward
    """

    lat1_rad = np.radians(lat1)
    lat2_rad = np.radians(lat2)

    dlat_rad = (
        lat2_rad
        - lat1_rad
    )

    dlon_deg = wrapped_lon_difference(
        lon2,
        lon1
    )

    dlon_rad = np.radians(
        dlon_deg
    )

    mean_lat_rad = (
        lat1_rad
        + lat2_rad
    ) / 2.0

    dy_km = (
        EARTH_RADIUS_KM
        * dlat_rad
    )

    dx_km = (
        EARTH_RADIUS_KM
        * np.cos(mean_lat_rad)
        * dlon_rad
    )

    return dx_km, dy_km


def distance_km(
    lat1,
    lon1,
    lat2,
    lon2
):
    """
    Great-circle Haversine distance.
    """

    lat1 = np.radians(lat1)
    lat2 = np.radians(lat2)

    lon1 = np.radians(lon1)
    lon2 = np.radians(lon2)

    dlat = (
        lat2
        - lat1
    )

    dlon = (
        lon2
        - lon1
    )

    dlon = (
        dlon
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
        * np.cos(lat2)
        * np.sin(
            dlon / 2.0
        ) ** 2
    )

    c = 2.0 * np.arctan2(
        np.sqrt(a),
        np.sqrt(1.0 - a)
    )

    return (
        EARTH_RADIUS_KM
        * c
    )


# ============================================================
# LOAD DATA
# ============================================================

print("=" * 75)
print("BUILDING ICEBERG TRAJECTORY FEATURES")
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
    f"Unique icebergs: "
    f"{df['iceberg_id'].nunique():,}"
)

print(
    f"Date range: "
    f"{df['date'].min()} "
    f"to "
    f"{df['date'].max()}"
)


# ============================================================
# BUILD FAST ICEBERG / DATE LOOKUP
# ============================================================

print("\nBuilding iceberg-date lookup...")

lookup = {}

for iceberg_id, group in df.groupby(
    "iceberg_id"
):

    iceberg_lookup = {}

    for row in group.itertuples(
        index=False
    ):

        iceberg_lookup[
            row.date
        ] = {
            "latitude": float(
                row.latitude
            ),
            "longitude": float(
                row.longitude
            ),
            "sensors_used": row.sensors_used,
            "sensor_count": row.sensor_count,
        }

    lookup[
        iceberg_id
    ] = iceberg_lookup


print("Lookup complete.")


# ============================================================
# BUILD TRAINING SAMPLES
# ============================================================

samples = []

rejected_missing_dates = 0
rejected_extreme_speed = 0

processed_windows = 0


print("\nBuilding 7-day trajectory samples...")


for iceberg_number, (
    iceberg_id,
    observations
) in enumerate(
    lookup.items(),
    start=1
):

    available_dates = set(
        observations.keys()
    )

    for current_date in sorted(
        available_dates
    ):

        # ----------------------------------------------------
        # REQUIRED DATES
        #
        # History:
        # t-3, t-2, t-1, t
        #
        # Targets:
        # t+1, t+2, t+3
        # ----------------------------------------------------

        dates = {
            "tm3": (
                current_date
                - pd.Timedelta(days=3)
            ),
            "tm2": (
                current_date
                - pd.Timedelta(days=2)
            ),
            "tm1": (
                current_date
                - pd.Timedelta(days=1)
            ),
            "t": current_date,
            "tp1": (
                current_date
                + pd.Timedelta(days=1)
            ),
            "tp2": (
                current_date
                + pd.Timedelta(days=2)
            ),
            "tp3": (
                current_date
                + pd.Timedelta(days=3)
            ),
        }

        if not all(
            date in available_dates
            for date in dates.values()
        ):
            rejected_missing_dates += 1
            continue

        processed_windows += 1

        # ----------------------------------------------------
        # GET POSITIONS
        # ----------------------------------------------------

        p_tm3 = observations[
            dates["tm3"]
        ]

        p_tm2 = observations[
            dates["tm2"]
        ]

        p_tm1 = observations[
            dates["tm1"]
        ]

        p_t = observations[
            dates["t"]
        ]

        p_tp1 = observations[
            dates["tp1"]
        ]

        p_tp2 = observations[
            dates["tp2"]
        ]

        p_tp3 = observations[
            dates["tp3"]
        ]


        # ----------------------------------------------------
        # DAILY DISTANCES
        #
        # Check all transitions inside the 7-day window.
        # ----------------------------------------------------

        seven_points = [
            p_tm3,
            p_tm2,
            p_tm1,
            p_t,
            p_tp1,
            p_tp2,
            p_tp3,
        ]

        daily_distances = []

        bad_window = False

        for j in range(
            len(seven_points) - 1
        ):

            point_a = seven_points[j]
            point_b = seven_points[j + 1]

            movement = distance_km(
                point_a["latitude"],
                point_a["longitude"],
                point_b["latitude"],
                point_b["longitude"],
            )

            daily_distances.append(
                movement
            )

            if (
                movement
                > MAX_DAILY_SPEED_KM
            ):
                bad_window = True
                break

        if bad_window:
            rejected_extreme_speed += 1
            continue


        # ====================================================
        # PAST VELOCITY / DISPLACEMENT FEATURES
        # ====================================================

        # t-3 -> t-2
        dx_3, dy_3 = (
            displacement_east_north_km(
                p_tm3["latitude"],
                p_tm3["longitude"],
                p_tm2["latitude"],
                p_tm2["longitude"],
            )
        )

        # t-2 -> t-1
        dx_2, dy_2 = (
            displacement_east_north_km(
                p_tm2["latitude"],
                p_tm2["longitude"],
                p_tm1["latitude"],
                p_tm1["longitude"],
            )
        )

        # t-1 -> t
        dx_1, dy_1 = (
            displacement_east_north_km(
                p_tm1["latitude"],
                p_tm1["longitude"],
                p_t["latitude"],
                p_t["longitude"],
            )
        )


        # ====================================================
        # SPEED FEATURES
        # ====================================================

        speed_tm3_tm2 = np.sqrt(
            dx_3 ** 2
            +
            dy_3 ** 2
        )

        speed_tm2_tm1 = np.sqrt(
            dx_2 ** 2
            +
            dy_2 ** 2
        )

        speed_tm1_t = np.sqrt(
            dx_1 ** 2
            +
            dy_1 ** 2
        )


        # ====================================================
        # ACCELERATION FEATURES
        # ====================================================

        accel_x_recent = (
            dx_1
            - dx_2
        )

        accel_y_recent = (
            dy_1
            - dy_2
        )

        accel_x_previous = (
            dx_2
            - dx_3
        )

        accel_y_previous = (
            dy_2
            - dy_3
        )


        # ====================================================
        # RECENT AVERAGE VELOCITY
        # ====================================================

        mean_vx_3day = np.mean(
            [
                dx_3,
                dx_2,
                dx_1,
            ]
        )

        mean_vy_3day = np.mean(
            [
                dy_3,
                dy_2,
                dy_1,
            ]
        )


        mean_speed_3day = np.mean(
            [
                speed_tm3_tm2,
                speed_tm2_tm1,
                speed_tm1_t,
            ]
        )


        # ====================================================
        # SEASONAL FEATURES
        # ====================================================

        day_of_year = (
            current_date.dayofyear
        )

        doy_sin = np.sin(
            2.0
            * np.pi
            * day_of_year
            / 365.25
        )

        doy_cos = np.cos(
            2.0
            * np.pi
            * day_of_year
            / 365.25
        )


        # ====================================================
        # FUTURE TARGET DISPLACEMENTS
        #
        # IMPORTANT:
        # These are measured from current time t.
        # ====================================================

        target_dx_24h, target_dy_24h = (
            displacement_east_north_km(
                p_t["latitude"],
                p_t["longitude"],
                p_tp1["latitude"],
                p_tp1["longitude"],
            )
        )

        target_dx_48h, target_dy_48h = (
            displacement_east_north_km(
                p_t["latitude"],
                p_t["longitude"],
                p_tp2["latitude"],
                p_tp2["longitude"],
            )
        )

        target_dx_72h, target_dy_72h = (
            displacement_east_north_km(
                p_t["latitude"],
                p_t["longitude"],
                p_tp3["latitude"],
                p_tp3["longitude"],
            )
        )


        # ====================================================
        # FUTURE TRUE POSITIONS
        #
        # Useful later for evaluating geodesic position error.
        # ====================================================

        true_lat_24h = (
            p_tp1["latitude"]
        )

        true_lon_24h = (
            p_tp1["longitude"]
        )

        true_lat_48h = (
            p_tp2["latitude"]
        )

        true_lon_48h = (
            p_tp2["longitude"]
        )

        true_lat_72h = (
            p_tp3["latitude"]
        )

        true_lon_72h = (
            p_tp3["longitude"]
        )


        # ====================================================
        # STORE SAMPLE
        # ====================================================

        samples.append(
            {
                # --------------------------------------------
                # IDENTIFIERS
                # --------------------------------------------

                "iceberg_id": iceberg_id,
                "init_date": current_date,

                # --------------------------------------------
                # CURRENT POSITION
                # --------------------------------------------

                "current_latitude": (
                    p_t["latitude"]
                ),

                "current_longitude": (
                    p_t["longitude"]
                ),

                # --------------------------------------------
                # POSITION HISTORY
                # --------------------------------------------

                "lat_tm1": (
                    p_tm1["latitude"]
                ),

                "lon_tm1": (
                    p_tm1["longitude"]
                ),

                "lat_tm2": (
                    p_tm2["latitude"]
                ),

                "lon_tm2": (
                    p_tm2["longitude"]
                ),

                "lat_tm3": (
                    p_tm3["latitude"]
                ),

                "lon_tm3": (
                    p_tm3["longitude"]
                ),

                # --------------------------------------------
                # DAILY VELOCITY / DISPLACEMENT FEATURES
                # --------------------------------------------

                "vx_tm3_tm2": dx_3,
                "vy_tm3_tm2": dy_3,

                "vx_tm2_tm1": dx_2,
                "vy_tm2_tm1": dy_2,

                "vx_tm1_t": dx_1,
                "vy_tm1_t": dy_1,

                # --------------------------------------------
                # SPEED FEATURES
                # --------------------------------------------

                "speed_tm3_tm2": (
                    speed_tm3_tm2
                ),

                "speed_tm2_tm1": (
                    speed_tm2_tm1
                ),

                "speed_tm1_t": (
                    speed_tm1_t
                ),

                # --------------------------------------------
                # ACCELERATION FEATURES
                # --------------------------------------------

                "accel_x_previous": (
                    accel_x_previous
                ),

                "accel_y_previous": (
                    accel_y_previous
                ),

                "accel_x_recent": (
                    accel_x_recent
                ),

                "accel_y_recent": (
                    accel_y_recent
                ),

                # --------------------------------------------
                # RECENT MEAN MOTION
                # --------------------------------------------

                "mean_vx_3day": (
                    mean_vx_3day
                ),

                "mean_vy_3day": (
                    mean_vy_3day
                ),

                "mean_speed_3day": (
                    mean_speed_3day
                ),

                # --------------------------------------------
                # SEASON
                # --------------------------------------------

                "day_of_year": (
                    day_of_year
                ),

                "doy_sin": (
                    doy_sin
                ),

                "doy_cos": (
                    doy_cos
                ),

                # --------------------------------------------
                # SENSOR METADATA
                # --------------------------------------------

                "current_sensors": (
                    p_t["sensors_used"]
                ),

                "current_sensor_count": (
                    p_t["sensor_count"]
                ),

                # --------------------------------------------
                # TARGET DISPLACEMENTS
                # --------------------------------------------

                "target_dx_24h": (
                    target_dx_24h
                ),

                "target_dy_24h": (
                    target_dy_24h
                ),

                "target_dx_48h": (
                    target_dx_48h
                ),

                "target_dy_48h": (
                    target_dy_48h
                ),

                "target_dx_72h": (
                    target_dx_72h
                ),

                "target_dy_72h": (
                    target_dy_72h
                ),

                # --------------------------------------------
                # TRUE FUTURE POSITIONS
                # --------------------------------------------

                "true_lat_24h": (
                    true_lat_24h
                ),

                "true_lon_24h": (
                    true_lon_24h
                ),

                "true_lat_48h": (
                    true_lat_48h
                ),

                "true_lon_48h": (
                    true_lon_48h
                ),

                "true_lat_72h": (
                    true_lat_72h
                ),

                "true_lon_72h": (
                    true_lon_72h
                ),
            }
        )

    if (
        iceberg_number % 20
        == 0
    ):
        print(
            f"Processed "
            f"{iceberg_number}/"
            f"{len(lookup)} icebergs"
        )


# ============================================================
# CREATE FEATURE DATAFRAME
# ============================================================

features = pd.DataFrame(
    samples
)

features = features.sort_values(
    [
        "init_date",
        "iceberg_id",
    ]
).reset_index(drop=True)


# ============================================================
# SUMMARY
# ============================================================

print("\n" + "=" * 75)
print("FEATURE DATASET SUMMARY")
print("=" * 75)

print(
    f"Potential complete windows: "
    f"{processed_windows:,}"
)

print(
    f"Rejected because of missing dates: "
    f"{rejected_missing_dates:,}"
)

print(
    f"Rejected because movement > "
    f"{MAX_DAILY_SPEED_KM:.0f} km/day: "
    f"{rejected_extreme_speed:,}"
)

print(
    f"Final training samples: "
    f"{len(features):,}"
)

print(
    f"Unique icebergs: "
    f"{features['iceberg_id'].nunique():,}"
)


# ============================================================
# YEAR DISTRIBUTION
# ============================================================

print("\nSamples by initialization year:")

year_counts = (
    features["init_date"]
    .dt.year
    .value_counts()
    .sort_index()
)

print(year_counts)


# ============================================================
# CHRONOLOGICAL SPLIT
# ============================================================

train = features[
    features["init_date"].dt.year
    <= 2023
].copy()

validation = features[
    features["init_date"].dt.year
    == 2024
].copy()

test = features[
    features["init_date"].dt.year
    == 2025
].copy()


print("\n" + "=" * 75)
print("CHRONOLOGICAL SPLIT")
print("=" * 75)

print(
    f"Train 2019-2023 : "
    f"{len(train):,}"
)

print(
    f"Validation 2024 : "
    f"{len(validation):,}"
)

print(
    f"Test 2025       : "
    f"{len(test):,}"
)


# ============================================================
# TARGET MOVEMENT SUMMARY
# ============================================================

print("\n" + "=" * 75)
print("TARGET DISPLACEMENT SUMMARY")
print("=" * 75)

for horizon in [
    24,
    48,
    72,
]:

    dx = features[
        f"target_dx_{horizon}h"
    ]

    dy = features[
        f"target_dy_{horizon}h"
    ]

    movement = np.sqrt(
        dx ** 2
        +
        dy ** 2
    )

    print(
        f"\n{horizon}h:"
    )

    print(
        f"  Median displacement : "
        f"{movement.median():.3f} km"
    )

    print(
        f"  Mean displacement   : "
        f"{movement.mean():.3f} km"
    )

    print(
        f"  95th percentile     : "
        f"{movement.quantile(0.95):.3f} km"
    )

    print(
        f"  Maximum              : "
        f"{movement.max():.3f} km"
    )


# ============================================================
# SAVE FULL FEATURE DATASET
# ============================================================

features.to_csv(
    OUTPUT_FILE,
    index=False
)


# ============================================================
# SAVE TRAIN / VALIDATION / TEST
# ============================================================

TRAIN_FILE = (
    OUTPUT_DIR
    / "iceberg_features_train_2019_2023.csv"
)

VALIDATION_FILE = (
    OUTPUT_DIR
    / "iceberg_features_validation_2024.csv"
)

TEST_FILE = (
    OUTPUT_DIR
    / "iceberg_features_test_2025.csv"
)


train.to_csv(
    TRAIN_FILE,
    index=False
)

validation.to_csv(
    VALIDATION_FILE,
    index=False
)

test.to_csv(
    TEST_FILE,
    index=False
)


# ============================================================
# FINAL OUTPUT
# ============================================================

print("\n" + "=" * 75)
print("FILES SAVED")
print("=" * 75)

print(OUTPUT_FILE)
print(TRAIN_FILE)
print(VALIDATION_FILE)
print(TEST_FILE)


print("\nSample feature rows:")

print(
    features.head(5).to_string(
        index=False
    )
)


print("\n" + "=" * 75)
print("TRAJECTORY FEATURE BUILD COMPLETE")
print("=" * 75)