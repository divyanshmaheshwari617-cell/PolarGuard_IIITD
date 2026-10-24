from __future__ import annotations
from navigation_map_service import build_navigation_map_data
from react_integration_service import (
    get_iceberg_intelligence,
    get_environment_intelligence,
    get_risk_intelligence,
    get_navigation_decision,
    get_model_intelligence,
)
import tempfile
import uuid
import xarray as xr
import io
import matplotlib.pyplot as plt
import numpy as np
from sea_ice_service import predict_sea_ice, load_uncertainty
from datetime import date, datetime, timezone
from typing import Any
from fastapi import (
    FastAPI,
    HTTPException,
    UploadFile,
    File,
    Form,
)
from fastapi.middleware.cors import CORSMiddleware

from satellite_data_service import load_latest_satellite_input
from sea_ice_input_service import (
    load_latest_available_input,
    load_historical_input,
    load_uploaded_input,
    get_historical_date_range,
)
from current_iceberg_service import load_current_icebergs
from operational_status_service import build_environmental_status


# ============================================================
# POLARGUARD API
# React <-> FastAPI <-> Existing PolarGuard Services
# ============================================================

app = FastAPI(
    title="PolarGuard API",
    description=(
        "Backend API for PolarGuard Antarctic Navigation "
        "Decision Support System."
    ),
    version="1.0.0",
)


# ============================================================
# CORS
# React development server
# ============================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],

    allow_credentials=True,

    allow_methods=[
        "*",
    ],

    allow_headers=[
        "*",
    ],
)


# ============================================================
# SEA-ICE UPLOAD SESSION CACHE
# ============================================================

SEA_ICE_UPLOAD_CACHE: dict[str, dict[str, Any]] = {}


# ============================================================
# HELPERS
# ============================================================

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_value(value: Any) -> Any:
    """
    Convert NumPy / Pandas scalar-like objects into JSON-safe values.
    """

    if value is None:
        return None

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    if isinstance(value, (date, datetime)):
        return value.isoformat()

    return value


def first_existing(mapping: Any, *keys: str, default=None):
    """
    Safely retrieve the first available key from a dictionary-like object.
    """

    if not isinstance(mapping, dict):
        return default

    for key in keys:
        if key in mapping:
            return mapping[key]

    return default



async def read_uploaded_sic_netcdf(
    uploaded_file: UploadFile,
    label: str,
) -> np.ndarray:
    """
    Read one uploaded NetCDF file and return one 332 x 316 SIC grid.

    Supported common SIC variable names:
        sea_ice_concentration
        cdr_seaice_conc
        sic
        SIC

    NaN / masked cells remain NaN.
    """
    filename = uploaded_file.filename or f"{label}.nc"

    if not filename.lower().endswith(".nc"):
        raise HTTPException(
            status_code=400,
            detail=f"{label}: only .nc NetCDF files are supported.",
        )

    raw = await uploaded_file.read()
    if not raw:
        raise HTTPException(
            status_code=400,
            detail=f"{label}: uploaded file is empty.",
        )

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = f"{temp_dir}/{label}.nc"

            with open(temp_path, "wb") as handle:
                handle.write(raw)

            ds = xr.open_dataset(temp_path, decode_times=False)

            try:
                candidates = [
                    "sea_ice_concentration",
                    "cdr_seaice_conc",
                    "sic",
                    "SIC",
                    "seaice_conc",
                    "ice_concentration",
                ]

                variable_name = None

                for candidate in candidates:
                    if candidate in ds.data_vars:
                        variable_name = candidate
                        break

                if variable_name is None:
                    for name, variable in ds.data_vars.items():
                        dims_lower = {
                            str(dim).lower()
                            for dim in variable.dims
                        }

                        if (
                            "x" in dims_lower
                            and "y" in dims_lower
                            and np.issubdtype(variable.dtype, np.number)
                        ):
                            variable_name = name
                            break

                if variable_name is None:
                    raise ValueError(
                        f"{label}: could not find a sea-ice concentration variable."
                    )

                data = ds[variable_name].squeeze(drop=True)

                if data.ndim != 2:
                    raise ValueError(
                        f"{label}: SIC variable '{variable_name}' has "
                        f"shape {tuple(data.shape)} after squeeze. "
                        "Expected one 2-D SIC grid."
                    )

                dims_lower = [
                    str(dim).lower()
                    for dim in data.dims
                ]

                if "y" in dims_lower and "x" in dims_lower:
                    y_dim = data.dims[dims_lower.index("y")]
                    x_dim = data.dims[dims_lower.index("x")]
                    data = data.transpose(y_dim, x_dim)

                grid = np.asarray(data.values, dtype=np.float32)
                grid = np.where(
                    np.isfinite(grid),
                    grid,
                    np.nan,
                ).astype(np.float32)

                finite = grid[np.isfinite(grid)]

                if finite.size == 0:
                    raise ValueError(
                        f"{label}: grid contains no valid SIC cells."
                    )

                finite_min = float(np.min(finite))
                finite_max = float(np.max(finite))

                # Clearly percentage-scale SIC can be safely converted.
                if (
                    finite_min >= 0.0
                    and finite_max > 1.0
                    and finite_max <= 100.0
                ):
                    grid = (grid / 100.0).astype(np.float32)

                return grid

            finally:
                ds.close()

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{label}: failed to read NetCDF file. {exc}",
        ) from exc


