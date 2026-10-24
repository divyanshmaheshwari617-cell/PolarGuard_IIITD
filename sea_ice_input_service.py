from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from satellite_data_service import load_latest_satellite_input


# ============================================================
# PolarGuard Sea-Ice Input Service
#
# Supported modes:
#   1. latest_available
#   2. historical_date
#   3. upload
#
# All modes produce the SAME Member-1 compatible structure:
#
#   current
#   lag1
#   lag2
#   lag3
#   x
#   y
#   date
#
# Member-1 itself remains frozen.
# ============================================================


PROJECT_ROOT = Path(__file__).resolve().parent

HISTORICAL_DATASET = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "sea_ice_2019_2025.nc"
)

HF_REPO_ID = "divyanshmahesh/PolarGuard-Data"
HF_DATASET_FILENAME = "sea_ice_2019_2025.nc"

SIC_VARIABLE = "sea_ice_concentration"

EXPECTED_SHAPE = (332, 316)

EXPECTED_Y_SIZE = 332
EXPECTED_X_SIZE = 316


@dataclass
class SeaIceInputBundle:
    mode: str

    current: np.ndarray
    lag1: np.ndarray
    lag2: np.ndarray
    lag3: np.ndarray

    x: np.ndarray
    y: np.ndarray

    date: np.datetime64

    metadata: dict[str, Any]

    def to_member1_inputs(self) -> dict[str, Any]:
        """Return the exact input structure required by Member 1."""
        return {
            "current": self.current,
            "lag1": self.lag1,
            "lag2": self.lag2,
            "lag3": self.lag3,
            "x_coords": self.x,
            "y_coords": self.y,
            "date": self.date,
        }


# ============================================================
# Validation
# ============================================================


def _validate_grid_shape(
    array: np.ndarray,
    name: str,
) -> np.ndarray:
    array = np.asarray(array, dtype=np.float32)

    if array.shape != EXPECTED_SHAPE:
        raise ValueError(
            f"{name} has shape {array.shape}; "
            f"expected {EXPECTED_SHAPE}."
        )

    return array


def _clean_and_validate_sic(
    array: np.ndarray,
    name: str,
) -> np.ndarray:
    """
    Validate a PolarGuard SIC grid.

    Valid SIC values are 0.0 to 1.0.
    NaN is allowed and represents invalid/masked cells.

    Invalid/masked cells are not converted to open water.
    """
    array = _validate_grid_shape(array, name).copy()

    finite = np.isfinite(array)

    if not np.any(finite):
        raise ValueError(f"{name} contains no valid SIC cells.")

    invalid_range = finite & ((array < 0.0) | (array > 1.0))
    invalid_count = int(np.count_nonzero(invalid_range))

    if invalid_count > 0:
        raise ValueError(
            f"{name} contains {invalid_count} SIC values "
            "outside the valid 0.0-1.0 range."
        )

    return array


def _validate_coordinates(
    x: np.ndarray,
    y: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)

    if x.ndim != 1:
        raise ValueError("x coordinates must be one-dimensional.")

    if y.ndim != 1:
        raise ValueError("y coordinates must be one-dimensional.")

    if x.shape[0] != EXPECTED_X_SIZE:
        raise ValueError(
            f"x contains {x.shape[0]} values; "
            f"expected {EXPECTED_X_SIZE}."
        )

    if y.shape[0] != EXPECTED_Y_SIZE:
        raise ValueError(
            f"y contains {y.shape[0]} values; "
            f"expected {EXPECTED_Y_SIZE}."
        )

    if not np.all(np.isfinite(x)):
        raise ValueError("x coordinates contain invalid values.")

    if not np.all(np.isfinite(y)):
        raise ValueError("y coordinates contain invalid values.")

    return x, y


