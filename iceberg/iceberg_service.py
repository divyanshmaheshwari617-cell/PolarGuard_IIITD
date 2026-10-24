from pathlib import Path
import joblib
import numpy as np
from datetime import datetime
import pandas as pd


# ============================================================
# PATHS
# ============================================================

BASE = Path(__file__).resolve().parent

MODEL_DIR = BASE / "models" / "environment"


# ============================================================
# CONSTANTS
# ============================================================

EARTH_RADIUS_KM = 6371.0088

HORIZONS = [24, 48, 72]


FEATURE_COLUMNS = [
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


# ============================================================
# LOAD FROZEN MODELS
# ============================================================

MODELS = {}

for horizon in HORIZONS:

    dx_path = (
        MODEL_DIR /
        f"iceberg_environment_{horizon}h_dx.joblib"
    )

    dy_path = (
        MODEL_DIR /
        f"iceberg_environment_{horizon}h_dy.joblib"
    )

    if not dx_path.exists():
        raise FileNotFoundError(
            f"Missing model: {dx_path}"
        )

    if not dy_path.exists():
        raise FileNotFoundError(
            f"Missing model: {dy_path}"
        )

    MODELS[horizon] = {
        "dx": joblib.load(dx_path),
        "dy": joblib.load(dy_path),
    }


# ============================================================
# GEOGRAPHIC HELPERS
# ============================================================

def wrapped_lon_difference(lon2, lon1):
    """
    Shortest signed longitude difference in degrees.
    Handles crossing +/-180 degrees.
    """

    return (
        (lon2 - lon1 + 180.0) % 360.0
    ) - 180.0


def displacement_east_north_km(
    lat1,
    lon1,
    lat2,
    lon2
):
    """
    Approximate local east/north displacement
    between two geographic coordinates.
    """

    lat1 = float(lat1)
    lon1 = float(lon1)
    lat2 = float(lat2)
    lon2 = float(lon2)

    mean_lat_rad = np.radians(
        (lat1 + lat2) / 2.0
    )

    dlat_rad = np.radians(
        lat2 - lat1
    )

    dlon_deg = wrapped_lon_difference(
        lon2,
        lon1
    )

    dlon_rad = np.radians(
        dlon_deg
    )

    dy = (
        EARTH_RADIUS_KM
        * dlat_rad
    )

    dx = (
        EARTH_RADIUS_KM
        * np.cos(mean_lat_rad)
        * dlon_rad
    )

    return float(dx), float(dy)


def destination_from_displacement(
    lat,
    lon,
    dx_km,
    dy_km
):
    """
    Convert predicted east/north displacement
    into future latitude/longitude.
    """

    lat = float(lat)
    lon = float(lon)
    dx_km = float(dx_km)
    dy_km = float(dy_km)

    lat_rad = np.radians(lat)

    future_lat = (
        lat
        + np.degrees(
            dy_km / EARTH_RADIUS_KM
        )
    )

    cos_lat = np.cos(lat_rad)

    if abs(cos_lat) < 1e-8:
        cos_lat = 1e-8

    future_lon = (
        lon
        + np.degrees(
            dx_km /
            (
                EARTH_RADIUS_KM
                * cos_lat
            )
        )
    )

    future_lon = (
        (future_lon + 180.0) % 360.0
    ) - 180.0

    return (
        float(future_lat),
        float(future_lon),
    )


# ============================================================
# FEATURE BUILDER
# ============================================================

def build_features(
    lat_tm3,
    lon_tm3,
    lat_tm2,
    lon_tm2,
    lat_tm1,
    lon_tm1,
    current_latitude,
    current_longitude,
    day_of_year,
    wind_u10,
    wind_v10,
    ocean_uo,
    ocean_vo,
    sea_ice_sic,
    sea_ice_available=1,
):
    """
    Build the exact 26-feature vector used
    by the frozen final Member 2 models.
    """

    # --------------------------------------------------------
    # Daily displacements
    # --------------------------------------------------------

    vx_1, vy_1 = displacement_east_north_km(
        lat_tm3,
        lon_tm3,
        lat_tm2,
        lon_tm2,
    )

    vx_2, vy_2 = displacement_east_north_km(
        lat_tm2,
        lon_tm2,
        lat_tm1,
        lon_tm1,
    )

    vx_3, vy_3 = displacement_east_north_km(
        lat_tm1,
        lon_tm1,
        current_latitude,
        current_longitude,
    )

    # --------------------------------------------------------
    # Speed
    # --------------------------------------------------------

    speed_1 = np.sqrt(
        vx_1 ** 2 + vy_1 ** 2
    )

    speed_2 = np.sqrt(
        vx_2 ** 2 + vy_2 ** 2
    )

    speed_3 = np.sqrt(
        vx_3 ** 2 + vy_3 ** 2
    )

    # --------------------------------------------------------
    # Acceleration
    # --------------------------------------------------------

    accel_x_previous = (
        vx_2 - vx_1
    )

    accel_y_previous = (
        vy_2 - vy_1
    )

    accel_x_recent = (
        vx_3 - vx_2
    )

    accel_y_recent = (
        vy_3 - vy_2
    )

    # --------------------------------------------------------
    # 3-day motion
    # --------------------------------------------------------

    mean_vx_3day = np.mean(
        [vx_1, vx_2, vx_3]
    )

    mean_vy_3day = np.mean(
        [vy_1, vy_2, vy_3]
    )

    mean_speed_3day = np.mean(
        [speed_1, speed_2, speed_3]
    )

    # --------------------------------------------------------
    # Seasonality
    # --------------------------------------------------------

    day_of_year = int(day_of_year)

    doy_sin = np.sin(
        2.0 * np.pi
        * day_of_year / 365.25
    )

    doy_cos = np.cos(
        2.0 * np.pi
        * day_of_year / 365.25
    )

    # --------------------------------------------------------
    # Sea ice
    #
    # Training-only imputation value was 0.8.
    # Use this only when SIC is unavailable.
    # --------------------------------------------------------

    if sea_ice_sic is None or not np.isfinite(sea_ice_sic):

        sea_ice_sic_filled = 0.8
        sea_ice_available = 0

    else:

        sea_ice_sic_filled = float(
            sea_ice_sic
        )

        sea_ice_available = int(
            sea_ice_available
        )

    # --------------------------------------------------------
    # Final feature vector
    # --------------------------------------------------------

    features = np.array(
        [
            current_latitude,
            current_longitude,

            vx_1,
            vy_1,

            vx_2,
            vy_2,

            vx_3,
            vy_3,

            speed_1,
            speed_2,
            speed_3,

            accel_x_previous,
            accel_y_previous,

            accel_x_recent,
            accel_y_recent,

            mean_vx_3day,
            mean_vy_3day,
            mean_speed_3day,

            doy_sin,
            doy_cos,

            wind_u10,
            wind_v10,

            ocean_uo,
            ocean_vo,

            sea_ice_sic_filled,
            sea_ice_available,
        ],
        dtype=np.float64
    )

    if not np.all(np.isfinite(features)):
        raise ValueError(
            "Non-finite values detected "
            "in iceberg model features."
        )

    return pd.DataFrame(
    [features],
    columns=FEATURE_COLUMNS
)


# ============================================================
# MAIN PREDICTION FUNCTION
# ============================================================

def predict_iceberg_trajectory(
    lat_tm3,
    lon_tm3,
    lat_tm2,
    lon_tm2,
    lat_tm1,
    lon_tm1,
    current_latitude,
    current_longitude,
    day_of_year,
    wind_u10,
    wind_v10,
    ocean_uo,
    ocean_vo,
    sea_ice_sic=None,
    sea_ice_available=1,
):
    """
    Predict iceberg positions at:
        +24 hours
        +48 hours
        +72 hours

    Inputs:
        Four consecutive daily iceberg positions
        Current environmental forcing
        Initialization day-of-year

    Returns:
        Dictionary containing predicted
        latitude/longitude and displacement.
    """

    X = build_features(
        lat_tm3=lat_tm3,
        lon_tm3=lon_tm3,

        lat_tm2=lat_tm2,
        lon_tm2=lon_tm2,

        lat_tm1=lat_tm1,
        lon_tm1=lon_tm1,

        current_latitude=current_latitude,
        current_longitude=current_longitude,

        day_of_year=day_of_year,

        wind_u10=wind_u10,
        wind_v10=wind_v10,

        ocean_uo=ocean_uo,
        ocean_vo=ocean_vo,

        sea_ice_sic=sea_ice_sic,
        sea_ice_available=sea_ice_available,
    )

    forecasts = {}

    for horizon in HORIZONS:

        model_dx = MODELS[
            horizon
        ]["dx"]

        model_dy = MODELS[
            horizon
        ]["dy"]

        pred_dx = float(
            model_dx.predict(X)[0]
        )

        pred_dy = float(
            model_dy.predict(X)[0]
        )

        pred_lat, pred_lon = (
            destination_from_displacement(
                current_latitude,
                current_longitude,
                pred_dx,
                pred_dy,
            )
        )

        displacement_km = float(
            np.sqrt(
                pred_dx ** 2
                + pred_dy ** 2
            )
        )

        forecasts[f"{horizon}h"] = {
            "latitude":
                pred_lat,

            "longitude":
                pred_lon,

            "dx_km":
                pred_dx,

            "dy_km":
                pred_dy,

            "predicted_displacement_km":
                displacement_km,
        }

    return {
        "model":
            "PolarGuard iceberg trajectory model",

        "version":
            "environment-v1-frozen",

        "current_position": {
            "latitude":
                float(current_latitude),

            "longitude":
                float(current_longitude),
        },

        "environment": {
            "wind_u10_mps":
                float(wind_u10),

            "wind_v10_mps":
                float(wind_v10),

            "ocean_uo_mps":
                float(ocean_uo),

            "ocean_vo_mps":
                float(ocean_vo),

            "sea_ice_concentration":
                (
                    None
                    if sea_ice_sic is None
                    else float(sea_ice_sic)
                ),

            "sea_ice_available":
                int(
                    sea_ice_sic is not None
                    and np.isfinite(sea_ice_sic)
                ),
        },

        "forecast": forecasts,
    }


# ============================================================
# OPTIONAL DATE WRAPPER
# ============================================================

def predict_from_date(
    lat_tm3,
    lon_tm3,
    lat_tm2,
    lon_tm2,
    lat_tm1,
    lon_tm1,
    current_latitude,
    current_longitude,
    date,
    wind_u10,
    wind_v10,
    ocean_uo,
    ocean_vo,
    sea_ice_sic=None,
):
    """
    Same forecast but accepts a date instead
    of day_of_year.
    """

    if isinstance(date, str):

        date = datetime.fromisoformat(
            date
        )

    day_of_year = date.timetuple().tm_yday

    return predict_iceberg_trajectory(
        lat_tm3=lat_tm3,
        lon_tm3=lon_tm3,

        lat_tm2=lat_tm2,
        lon_tm2=lon_tm2,

        lat_tm1=lat_tm1,
        lon_tm1=lon_tm1,

        current_latitude=current_latitude,
        current_longitude=current_longitude,

        day_of_year=day_of_year,

        wind_u10=wind_u10,
        wind_v10=wind_v10,

        ocean_uo=ocean_uo,
        ocean_vo=ocean_vo,

        sea_ice_sic=sea_ice_sic,
    )