"""
PolarGuard - Current Iceberg Observation History
================================================

Stores real observations obtained from current_iceberg_service.py.

Purpose:
    - Build a local observation history from real BYU current-position updates.
    - Never fabricate missing daily observations.
    - Detect when an iceberg has enough recent history for PolarGuard Member-2.

The frozen Member-2 model requires:
    t, t-1, t-2, t-3

Therefore four consecutive daily positions are required for direct model input.
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from current_iceberg_service import load_current_icebergs


# ============================================================
# CONFIGURATION
# ============================================================

HISTORY_DIRECTORY = Path(
    "data/current_icebergs"
)

HISTORY_FILE = (
    HISTORY_DIRECTORY
    / "byu_current_iceberg_history.csv"
)

METADATA_FILE = (
    HISTORY_DIRECTORY
    / "byu_current_iceberg_history_metadata.json"
)


# ============================================================
# STORAGE INITIALIZATION
# ============================================================

def ensure_storage() -> None:
    """
    Create local storage directory if it does not exist.
    """

    HISTORY_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )


# ============================================================
# EMPTY TABLE
# ============================================================

def empty_history_dataframe() -> pd.DataFrame:
    """
    Return the canonical PolarGuard current iceberg history schema.
    """

    return pd.DataFrame(
        columns=[
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
    )


# ============================================================
# LOAD HISTORY
# ============================================================

def load_history() -> pd.DataFrame:
    """
    Load locally accumulated real iceberg observations.
    """

    ensure_storage()

    if not HISTORY_FILE.exists():
        return empty_history_dataframe()

    dataframe = pd.read_csv(
        HISTORY_FILE,
        dtype={
            "iceberg_id": str,
        },
    )

    if dataframe.empty:
        return empty_history_dataframe()

    dataframe["iceberg_id"] = (
        dataframe["iceberg_id"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    dataframe["observation_date"] = (
        pd.to_datetime(
            dataframe["observation_date"],
            errors="coerce",
        )
        .dt.date
        .astype(str)
    )

    dataframe["latitude"] = pd.to_numeric(
        dataframe["latitude"],
        errors="coerce",
    )

    dataframe["longitude"] = pd.to_numeric(
        dataframe["longitude"],
        errors="coerce",
    )

    dataframe = dataframe.dropna(
        subset=[
            "iceberg_id",
            "observation_date",
            "latitude",
            "longitude",
        ]
    )

    dataframe = dataframe.sort_values(
        [
            "iceberg_id",
            "observation_date",
        ]
    ).reset_index(drop=True)

    return dataframe


# ============================================================
# BUILD RECORDS FROM CURRENT BUNDLE
# ============================================================

def current_bundle_to_history_rows(
    bundle: Dict,
) -> pd.DataFrame:
    """
    Convert current_iceberg_service output to history rows.
    """

    dataframe = bundle[
        "dataframe"
    ].copy()

    required = [
        "iceberg_id",
        "observation_date",
        "latitude",
        "longitude",
        "observation_day_of_year",
        "observation_year",
        "source",
        "source_type",
        "freshness_status",
    ]

    missing = [
        column
        for column in required
        if column not in dataframe.columns
    ]

    if missing:
        raise ValueError(
            "Current iceberg bundle is missing columns: "
            + ", ".join(missing)
        )

    output = dataframe[
        required
    ].copy()

    output["retrieved_at_utc"] = (
        bundle["retrieved_at_utc"]
    )

    output["page_last_revised"] = (
        bundle["page_last_revised"]
    )

    output["iceberg_id"] = (
        output["iceberg_id"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    return output


# ============================================================
# MERGE HISTORY
# ============================================================

def update_history() -> Dict:
    """
    Download the latest BYU current iceberg positions and merge them
    into the local history.

    Duplicate observations are identified by:
        iceberg_id + observation_date

    If the provider republishes the same date with a revised coordinate,
    the newest retrieved coordinate replaces the previously stored row.
    """

    ensure_storage()

    existing = load_history()

    bundle = load_current_icebergs()

    incoming = current_bundle_to_history_rows(
        bundle
    )

    before_rows = len(existing)

    combined = pd.concat(
        [
            existing,
            incoming,
        ],
        ignore_index=True,
    )

    combined["observation_date"] = (
        pd.to_datetime(
            combined["observation_date"],
            errors="coerce",
        )
        .dt.date
        .astype(str)
    )

    combined = combined.dropna(
        subset=[
            "iceberg_id",
            "observation_date",
            "latitude",
            "longitude",
        ]
    )

    # Keep newest retrieval when same iceberg/date appears again.
    combined = combined.sort_values(
        "retrieved_at_utc"
    )

    combined = combined.drop_duplicates(
        subset=[
            "iceberg_id",
            "observation_date",
        ],
        keep="last",
    )

    combined = combined.sort_values(
        [
            "iceberg_id",
            "observation_date",
        ]
    ).reset_index(drop=True)

    after_rows = len(combined)

    combined.to_csv(
        HISTORY_FILE,
        index=False,
    )

    metadata = {
        "system": "PolarGuard",
        "source": bundle["source"],
        "source_url": bundle["source_url"],
        "last_collection_utc":
            bundle["retrieved_at_utc"],
        "source_page_last_revised":
            bundle["page_last_revised"],
        "current_provider_iceberg_count":
            bundle["iceberg_count"],
        "history_rows":
            int(after_rows),
        "unique_icebergs":
            int(
                combined["iceberg_id"]
                .nunique()
            ),
        "new_history_rows":
            int(
                max(
                    after_rows - before_rows,
                    0,
                )
            ),
        "note": (
            "Only real provider observations are stored. "
            "Missing daily observations are never interpolated "
            "for frozen Member-2 input."
        ),
    }

    METADATA_FILE.write_text(
        json.dumps(
            metadata,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "history": combined,
        "metadata": metadata,
        "current_bundle": bundle,
    }


# ============================================================
# GET ICEBERG HISTORY
# ============================================================

def get_iceberg_history(
    iceberg_id: str,
    history: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Return all locally collected observations for one iceberg.
    """

    if history is None:
        history = load_history()

    target = (
        str(iceberg_id)
        .strip()
        .lower()
    )

    result = history[
        history["iceberg_id"]
        .str.lower()
        .eq(target)
    ].copy()

    if result.empty:
        return result

    result["_date"] = pd.to_datetime(
        result["observation_date"]
    )

    result = result.sort_values(
        "_date"
    ).drop(
        columns="_date"
    )

    return result.reset_index(
        drop=True
    )


