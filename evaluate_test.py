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


print("=" * 75)
print("POLARGUARD — FINAL 2025 TEST")
print("=" * 75)


# ============================================================
# LOAD DATA
# ============================================================

val = xr.open_dataarray(VAL_FILE)
test = xr.open_dataarray(TEST_FILE)

# Final three days of 2024 provide history
history = val.isel(
    time=slice(-3, None)
)

combined = xr.concat(
    [history, test],
    dim="time"
)

values = combined.values
times = combined.time.values

x_coords = combined.x.values
y_coords = combined.y.values

x_scale = np.max(
    np.abs(x_coords)
)

y_scale = np.max(
    np.abs(y_coords)
)


print("\nTest data loaded.")
print("Combined shape:", combined.shape)
print("History starts :", times[0])
print("Test ends      :", times[-1])

print(
    f"Frozen hybrid threshold: "
    f"{THRESHOLD}"
)


# ============================================================
# EVALUATE
# ============================================================

results = {}


for horizon_name, horizon in HORIZONS.items():

    print("\n" + "=" * 75)
    print(f"TESTING {horizon_name}")
    print("=" * 75)

    model = joblib.load(
        MODEL_DIR /
        f"sea_ice_model_{horizon_name}.joblib"
    )

    baseline_abs = 0.0
    baseline_sq = 0.0

    ml_abs = 0.0
    ml_sq = 0.0

    hybrid_abs = 0.0
    hybrid_sq = 0.0

    count = 0
    ml_used = 0


    for t in range(
        3,
        len(values) - horizon
    ):

        current = values[t]
        lag1 = values[t - 1]
        lag2 = values[t - 2]
        lag3 = values[t - 3]

        target = values[
            t + horizon
        ]


        valid = (
            np.isfinite(current)
            & np.isfinite(lag1)
            & np.isfinite(lag2)
            & np.isfinite(lag3)
            & np.isfinite(target)
        )


        rows, cols = np.where(
            valid
        )

        if len(rows) == 0:
            continue


        # ====================================================
        # SEASON
        # ====================================================

        date = np.datetime64(
            times[t],
            "D"
        )

        year_start = date.astype(
            "datetime64[Y]"
        )

        day_of_year = int(
            (date - year_start)
            / np.timedelta64(
                1,
                "D"
            )
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


        # ====================================================
        # FEATURES
        # ====================================================

        X = np.column_stack([

            current[
                rows,
                cols
            ],

            lag1[
                rows,
                cols
            ],

            lag2[
                rows,
                cols
            ],

            lag3[
                rows,
                cols
            ],

            x_coords[cols] /
            x_scale,

            y_coords[rows] /
            y_scale,

            np.full(
                n,
                seasonal_sin
            ),

            np.full(
                n,
                seasonal_cos
            )

        ]).astype(
            np.float32
        )


        # ====================================================
        # PREDICTIONS
        # ====================================================

        actual = target[
            rows,
            cols
        ]


        persistence = current[
            rows,
            cols
        ]


        ml_prediction = model.predict(
            X
        )

        ml_prediction = np.clip(
            ml_prediction,
            0.0,
            1.0
        )


        recent_change = np.abs(

            current[
                rows,
                cols
            ]

            -

            lag3[
                rows,
                cols
            ]
        )


        use_ml = (
            recent_change
            >= THRESHOLD
        )


        hybrid = np.where(

            use_ml,

            ml_prediction,

            persistence
        )


        # ====================================================
        # ERRORS
        # ====================================================

        baseline_error = (
            persistence - actual
        )

        ml_error = (
            ml_prediction - actual
        )

        hybrid_error = (
            hybrid - actual
        )


        baseline_abs += np.sum(
            np.abs(
                baseline_error
            ),
            dtype=np.float64
        )

        baseline_sq += np.sum(
            baseline_error ** 2,
            dtype=np.float64
        )


        ml_abs += np.sum(
            np.abs(
                ml_error
            ),
            dtype=np.float64
        )

        ml_sq += np.sum(
            ml_error ** 2,
            dtype=np.float64
        )


        hybrid_abs += np.sum(
            np.abs(
                hybrid_error
            ),
            dtype=np.float64
        )

        hybrid_sq += np.sum(
            hybrid_error ** 2,
            dtype=np.float64
        )


        count += n

        ml_used += np.sum(
            use_ml
        )


        if (t - 3) % 50 == 0:

            print(
                f"Processed "
                f"{t - 2} days"
            )


    # ========================================================
    # METRICS
    # ========================================================

    baseline_mae = (
        baseline_abs /
        count
    )

    baseline_rmse = np.sqrt(
        baseline_sq /
        count
    )


    ml_mae = (
        ml_abs /
        count
    )

    ml_rmse = np.sqrt(
        ml_sq /
        count
    )


    hybrid_mae = (
        hybrid_abs /
        count
    )

    hybrid_rmse = np.sqrt(
        hybrid_sq /
        count
    )


    mae_improvement = (

        (
            baseline_mae
            - hybrid_mae
        )

        / baseline_mae

        * 100
    )


    rmse_improvement = (

        (
            baseline_rmse
            - hybrid_rmse
        )

        / baseline_rmse

        * 100
    )


    ml_percentage = (
        ml_used /
        count *
        100
    )


    results[horizon_name] = {

        "baseline_mae":
            baseline_mae,

        "baseline_rmse":
            baseline_rmse,

        "ml_mae":
            ml_mae,

        "ml_rmse":
            ml_rmse,

        "hybrid_mae":
            hybrid_mae,

        "hybrid_rmse":
            hybrid_rmse,

        "mae_improvement":
            mae_improvement,

        "rmse_improvement":
            rmse_improvement,

        "ml_percentage":
            ml_percentage,

        "count":
            count
    }


# ============================================================
# FINAL RESULTS
# ============================================================

print("\n" + "=" * 75)
print("FINAL 2025 TEST RESULTS")
print("=" * 75)


for horizon, r in results.items():

    print("\n" + horizon)
    print("-" * 50)

    print(
        f"Persistence MAE  : "
        f"{r['baseline_mae']:.6f}"
    )

    print(
        f"Pure ML MAE      : "
        f"{r['ml_mae']:.6f}"
    )

    print(
        f"Hybrid MAE       : "
        f"{r['hybrid_mae']:.6f}"
    )

    print(
        f"Hybrid MAE gain  : "
        f"{r['mae_improvement']:.2f}%"
    )


    print()

    print(
        f"Persistence RMSE : "
        f"{r['baseline_rmse']:.6f}"
    )

    print(
        f"Pure ML RMSE     : "
        f"{r['ml_rmse']:.6f}"
    )

    print(
        f"Hybrid RMSE      : "
        f"{r['hybrid_rmse']:.6f}"
    )

    print(
        f"Hybrid RMSE gain : "
        f"{r['rmse_improvement']:.2f}%"
    )


    print(
        f"ML used          : "
        f"{r['ml_percentage']:.2f}%"
    )

    print(
        f"Comparisons      : "
        f"{r['count']:,}"
    )


print("\n" + "=" * 75)
print("FINAL TEST COMPLETE")
print("=" * 75)


val.close()
test.close()
combined.close()