def sea_ice_grid_stats(grid: np.ndarray) -> dict[str, Any]:
    arr = np.asarray(grid, dtype=float)
    valid = np.isfinite(arr)

    if not valid.any():
        return {
            "valid_cells": 0,
            "masked_cells": int(arr.size),
            "mean_sic": None,
            "min_sic": None,
            "max_sic": None,
        }

    values = arr[valid]

    return {
        "valid_cells": int(valid.sum()),
        "masked_cells": int(arr.size - valid.sum()),
        "mean_sic": float(np.mean(values)),
        "min_sic": float(np.min(values)),
        "max_sic": float(np.max(values)),
    }


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "system": "PolarGuard",
        "service": "Antarctic Navigation Intelligence API",
        "status": "online",
        "version": "1.0.0",
        "timestamp_utc": utc_now(),
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/api/health")
def health():
    return {
        "ok": True,
        "system": "PolarGuard",
        "api": "online",
        "timestamp_utc": utc_now(),
    }


# ============================================================
# SEA-ICE PROVIDER
# NOAA / NSIDC
# ============================================================

@app.get("/api/providers/sea-ice")
def sea_ice_provider():
    try:
        bundle = load_latest_satellite_input()

        dates = bundle.get("dates", [])

        dates_json = [
            str(safe_value(x))
            for x in dates
        ]

        latest_date = (
            dates_json[-1]
            if dates_json
            else str(
                safe_value(
                    first_existing(
                        bundle,
                        "date",
                        "latest_date",
                        "observation_date",
                    )
                )
            )
        )

        current = bundle.get("current")

        valid_cells = first_existing(
            bundle,
            "valid_cells",
            "valid_cell_count",
        )

        if valid_cells is None and current is not None:
            try:
                import numpy as np

                valid_cells = int(
                    np.isfinite(current).sum()
                )
            except Exception:
                valid_cells = None

        provider_lag = first_existing(
            bundle,
            "provider_lag_days",
            "provider_lag",
            "lag_days",
        )

        return {
            "ok": True,
            "provider": "NOAA / NSIDC",
            "product": "G10016 Version 4",
            "mode": "latest_available",
            "latest_observation": latest_date,
            "available_dates": dates_json,
            "provider_lag_days": safe_value(provider_lag),
            "valid_cells": safe_value(valid_cells),
            "grid_shape": (
                list(current.shape)
                if current is not None
                else None
            ),
            "timestamp_utc": utc_now(),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Sea-ice provider unavailable: {exc}",
        ) from exc


# ============================================================
# CURRENT ICEBERGS
# BYU SCP
# ============================================================

@app.get("/api/providers/icebergs")
def iceberg_provider():
    try:
        bundle = load_current_icebergs()

        icebergs = first_existing(
            bundle,
            "icebergs",
            "records",
            "data",
            default=[],
        )

        if icebergs is None:
            icebergs = []

        count = first_existing(
            bundle,
            "count",
            "iceberg_count",
            "total_icebergs",
        )

        if count is None:
            try:
                count = len(icebergs)
            except Exception:
                count = None

        latest_observation = first_existing(
            bundle,
            "latest_observation",
            "latest_observation_date",
            "observation_date",
            "latest_date",
        )

        source = first_existing(
            bundle,
            "source",
            "provider",
            default="BYU Scatterometer Climate Pathfinder",
        )

        return {
            "ok": True,
            "provider": "BYU SCP",
            "source": safe_value(source),
            "mode": "latest_available",
            "iceberg_count": safe_value(count),
            "latest_observation": safe_value(
                latest_observation
            ),
            "timestamp_utc": utc_now(),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Iceberg provider unavailable: {exc}",
        ) from exc


# ============================================================
# COMMAND CENTER
# Lightweight provider summary
# ============================================================

@app.get("/api/command-center")
def command_center():
    providers = {
        "sea_ice": {
            "name": "NOAA / NSIDC",
            "status": "unknown",
        },
        "icebergs": {
            "name": "BYU SCP",
            "status": "unknown",
        },
        "wind": {
            "name": "ECMWF",
            "status": "configured",
        },
        "ocean": {
            "name": "Copernicus Marine",
            "status": "configured",
        },
    }

    sea_ice_data = None
    iceberg_data = None

    # ------------------------------
    # NOAA / NSIDC
    # ------------------------------

    try:
        sea_ice_data = sea_ice_provider()

        providers["sea_ice"].update(
            {
                "status": "online",
                "latest_observation": (
                    sea_ice_data.get(
                        "latest_observation"
                    )
                ),
                "provider_lag_days": (
                    sea_ice_data.get(
                        "provider_lag_days"
                    )
                ),
                "valid_cells": (
                    sea_ice_data.get(
                        "valid_cells"
                    )
                ),
            }
        )

    except Exception as exc:
        providers["sea_ice"].update(
            {
                "status": "unavailable",
                "error": str(exc),
            }
        )

    # ------------------------------
    # BYU
    # ------------------------------

    try:
        iceberg_data = iceberg_provider()

        providers["icebergs"].update(
            {
                "status": "online",
                "iceberg_count": (
                    iceberg_data.get(
                        "iceberg_count"
                    )
                ),
                "latest_observation": (
                    iceberg_data.get(
                        "latest_observation"
                    )
                ),
            }
        )

    except Exception as exc:
        providers["icebergs"].update(
            {
                "status": "unavailable",
                "error": str(exc),
            }
        )

    return {
        "ok": True,
        "system": "PolarGuard",
        "mode": "latest_available",
        "providers": providers,
        "summary": {
            "sea_ice_forecast_horizon_hours": 72,
            "safe_navigation": "ready",
        },
        "timestamp_utc": utc_now(),
    }


