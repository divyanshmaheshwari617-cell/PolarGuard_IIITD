from pathlib import Path

import joblib
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt


# ============================================================
# CONFIG
# ============================================================

TRAIN_FILE = Path("data/processed/train_2019_2023.nc")
VAL_FILE = Path("data/processed/validation_2024.nc")

MODEL_DIR = Path("models")
OUTPUT_DIR = Path("outputs")
MAP_DIR = OUTPUT_DIR / "maps"

OUTPUT_DIR.mkdir(exist_ok=True)
MAP_DIR.mkdir(exist_ok=True)

THRESHOLD = 0.002

HORIZONS = {
    "24h": 1,
    "48h": 2,
    "72h": 3
}


print("=" * 75)
print("POLARGUARD — VALIDATION-BASED FORECAST UNCERTAINTY")
print("=" * 75)


# ============================================================
# LOAD DATA
# ============================================================

print("\nLoading training history and 2024 validation data...")

train = xr.open_dataarray(TRAIN_FILE)
validation = xr.open_dataarray(VAL_FILE)

# Need final 3 days of 2023 for Jan 2024 lag features
history = train.isel(time=slice(-3, None))

combined = xr.concat(
    [history, validation],
    dim="time"
)

values = combined.values
times = combined.time.values

x_coords = combined.x.values
y_coords = combined.y.values

ny = len(y_coords)
nx = len(x_coords)

x_scale = np.max(np.abs(x_coords))
y_scale = np.max(np.abs(y_coords))


# ============================================================
# OUTPUT DATASET
# ============================================================

output = xr.Dataset(
    coords={
        "y": y_coords,
        "x": x_coords
    }
)


# ============================================================
# PROCESS EACH HORIZON
# ============================================================

for horizon_name, horizon_days in HORIZONS.items():

    print("\n" + "-" * 60)
    print(f"Calculating {horizon_name} uncertainty...")
    print("-" * 60)

    model = joblib.load(
        MODEL_DIR /
        f"sea_ice_model_{horizon_name}.joblib"
    )

    # Running statistics for every grid cell
    sum_squared_error = np.zeros(
        (ny, nx),
        dtype=np.float64
    )

    sum_absolute_error = np.zeros(
        (ny, nx),
        dtype=np.float64
    )

    counts = np.zeros(
        (ny, nx),
        dtype=np.int32
    )


    # --------------------------------------------------------
    # LOOP OVER 2024 FORECAST INITIALIZATION DAYS
    # --------------------------------------------------------

    processed_days = 0

    for t in range(
        3,
        len(values) - horizon_days
    ):

        initialization_date = np.datetime64(
            times[t],
            "D"
        )

        # Only use initialization dates from 2024
        if str(initialization_date)[:4] != "2024":
            continue


        current = values[t]
        lag1 = values[t - 1]
        lag2 = values[t - 2]
        lag3 = values[t - 3]

        actual = values[t + horizon_days]


        # ----------------------------------------------------
        # VALID CELLS
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # SEASONAL FEATURES
        # ----------------------------------------------------

        year_start = initialization_date.astype(
            "datetime64[Y]"
        )

        day_of_year = int(
            (
                initialization_date
                - year_start
            )
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


        # ----------------------------------------------------
        # FEATURES
        # ----------------------------------------------------

        n = len(rows)

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


        # ----------------------------------------------------
        # PURE ML PREDICTION
        # ----------------------------------------------------

        ml_prediction = model.predict(X)

        ml_prediction = np.clip(
            ml_prediction,
            0.0,
            1.0
        )


        # ----------------------------------------------------
        # HYBRID DECISION
        # ----------------------------------------------------

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

        hybrid_prediction = np.where(
            use_ml,
            ml_prediction,
            persistence
        )


        # ----------------------------------------------------
        # ERRORS
        # ----------------------------------------------------

        truth = actual[
            rows,
            cols
        ]

        errors = (
            hybrid_prediction - truth
        )

        abs_errors = np.abs(errors)

        squared_errors = errors ** 2


        # ----------------------------------------------------
        # ACCUMULATE PER-CELL STATISTICS
        # ----------------------------------------------------

        sum_absolute_error[
            rows,
            cols
        ] += abs_errors

        sum_squared_error[
            rows,
            cols
        ] += squared_errors

        counts[
            rows,
            cols
        ] += 1


        processed_days += 1

        if processed_days % 50 == 0:
            print(
                f"Processed {processed_days} days..."
            )


    # ========================================================
    # CREATE UNCERTAINTY MAP
    # ========================================================

    uncertainty_rmse = np.full(
        (ny, nx),
        np.nan,
        dtype=np.float32
    )

    historical_mae = np.full(
        (ny, nx),
        np.nan,
        dtype=np.float32
    )

    valid_cells = counts > 0


    uncertainty_rmse[
        valid_cells
    ] = np.sqrt(

        sum_squared_error[
            valid_cells
        ]

        /

        counts[
            valid_cells
        ]

    ).astype(np.float32)


    historical_mae[
        valid_cells
    ] = (

        sum_absolute_error[
            valid_cells
        ]

        /

        counts[
            valid_cells
        ]

    ).astype(np.float32)


    # ========================================================
    # SAVE VARIABLES
    # ========================================================

    output[
        f"uncertainty_rmse_{horizon_name}"
    ] = (
        ("y", "x"),
        uncertainty_rmse
    )

    output[
        f"historical_mae_{horizon_name}"
    ] = (
        ("y", "x"),
        historical_mae
    )


    mean_uncertainty = np.nanmean(
        uncertainty_rmse
    )

    print(
        f"{horizon_name} mean spatial RMSE uncertainty: "
        f"{mean_uncertainty:.6f}"
    )

    print(
        f"Validation days processed: "
        f"{processed_days}"
    )


    # ========================================================
    # VISUALIZE
    # ========================================================

    plt.figure(figsize=(8, 8))

    plt.imshow(
        uncertainty_rmse,
        origin="lower"
    )

    plt.colorbar(
        label="Historical RMSE (SIC)"
    )

    plt.title(
        f"PolarGuard — {horizon_name} Forecast Uncertainty\n"
        "Estimated from 2024 Validation Errors"
    )

    plt.xlabel("Grid X")
    plt.ylabel("Grid Y")

    plt.tight_layout()

    map_file = (
        MAP_DIR /
        f"uncertainty_{horizon_name}.png"
    )

    plt.savefig(
        map_file,
        dpi=200
    )

    plt.close()

    print(
        "Saved map:",
        map_file
    )


# ============================================================
# METADATA
# ============================================================

output.attrs[
    "system"
] = "PolarGuard Sea-Ice Forecast"

output.attrs[
    "uncertainty_method"
] = (
    "Per-grid-cell RMSE calculated from "
    "2024 validation residuals"
)

output.attrs[
    "validation_period"
] = "2024"

output.attrs[
    "hybrid_threshold"
] = THRESHOLD


# ============================================================
# SAVE NETCDF
# ============================================================

output_file = (
    OUTPUT_DIR /
    "sea_ice_uncertainty.nc"
)

output.to_netcdf(
    output_file
)


print("\n" + "=" * 75)
print("UNCERTAINTY GENERATION COMPLETE")
print("=" * 75)

print(
    "Saved:",
    output_file
)

print("\nVariables:")

for var in output.data_vars:
    print(" -", var)


train.close()
validation.close()
combined.close()