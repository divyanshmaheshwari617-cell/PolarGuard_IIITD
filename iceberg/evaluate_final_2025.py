from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd


BASE = Path(__file__).resolve().parent

DATA_FILE = (
    BASE / "data" / "processed" /
    "iceberg_features_environment_ml_ready_2019_2025.csv"
)

MODEL_DIR = BASE / "models" / "environment"
OUTPUT_DIR = BASE / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


FEATURES = [
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

    "wind_u10",
    "wind_v10",

    "ocean_uo",
    "ocean_vo",

    "sea_ice_sic_filled",
    "sea_ice_available",
]


HORIZONS = [24, 48, 72]
EARTH_RADIUS_KM = 6371.0088


def destination_from_displacement(lat, lon, dx, dy):

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


def haversine_km(lat1, lon1, lat2, lon2):

    lat1 = np.radians(np.asarray(lat1))
    lon1 = np.radians(np.asarray(lon1))
    lat2 = np.radians(np.asarray(lat2))
    lon2 = np.radians(np.asarray(lon2))

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        np.sin(dlat / 2) ** 2
        +
        np.cos(lat1)
        * np.cos(lat2)
        * np.sin(dlon / 2) ** 2
    )

    a = np.clip(a, 0, 1)

    return (
        2
        * EARTH_RADIUS_KM
        * np.arcsin(np.sqrt(a))
    )


def metrics(errors):

    errors = np.asarray(errors)

    return {
        "mean_km":
            float(np.mean(errors)),

        "median_km":
            float(np.median(errors)),

        "rmse_km":
            float(np.sqrt(np.mean(errors ** 2))),

        "p90_km":
            float(np.percentile(errors, 90)),

        "p95_km":
            float(np.percentile(errors, 95)),

        "within_1km_pct":
            float(100 * np.mean(errors <= 1)),

        "within_5km_pct":
            float(100 * np.mean(errors <= 5)),

        "within_10km_pct":
            float(100 * np.mean(errors <= 10)),

        "within_25km_pct":
            float(100 * np.mean(errors <= 25)),

        "within_50km_pct":
            float(100 * np.mean(errors <= 50)),
    }


def baseline_displacement(df, horizon, method):

    factor = horizon / 24.0

    if method == "persistence":
        dx = np.zeros(len(df))
        dy = np.zeros(len(df))

    elif method == "last_velocity":
        dx = df["vx_tm1_t"].to_numpy() * factor
        dy = df["vy_tm1_t"].to_numpy() * factor

    elif method == "mean_velocity_3day":
        dx = df["mean_vx_3day"].to_numpy() * factor
        dy = df["mean_vy_3day"].to_numpy() * factor

    else:
        raise ValueError(method)

    return dx, dy


def main():

    print("=" * 80)
    print("POLARGUARD FINAL HELD-OUT 2025 ICEBERG EVALUATION")
    print("=" * 80)

    df = pd.read_csv(
        DATA_FILE,
        parse_dates=["init_date"]
    )

    test = df[
        df["data_split"] == "test"
    ].copy()

    print("\n2025 test rows:", len(test))

    if len(test) != 14694:
        raise ValueError(
            f"Unexpected test size: {len(test)}"
        )

    if test[FEATURES].isna().sum().sum() != 0:
        raise ValueError(
            "NaNs found in 2025 model features."
        )

    X_test = test[FEATURES]

    final_results = {}
    prediction_output = test[
        [
            "iceberg_id",
            "init_date",
            "current_latitude",
            "current_longitude",
        ]
    ].copy()

    for horizon in HORIZONS:

        print()
        print("=" * 80)
        print(f"{horizon}H FINAL TEST")
        print("=" * 80)

        dx_model = joblib.load(
            MODEL_DIR /
            f"iceberg_environment_{horizon}h_dx.joblib"
        )

        dy_model = joblib.load(
            MODEL_DIR /
            f"iceberg_environment_{horizon}h_dy.joblib"
        )

        pred_dx = dx_model.predict(X_test)
        pred_dy = dy_model.predict(X_test)

        pred_lat, pred_lon = destination_from_displacement(
            test["current_latitude"],
            test["current_longitude"],
            pred_dx,
            pred_dy
        )

        true_lat = test[
            f"true_lat_{horizon}h"
        ].to_numpy()

        true_lon = test[
            f"true_lon_{horizon}h"
        ].to_numpy()

        model_errors = haversine_km(
            pred_lat,
            pred_lon,
            true_lat,
            true_lon
        )

        model_metrics = metrics(
            model_errors
        )

        baseline_results = {}

        for baseline_name in [
            "persistence",
            "last_velocity",
            "mean_velocity_3day",
        ]:

            bdx, bdy = baseline_displacement(
                test,
                horizon,
                baseline_name
            )

            blat, blon = destination_from_displacement(
                test["current_latitude"],
                test["current_longitude"],
                bdx,
                bdy
            )

            berrors = haversine_km(
                blat,
                blon,
                true_lat,
                true_lon
            )

            baseline_results[
                baseline_name
            ] = metrics(berrors)

        best_baseline_name = min(
            baseline_results,
            key=lambda x:
                baseline_results[x]["rmse_km"]
        )

        best_baseline_rmse = (
            baseline_results[
                best_baseline_name
            ]["rmse_km"]
        )

        improvement = (
            100
            * (
                best_baseline_rmse
                - model_metrics["rmse_km"]
            )
            / best_baseline_rmse
        )

        final_results[
            f"{horizon}h"
        ] = {
            "model":
                model_metrics,

            "baselines":
                baseline_results,

            "best_baseline":
                best_baseline_name,

            "rmse_improvement_vs_best_baseline_pct":
                float(improvement),
        }

        prediction_output[
            f"pred_lat_{horizon}h"
        ] = pred_lat

        prediction_output[
            f"pred_lon_{horizon}h"
        ] = pred_lon

        prediction_output[
            f"error_km_{horizon}h"
        ] = model_errors

        print(
            f"Mean error:   "
            f"{model_metrics['mean_km']:.3f} km"
        )

        print(
            f"Median error: "
            f"{model_metrics['median_km']:.3f} km"
        )

        print(
            f"RMSE:         "
            f"{model_metrics['rmse_km']:.3f} km"
        )

        print(
            f"P90:          "
            f"{model_metrics['p90_km']:.3f} km"
        )

        print(
            f"P95:          "
            f"{model_metrics['p95_km']:.3f} km"
        )

        print(
            f"Within 1 km:  "
            f"{model_metrics['within_1km_pct']:.2f}%"
        )

        print(
            f"Within 5 km:  "
            f"{model_metrics['within_5km_pct']:.2f}%"
        )

        print(
            f"Within 10 km: "
            f"{model_metrics['within_10km_pct']:.2f}%"
        )

        print(
            f"Within 25 km: "
            f"{model_metrics['within_25km_pct']:.2f}%"
        )

        print(
            f"Within 50 km: "
            f"{model_metrics['within_50km_pct']:.2f}%"
        )

        print("\nBaselines:")

        for name, result in baseline_results.items():

            print(
                f"{name:20s} "
                f"RMSE = "
                f"{result['rmse_km']:.3f} km"
            )

        print(
            f"\nBest baseline: "
            f"{best_baseline_name}"
        )

        print(
            f"RMSE improvement: "
            f"{improvement:+.2f}%"
        )

    metrics_file = (
        OUTPUT_DIR /
        "iceberg_final_test_2025.json"
    )

    with open(
        metrics_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            final_results,
            f,
            indent=2
        )

    prediction_file = (
        OUTPUT_DIR /
        "iceberg_final_predictions_2025.csv"
    )

    prediction_output.to_csv(
        prediction_file,
        index=False
    )

    print()
    print("=" * 80)
    print("FINAL HELD-OUT 2025 SUMMARY")
    print("=" * 80)

    print(
        f"\n{'Horizon':<10}"
        f"{'Model RMSE':>14}"
        f"{'Best baseline':>20}"
        f"{'Baseline RMSE':>16}"
        f"{'Improvement':>14}"
    )

    print("-" * 74)

    for horizon in HORIZONS:

        result = final_results[
            f"{horizon}h"
        ]

        model_rmse = (
            result["model"]["rmse_km"]
        )

        baseline_name = (
            result["best_baseline"]
        )

        baseline_rmse = (
            result["baselines"]
            [baseline_name]
            ["rmse_km"]
        )

        improvement = (
            result[
                "rmse_improvement_vs_best_baseline_pct"
            ]
        )

        print(
            f"{str(horizon)+'h':<10}"
            f"{model_rmse:>12.3f} km"
            f"{baseline_name:>20}"
            f"{baseline_rmse:>14.3f} km"
            f"{improvement:>+12.2f}%"
        )

    print("\nMetrics saved:")
    print(metrics_file)

    print("\nPredictions saved:")
    print(prediction_file)

    print()
    print("=" * 80)
    print("FINAL 2025 TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()