# ============================================================
# FULL ENVIRONMENTAL STATUS
#
# This endpoint performs heavier provider work:
# ECMWF + Copernicus + NOAA/NSIDC
# ============================================================

@app.get("/api/environment/status")
def environment_status(
    latitude: float = -53.55,
    longitude: float = -29.95,
):
    try:
        result = build_environmental_status(
            requested_date=date.today(),
            latitude=latitude,
            longitude=longitude,
        )

        return {
            "ok": True,
            "mode": "near_real_time",
            "latitude": latitude,
            "longitude": longitude,
            "status": result,
            "timestamp_utc": utc_now(),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Environmental provider refresh failed: "
                f"{exc}"
            ),
        ) from exc


# ============================================================
# START
# ============================================================
# ============================================================
# SEA-ICE INPUT MODES
# ============================================================


@app.get("/api/sea-ice/input-modes")
def sea_ice_input_modes():
    """
    Describe the input modes supported by PolarGuard Member-1.
    """

    try:
        historical_range = get_historical_date_range()

        return {
            "ok": True,

            "default_mode": "latest_available",

            "modes": {
                "latest_available": {
                    "id": "latest_available",
                    "label": "Latest Available",
                    "description": (
                        "Automatically load the latest four "
                        "consecutive NOAA/NSIDC near-real-time "
                        "sea-ice observations."
                    ),
                    "requires_date": False,
                    "requires_upload": False,
                    "available": True,
                },

                "historical_date": {
                    "id": "historical_date",
                    "label": "Historical Date",
                    "description": (
                        "Select a historical initialization date. "
                        "PolarGuard loads that observation and the "
                        "three preceding daily SIC fields."
                    ),
                    "requires_date": True,
                    "requires_upload": False,
                    "available": True,
                    "first_dataset_date": (
                        historical_range["first_date"]
                    ),
                    "last_dataset_date": (
                        historical_range["last_date"]
                    ),
                    "first_usable_date": "2019-01-04",
                },

                "upload": {
                    "id": "upload",
                    "label": "Upload Data",
                    "description": (
                        "Upload current, lag-1, lag-2 and lag-3 "
                        "SIC grids for validation and forecasting."
                    ),
                    "requires_date": True,
                    "requires_upload": True,
                    "available": True,
                },
            },

            "model": {
                "name": "PolarGuard Sea-Ice Member-1",
                "status": "frozen",
                "forecast_horizons_hours": [
                    24,
                    48,
                    72,
                ],
                "required_input_days": 4,
                "expected_grid_shape": [
                    332,
                    316,
                ],
                "crs": "EPSG:3412",
            },

            "generated_at": utc_now(),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not load sea-ice input modes: "
                f"{exc}"
            ),
        ) from exc


@app.get("/api/sea-ice/historical/range")
def sea_ice_historical_range():
    """
    Return the available historical-date range.
    """

    try:
        historical_range = get_historical_date_range()

        return {
            "ok": True,
            "dataset_first_date": (
                historical_range["first_date"]
            ),
            "dataset_last_date": (
                historical_range["last_date"]
            ),

            # Member-1 requires:
            # current + previous 3 daily fields
            "first_usable_date": "2019-01-04",
            "last_usable_date": (
                historical_range["last_date"]
            ),

            "required_previous_days": 3,
            "product": (
                "NOAA/NSIDC G02202 Version 6"
            ),
            "grid_shape": [
                332,
                316,
            ],
            "crs": "EPSG:3412",
        }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not load historical range: "
                f"{exc}"
            ),
        ) from exc
