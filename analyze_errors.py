from pathlib import Path

import joblib
import numpy as np
import xarray as xr


TRAIN_FILE = Path("data/processed/train_2019_2023.nc")
VAL_FILE = Path("data/processed/validation_2024.nc")
MODEL_FILE = Path("models/sea_ice_model_72h.joblib")

HORIZON = 3


print("=" * 70)
print("POLARGUARD — 72H ERROR ANALYSIS")
print("=" * 70)


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

model = joblib.load(MODEL_FILE)


# ------------------------------------------------------------
# ERROR GROUPS
# ------------------------------------------------------------

groups = {

    "Stable (<0.01 change)": {
        "ml": [],
        "persistence": []
    },

    "Moderate (0.01-0.05 change)": {
        "ml": [],
        "persistence": []
    },

    "Large (>0.05 change)": {
        "ml": [],
        "persistence": []
    }
}


for t in range(3, len(values) - HORIZON):

    current = values[t]
    lag1 = values[t - 1]
    lag2 = values[t - 2]
    lag3 = values[t - 3]

    target = values[t + HORIZON]

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


    # --------------------------------------------------------
    # DATE FEATURES
    # --------------------------------------------------------

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


    prediction = model.predict(X)

    prediction = np.clip(
        prediction,
        0.0,
        1.0
    )


    actual = target[
        rows,
        cols
    ]

    persistence = current[
        rows,
        cols
    ]


    # Actual amount of change over 72h
    change = np.abs(
        actual - persistence
    )


    masks = {

        "Stable (<0.01 change)":
            change < 0.01,

        "Moderate (0.01-0.05 change)":
            (change >= 0.01)
            & (change < 0.05),

        "Large (>0.05 change)":
            change >= 0.05
    }


    for name, mask in masks.items():

        if not np.any(mask):
            continue

        ml_error = (
            prediction[mask]
            - actual[mask]
        )

        persistence_error = (
            persistence[mask]
            - actual[mask]
        )

        groups[name]["ml"].append(
            ml_error
        )

        groups[name]["persistence"].append(
            persistence_error
        )


    if (t - 3) % 50 == 0:
        print(
            f"Processed {t - 2} days"
        )


print("\n" + "=" * 70)
print("72H ERROR ANALYSIS")
print("=" * 70)


for name, errors in groups.items():

    ml = np.concatenate(
        errors["ml"]
    )

    persistence = np.concatenate(
        errors["persistence"]
    )

    ml_mae = np.mean(
        np.abs(ml)
    )

    persistence_mae = np.mean(
        np.abs(persistence)
    )

    ml_rmse = np.sqrt(
        np.mean(ml ** 2)
    )

    persistence_rmse = np.sqrt(
        np.mean(persistence ** 2)
    )

    print("\n", name)

    print(
        "Samples:",
        f"{len(ml):,}"
    )

    print(
        f"Persistence MAE : "
        f"{persistence_mae:.6f}"
    )

    print(
        f"ML MAE          : "
        f"{ml_mae:.6f}"
    )

    print(
        f"Persistence RMSE: "
        f"{persistence_rmse:.6f}"
    )

    print(
        f"ML RMSE         : "
        f"{ml_rmse:.6f}"
    )


train.close()
val.close()
combined.close()