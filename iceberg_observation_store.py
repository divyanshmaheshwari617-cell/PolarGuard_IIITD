from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_HISTORY_PATH = Path(
    "data/current_icebergs/byu_current_iceberg_history.csv"
)

REQUIRED_COLUMNS = [
    "iceberg_id",
    "observation_date",
    "latitude",
    "longitude",
]

FULL_COLUMNS = [
    "iceberg_id",
    "observation_date",
    "latitude",
    "longitude",
    "observation_day_of_year",
    "observation_year",
    "source",
    "source_type",
    "freshness_status",
    "retrieved_at_utc",
    "page_last_revised",
]


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _normalize_iceberg_id(value) -> str:
    """
    Normalize iceberg IDs to uppercase.

    Example:
        a76c -> A76C
    """
    if value is None:
        return ""

    return str(value).strip().upper()


def _ensure_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure all expected operational-history columns exist.
    """
    df = dataframe.copy()

    for column in FULL_COLUMNS:
        if column not in df.columns:
            df[column] = None

    return df[FULL_COLUMNS]


def _normalize_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize iceberg observation records without synthesizing data.
    """
    df = _ensure_columns(dataframe)

    if df.empty:
        return df

    # --------------------------------------------------------
    # ICEBERG ID
    # --------------------------------------------------------

    df["iceberg_id"] = (
        df["iceberg_id"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    df["observation_date"] = pd.to_datetime(
        df["observation_date"],
        errors="coerce",
    )

    # --------------------------------------------------------
    # COORDINATES
    # --------------------------------------------------------

    df["latitude"] = pd.to_numeric(
        df["latitude"],
        errors="coerce",
    )

    df["longitude"] = pd.to_numeric(
        df["longitude"],
        errors="coerce",
    )

    # --------------------------------------------------------
    # REMOVE INVALID OBSERVATIONS
    # --------------------------------------------------------

    df = df[
        df["iceberg_id"].ne("")
        & df["observation_date"].notna()
        & np.isfinite(df["latitude"])
        & np.isfinite(df["longitude"])
    ].copy()

    if df.empty:
        return _ensure_columns(df)

    # Geographic sanity checks.
    df = df[
        df["latitude"].between(-90.0, 90.0)
        & df["longitude"].between(-180.0, 180.0)
    ].copy()

    # --------------------------------------------------------
    # DERIVED DATE FIELDS
    # --------------------------------------------------------

    df["observation_day_of_year"] = (
        df["observation_date"].dt.dayofyear.astype(int)
    )

    df["observation_year"] = (
        df["observation_date"].dt.year.astype(int)
    )

    # Store date in ISO YYYY-MM-DD format.
    df["observation_date"] = (
        df["observation_date"]
        .dt.strftime("%Y-%m-%d")
    )

    # --------------------------------------------------------
    # NORMALIZE TEXT COLUMNS
    # --------------------------------------------------------

    text_columns = [
        "source",
        "source_type",
        "freshness_status",
        "retrieved_at_utc",
        "page_last_revised",
    ]

    for column in text_columns:
        df[column] = (
            df[column]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    return df[FULL_COLUMNS]


# ============================================================
# PUBLIC API
# ============================================================

def load_observation_history(
    path: Path | str = DEFAULT_HISTORY_PATH,
) -> pd.DataFrame:
    """
    Load the operational iceberg observation history.

    Returns an empty correctly-shaped DataFrame if the file
    does not yet exist.
    """
    path = Path(path)

    if not path.exists():
        return pd.DataFrame(columns=FULL_COLUMNS)

    dataframe = pd.read_csv(path)

    return _normalize_dataframe(dataframe)


def save_observation_history(
    dataframe: pd.DataFrame,
    path: Path | str = DEFAULT_HISTORY_PATH,
) -> pd.DataFrame:
    """
    Save a cleaned, de-duplicated operational iceberg history.

    De-duplication key:
        iceberg_id + observation_date

    If the same iceberg/date is seen multiple times, the most
    recently appended record is retained.
    """
    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df = _normalize_dataframe(dataframe)

    if not df.empty:
        df = (
            df.drop_duplicates(
                subset=[
                    "iceberg_id",
                    "observation_date",
                ],
                keep="last",
            )
            .sort_values(
                by=[
                    "iceberg_id",
                    "observation_date",
                ]
            )
            .reset_index(drop=True)
        )

    df.to_csv(
        path,
        index=False,
    )

    return df


def append_observations(
    observations: pd.DataFrame,
    path: Path | str = DEFAULT_HISTORY_PATH,
) -> Dict:
    """
    Append genuine iceberg observations to the persistent history.

    This function does NOT:
        - interpolate positions
        - repeat positions
        - synthesize missing dates
        - fabricate trajectory points
    """
    path = Path(path)

    incoming = _normalize_dataframe(
        observations
    )

    existing = load_observation_history(
        path=path
    )

    rows_before = len(existing)

    combined = pd.concat(
        [
            existing,
            incoming,
        ],
        ignore_index=True,
    )

    saved = save_observation_history(
        combined,
        path=path,
    )

    rows_after = len(saved)

    return {
        "history_path": str(path),
        "incoming_rows": int(len(incoming)),
        "rows_before": int(rows_before),
        "rows_after": int(rows_after),
        "new_unique_observations": int(
            max(
                0,
                rows_after - rows_before,
            )
        ),
        "iceberg_count": int(
            saved["iceberg_id"].nunique()
            if not saved.empty
            else 0
        ),
        "dataframe": saved,
    }


def append_observation_records(
    records: Iterable[Dict],
    path: Path | str = DEFAULT_HISTORY_PATH,
) -> Dict:
    """
    Convenience wrapper for a list of dictionaries.

    Example record:
        {
            "iceberg_id": "A76C",
            "observation_date": "2026-08-23",
            "latitude": -53.55,
            "longitude": -29.95,
            ...
        }
    """
    dataframe = pd.DataFrame(
        list(records)
    )

    return append_observations(
        observations=dataframe,
        path=path,
    )


def get_iceberg_history(
    iceberg_id: str,
    path: Path | str = DEFAULT_HISTORY_PATH,
) -> pd.DataFrame:
    """
    Return all genuine stored observations for one iceberg,
    sorted chronologically.
    """
    iceberg_id = _normalize_iceberg_id(
        iceberg_id
    )

    history = load_observation_history(
        path=path
    )

    if history.empty:
        return history

    result = history[
        history["iceberg_id"]
        == iceberg_id
    ].copy()

    if result.empty:
        return result

    result["observation_date"] = pd.to_datetime(
        result["observation_date"],
        errors="coerce",
    )

    result = (
        result.dropna(
            subset=["observation_date"]
        )
        .sort_values("observation_date")
        .reset_index(drop=True)
    )

    result[
        "observation_date"
    ] = result[
        "observation_date"
    ].dt.strftime("%Y-%m-%d")

    return result


def get_latest_observation(
    iceberg_id: str,
    path: Path | str = DEFAULT_HISTORY_PATH,
) -> Optional[Dict]:
    """
    Return the newest stored genuine observation for one iceberg.
    """
    history = get_iceberg_history(
        iceberg_id=iceberg_id,
        path=path,
    )

    if history.empty:
        return None

    return history.iloc[-1].to_dict()


def get_history_summary(
    path: Path | str = DEFAULT_HISTORY_PATH,
) -> Dict:
    """
    Return a compact summary of the operational history store.
    """
    history = load_observation_history(
        path=path
    )

    if history.empty:
        return {
            "history_path": str(path),
            "row_count": 0,
            "iceberg_count": 0,
            "earliest_date": None,
            "latest_date": None,
        }

    dates = pd.to_datetime(
        history["observation_date"],
        errors="coerce",
    )

    return {
        "history_path": str(path),
        "row_count": int(
            len(history)
        ),
        "iceberg_count": int(
            history["iceberg_id"].nunique()
        ),
        "earliest_date": (
            dates.min().strftime("%Y-%m-%d")
            if dates.notna().any()
            else None
        ),
        "latest_date": (
            dates.max().strftime("%Y-%m-%d")
            if dates.notna().any()
            else None
        ),
    }


# ============================================================
# COMMAND-LINE TEST
# ============================================================

def main():
    summary = get_history_summary()

    print("=" * 72)
    print("POLARGUARD ICEBERG OBSERVATION STORE")
    print("=" * 72)

    for key, value in summary.items():
        print(
            f"{key}: {value}"
        )

    history = load_observation_history()

    print()
    print("First 10 normalized rows:")
    print()

    if history.empty:
        print(
            "No observations available."
        )
    else:
        print(
            history.head(10).to_string(
                index=False
            )
        )


if __name__ == "__main__":
    main()