@app.get("/api/sea-ice/historical")
def sea_ice_historical(
    date: str,
):
    """
    Run frozen Member-1 from a selected historical date.

    Example:
        /api/sea-ice/historical?date=2025-08-15
    """

    try:
        bundle = load_historical_input(date)

        forecasts = predict_sea_ice(
            current=bundle.current,
            lag1=bundle.lag1,
            lag2=bundle.lag2,
            lag3=bundle.lag3,
            x_coords=bundle.x,
            y_coords=bundle.y,
            date=bundle.date,
        )

        uncertainty = load_uncertainty()

        def grid_stats(grid):
            arr = np.asarray(
                grid,
                dtype=float,
            )

            valid = np.isfinite(arr)

            if not valid.any():
                return {
                    "valid_cells": 0,
                    "mean_sic": None,
                    "min_sic": None,
                    "max_sic": None,
                }

            values = arr[valid]

            return {
                "valid_cells": int(
                    valid.sum()
                ),
                "mean_sic": float(
                    np.mean(values)
                ),
                "min_sic": float(
                    np.min(values)
                ),
                "max_sic": float(
                    np.max(values)
                ),
            }

        def forecast_grid(
            horizon: str,
        ):
            if horizon not in forecasts:
                raise RuntimeError(
                    f"Member-1 did not return "
                    f"{horizon} forecast."
                )

            return forecasts[horizon]

        def uncertainty_grid(
            horizon: str,
        ):
            candidates = [
                horizon,
                f"uncertainty_{horizon}",
                f"rmse_{horizon}",
            ]

            if isinstance(
                uncertainty,
                dict,
            ):
                for key in candidates:
                    if key in uncertainty:
                        return uncertainty[key]

            return None

        forecast_24 = forecast_grid("24h")
        forecast_48 = forecast_grid("48h")
        forecast_72 = forecast_grid("72h")

        uncertainty_24 = uncertainty_grid("24h")
        uncertainty_48 = uncertainty_grid("48h")
        uncertainty_72 = uncertainty_grid("72h")

        response = {
            "ok": True,

            "source": {
                "provider": (
                    bundle.metadata[
                        "provider"
                    ]
                ),
                "product": (
                    bundle.metadata[
                        "product"
                    ]
                ),
                "mode": (
                    "historical_date"
                ),
                "mode_label": (
                    "Historical Date"
                ),
                "latest_observation": str(
                    bundle.date
                ),
                "selected_date": str(
                    bundle.date
                ),
                "provider_lag_days": None,
                "input_dates": (
                    bundle.metadata[
                        "input_dates"
                    ]
                ),
            },

            "grid": {
                "shape": list(
                    bundle.current.shape
                ),
                "crs": "EPSG:3412",
            },

            "current": grid_stats(
                bundle.current
            ),

            "forecast": {
                "24h": grid_stats(
                    forecast_24
                ),
                "48h": grid_stats(
                    forecast_48
                ),
                "72h": grid_stats(
                    forecast_72
                ),
            },

            "uncertainty": {
                "24h": (
                    grid_stats(
                        uncertainty_24
                    )
                    if uncertainty_24
                    is not None
                    else None
                ),
                "48h": (
                    grid_stats(
                        uncertainty_48
                    )
                    if uncertainty_48
                    is not None
                    else None
                ),
                "72h": (
                    grid_stats(
                        uncertainty_72
                    )
                    if uncertainty_72
                    is not None
                    else None
                ),
            },

            # Same frozen official held-out
            # evaluation. These values do NOT
            # describe this individual historical date.
            "evaluation_2025": {
                "24h": {
                    "mae": 0.008854,
                    "rmse": 0.036288,
                    "within_5pp_percent": 94.87,
                    "rmse_improvement_vs_persistence_percent": 4.56,
                },
                "48h": {
                    "mae": 0.012707,
                    "rmse": 0.050063,
                    "within_5pp_percent": 93.18,
                    "rmse_improvement_vs_persistence_percent": 5.73,
                },
                "72h": {
                    "mae": 0.015287,
                    "rmse": 0.059311,
                    "within_5pp_percent": 92.33,
                    "rmse_improvement_vs_persistence_percent": 7.04,
                },
            },

            "input": {
                "mode": (
                    bundle.mode
                ),
                "validation_status": (
                    bundle.metadata[
                        "validation_status"
                    ]
                ),
                "member1_ready": (
                    bundle.metadata[
                        "member1_ready"
                    ]
                ),
                "input_dates": (
                    bundle.metadata[
                        "input_dates"
                    ]
                ),
            },

            "scientific_note": (
                "Historical replay uses the selected "
                "NOAA/NSIDC SIC observation and the "
                "three preceding daily SIC fields. "
                "Forecast uncertainty is the historical "
                "per-grid-cell RMSE calculated from 2024 "
                "validation residuals and is not a "
                "calibrated confidence interval."
            ),

            "generated_at": utc_now(),
        }

        return response

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Historical sea-ice forecast failed: "
                f"{exc}"
            ),
        ) from exc

