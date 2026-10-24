from pathlib import Path

import joblib
import numpy as np
import xarray as xr


# ============================================================
# PATHS
# ============================================================

TRAIN_FILE = Path("data/processed/train_2019_2023.nc")
VAL_FILE = Path("data/processed/validation_2024.nc")
MODEL_DIR = Path("models")


# ============================================================
# CONFIGURATION
# ============================================================

HORIZONS = {
    "24h": 1,
    "48h": 2,
    "72h": 3,
}


print("=" * 75)
print("POLARGUARD — 2024 ML VALIDATION")
print("=" * 75)


# ============================================================
# LOAD DATA
# ============================================================

print("\nLoading data...")

train = xr.open_dataarray(TRAIN_FILE)
val = xr.open_dataarray(VAL_FILE)

# Need final 3 days of 2023 so that
# Jan 1, 2024 has t-1, t-2 and t-3 history.
history = train.isel(time=slice(-3, None))

combined = xr.concat(
    [history, val],
    dim="time"
)

values = combined.values

times = combined.time.values

x_coords = combined.x.values
y_coords = combined.y.values


# Coordinate normalization MUST match training.
x_scale = np.max(np.abs(x_coords))
y_scale = np.max(np.abs(y_coords))


print("Combined shape:", combined.shape)
print("History starts :", times[0])
print("Validation ends:", times[-1])


# ============================================================
# LOAD MODELS
# ============================================================

models = {}

for name in HORIZONS:

    model_file = (
        MODEL_DIR /
        f"sea_ice_model_{name}.joblib"
    )

    print("Loading:", model_file)

    models[name] = joblib.load(model_file)


# ============================================================
# EVALUATION FUNCTION
# ============================================================

def evaluate_horizon(horizon_name, days_ahead):

    model = models[horizon_name]

    ml_abs_error_sum = 0.0
    ml_squared_error_sum = 0.0

    baseline_abs_error_sum = 0.0
    baseline_squared_error_sum = 0.0

    total_valid = 0

    # Index 3 = 2024-01-01 because first
    # three entries are Dec 29–31, 2023.
    first_t = 3

    # Target must remain inside validation 2024.
    last_t = len(values) - days_ahead

    print("\n" + "-" * 75)
    print(f"Evaluating {horizon_name}...")
    print("-" * 75)

    for t in range(first_t, last_t):

        current = values[t]
        lag1 = values[t - 1]
        lag2 = values[t - 2]
        lag3 = values[t - 3]

        target = values[t + days_ahead]

        # Same valid cells will be used for ML
        # AND persistence.
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
        # SEASONAL FEATURES
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
            2 * np.pi
            * day_of_year
            / 365.25
        )

        seasonal_cos = np.cos(
            2 * np.pi
            * day_of_year
            / 365.25
        )

        n = len(rows)

        # ----------------------------------------------------
        # BUILD FEATURES
        # ----------------------------------------------------

        X = np.column_stack([

            current[rows, cols],
            lag1[rows, cols],
            lag2[rows, cols],
            lag3[rows, cols],

            x_coords[cols] / x_scale,
            y_coords[rows] / y_scale,

            np.full(n, seasonal_sin),
            np.full(n, seasonal_cos),

        ]).astype(np.float32)


        actual = target[
            rows,
            cols
        ].astype(np.float32)


        # ----------------------------------------------------
        # ML PREDICTION
        # ----------------------------------------------------

        prediction = model.predict(X)

        # Sea-ice concentration must remain 0–1.
        prediction = np.clip(
            prediction,
            0.0,
            1.0
        )


        # ----------------------------------------------------
        # PERSISTENCE PREDICTION
        # ----------------------------------------------------

        persistence = current[
            rows,
            cols
        ]


        # ----------------------------------------------------
        # ML ERRORS
        # ----------------------------------------------------

        ml_error = prediction - actual

        ml_abs_error_sum += np.sum(
            np.abs(ml_error),
            dtype=np.float64
        )

        ml_squared_error_sum += np.sum(
            ml_error ** 2,
            dtype=np.float64
        )


        # ----------------------------------------------------
        # BASELINE ERRORS
        # ----------------------------------------------------

        baseline_error = (
            persistence - actual
        )

        baseline_abs_error_sum += np.sum(
            np.abs(baseline_error),
            dtype=np.float64
        )

        baseline_squared_error_sum += np.sum(
            baseline_error ** 2,
            dtype=np.float64
        )


        total_valid += n


        if (t - first_t) % 50 == 0:

            print(
                f"Processed "
                f"{t - first_t + 1} days"
            )


    # ========================================================
    # FINAL METRICS
    # ========================================================

    ml_mae = (
        ml_abs_error_sum
        / total_valid
    )

    ml_rmse = np.sqrt(
        ml_squared_error_sum
        / total_valid
    )

    baseline_mae = (
        baseline_abs_error_sum
        / total_valid
    )

    baseline_rmse = np.sqrt(
        baseline_squared_error_sum
        / total_valid
    )


    mae_improvement = (
        (baseline_mae - ml_mae)
        / baseline_mae
        * 100
    )

    rmse_improvement = (
        (baseline_rmse - ml_rmse)
        / baseline_rmse
        * 100
    )


    return {
        "baseline_mae": baseline_mae,
        "baseline_rmse": baseline_rmse,
        "ml_mae": ml_mae,
        "ml_rmse": ml_rmse,
        "mae_improvement": mae_improvement,
        "rmse_improvement": rmse_improvement,
        "count": total_valid,
    }


# ============================================================
# RUN ALL HORIZONS
# ============================================================

results = {}

for name, days in HORIZONS.items():

    results[name] = evaluate_horizon(
        name,
        days
    )


# ============================================================
# RESULTS
# ============================================================

print("\n")
print("=" * 75)
print("2024 VALIDATION RESULTS")
print("=" * 75)

for name, result in results.items():

    print(f"\n{name}")
    print("-" * 40)

    print(
        f"Persistence MAE  : "
        f"{result['baseline_mae']:.6f}"
    )

    print(
        f"ML MAE           : "
        f"{result['ml_mae']:.6f}"
    )

    print(
        f"MAE improvement  : "
        f"{result['mae_improvement']:.2f}%"
    )

    print()

    print(
        f"Persistence RMSE : "
        f"{result['baseline_rmse']:.6f}"
    )

    print(
        f"ML RMSE          : "
        f"{result['ml_rmse']:.6f}"
    )

    print(
        f"RMSE improvement : "
        f"{result['rmse_improvement']:.2f}%"
    )

    print(
        f"Valid comparisons: "
        f"{result['count']:,}"
    )


print("\n" + "=" * 75)
print("VALIDATION COMPLETE")
print("=" * 75)


train.close()
val.close()
combined.close()