# ============================================================
# FIND FOUR CONSECUTIVE DAYS
# ============================================================

def get_latest_four_consecutive_positions(
    iceberg_id: str,
    history: Optional[pd.DataFrame] = None,
) -> Optional[pd.DataFrame]:
    """
    Return the newest four consecutive REAL daily observations.

    Required pattern:
        D-3
        D-2
        D-1
        D

    No interpolation is performed.
    """

    iceberg_history = get_iceberg_history(
        iceberg_id,
        history=history,
    )

    if len(iceberg_history) < 4:
        return None

    iceberg_history = (
        iceberg_history.copy()
    )

    iceberg_history["_date"] = (
        pd.to_datetime(
            iceberg_history[
                "observation_date"
            ]
        )
    )

    iceberg_history = (
        iceberg_history
        .sort_values("_date")
        .reset_index(drop=True)
    )

    # Search from newest backwards.
    for end_index in range(
        len(iceberg_history) - 1,
        2,
        -1,
    ):

        candidate = iceberg_history.iloc[
            end_index - 3:
            end_index + 1
        ].copy()

        dates = candidate[
            "_date"
        ].values.astype(
            "datetime64[D]"
        )

        differences = np.diff(
            dates
        ).astype(
            "timedelta64[D]"
        ).astype(int)

        if np.all(
            differences == 1
        ):
            return (
                candidate
                .drop(
                    columns="_date"
                )
                .reset_index(drop=True)
            )

    return None


# ============================================================
# MEMBER-2 READINESS
# ============================================================