@app.post("/api/sea-ice/upload")
async def upload_sea_ice_inputs(
    initialization_date: str = Form(...),
    current_file: UploadFile = File(...),
    lag1_file: UploadFile = File(...),
    lag2_file: UploadFile = File(...),
    lag3_file: UploadFile = File(...),
):
    """
    Upload four SIC grids and run frozen PolarGuard Member-1.

    current = initialization_date
    lag1    = initialization_date - 1 day
    lag2    = initialization_date - 2 days
    lag3    = initialization_date - 3 days
    """
    try:
        current = await read_uploaded_sic_netcdf(current_file, "current")
        lag1 = await read_uploaded_sic_netcdf(lag1_file, "lag1")
        lag2 = await read_uploaded_sic_netcdf(lag2_file, "lag2")
        lag3 = await read_uploaded_sic_netcdf(lag3_file, "lag3")

        bundle = load_uploaded_input(
            current=current,
            lag1=lag1,
            lag2=lag2,
            lag3=lag3,
            date=initialization_date,
            source_name="Operator Upload",
        )

        forecasts = predict_sea_ice(
            current=bundle.current,
            lag1=bundle.lag1,
            lag2=bundle.lag2,
            lag3=bundle.lag3,
            x_coords=bundle.x,
            y_coords=bundle.y,
            date=np.datetime64(bundle.date, "D"),
        )

        normalized_forecasts: dict[str, np.ndarray] = {}

        for horizon in ("24h", "48h", "72h"):
            hours = int(horizon.replace("h", ""))
            candidates = [
                horizon,
                hours,
                f"forecast_{horizon}",
                f"forecast_{hours}",
                f"sic_{horizon}",
            ]

            grid = None

            if isinstance(forecasts, dict):
                for key in candidates:
                    if key in forecasts:
                        grid = forecasts[key]
                        break

            if grid is None:
                raise RuntimeError(
                    f"Member-1 did not return {horizon} forecast."
                )

            normalized_forecasts[horizon] = np.asarray(
                grid,
                dtype=np.float32,
            )

        uncertainty = load_uncertainty()
        upload_token = uuid.uuid4().hex

        SEA_ICE_UPLOAD_CACHE[upload_token] = {
            "bundle": bundle,
            "forecast": normalized_forecasts,
            "uncertainty": uncertainty,
            "created_at": utc_now(),
        }

        # Keep this prototype cache bounded.
        while len(SEA_ICE_UPLOAD_CACHE) > 10:
            oldest_token = next(iter(SEA_ICE_UPLOAD_CACHE))
            if oldest_token == upload_token and len(SEA_ICE_UPLOAD_CACHE) == 1:
                break
            SEA_ICE_UPLOAD_CACHE.pop(oldest_token, None)

        uncertainty_response: dict[str, Any] = {}

        if isinstance(uncertainty, dict):
            for horizon in ("24h", "48h", "72h"):
                candidates = [
                    horizon,
                    int(horizon.replace("h", "")),
                    f"uncertainty_{horizon}",
                    f"rmse_{horizon}",
                ]

                uncertainty_grid = None

                for key in candidates:
                    if key in uncertainty:
                        uncertainty_grid = uncertainty[key]
                        break

                uncertainty_response[horizon] = (
                    sea_ice_grid_stats(uncertainty_grid)
                    if uncertainty_grid is not None
                    else None
                )

        return {
            "ok": True,
            "upload_token": upload_token,
            "source": {
                "provider": "Operator Upload",
                "product": "User-provided SIC grids",
                "mode": "upload",
                "mode_label": "Upload Data",
                "latest_observation": str(bundle.date),
                "selected_date": str(bundle.date),
                "provider_lag_days": None,
                "input_dates": bundle.metadata.get("input_dates", []),
            },
            "grid": {
                "shape": list(bundle.current.shape),
                "crs": "EPSG:3412",
            },
            "current": sea_ice_grid_stats(bundle.current),
            "forecast": {
                horizon: sea_ice_grid_stats(grid)
                for horizon, grid in normalized_forecasts.items()
            },
            "uncertainty": uncertainty_response,
            "input": {
                "mode": "upload",
                "initialization_date": str(bundle.date),
                "input_dates": bundle.metadata.get("input_dates", []),
                "validation_status": bundle.metadata.get(
                    "validation_status",
                    "passed",
                ),
                "member1_ready": bool(
                    bundle.metadata.get("member1_ready", True)
                ),
                "coordinate_source": bundle.metadata.get(
                    "coordinate_source"
                ),
                "files": {
                    "current": current_file.filename,
                    "lag1": lag1_file.filename,
                    "lag2": lag2_file.filename,
                    "lag3": lag3_file.filename,
                },
            },
            "evaluation_2025": {
                "label": "Held-out 2025 test set",
                "24h": {
                    "mae": 0.008854,
                    "rmse": 0.036288,
                    "within_5pp_percent": 94.87,
                    "rmse_improvement_vs_persistence_percent": 4.56,
                },
                "48h": {
                    "mae": 0.012707,
                    "rmse": 0.050063,
                    "within_5pp_percent": 93.18,
                    "rmse_improvement_vs_persistence_percent": 5.73,
                },
                "72h": {
                    "mae": 0.015287,
                    "rmse": 0.059311,
                    "within_5pp_percent": 92.33,
                    "rmse_improvement_vs_persistence_percent": 7.04,
                },
            },
            "scientific_note": (
                "Uploaded SIC grids were validated against the frozen "
                "PolarGuard Member-1 interface. NaN cells remain masked "
                "and are not treated as open water. Forecast uncertainty "
                "represents historical per-grid-cell RMSE from 2024 "
                "validation residuals, not a calibrated confidence interval."
            ),
            "generated_at": utc_now(),
        }

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Sea-ice upload forecast failed: {exc}",
        ) from exc


