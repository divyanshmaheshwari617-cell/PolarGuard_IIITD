from pathlib import Path

import joblib
import numpy as np
import xarray as xr


VAL_FILE = Path("data/processed/validation_2024.nc")
TEST_FILE = Path("data/processed/test_2025.nc")
MODEL_DIR = Path("models")

THRESHOLD = 0.002

HORIZONS = {
    "24h": 1,
    "48h": 2,
    "72h": 3
}


print("=" * 72)
print("POLARGUARD — HELD-OUT 2025 FORECAST TOLERANCE METRICS")
print("=" * 72)


# ============================================================
# LOAD DATA
# ============================================================

validation = xr.open_dataarray(VAL_FILE)
test = xr.open_dataarray(TEST_FILE)

# Need final 3 days of 2024 for lag features
history = validation.isel(time=slice(-3, None))

combined = xr.concat(
    [history, test],
    dim="time"
)

values = combined.values
times = combined.time.values

x_coords = combined.x.values
y_coords = combined.y.values

x_scale = np.max(np.abs(x_coords))
y_scale = np.max(np.abs(y_coords))


# ============================================================
# EACH FORECAST HORIZON
# ============================================================

for horizon_name, horizon_days in HORIZONS.items():

    print("\n" + "-" * 55)
    print(horizon_name)
    print("-" * 55)

    model = joblib.load(
        MODEL_DIR /
        f"sea_ice_model_{horizon_name}.joblib"
    )

    total = 0

    within_1 = 0
    within_5 = 0
    within_10 = 0


    for t in range(
        3,
        len(values) - horizon_days
    ):

        date = np.datetime64(
            times[t],
            "D"
        )

        # Evaluate only 2025
        if str(date)[:4] != "2025":
            continue


        current = values[t]
        lag1 = values[t - 1]
        lag2 = values[t - 2]
        lag3 = values[t - 3]

        actual = values[
            t + horizon_days
        ]


        valid = (
            np.isfinite(current)
            & np.isfinite(lag1)
            & np.isfinite(lag2)
            & np.isfinite(lag3)
            & np.isfinite(actual)
        )

        rows, cols = np.where(valid)

        if len(rows) == 0:
            continue


        # ====================================================
        # TIME FEATURES
        # ====================================================

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


        # ====================================================
        # FEATURES
        # ====================================================

        n = len(rows)

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


        # ====================================================
        # ML + HYBRID
        # ====================================================

        ml_prediction = model.predict(X)

        ml_prediction = np.clip(
            ml_prediction,
            0,
            1
        )


        recent_change = np.abs(
            current[rows, cols]
            - lag3[rows, cols]
        )


        use_ml = (
            recent_change >= THRESHOLD
        )


        persistence = current[
            rows,
            cols
        ]


        prediction = np.where(
            use_ml,
            ml_prediction,
            persistence
        )


        truth = actual[
            rows,
            cols
        ]


        # ====================================================
        # ABSOLUTE ERROR
        # ====================================================

        error = np.abs(
            prediction - truth
        )


        total += len(error)

        # ±1 SIC percentage point
        within_1 += np.sum(
            error <= 0.01
        )

        # ±5 SIC percentage points
        within_5 += np.sum(
            error <= 0.05
        )

        # ±10 SIC percentage points
        within_10 += np.sum(
            error <= 0.10
        )


    # ========================================================
    # FINAL RESULTS
    # ========================================================

    pct_1 = (
        within_1 /
        total * 100
    )

    pct_5 = (
        within_5 /
        total * 100
    )

    pct_10 = (
        within_10 /
        total * 100
    )


    print(
        f"Within ±1 percentage point : "
        f"{pct_1:.2f}%"
    )

    print(
        f"Within ±5 percentage points: "
        f"{pct_5:.2f}%"
    )

    print(
        f"Within ±10 percentage points: "
        f"{pct_10:.2f}%"
    )

    print(
        f"Total comparisons: "
        f"{total:,}"
    )


validation.close()
test.close()
combined.close()


print("\n" + "=" * 72)
print("TOLERANCE METRICS COMPLETE")
print("=" * 72)