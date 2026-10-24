from pathlib import Path

import joblib
import numpy as np
import xarray as xr


MODEL_DIR = Path("models")
UNCERTAINTY_FILE = Path("outputs/sea_ice_uncertainty.nc")

THRESHOLD = 0.002

MODELS = {
    "24h": joblib.load(MODEL_DIR / "sea_ice_model_24h.joblib"),
    "48h": joblib.load(MODEL_DIR / "sea_ice_model_48h.joblib"),
    "72h": joblib.load(MODEL_DIR / "sea_ice_model_72h.joblib"),
}


def predict_sea_ice(current, lag1, lag2, lag3, x_coords, y_coords, date):
    """
    Generate PolarGuard hybrid sea-ice forecasts.

    Returns:
        {
            "24h": 2D numpy array,
            "48h": 2D numpy array,
            "72h": 2D numpy array
        }
    """

    x_scale = np.max(np.abs(x_coords))
    y_scale = np.max(np.abs(y_coords))

    valid = (
        np.isfinite(current)
        & np.isfinite(lag1)
        & np.isfinite(lag2)
        & np.isfinite(lag3)
    )

    rows, cols = np.where(valid)

    year_start = date.astype("datetime64[Y]")

    day_of_year = int(
        (date - year_start)
        / np.timedelta64(1, "D")
    ) + 1

    seasonal_sin = np.sin(
        2 * np.pi * day_of_year / 365.25
    )

    seasonal_cos = np.cos(
        2 * np.pi * day_of_year / 365.25
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

    recent_change = np.abs(
        current[rows, cols]
        - lag3[rows, cols]
    )

    use_ml = recent_change >= THRESHOLD

    persistence = current[rows, cols]

    results = {}

    for horizon in ["24h", "48h", "72h"]:

        ml_prediction = MODELS[horizon].predict(X)

        ml_prediction = np.clip(
            ml_prediction,
            0.0,
            1.0
        )

        hybrid_prediction = np.where(
            use_ml,
            ml_prediction,
            persistence
        )

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

        results[horizon] = forecast_map

    return results


def load_uncertainty():
    """
    Load validation-derived uncertainty maps.
    """

    ds = xr.open_dataset(
        UNCERTAINTY_FILE
    )

    result = {
        "24h": ds["uncertainty_rmse_24h"].values.copy(),
        "48h": ds["uncertainty_rmse_48h"].values.copy(),
        "72h": ds["uncertainty_rmse_72h"].values.copy()
    }

    ds.close()

    return result