@app.get("/api/sea-ice/intelligence")
def sea_ice_intelligence():
    try:
        satellite = load_latest_satellite_input()

        current = satellite["current"]
        lag1 = satellite["lag1"]
        lag2 = satellite["lag2"]
        lag3 = satellite["lag3"]

        x_coords = satellite["x"]
        y_coords = satellite["y"]

        init_date = np.datetime64(
            safe_value(
                first_existing(
                    satellite,
                    "date",
                    "latest_date",
                    "observation_date",
                )
            )
        )

        forecasts = predict_sea_ice(
            current=current,
            lag1=lag1,
            lag2=lag2,
            lag3=lag3,
            x_coords=x_coords,
            y_coords=y_coords,
            date=init_date,
        )

        uncertainty = load_uncertainty()

        dates = satellite.get("dates", [])
        dates_json = [str(safe_value(x)) for x in dates]

        latest_observation = (
            dates_json[-1]
            if dates_json
            else str(init_date)
        )

        def grid_stats(grid):
            arr = np.asarray(grid, dtype=float)
            valid = np.isfinite(arr)

            if not valid.any():
                return {
                    "valid_cells": 0,
                    "mean_sic": None,
                    "min_sic": None,
                    "max_sic": None,
                }

            values = arr[valid]

            return {
                "valid_cells": int(valid.sum()),
                "mean_sic": float(np.mean(values)),
                "min_sic": float(np.min(values)),
                "max_sic": float(np.max(values)),
            }

        def get_forecast_grid(container, horizon):
            candidates = [
                horizon,
                f"{horizon}h",
                f"forecast_{horizon}h",
                f"forecast_{horizon}",
                f"sic_{horizon}h",
            ]

            if isinstance(container, dict):
                for key in candidates:
                    if key in container:
                        return container[key]

            return None

        forecast_24 = get_forecast_grid(forecasts, 24)
        forecast_48 = get_forecast_grid(forecasts, 48)
        forecast_72 = get_forecast_grid(forecasts, 72)

        if forecast_24 is None or forecast_48 is None or forecast_72 is None:
            raise RuntimeError(
                "Could not locate one or more Member 1 forecast grids "
                "in predict_sea_ice() output."
            )

        def get_uncertainty_grid(container, horizon):
            candidates = [
                horizon,
                f"{horizon}h",
                f"uncertainty_{horizon}h",
                f"rmse_{horizon}h",
            ]

            if isinstance(container, dict):
                for key in candidates:
                    if key in container:
                        return container[key]

            return None

        uncertainty_24 = get_uncertainty_grid(uncertainty, 24)
        uncertainty_48 = get_uncertainty_grid(uncertainty, 48)
        uncertainty_72 = get_uncertainty_grid(uncertainty, 72)

        response = {
            "ok": True,

            "source": {
                "provider": "NOAA / NSIDC",
                "product": "G10016 Version 4",
                "mode": "latest_available",
                "latest_observation": latest_observation,
                "provider_lag_days": safe_value(
                    first_existing(
                        satellite,
                        "provider_lag_days",
                        "provider_lag",
                        "lag_days",
                    )
                ),
            },

            "grid": {
                "shape": list(current.shape),
                "crs": "EPSG:3412",
            },

            "current": grid_stats(current),

            "forecast": {
                "24h": grid_stats(forecast_24),
                "48h": grid_stats(forecast_48),
                "72h": grid_stats(forecast_72),
            },

            "uncertainty": {
                "24h": grid_stats(uncertainty_24)
                if uncertainty_24 is not None
                else None,

                "48h": grid_stats(uncertainty_48)
                if uncertainty_48 is not None
                else None,

                "72h": grid_stats(uncertainty_72)
                if uncertainty_72 is not None
                else None,
            },

            "evaluation_2025": {
                "label": "Held-out 2025 test set",

                "24h": {
                    "mae": 0.008854,
                    "rmse": 0.036288,
                    "within_5pp_percent": 94.87,
                    "rmse_improvement_vs_persistence_percent": 4.56,
                },

                "48h": {
                    "mae": 0.012707,
                    "rmse": 0.050063,
                    "within_5pp_percent": 93.18,
                    "rmse_improvement_vs_persistence_percent": 5.73,
                },

                "72h": {
                    "mae": 0.015287,
                    "rmse": 0.059311,
                    "within_5pp_percent": 92.33,
                    "rmse_improvement_vs_persistence_percent": 7.04,
                },
            },

            "scientific_note": (
                "Uncertainty represents historical per-grid-cell RMSE "
                "calculated from 2024 validation residuals and is not "
                "a calibrated confidence interval."
            ),

            "timestamp_utc": utc_now(),
        }

        return response

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Sea-Ice Intelligence failed: {exc}",
        ) from exc
