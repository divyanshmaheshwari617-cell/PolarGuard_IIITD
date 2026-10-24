from pathlib import Path
import numpy as np
import pandas as pd

from sklearn.ensemble import HistGradientBoostingRegressor


BASE = Path(__file__).resolve().parent

DATA_FILE = (
    BASE / "data" / "processed" /
    "iceberg_features_environment_ml_ready_2019_2025.csv"
)


TRAJECTORY_FEATURES = [
    "current_latitude",
    "current_longitude",

    "vx_tm3_tm2",
    "vy_tm3_tm2",

    "vx_tm2_tm1",
    "vy_tm2_tm1",

    "vx_tm1_t",
    "vy_tm1_t",

    "speed_tm3_tm2",
    "speed_tm2_tm1",
    "speed_tm1_t",

    "accel_x_previous",
    "accel_y_previous",

    "accel_x_recent",
    "accel_y_recent",

    "mean_vx_3day",
    "mean_vy_3day",
    "mean_speed_3day",

    "doy_sin",
    "doy_cos",
]


FEATURE_SETS = {

    "trajectory_only":
        TRAJECTORY_FEATURES,

    "trajectory_plus_wind":
        TRAJECTORY_FEATURES + [
            "wind_u10",
            "wind_v10",
        ],

    "trajectory_plus_current":
        TRAJECTORY_FEATURES + [
            "ocean_uo",
            "ocean_vo",
        ],

    "trajectory_plus_seaice":
        TRAJECTORY_FEATURES + [
            "sea_ice_sic_filled",
            "sea_ice_available",
        ],

    "trajectory_plus_all":
        TRAJECTORY_FEATURES + [
            "wind_u10",
            "wind_v10",
            "ocean_uo",
            "ocean_vo",
            "sea_ice_sic_filled",
            "sea_ice_available",
        ],
}


HORIZONS = [24, 48, 72]

EARTH_RADIUS_KM = 6371.0088


def destination_from_displacement(
    lat,
    lon,
    dx,
    dy
):

    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    dx = np.asarray(dx, dtype=float)
    dy = np.asarray(dy, dtype=float)

    lat_rad = np.radians(lat)

    pred_lat = (
        lat
        + np.degrees(
            dy / EARTH_RADIUS_KM
        )
    )

    cos_lat = np.cos(lat_rad)

    cos_lat = np.where(
        np.abs(cos_lat) < 1e-8,
        1e-8,
        cos_lat
    )

    pred_lon = (
        lon
        + np.degrees(
            dx /
            (
                EARTH_RADIUS_KM
                * cos_lat
            )
        )
    )

    pred_lon = (
        (pred_lon + 180) % 360
    ) - 180

    return pred_lat, pred_lon


def haversine_km(
    lat1,
    lon1,
    lat2,
    lon2
):

    lat1 = np.radians(
        np.asarray(lat1)
    )

    lon1 = np.radians(
        np.asarray(lon1)
    )

    lat2 = np.radians(
        np.asarray(lat2)
    )

    lon2 = np.radians(
        np.asarray(lon2)
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        np.sin(dlat / 2) ** 2
        +
        np.cos(lat1)
        * np.cos(lat2)
        * np.sin(dlon / 2) ** 2
    )

    a = np.clip(
        a,
        0,
        1
    )

    return (
        2
        * EARTH_RADIUS_KM
        * np.arcsin(
            np.sqrt(a)
        )
    )


def rmse(errors):

    return float(
        np.sqrt(
            np.mean(
                errors ** 2
            )
        )
    )


def main():

    print("=" * 80)
    print("POLARGUARD ENVIRONMENT FEATURE ABLATION")
    print("=" * 80)

    df = pd.read_csv(
        DATA_FILE,
        parse_dates=["init_date"]
    )

    train = df[
        df["data_split"] == "train"
    ].copy()

    val = df[
        df["data_split"] == "validation"
    ].copy()

    test = df[
        df["data_split"] == "test"
    ]

    print("\nTraining rows:", len(train))
    print("Validation rows:", len(val))
    print(
        "Locked 2025 rows:",
        len(test),
        "(NOT USED)"
    )

    results = []

    for experiment_name, features in FEATURE_SETS.items():

        print()
        print("=" * 80)
        print(experiment_name.upper())
        print("=" * 80)

        print(
            "Feature count:",
            len(features)
        )

        X_train = train[features]
        X_val = val[features]

        for horizon in HORIZONS:

            print(
                f"\nTraining {horizon}h..."
            )

            dx_target = (
                f"target_dx_{horizon}h"
            )

            dy_target = (
                f"target_dy_{horizon}h"
            )

            model_dx = (
                HistGradientBoostingRegressor(
                    learning_rate=0.06,
                    max_iter=250,
                    max_leaf_nodes=31,
                    min_samples_leaf=30,
                    l2_regularization=0.2,
                    random_state=42,
                )
            )

            model_dy = (
                HistGradientBoostingRegressor(
                    learning_rate=0.06,
                    max_iter=250,
                    max_leaf_nodes=31,
                    min_samples_leaf=30,
                    l2_regularization=0.2,
                    random_state=42,
                )
            )

            model_dx.fit(
                X_train,
                train[dx_target]
            )

            model_dy.fit(
                X_train,
                train[dy_target]
            )

            pred_dx = (
                model_dx.predict(
                    X_val
                )
            )

            pred_dy = (
                model_dy.predict(
                    X_val
                )
            )

            pred_lat, pred_lon = (
                destination_from_displacement(
                    val[
                        "current_latitude"
                    ],
                    val[
                        "current_longitude"
                    ],
                    pred_dx,
                    pred_dy,
                )
            )

            errors = haversine_km(
                pred_lat,
                pred_lon,
                val[
                    f"true_lat_{horizon}h"
                ],
                val[
                    f"true_lon_{horizon}h"
                ],
            )

            score = rmse(errors)

            mean_error = float(
                np.mean(errors)
            )

            median_error = float(
                np.median(errors)
            )

            within5 = float(
                100
                * np.mean(
                    errors <= 5
                )
            )

            print(
                f"{horizon}h RMSE: "
                f"{score:.3f} km"
            )

            results.append(
                {
                    "experiment":
                        experiment_name,

                    "horizon":
                        horizon,

                    "rmse_km":
                        score,

                    "mean_error_km":
                        mean_error,

                    "median_error_km":
                        median_error,

                    "within_5km_pct":
                        within5,
                }
            )

    results_df = pd.DataFrame(
        results
    )

    output = (
        BASE / "outputs" /
        "environment_ablation_2024.csv"
    )

    results_df.to_csv(
        output,
        index=False
    )

    print()
    print("=" * 80)
    print("2024 RMSE COMPARISON")
    print("=" * 80)

    table = (
        results_df
        .pivot(
            index="experiment",
            columns="horizon",
            values="rmse_km"
        )
    )

    table.columns = [
        f"{c}h"
        for c in table.columns
    ]

    print()
    print(
        table.round(3)
    )

    print()
    print("Saved:")
    print(output)

    print()
    print(
        "2025 TEST SET WAS NOT USED."
    )

    print("=" * 80)


if __name__ == "__main__":
    main()