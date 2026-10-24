from pathlib import Path

import joblib
import numpy as np
import xarray as xr


# ============================================================
# CONFIGURATION
# ============================================================

TEST_FILE = Path("data/processed/test_2025.nc")
VAL_FILE = Path("data/processed/validation_2024.nc")

MODEL_DIR = Path("models")
OUTPUT_DIR = Path("outputs")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

THRESHOLD = 0.002

FORECAST_DATE = np.datetime64("2025-12-28")

HORIZONS = {
    "24h": 1,
    "48h": 2,
    "72h": 3
}


print("=" * 75)
print("POLARGUARD — SEA-ICE FORECAST GENERATOR")
print("=" * 75)


# ============================================================
# LOAD DATA
# ============================================================

print("\nLoading data...")

validation = xr.open_dataarray(VAL_FILE)
test = xr.open_dataarray(TEST_FILE)

# Include final 3 days of 2024 so the code also works
# for forecasts near the start of 2025.
history = validation.isel(
    time=slice(-3, None)
)

combined = xr.concat(
    [history, test],
    dim="time"
)

times = combined.time.values
values = combined.values

x_coords = combined.x.values
y_coords = combined.y.values


# ============================================================
# FIND FORECAST DATE
# ============================================================

forecast_indices = np.where(
    times.astype("datetime64[D]")
    == FORECAST_DATE
)[0]

if len(forecast_indices) == 0:
    raise ValueError(
        f"Forecast date {FORECAST_DATE} not found."
    )

t = int(forecast_indices[0])

if t < 3:
    raise ValueError(
        "Not enough historical days before forecast date."
    )

if t + 3 >= len(values):
    raise ValueError(
        "Not enough future observations for 72h evaluation."
    )


print(
    "Forecast initialization:",
    times[t]
)


# ============================================================
# HISTORICAL MAPS
# ============================================================

current = values[t]
lag1 = values[t - 1]
lag2 = values[t - 2]
lag3 = values[t - 3]


x_scale = np.max(
    np.abs(x_coords)
)

y_scale = np.max(
    np.abs(y_coords)
)


# ============================================================
# DATE FEATURES
# ============================================================

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


print(
    "Day of year:",
    day_of_year
)


# ============================================================
# VALID FORECAST CELLS
# ============================================================

# IMPORTANT:
# Real forecasting cannot use future observations to
# determine whether a cell is valid.

valid = (
    np.isfinite(current)
    & np.isfinite(lag1)
    & np.isfinite(lag2)
    & np.isfinite(lag3)
)

rows, cols = np.where(valid)

n = len(rows)

print(
    f"Valid forecast cells: {n:,}"
)


# ============================================================
# BUILD FEATURES
# ============================================================

X = np.column_stack([

    current[rows, cols],
    lag1[rows, cols],
    lag2[rows, cols],
    lag3[rows, cols],

    x_coords[cols] / x_scale,
    y_coords[rows] / y_scale,

    np.full(
        n,
        seasonal_sin
    ),

    np.full(
        n,
        seasonal_cos
    )

]).astype(np.float32)


# ============================================================
# HYBRID SIGNAL
# ============================================================

recent_change = np.abs(

    current[rows, cols]
    - lag3[rows, cols]

)

use_ml = (
    recent_change
    >= THRESHOLD
)


print(
    f"ML selected for "
    f"{np.mean(use_ml) * 100:.2f}% "
    f"of valid cells"
)


# ============================================================
# OUTPUT DATASET
# ============================================================

output = xr.Dataset(
    coords={
        "y": y_coords,
        "x": x_coords
    }
)


output["current_sic"] = (
    ("y", "x"),
    current.astype(np.float32)
)


# ============================================================
# FORECAST EACH HORIZON
# ============================================================

for horizon_name, horizon_days in HORIZONS.items():

    print(
        "\nGenerating",
        horizon_name,
        "forecast..."
    )


    # --------------------------------------------------------
    # LOAD MODEL
    # --------------------------------------------------------

    model = joblib.load(

        MODEL_DIR /
        f"sea_ice_model_{horizon_name}.joblib"

    )


    # --------------------------------------------------------
    # PURE ML
    # --------------------------------------------------------

    ml_prediction = model.predict(X)

    ml_prediction = np.clip(
        ml_prediction,
        0.0,
        1.0
    )


    # --------------------------------------------------------
    # HYBRID
    # --------------------------------------------------------

    persistence = current[
        rows,
        cols
    ]

    hybrid_prediction = np.where(

        use_ml,

        ml_prediction,

        persistence

    )


    # --------------------------------------------------------
    # REBUILD 2D MAP
    # --------------------------------------------------------

    forecast_map = np.full(

        current.shape,

        np.nan,

        dtype=np.float32

    )

    forecast_map[
        rows,
        cols
    ] = hybrid_prediction.astype(
        np.float32
    )


    output[
        f"forecast_{horizon_name}"
    ] = (

        ("y", "x"),

        forecast_map

    )


    # --------------------------------------------------------
    # ACTUAL OBSERVATION
    #
    # Included only because this is a historical demonstration.
    # A real future forecast obviously will not have this.
    # --------------------------------------------------------

    actual = values[
        t + horizon_days
    ].astype(np.float32)


    output[
        f"actual_{horizon_name}"
    ] = (

        ("y", "x"),

        actual

    )


    # --------------------------------------------------------
    # ABSOLUTE ERROR MAP
    # --------------------------------------------------------

    error_map = np.abs(
        forecast_map - actual
    )


    output[
        f"absolute_error_{horizon_name}"
    ] = (

        ("y", "x"),

        error_map.astype(
            np.float32
        )

    )


    valid_eval = (
        np.isfinite(forecast_map)
        & np.isfinite(actual)
    )


    mae = np.mean(

        np.abs(
            forecast_map[valid_eval]
            - actual[valid_eval]
        )

    )


    rmse = np.sqrt(

        np.mean(

            (
                forecast_map[valid_eval]
                - actual[valid_eval]
            ) ** 2

        )

    )


    print(
        f"{horizon_name} MAE : "
        f"{mae:.6f}"
    )

    print(
        f"{horizon_name} RMSE: "
        f"{rmse:.6f}"
    )


# ============================================================
# METADATA
# ============================================================

output.attrs[
    "system"
] = "PolarGuard Sea-Ice Forecast"

output.attrs[
    "forecast_initialization"
] = str(FORECAST_DATE)

output.attrs[
    "hybrid_threshold"
] = THRESHOLD

output.attrs[
    "forecast_method"
] = (
    "Persistence + HistGradientBoosting hybrid"
)


# ============================================================
# SAVE
# ============================================================

OUTPUT_FILE = (
    OUTPUT_DIR /
    "sea_ice_forecast_demo.nc"
)


print("\nSaving forecast product...")

output.to_netcdf(
    OUTPUT_FILE
)


print("\n" + "=" * 75)
print("FORECAST GENERATION COMPLETE")
print("=" * 75)

print(
    "Saved:",
    OUTPUT_FILE
)

print("\nVariables:")

for variable in output.data_vars:
    print(" -", variable)


validation.close()
test.close()
combined.close()