@app.get("/api/sea-ice/map/{horizon}")
def sea_ice_map(
    horizon: str,
    mode: str = "latest_available",
    date: str | None = None,
    token: str | None = None,
):
    """
    Render a PolarGuard Antarctic sea-ice field as a PNG.

    Supported horizons:
        current
        24h
        48h
        72h

    Supported modes:
        latest_available
        historical_date
        upload

    Examples:

        Latest:
        /api/sea-ice/map/current?mode=latest_available

        Historical:
        /api/sea-ice/map/24h?mode=historical_date&date=2025-08-15
    """

    from fastapi.responses import Response
    from matplotlib.colors import LinearSegmentedColormap

    try:
        # =====================================================
        # Validate horizon
        # =====================================================

        allowed_horizons = {
            "current",
            "24h",
            "48h",
            "72h",
        }

        horizon = horizon.lower().strip()

        if horizon not in allowed_horizons:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid horizon. Use one of: "
                    "current, 24h, 48h, 72h"
                ),
            )

        # =====================================================
        # Validate / normalize mode
        # =====================================================

        mode = mode.lower().strip()

        mode_aliases = {
            "latest": "latest_available",
            "realtime": "latest_available",
            "real_time": "latest_available",
            "near_real_time": "latest_available",
            "nrt": "latest_available",
            "historical": "historical_date",
            "date": "historical_date",
            "uploaded": "upload",
        }

        mode = mode_aliases.get(
            mode,
            mode,
        )

        allowed_modes = {
            "latest_available",
            "historical_date",
            "upload",
        }

        if mode not in allowed_modes:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid sea-ice mode. Use one of: "
                    "latest_available, historical_date, upload"
                ),
            )

        # =====================================================
        # Load selected input bundle
        # =====================================================

        cached_forecasts = None

        if mode == "latest_available":

            bundle = load_latest_available_input()

        elif mode == "historical_date":

            if not date:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "date is required when "
                        "mode=historical_date"
                    ),
                )

            bundle = load_historical_input(date)

        else:

            if not token:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "token is required when mode=upload"
                    ),
                )

            cached = SEA_ICE_UPLOAD_CACHE.get(token)

            if cached is None:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "Upload session not found or expired. "
                        "Upload the four SIC files again."
                    ),
                )

            bundle = cached["bundle"]
            cached_forecasts = cached["forecast"]

        # =====================================================
        # Member-1 compatible inputs
        # =====================================================

        current = np.asarray(
            bundle.current,
            dtype=np.float32,
        )

        lag1 = np.asarray(
            bundle.lag1,
            dtype=np.float32,
        )

        lag2 = np.asarray(
            bundle.lag2,
            dtype=np.float32,
        )

        lag3 = np.asarray(
            bundle.lag3,
            dtype=np.float32,
        )

        x_coords = np.asarray(
            bundle.x,
            dtype=np.float64,
        )

        y_coords = np.asarray(
            bundle.y,
            dtype=np.float64,
        )

        init_date = np.datetime64(
            bundle.date,
            "D",
        )

        # =====================================================
        # Select current observation or forecast
        # =====================================================

        if horizon == "current":

            grid = current

            if mode == "latest_available":
                title_horizon = "CURRENT OBSERVATION"
            elif mode == "historical_date":
                title_horizon = "HISTORICAL OBSERVATION"
            else:
                title_horizon = "UPLOADED OBSERVATION"

        else:

            if mode == "upload" and cached_forecasts is not None:
                forecasts = cached_forecasts
            else:
                forecasts = predict_sea_ice(
                    current=current,
                    lag1=lag1,
                    lag2=lag2,
                    lag3=lag3,
                    x_coords=x_coords,
                    y_coords=y_coords,
                    date=init_date,
                )

            hours = int(
                horizon.replace(
                    "h",
                    "",
                )
            )

            candidates = [
                hours,
                horizon,
                f"forecast_{horizon}",
                f"forecast_{hours}",
                f"sic_{horizon}",
            ]

            grid = None

            if isinstance(
                forecasts,
                dict,
            ):
                for key in candidates:
                    if key in forecasts:
                        grid = forecasts[key]
                        break

            if grid is None:
                raise RuntimeError(
                    f"Could not locate {horizon} "
                    "forecast grid."
                )

            grid = np.asarray(
                grid,
                dtype=np.float32,
            )

            title_horizon = (
                f"+{hours} HOUR FORECAST"
            )

        # =====================================================
        # Validate SIC
        # =====================================================

        grid = np.asarray(
            grid,
            dtype=np.float32,
        )

        grid[
            (grid < 0.0)
            | (grid > 1.0)
        ] = np.nan

        masked = np.ma.masked_invalid(
            grid
        )

        # =====================================================
        # PolarGuard high-contrast SIC colour map
        # =====================================================

        sic_cmap = (
            LinearSegmentedColormap.from_list(
                "polarguard_sic",
                [
                    (0.00, "#03101a"),
                    (0.08, "#062b45"),
                    (0.22, "#075b82"),
                    (0.40, "#078fb0"),
                    (0.58, "#1bd4df"),
                    (0.75, "#79eef1"),
                    (0.90, "#c7f8f4"),
                    (1.00, "#f4ffff"),
                ],
            )
        )

        sic_cmap.set_bad(
            "#02070b"
        )

        # =====================================================
        # Render
        # =====================================================

        fig, ax = plt.subplots(
            figsize=(9.2, 9.2),
            dpi=150,
        )

        fig.patch.set_facecolor(
            "#02070b"
        )

        ax.set_facecolor(
            "#02070b"
        )

        image = ax.imshow(
            masked,
            origin="lower",
            cmap=sic_cmap,
            vmin=0.0,
            vmax=1.0,
            interpolation="bilinear",
        )

        # subtle frame

        for spine in ax.spines.values():
            spine.set_color(
                "#183946"
            )
            spine.set_linewidth(
                0.8
            )

        ax.set_xticks([])
        ax.set_yticks([])

        # =====================================================
        # Title / provenance
        # =====================================================

        init_date_text = str(
            init_date
        )

        if mode == "latest_available":

            source_line = "NOAA / NSIDC G10016 V4"
            mode_line = "LATEST AVAILABLE"
            source_color = "#66e9ff"

        elif mode == "historical_date":

            source_line = "NOAA / NSIDC G02202 V6"
            mode_line = "HISTORICAL REPLAY"
            source_color = "#9ce870"

        else:

            source_line = "OPERATOR-PROVIDED SIC"
            mode_line = "UPLOAD DATA"
            source_color = "#ecc966"

        ax.text(
            0.025,
            0.965,
            "POLARGUARD",
            transform=ax.transAxes,
            color="#66e9ff",
            fontsize=8,
            fontweight="bold",
            va="top",
            ha="left",
        )

        ax.text(
            0.025,
            0.925,
            title_horizon,
            transform=ax.transAxes,
            color="#f0fcff",
            fontsize=15,
            fontweight="bold",
            va="top",
            ha="left",
        )

        ax.text(
            0.025,
            0.885,
            (
                f"{source_line}  |  "
                f"INIT {init_date_text}"
            ),
            transform=ax.transAxes,
            color="#7395a1",
            fontsize=6.5,
            va="top",
            ha="left",
        )

        ax.text(
            0.025,
            0.855,
            mode_line,
            transform=ax.transAxes,
            color=source_color,
            fontsize=5.8,
            fontweight="bold",
            va="top",
            ha="left",
        )

        # =====================================================
        # Colorbar
        # =====================================================

        colorbar = fig.colorbar(
            image,
            ax=ax,
            orientation="horizontal",
            fraction=0.035,
            pad=0.025,
            aspect=35,
        )

        colorbar.set_ticks(
            [
                0.0,
                0.25,
                0.50,
                0.75,
                1.0,
            ]
        )

        colorbar.set_ticklabels(
            [
                "0%",
                "25%",
                "50%",
                "75%",
                "100%",
            ]
        )

        colorbar.ax.tick_params(
            colors="#78949e",
            labelsize=6,
            length=0,
        )

        colorbar.outline.set_edgecolor(
            "#183946"
        )

        colorbar.set_label(
            "SEA-ICE CONCENTRATION",
            color="#6e909b",
            fontsize=6,
            labelpad=5,
        )

        # =====================================================
        # Footer
        # =====================================================

        ax.text(
            0.975,
            0.025,
            "EPSG:3412  /  25 KM GRID",
            transform=ax.transAxes,
            color="#496772",
            fontsize=5.5,
            va="bottom",
            ha="right",
        )

        plt.tight_layout(
            pad=0.7
        )

        # =====================================================
        # Encode PNG in memory
        # =====================================================

        buffer = io.BytesIO()

        fig.savefig(
            buffer,
            format="png",
            facecolor=fig.get_facecolor(),
            bbox_inches="tight",
            pad_inches=0.08,
        )

        plt.close(fig)

        buffer.seek(0)

        return Response(
            content=buffer.getvalue(),
            media_type="image/png",
            headers={
                "Cache-Control": "no-store",
                "X-PolarGuard-Horizon": horizon,
                "X-PolarGuard-Mode": mode,
                "X-PolarGuard-Date": (
                    init_date_text
                ),
                "X-PolarGuard-Source": (
                    "Operator-Upload"
                    if mode == "upload"
                    else "NOAA-NSIDC"
                ),
            },
        )

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Sea-ice map generation failed: "
                f"{exc}"
            ),
        ) from exc