def _validate_four_grids(
    current: np.ndarray,
    lag1: np.ndarray,
    lag2: np.ndarray,
    lag3: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    current = _clean_and_validate_sic(current, "current")
    lag1 = _clean_and_validate_sic(lag1, "lag1")
    lag2 = _clean_and_validate_sic(lag2, "lag2")
    lag3 = _clean_and_validate_sic(lag3, "lag3")

    return current, lag1, lag2, lag3


def _grid_statistics(array: np.ndarray) -> dict[str, Any]:
    finite = np.isfinite(array)
    valid_cells = int(np.count_nonzero(finite))
    total_cells = int(array.size)

    if valid_cells == 0:
        return {
            "valid_cells": 0,
            "masked_cells": total_cells,
            "valid_fraction": 0.0,
            "mean_sic": None,
            "min_sic": None,
            "max_sic": None,
        }

    values = array[finite]

    return {
        "valid_cells": valid_cells,
        "masked_cells": total_cells - valid_cells,
        "valid_fraction": valid_cells / total_cells,
        "mean_sic": float(np.mean(values)),
        "min_sic": float(np.min(values)),
        "max_sic": float(np.max(values)),
    }


# ============================================================
# Historical dataset
# ============================================================


def _resolve_historical_dataset_path() -> Path:
    """
    Use the local historical NetCDF file when present.

    On Streamlit Cloud, where the large file is not stored in
    the GitHub repository, download it from Hugging Face using
    the HF_TOKEN secret.
    """
    if HISTORICAL_DATASET.is_file():
        return HISTORICAL_DATASET

    try:
        import streamlit as st
        from huggingface_hub import hf_hub_download

        token = st.secrets["HF_TOKEN"]

        downloaded_path = hf_hub_download(
            repo_id=HF_REPO_ID,
            filename=HF_DATASET_FILENAME,
            repo_type="dataset",
            token=token,
        )

        dataset_path = Path(downloaded_path)

        if not dataset_path.is_file():
            raise FileNotFoundError(
                f"Hugging Face returned a path that does not exist: "
                f"{dataset_path}"
            )

        return dataset_path

    except Exception as exc:
        raise FileNotFoundError(
            "The historical sea-ice dataset was not found locally, "
            "and the Hugging Face download failed. Verify that "
            "HF_TOKEN is set in Streamlit app Secrets and that the "
            "token can read the dataset "
            f"'{HF_REPO_ID}/{HF_DATASET_FILENAME}'."
        ) from exc


def _open_historical_dataset() -> xr.Dataset:
    dataset_path = _resolve_historical_dataset_path()

    ds = xr.open_dataset(dataset_path)

    required_dimensions = {"time", "y", "x"}
    missing_dimensions = required_dimensions - set(ds.dims)

    if missing_dimensions:
        ds.close()
        raise ValueError(
            "Historical dataset is missing dimensions: "
            + ", ".join(sorted(missing_dimensions))
        )

    if SIC_VARIABLE not in ds.data_vars:
        ds.close()
        raise ValueError(
            f"Historical dataset does not contain '{SIC_VARIABLE}'."
        )

    if (
        ds.sizes["y"] != EXPECTED_Y_SIZE
        or ds.sizes["x"] != EXPECTED_X_SIZE
    ):
        shape = (ds.sizes["y"], ds.sizes["x"])
        ds.close()
        raise ValueError(
            f"Historical grid shape is {shape}; "
            f"expected {EXPECTED_SHAPE}."
        )

    return ds


def get_historical_date_range() -> dict[str, str]:
    ds = _open_historical_dataset()

    try:
        times = np.asarray(ds["time"].values).astype("datetime64[D]")

        return {
            "first_date": str(times.min()),
            "last_date": str(times.max()),
        }

    finally:
        ds.close()


# ============================================================
# MODE 1 — Latest available
# ============================================================


def load_latest_available_input() -> SeaIceInputBundle:
    """Load the latest four consecutive NOAA/NSIDC SIC observations."""
    satellite = load_latest_satellite_input()

    current = satellite["current"]
    lag1 = satellite["lag1"]
    lag2 = satellite["lag2"]
    lag3 = satellite["lag3"]

    current, lag1, lag2, lag3 = _validate_four_grids(
        current,
        lag1,
        lag2,
        lag3,
    )

    x, y = _validate_coordinates(
        satellite["x"],
        satellite["y"],
    )

    date = np.datetime64(satellite["date"], "D")
    dates = satellite.get("dates", [])

    metadata = {
        "mode": "latest_available",
        "mode_label": "Latest Available",
        "source_type": "provider",
        "provider": "NOAA / NSIDC",
        "product": "G10016 Version 4",
        "crs": "EPSG:3412",
        "grid_shape": list(EXPECTED_SHAPE),
        "initialization_date": str(date),
        "input_dates": [str(value) for value in dates],
        "provider_lag_days": satellite.get("provider_lag_days"),
        "validation_status": "passed",
        "member1_ready": True,
        "current_statistics": _grid_statistics(current),
        "note": (
            "Latest available near-real-time NOAA/NSIDC "
            "satellite-derived SIC. This is not a literal live stream."
        ),
    }

    return SeaIceInputBundle(
        mode="latest_available",
        current=current,
        lag1=lag1,
        lag2=lag2,
        lag3=lag3,
        x=x,
        y=y,
        date=date,
        metadata=metadata,
    )


# ============================================================
# MODE 2 — Historical date
# ============================================================


def load_historical_input(
    selected_date: str | np.datetime64,
) -> SeaIceInputBundle:
    """
    Load the selected date and its three preceding days
    from the combined 2019-2025 historical dataset.
    """
    try:
        requested_date = np.datetime64(selected_date, "D")
    except Exception as exc:
        raise ValueError("Invalid historical date.") from exc

    ds = _open_historical_dataset()

    try:
        times = np.asarray(ds["time"].values).astype("datetime64[D]")
        first_date = times.min()
        last_date = times.max()

        required_dates = [
            requested_date,
            requested_date - np.timedelta64(1, "D"),
            requested_date - np.timedelta64(2, "D"),
            requested_date - np.timedelta64(3, "D"),
        ]

        if requested_date > last_date:
            raise ValueError(
                f"Selected date {requested_date} is outside the "
                f"historical dataset. Latest available historical "
                f"date is {last_date}."
            )

        if required_dates[-1] < first_date:
            earliest_valid = first_date + np.timedelta64(3, "D")
            raise ValueError(
                f"Selected date {requested_date} does not have three "
                f"previous daily inputs. Earliest usable initialization "
                f"date is {earliest_valid}."
            )

        index_by_date = {
            date: index
            for index, date in enumerate(times)
        }

        missing_dates = [
            date for date in required_dates if date not in index_by_date
        ]

        if missing_dates:
            missing_text = ", ".join(str(date) for date in missing_dates)
            raise ValueError(
                "Historical input sequence is incomplete. "
                f"Missing date(s): {missing_text}"
            )

        arrays = []

        for date in required_dates:
            index = index_by_date[date]
            array = np.asarray(
                ds[SIC_VARIABLE].isel(time=index).values,
                dtype=np.float32,
            )
            arrays.append(array)

        current, lag1, lag2, lag3 = _validate_four_grids(
            arrays[0],
            arrays[1],
            arrays[2],
            arrays[3],
        )

        x, y = _validate_coordinates(
            ds["x"].values,
            ds["y"].values,
        )

    finally:
        ds.close()

    metadata = {
        "mode": "historical_date",
        "mode_label": "Historical Date",
        "source_type": "historical_archive",
        "provider": "NOAA / NSIDC",
        "product": "G02202 Version 6 historical archive",
        "crs": "EPSG:3412",
        "grid_shape": list(EXPECTED_SHAPE),
        "initialization_date": str(requested_date),
        "input_dates": [str(date) for date in required_dates],
        "historical_dataset_start": str(first_date),
        "historical_dataset_end": str(last_date),
        "provider_lag_days": None,
        "validation_status": "passed",
        "member1_ready": True,
        "current_statistics": _grid_statistics(current),
        "note": (
            "Historical replay using the selected NOAA/NSIDC "
            "observation and the three preceding daily SIC fields."
        ),
    }

    return SeaIceInputBundle(
        mode="historical_date",
        current=current,
        lag1=lag1,
        lag2=lag2,
        lag3=lag3,
        x=x,
        y=y,
        date=requested_date,
        metadata=metadata,
    )


# ============================================================
# MODE 3 — User upload
# ============================================================


def load_uploaded_input(
    *,
    current: np.ndarray,
    lag1: np.ndarray,
    lag2: np.ndarray,
    lag3: np.ndarray,
    date: str | np.datetime64,
    x: np.ndarray | None = None,
    y: np.ndarray | None = None,
    source_name: str = "User Provided",
) -> SeaIceInputBundle:
    """
    Validate user-provided Member-1 SIC inputs.

    The user must provide current, lag1, lag2, and lag3 grids.

    If x/y are omitted, use the canonical x/y grid from the
    historical Member-1 dataset.
    """
    try:
        initialization_date = np.datetime64(date, "D")
    except Exception as exc:
        raise ValueError("Invalid initialization date.") from exc

    current, lag1, lag2, lag3 = _validate_four_grids(
        current,
        lag1,
        lag2,
        lag3,
    )

    coordinate_source = "uploaded"

    if x is None or y is None:
        ds = _open_historical_dataset()

        try:
            reference_x = np.asarray(ds["x"].values, dtype=np.float64)
            reference_y = np.asarray(ds["y"].values, dtype=np.float64)
        finally:
            ds.close()

        if x is None:
            x = reference_x

        if y is None:
            y = reference_y

        coordinate_source = "PolarGuard canonical EPSG:3412 grid"

    x, y = _validate_coordinates(x, y)

    input_dates = [
        initialization_date,
        initialization_date - np.timedelta64(1, "D"),
        initialization_date - np.timedelta64(2, "D"),
        initialization_date - np.timedelta64(3, "D"),
    ]

    metadata = {
        "mode": "upload",
        "mode_label": "Upload Data",
        "source_type": "user_upload",
        "provider": source_name,
        "product": "User-provided SIC grids",
        "crs": "EPSG:3412",
        "grid_shape": list(EXPECTED_SHAPE),
        "initialization_date": str(initialization_date),
        "input_dates": [str(value) for value in input_dates],
        "coordinate_source": coordinate_source,
        "provider_lag_days": None,
        "validation_status": "passed",
        "member1_ready": True,
        "current_statistics": _grid_statistics(current),
        "note": (
            "User-provided SIC input validated against the frozen "
            "Member-1 interface. NaN remains masked/invalid and is not "
            "converted to open water."
        ),
    }

    return SeaIceInputBundle(
        mode="upload",
        current=current,
        lag1=lag1,
        lag2=lag2,
        lag3=lag3,
        x=x,
        y=y,
        date=initialization_date,
        metadata=metadata,
    )


# ============================================================
# Unified mode loader
# ============================================================


def load_sea_ice_input(
    mode: str,
    *,
    selected_date: str | np.datetime64 | None = None,
    current: np.ndarray | None = None,
    lag1: np.ndarray | None = None,
    lag2: np.ndarray | None = None,
    lag3: np.ndarray | None = None,
    date: str | np.datetime64 | None = None,
    x: np.ndarray | None = None,
    y: np.ndarray | None = None,
    source_name: str = "User Provided",
) -> SeaIceInputBundle:
    """Unified PolarGuard sea-ice input entry point."""
    normalized_mode = mode.strip().lower()

    aliases = {
        "latest": "latest_available",
        "real_time": "latest_available",
        "realtime": "latest_available",
        "near_real_time": "latest_available",
        "nrt": "latest_available",
        "historical": "historical_date",
        "date": "historical_date",
        "user_upload": "upload",
        "uploaded": "upload",
    }

    normalized_mode = aliases.get(normalized_mode, normalized_mode)

    if normalized_mode == "latest_available":
        return load_latest_available_input()

    if normalized_mode == "historical_date":
        if selected_date is None:
            raise ValueError(
                "selected_date is required for historical_date mode."
            )

        return load_historical_input(selected_date)

    if normalized_mode == "upload":
        required = {
            "current": current,
            "lag1": lag1,
            "lag2": lag2,
            "lag3": lag3,
            "date": date,
        }

        missing = [
            name for name, value in required.items() if value is None
        ]

        if missing:
            raise ValueError(
                "Upload mode is missing required input(s): "
                + ", ".join(missing)
            )

        return load_uploaded_input(
            current=current,
            lag1=lag1,
            lag2=lag2,
            lag3=lag3,
            date=date,
            x=x,
            y=y,
            source_name=source_name,
        )

    raise ValueError(
        f"Unknown sea-ice input mode '{mode}'. Supported modes: "
        "latest_available, historical_date, upload."
    )


# ============================================================
# Debug / standalone test
# ============================================================


if __name__ == "__main__":
    print("\n=== POLARGUARD SEA-ICE INPUT SERVICE ===\n")

    date_range = get_historical_date_range()
    print("Historical range:", date_range)

    historical = load_historical_input("2025-08-15")

    print("\nHistorical mode:")
    print("Mode:", historical.mode)
    print("Initialization:", historical.date)
    print("Current shape:", historical.current.shape)
    print("Lag1 shape:", historical.lag1.shape)
    print("Lag2 shape:", historical.lag2.shape)
    print("Lag3 shape:", historical.lag3.shape)
    print("X:", historical.x.shape)
    print("Y:", historical.y.shape)
    print("Metadata:", historical.metadata)
    print(
        "\nMember-1 ready:",
        historical.metadata["member1_ready"],
    )