def assess_history_readiness(
    iceberg_id: str,
    history: Optional[pd.DataFrame] = None,
) -> Dict:
    """
    Determine whether an iceberg can be passed to frozen Member-2.
    """

    if history is None:
        history = load_history()

    iceberg_history = get_iceberg_history(
        iceberg_id,
        history=history,
    )

    four = get_latest_four_consecutive_positions(
        iceberg_id,
        history=history,
    )

    if iceberg_history.empty:

        return {
            "iceberg_id":
                iceberg_id.upper(),

            "observations_stored":
                0,

            "trajectory_model_ready":
                False,

            "reason":
                "No locally collected real observations are available.",
        }

    latest_date = iceberg_history[
        "observation_date"
    ].iloc[-1]

    if four is None:

        return {
            "iceberg_id":
                iceberg_id.upper(),

            "observations_stored":
                int(
                    len(
                        iceberg_history
                    )
                ),

            "latest_observation_date":
                latest_date,

            "trajectory_model_ready":
                False,

            "required_consecutive_days":
                4,

            "reason": (
                "Four consecutive real daily positions "
                "have not yet been collected."
            ),
        }

    dates = four[
        "observation_date"
    ].tolist()

    return {
        "iceberg_id":
            iceberg_id.upper(),

        "observations_stored":
            int(
                len(
                    iceberg_history
                )
            ),

        "latest_observation_date":
            latest_date,

        "trajectory_model_ready":
            True,

        "required_consecutive_days":
            4,

        "member2_input_dates":
            dates,

        "positions":
            four[
                [
                    "observation_date",
                    "latitude",
                    "longitude",
                ]
            ].to_dict(
                orient="records"
            ),

        "reason":
            "Four consecutive real daily observations are available.",
    }


# ============================================================
# ALL READY ICEBERGS
# ============================================================

def find_member2_ready_icebergs(
    history: Optional[pd.DataFrame] = None,
) -> List[Dict]:
    """
    Return every iceberg that currently has four consecutive real
    daily observations.
    """

    if history is None:
        history = load_history()

    ready = []

    for iceberg_id in sorted(
        history["iceberg_id"]
        .dropna()
        .unique()
    ):

        status = assess_history_readiness(
            iceberg_id,
            history=history,
        )

        if status[
            "trajectory_model_ready"
        ]:
            ready.append(
                status
            )

    return ready


# ============================================================
# TERMINAL DISPLAY
# ============================================================

def main() -> None:

    print()
    print("=" * 76)
    print(
        "POLARGUARD - CURRENT ICEBERG HISTORY COLLECTOR"
    )
    print("=" * 76)

    print()
    print(
        "Checking BYU current iceberg positions..."
    )

    result = update_history()

    history = result[
        "history"
    ]

    metadata = result[
        "metadata"
    ]

    print()
    print(
        f"Provider page revised: "
        f"{metadata['source_page_last_revised']}"
    )

    print(
        f"Provider icebergs now: "
        f"{metadata['current_provider_iceberg_count']}"
    )

    print(
        f"Stored history rows: "
        f"{metadata['history_rows']}"
    )

    print(
        f"Unique stored icebergs: "
        f"{metadata['unique_icebergs']}"
    )

    print(
        f"New observations added: "
        f"{metadata['new_history_rows']}"
    )

    ready = find_member2_ready_icebergs(
        history
    )

    print()
    print(
        f"Member-2 ready icebergs: "
        f"{len(ready)}"
    )

    if ready:

        print()
        print(
            "READY ICEBERGS"
        )
        print("-" * 76)

        for item in ready:

            print(
                f"{item['iceberg_id']}: "
                f"{item['member2_input_dates']}"
            )

    else:

        print()
        print(
            "No iceberg currently has four consecutive "
            "real daily observations in the local current-data history."
        )

        print()
        print(
            "This is expected on the first collection."
        )

    print()
    print("-" * 76)

    counts = (
        history.groupby(
            "iceberg_id"
        )
        .size()
        .sort_values(
            ascending=False
        )
    )

    print()
    print(
        "OBSERVATIONS STORED PER ICEBERG"
    )

    print(
        counts.head(20)
        .to_string()
    )

    print()
    print("=" * 76)

    print(
        "History collector: READY"
    )

    print(
        "No synthetic/interpolated positions created."
    )

    print("=" * 76)
    print()


if __name__ == "__main__":
    main()