# ============================================================
# REACT FULL INTEGRATION
# Icebergs / Environment / Risk / Navigation / Models
# ============================================================


@app.get("/api/icebergs/intelligence")
def iceberg_intelligence():
    try:
        result = (
            get_iceberg_intelligence()
        )

        result["timestamp_utc"] = (
            utc_now()
        )

        return result

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Iceberg Intelligence failed: "
                f"{exc}"
            ),
        ) from exc


@app.get("/api/environment/intelligence")
def environment_intelligence(
    latitude: float = -53.55,
    longitude: float = -29.95,
):
    try:
        result = (
            get_environment_intelligence(
                latitude=latitude,
                longitude=longitude,
            )
        )

        result["timestamp_utc"] = (
            utc_now()
        )

        return result

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Environmental Intelligence failed: "
                f"{exc}"
            ),
        ) from exc


@app.get("/api/risk/intelligence")
def risk_intelligence(
    vessel_profile: str = "MEDIUM",
    safety_radius_km: float = 8.0,
    influence_radius_km: float = 24.0,
):
    try:
        result = (
            get_risk_intelligence(
                vessel_profile=vessel_profile,
                safety_radius_km=(
                    safety_radius_km
                ),
                influence_radius_km=(
                    influence_radius_km
                ),
            )
        )

        result["timestamp_utc"] = (
            utc_now()
        )

        return result

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Risk Intelligence failed: "
                f"{exc}"
            ),
        ) from exc
@app.get("/api/navigation/map")
def navigation_map(
    horizon: str = "CURRENT",
    vessel_profile: str = "MEDIUM",
    safety_radius_km: float = 8.0,
    influence_radius_km: float = 24.0,
    sample_step: int = 6,
):
    try:
        result = build_navigation_map_data(
            horizon=horizon,
            vessel_profile=vessel_profile,
            safety_radius_km=safety_radius_km,
            influence_radius_km=influence_radius_km,
            sample_step=sample_step,
        )

        result["timestamp_utc"] = utc_now()

        return result

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Navigation map data failed: "
                f"{exc}"
            ),
        ) from exc

@app.post("/api/navigation/route")
def navigation_route(
    payload: dict[str, Any],
):
    try:
        required = [
            "start_lat",
            "start_lon",
            "destination_lat",
            "destination_lon",
        ]

        missing = [
            key
            for key in required
            if key not in payload
        ]

        if missing:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Missing required navigation "
                    "fields: "
                    + ", ".join(missing)
                ),
            )

        result = (
            get_navigation_decision(
                start_lat=float(
                    payload[
                        "start_lat"
                    ]
                ),
                start_lon=float(
                    payload[
                        "start_lon"
                    ]
                ),
                destination_lat=float(
                    payload[
                        "destination_lat"
                    ]
                ),
                destination_lon=float(
                    payload[
                        "destination_lon"
                    ]
                ),
                vessel_profile=str(
                    payload.get(
                        "vessel_profile",
                        "MEDIUM",
                    )
                ),
                safety_radius_km=float(
                    payload.get(
                        "safety_radius_km",
                        8.0,
                    )
                ),
                influence_radius_km=float(
                    payload.get(
                        "influence_radius_km",
                        24.0,
                    )
                ),
            )
        )

        result["timestamp_utc"] = (
            utc_now()
        )

        return result

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Navigation calculation failed: "
                f"{exc}"
            ),
        ) from exc


@app.get("/api/models/intelligence")
def model_intelligence():
    try:
        result = (
            get_model_intelligence()
        )

        result["timestamp_utc"] = (
            utc_now()
        )

        return result

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Model Intelligence failed: "
                f"{exc}"
            ),
        ) from exc
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api_server:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )