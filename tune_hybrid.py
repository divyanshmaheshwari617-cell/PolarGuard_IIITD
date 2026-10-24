from pathlib import Path
import joblib
import numpy as np
import xarray as xr


TRAIN_FILE = Path("data/processed/train_2019_2023.nc")
VAL_FILE = Path("data/processed/validation_2024.nc")

MODEL_DIR = Path("models")

HORIZONS = {
    "24h": 1,
    "48h": 2,
    "72h": 3
}

# Thresholds for recent observed SIC change
THRESHOLDS = [
    0.000,
    0.002,
    0.005,
    0.010,
    0.015,
    0.020,
    0.030,
    0.040,
    0.050,
    0.075,
    0.100
]


print("=" * 75)
print("POLARGUARD — HYBRID FORECAST TUNING")
print("=" * 75)


# ============================================================
# LOAD DATA
# ============================================================

train = xr.open_dataarray(TRAIN_FILE)
val = xr.open_dataarray(VAL_FILE)

history = train.isel(time=slice(-3, None))

combined = xr.concat(
    [history, val],
    dim="time"
)

values = combined.values
times = combined.time.values

x_coords = combined.x.values
y_coords = combined.y.values

x_scale = np.max(np.abs(x_coords))
y_scale = np.max(np.abs(y_coords))


# ============================================================
# HORIZON LOOP
# ============================================================

best_thresholds = {}


for horizon_name, horizon in HORIZONS.items():

    print("\n" + "=" * 75)
    print(f"TUNING {horizon_name}")
    print("=" * 75)

    model = joblib.load(
        MODEL_DIR /
        f"sea_ice_model_{horizon_name}.joblib"
    )

    # Accumulate errors without storing millions of predictions.
    stats = {}

    for threshold in THRESHOLDS:

        stats[threshold] = {
            "abs": 0.0,
            "sq": 0.0,
            "count": 0,
            "ml_count": 0
        }


    for t in range(
        3,
        len(values) - horizon
    ):

        current = values[t]
        lag1 = values[t - 1]
        lag2 = values[t - 2]
        lag3 = values[t - 3]

        target = values[t + horizon]


        valid = (
            np.isfinite(current)
            & np.isfinite(lag1)
            & np.isfinite(lag2)
            & np.isfinite(lag3)
            & np.isfinite(target)
        )


        rows, cols = np.where(valid)

        if len(rows) == 0:
            continue


        # ----------------------------------------------------
        # SEASON
        # ----------------------------------------------------

        date = np.datetime64(
            times[t],
            "D"
        )

        year_start = date.astype(
            "datetime64[Y]"
        )

        day_of_year = int(
            (date - year_start)
            / np.timedelta64(1, "D")
        ) + 1


        seasonal_sin = np.sin(
            2 * np.pi *
            day_of_year /
            365.25
        )

        seasonal_cos = np.cos(
            2 * np.pi *
            day_of_year /
            365.25
        )


        n = len(rows)


        # ----------------------------------------------------
        # FEATURES
        # ----------------------------------------------------

        X = np.column_stack([

            current[rows, cols],
            lag1[rows, cols],
            lag2[rows, cols],
            lag3[rows, cols],

            x_coords[cols] / x_scale,
            y_coords[rows] / y_scale,

            np.full(n, seasonal_sin),
            np.full(n, seasonal_cos)

        ]).astype(np.float32)


        ml_prediction = model.predict(X)

        ml_prediction = np.clip(
            ml_prediction,
            0.0,
            1.0
        )


        persistence = current[
            rows,
            cols
        ]

        actual = target[
            rows,
            cols
        ]


        # ----------------------------------------------------
        # OPERATIONAL CHANGE SIGNAL
        #
        # IMPORTANT:
        # only past/current observations are used.
        # No future information.
        # ----------------------------------------------------

        recent_change = np.abs(
            current[rows, cols]
            - lag3[rows, cols]
        )


        # ----------------------------------------------------
        # TEST THRESHOLDS
        # ----------------------------------------------------

        for threshold in THRESHOLDS:

            use_ml = (
                recent_change >= threshold
            )

            hybrid = np.where(
                use_ml,
                ml_prediction,
                persistence
            )

            error = (
                hybrid - actual
            )


            stats[threshold]["abs"] += np.sum(
                np.abs(error),
                dtype=np.float64
            )

            stats[threshold]["sq"] += np.sum(
                error ** 2,
                dtype=np.float64
            )

            stats[threshold]["count"] += n

            stats[threshold]["ml_count"] += np.sum(
                use_ml
            )


        if (t - 3) % 50 == 0:

            print(
                f"Processed "
                f"{t - 2} days"
            )


    # ========================================================
    # DISPLAY THRESHOLD RESULTS
    # ========================================================

    print("\nThreshold results:\n")

    results = []

    for threshold in THRESHOLDS:

        s = stats[threshold]

        mae = (
            s["abs"]
            / s["count"]
        )

        rmse = np.sqrt(
            s["sq"]
            / s["count"]
        )

        ml_percentage = (
            s["ml_count"]
            / s["count"]
            * 100
        )

        results.append(
            (
                threshold,
                mae,
                rmse,
                ml_percentage
            )
        )

        print(
            f"Threshold {threshold:>5.3f} | "
            f"MAE {mae:.6f} | "
            f"RMSE {rmse:.6f} | "
            f"ML used {ml_percentage:.2f}%"
        )


    # ========================================================
    # SELECT BEST
    #
    # For navigation-oriented forecasting we initially choose
    # minimum RMSE because large errors matter strongly.
    # ========================================================

    best = min(
        results,
        key=lambda x: x[2]
    )

    best_thresholds[horizon_name] = best


    print(
        f"\nBEST {horizon_name}:"
    )

    print(
        f"Threshold : {best[0]:.3f}"
    )

    print(
        f"MAE       : {best[1]:.6f}"
    )

    print(
        f"RMSE      : {best[2]:.6f}"
    )

    print(
        f"ML usage  : {best[3]:.2f}%"
    )


# ============================================================
# FINAL SUMMARY
# ============================================================

print("\n" + "=" * 75)
print("BEST HYBRID THRESHOLDS — 2024 VALIDATION")
print("=" * 75)


for horizon, result in best_thresholds.items():

    threshold, mae, rmse, ml_percentage = result

    print(
        f"{horizon}: "
        f"threshold={threshold:.3f}, "
        f"MAE={mae:.6f}, "
        f"RMSE={rmse:.6f}, "
        f"ML usage={ml_percentage:.2f}%"
    )


train.close()
val.close()
combined.close()