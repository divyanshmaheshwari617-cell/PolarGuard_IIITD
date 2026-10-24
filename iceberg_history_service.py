"""
PolarGuard - Iceberg History Service
------------------------------------

Purpose
-------
Prepare genuine iceberg observation sequences for the frozen
Member-2 trajectory model.

Member 2 requires:

    t-3
    t-2
    t-1
    t

Scientific rules
----------------
- Never repeat a position.
- Never interpolate missing positions.
- Never fabricate dates or coordinates.
- Historical readiness and CURRENT operational readiness are
  kept separate.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

OPERATIONAL_HISTORY_PATH = Path(
    "data/current_icebergs/byu_current_iceberg_history.csv"
)

HISTORICAL_TRAJECTORY_PATH = Path(
    "iceberg/data/processed/byu_trajectories_2019_2025.csv"
)

REQUIRED_POSITION_COUNT = 4


# ============================================================
# HELPERS
# ============================================================

def normalize_iceberg_id(value) -> str:
    if value is None:
        return ""

    return str(value).strip().upper()


def _find_column(
    dataframe: pd.DataFrame,
    candidates: List[str],
) -> Optional[str]:

    lookup = {
        str(column).strip().lower(): column
        for column in dataframe.columns
    }

    for candidate in candidates:
        key = candidate.lower()

        if key in lookup:
            return lookup[key]

    return None


def _empty_history_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "iceberg_id",
            "observation_date",
            "latitude",
            "longitude",
            "history_source",
        ]
    )


# ============================================================
# OPERATIONAL HISTORY
# ============================================================

def load_operational_history(
    path: Path | str = OPERATIONAL_HISTORY_PATH,
) -> pd.DataFrame:
    """
    Load genuine observations collected from the BYU current
    iceberg service.
    """

    path = Path(path)

    if not path.exists():
        return _empty_history_dataframe()

    raw = pd.read_csv(path)

    if raw.empty:
        return _empty_history_dataframe()

    required = [
        "iceberg_id",
        "observation_date",
        "latitude",
        "longitude",
    ]

    missing = [
        column
        for column in required
        if column not in raw.columns
    ]

    if missing:
        raise RuntimeError(
            "Operational iceberg history is missing columns: "
            + ", ".join(missing)
        )

    result = raw[
        required
    ].copy()

    result["iceberg_id"] = (
        result["iceberg_id"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    result["observation_date"] = pd.to_datetime(
        result["observation_date"],
        errors="coerce",
    )

    result["latitude"] = pd.to_numeric(
        result["latitude"],
        errors="coerce",
    )

    result["longitude"] = pd.to_numeric(
        result["longitude"],
        errors="coerce",
    )

    result = result.dropna(
        subset=[
            "iceberg_id",
            "observation_date",
            "latitude",
            "longitude",
        ]
    )

    result = result[
        result["latitude"].between(
            -90.0,
            90.0,
        )
        & result["longitude"].between(
            -180.0,
            180.0,
        )
    ].copy()

    result["history_source"] = (
        "BYU current operational observation store"
    )

    result = (
        result.drop_duplicates(
            subset=[
                "iceberg_id",
                "observation_date",
            ],
            keep="last",
        )
        .sort_values(
            [
                "iceberg_id",
                "observation_date",
            ]
        )
        .reset_index(drop=True)
    )

    return result


# ============================================================
# HISTORICAL DATASET
# ============================================================

def load_historical_trajectory_data(
    path: Path | str = HISTORICAL_TRAJECTORY_PATH,
) -> pd.DataFrame:
    """
    Load the genuine BYU historical trajectory dataset.

    Column names are detected so this service does not depend
    on one exact historical schema.
    """

    path = Path(path)

    if not path.exists():
        return _empty_history_dataframe()

    raw = pd.read_csv(path)

    if raw.empty:
        return _empty_history_dataframe()

    id_column = _find_column(
        raw,
        [
            "iceberg_id",
            "iceberg",
            "id",
            "name",
        ],
    )

    date_column = _find_column(
        raw,
        [
            "observation_date",
            "date",
            "datetime",
            "timestamp",
            "time",
        ],
    )

    latitude_column = _find_column(
        raw,
        [
            "latitude",
            "lat",
        ],
    )

    longitude_column = _find_column(
        raw,
        [
            "longitude",
            "lon",
            "long",
        ],
    )

    missing = []

    if id_column is None:
        missing.append("iceberg ID")

    if date_column is None:
        missing.append("date")

    if latitude_column is None:
        missing.append("latitude")

    if longitude_column is None:
        missing.append("longitude")

    if missing:
        raise RuntimeError(
            "Historical iceberg dataset is missing recognizable "
            "columns for: "
            + ", ".join(missing)
            + ". Available columns: "
            + ", ".join(
                map(
                    str,
                    raw.columns,
                )
            )
        )

    result = pd.DataFrame(
        {
            "iceberg_id":
                raw[id_column],

            "observation_date":
                raw[date_column],

            "latitude":
                raw[latitude_column],

            "longitude":
                raw[longitude_column],
        }
    )

    result["iceberg_id"] = (
        result["iceberg_id"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    result["observation_date"] = pd.to_datetime(
        result["observation_date"],
        errors="coerce",
    )

    result["latitude"] = pd.to_numeric(
        result["latitude"],
        errors="coerce",
    )

    result["longitude"] = pd.to_numeric(
        result["longitude"],
        errors="coerce",
    )

    result = result.dropna(
        subset=[
            "iceberg_id",
            "observation_date",
            "latitude",
            "longitude",
        ]
    )

    result = result[
        result["latitude"].between(
            -90.0,
            90.0,
        )
        & result["longitude"].between(
            -180.0,
            180.0,
        )
    ].copy()

    result["history_source"] = (
        "BYU processed historical trajectory dataset"
    )

    result = (
        result.drop_duplicates(
            subset=[
                "iceberg_id",
                "observation_date",
            ],
            keep="last",
        )
        .sort_values(
            [
                "iceberg_id",
                "observation_date",
            ]
        )
        .reset_index(drop=True)
    )

    return result


# ============================================================
# COMBINED HISTORY
# ============================================================

def load_combined_history() -> pd.DataFrame:
    """
    Combine historical and operational genuine observations.

    Operational observations are appended last and therefore
    win when the same iceberg/date appears in both sources.
    """

    historical = (
        load_historical_trajectory_data()
    )

    operational = (
        load_operational_history()
    )

    combined = pd.concat(
        [
            historical,
            operational,
        ],
        ignore_index=True,
    )

    if combined.empty:
        return _empty_history_dataframe()

    combined["iceberg_id"] = (
        combined["iceberg_id"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    combined["observation_date"] = pd.to_datetime(
        combined["observation_date"],
        errors="coerce",
    )

    combined["latitude"] = pd.to_numeric(
        combined["latitude"],
        errors="coerce",
    )

    combined["longitude"] = pd.to_numeric(
        combined["longitude"],
        errors="coerce",
    )

    combined = combined.dropna(
        subset=[
            "iceberg_id",
            "observation_date",
            "latitude",
            "longitude",
        ]
    )

    combined = (
        combined.drop_duplicates(
            subset=[
                "iceberg_id",
                "observation_date",
            ],
            keep="last",
        )
        .sort_values(
            [
                "iceberg_id",
                "observation_date",
            ]
        )
        .reset_index(drop=True)
    )

    return combined


def get_combined_iceberg_history(
    iceberg_id: str,
) -> pd.DataFrame:

    iceberg_id = normalize_iceberg_id(
        iceberg_id
    )

    combined = load_combined_history()

    if combined.empty:
        return _empty_history_dataframe()

    result = combined[
        combined["iceberg_id"]
        == iceberg_id
    ].copy()

    return (
        result.sort_values(
            "observation_date"
        )
        .reset_index(drop=True)
    )


# ============================================================
# HISTORICAL READINESS
# ============================================================

def _is_daily_sequence(
    dataframe: pd.DataFrame,
) -> bool:

    if len(dataframe) != REQUIRED_POSITION_COUNT:
        return False

    dates = pd.to_datetime(
        dataframe["observation_date"],
        errors="coerce",
    )

    if dates.isna().any():
        return False

    dates = (
        dates
        .sort_values()
        .reset_index(drop=True)
    )

    differences = (
        dates.diff()
        .dropna()
        .dt.total_seconds()
        / 86400.0
    )

    return bool(
        np.allclose(
            differences.to_numpy(),
            1.0,
        )
    )


def find_latest_four_consecutive(
    iceberg_id: str,
) -> Dict:
    """
    Find the newest genuine four-day sequence anywhere in the
    combined history.

    This is HISTORICAL readiness, not CURRENT readiness.
    """

    iceberg_id = normalize_iceberg_id(
        iceberg_id
    )

    history = (
        get_combined_iceberg_history(
            iceberg_id
        )
    )

    if history.empty:
        return {
            "iceberg_id":
                iceberg_id,

            "trajectory_model_ready":
                False,

            "positions_available":
                0,

            "required_positions":
                REQUIRED_POSITION_COUNT,

            "observations":
                [],

            "reason":
                (
                    "No genuine observation history "
                    "was found for this iceberg."
                ),
        }

    history = (
        history.sort_values(
            "observation_date"
        )
        .reset_index(drop=True)
    )

    for end_index in range(
        len(history),
        REQUIRED_POSITION_COUNT - 1,
        -1,
    ):

        start_index = (
            end_index
            - REQUIRED_POSITION_COUNT
        )

        candidate = history.iloc[
            start_index:end_index
        ].copy()

        if not _is_daily_sequence(
            candidate
        ):
            continue

        observations = []

        for _, row in candidate.iterrows():

            observations.append(
                {
                    "iceberg_id":
                        iceberg_id,

                    "observation_date":
                        pd.Timestamp(
                            row[
                                "observation_date"
                            ]
                        ).strftime(
                            "%Y-%m-%d"
                        ),

                    "latitude":
                        float(
                            row["latitude"]
                        ),

                    "longitude":
                        float(
                            row["longitude"]
                        ),

                    "history_source":
                        str(
                            row[
                                "history_source"
                            ]
                        ),
                }
            )

        return {
            "iceberg_id":
                iceberg_id,

            "trajectory_model_ready":
                True,

            "positions_available":
                int(
                    len(history)
                ),

            "required_positions":
                REQUIRED_POSITION_COUNT,

            "sequence_start":
                observations[0][
                    "observation_date"
                ],

            "sequence_end":
                observations[-1][
                    "observation_date"
                ],

            "observations":
                observations,

            "reason":
                (
                    "Four genuine consecutive daily "
                    "observations are available."
                ),
        }

    return {
        "iceberg_id":
            iceberg_id,

        "trajectory_model_ready":
            False,

        "positions_available":
            int(
                len(history)
            ),

        "required_positions":
            REQUIRED_POSITION_COUNT,

        "observations":
            [],

        "reason":
            (
                "Observation history exists, but no four "
                "consecutive daily observations were found."
            ),
    }


def build_member2_position_input(
    iceberg_id: str,
) -> Dict:
    """
    Build historical/demo Member-2 positional input.
    """

    readiness = (
        find_latest_four_consecutive(
            iceberg_id
        )
    )

    if not readiness[
        "trajectory_model_ready"
    ]:
        return {
            **readiness,
            "member2_input":
                None,
        }

    observations = readiness[
        "observations"
    ]

    tm3 = observations[0]
    tm2 = observations[1]
    tm1 = observations[2]
    current = observations[3]

    member2_input = {
        "lat_tm3":
            float(
                tm3["latitude"]
            ),

        "lon_tm3":
            float(
                tm3["longitude"]
            ),

        "lat_tm2":
            float(
                tm2["latitude"]
            ),

        "lon_tm2":
            float(
                tm2["longitude"]
            ),

        "lat_tm1":
            float(
                tm1["latitude"]
            ),

        "lon_tm1":
            float(
                tm1["longitude"]
            ),

        "current_latitude":
            float(
                current["latitude"]
            ),

        "current_longitude":
            float(
                current["longitude"]
            ),

        "date":
            current[
                "observation_date"
            ],
    }

    return {
        **readiness,

        "member2_input":
            member2_input,
    }


# ============================================================
# STRICT CURRENT OPERATIONAL READINESS
# ============================================================

def find_operational_four_day_sequence(
    iceberg_id: str,
) -> Dict:
    """
    Find a genuine four-day sequence ending EXACTLY on the
    newest operational BYU observation for this iceberg.

    This prevents an old historical trajectory from being
    presented as a CURRENT forecast.
    """

    iceberg_id = normalize_iceberg_id(
        iceberg_id
    )

    operational = (
        load_operational_history()
    )

    operational = operational[
        operational["iceberg_id"]
        == iceberg_id
    ].copy()

    if operational.empty:
        return {
            "iceberg_id":
                iceberg_id,

            "operational_member2_ready":
                False,

            "trajectory_model_ready":
                False,

            "latest_operational_date":
                None,

            "missing_date":
                None,

            "observations":
                [],

            "member2_input":
                None,

            "reason":
                (
                    "No genuine current operational "
                    "observation exists for this iceberg."
                ),
        }

    operational = (
        operational.sort_values(
            "observation_date"
        )
        .reset_index(drop=True)
    )

    latest_operational = (
        operational.iloc[-1]
    )

    current_date = pd.Timestamp(
        latest_operational[
            "observation_date"
        ]
    ).normalize()

    combined = (
        get_combined_iceberg_history(
            iceberg_id
        )
    )

    if combined.empty:
        return {
            "iceberg_id":
                iceberg_id,

            "operational_member2_ready":
                False,

            "trajectory_model_ready":
                False,

            "latest_operational_date":
                current_date.strftime(
                    "%Y-%m-%d"
                ),

            "missing_date":
                None,

            "observations":
                [],

            "member2_input":
                None,

            "reason":
                (
                    "Current observation exists, but "
                    "combined history is unavailable."
                ),
        }

    combined["observation_date"] = pd.to_datetime(
        combined["observation_date"],
        errors="coerce",
    )

    combined = combined.dropna(
        subset=[
            "observation_date",
        ]
    )

    combined["observation_date"] = (
        combined[
            "observation_date"
        ].dt.normalize()
    )

    required_dates = [
        current_date
        - pd.Timedelta(
            days=3
        ),

        current_date
        - pd.Timedelta(
            days=2
        ),

        current_date
        - pd.Timedelta(
            days=1
        ),

        current_date,
    ]

    selected_rows = []

    for required_date in required_dates:

        match = combined[
            combined[
                "observation_date"
            ]
            == required_date
        ].copy()

        if match.empty:

            missing_date = (
                required_date.strftime(
                    "%Y-%m-%d"
                )
            )

            return {
                "iceberg_id":
                    iceberg_id,

                "operational_member2_ready":
                    False,

                "trajectory_model_ready":
                    False,

                "latest_operational_date":
                    current_date.strftime(
                        "%Y-%m-%d"
                    ),

                "missing_date":
                    missing_date,

                "observations":
                    [],

                "member2_input":
                    None,

                "reason":
                    (
                        "Current observation is available, "
                        "but the genuine four-day sequence "
                        "is incomplete. Missing observation: "
                        f"{missing_date}."
                    ),
            }

        selected_rows.append(
            match.iloc[-1]
        )

    observations = []

    for row in selected_rows:

        observations.append(
            {
                "iceberg_id":
                    iceberg_id,

                "observation_date":
                    pd.Timestamp(
                        row[
                            "observation_date"
                        ]
                    ).strftime(
                        "%Y-%m-%d"
                    ),

                "latitude":
                    float(
                        row["latitude"]
                    ),

                "longitude":
                    float(
                        row["longitude"]
                    ),

                "history_source":
                    str(
                        row[
                            "history_source"
                        ]
                    ),
            }
        )

    tm3 = observations[0]
    tm2 = observations[1]
    tm1 = observations[2]
    current = observations[3]

    member2_input = {
        "lat_tm3":
            float(
                tm3["latitude"]
            ),

        "lon_tm3":
            float(
                tm3["longitude"]
            ),

        "lat_tm2":
            float(
                tm2["latitude"]
            ),

        "lon_tm2":
            float(
                tm2["longitude"]
            ),

        "lat_tm1":
            float(
                tm1["latitude"]
            ),

        "lon_tm1":
            float(
                tm1["longitude"]
            ),

        "current_latitude":
            float(
                current["latitude"]
            ),

        "current_longitude":
            float(
                current["longitude"]
            ),

        "date":
            current[
                "observation_date"
            ],
    }

    return {
        "iceberg_id":
            iceberg_id,

        "operational_member2_ready":
            True,

        "trajectory_model_ready":
            True,

        "latest_operational_date":
            current[
                "observation_date"
            ],

        "missing_date":
            None,

        "observations":
            observations,

        "member2_input":
            member2_input,

        "reason":
            (
                "Four genuine consecutive daily observations "
                "ending on the current operational observation "
                "are available."
            ),
    }


# ============================================================
# READINESS TABLES
# ============================================================

def assess_all_icebergs() -> pd.DataFrame:
    """
    Historical/demo readiness for every known iceberg.
    """

    combined = load_combined_history()

    columns = [
        "iceberg_id",
        "observations",
        "member2_ready",
        "sequence_start",
        "sequence_end",
        "reason",
    ]

    if combined.empty:
        return pd.DataFrame(
            columns=columns
        )

    rows = []

    iceberg_ids = sorted(
        combined[
            "iceberg_id"
        ].dropna().unique()
    )

    for iceberg_id in iceberg_ids:

        result = (
            find_latest_four_consecutive(
                iceberg_id
            )
        )

        rows.append(
            {
                "iceberg_id":
                    iceberg_id,

                "observations":
                    result[
                        "positions_available"
                    ],

                "member2_ready":
                    result[
                        "trajectory_model_ready"
                    ],

                "sequence_start":
                    result.get(
                        "sequence_start"
                    ),

                "sequence_end":
                    result.get(
                        "sequence_end"
                    ),

                "reason":
                    result[
                        "reason"
                    ],
            }
        )

    return pd.DataFrame(
        rows,
        columns=columns,
    )


def assess_operational_icebergs() -> pd.DataFrame:
    """
    CURRENT operational readiness only.
    """

    operational = (
        load_operational_history()
    )

    columns = [
        "iceberg_id",
        "latest_operational_date",
        "operational_member2_ready",
        "missing_date",
        "reason",
    ]

    if operational.empty:
        return pd.DataFrame(
            columns=columns
        )

    rows = []

    iceberg_ids = sorted(
        operational[
            "iceberg_id"
        ].dropna().unique()
    )

    for iceberg_id in iceberg_ids:

        result = (
            find_operational_four_day_sequence(
                iceberg_id
            )
        )

        rows.append(
            {
                "iceberg_id":
                    iceberg_id,

                "latest_operational_date":
                    result.get(
                        "latest_operational_date"
                    ),

                "operational_member2_ready":
                    result[
                        "operational_member2_ready"
                    ],

                "missing_date":
                    result.get(
                        "missing_date"
                    ),

                "reason":
                    result[
                        "reason"
                    ],
            }
        )

    return pd.DataFrame(
        rows,
        columns=columns,
    )


# ============================================================
# SUMMARIES
# ============================================================

def get_history_service_summary() -> Dict:

    combined = (
        load_combined_history()
    )

    readiness = (
        assess_all_icebergs()
    )

    if readiness.empty:
        ready_count = 0

    else:
        ready_count = int(
            readiness[
                "member2_ready"
            ].sum()
        )

    return {
        "combined_observation_count":
            int(
                len(combined)
            ),

        "combined_iceberg_count":
            int(
                combined[
                    "iceberg_id"
                ].nunique()
                if not combined.empty
                else 0
            ),

        "historical_member2_ready_count":
            ready_count,

        "historical_member2_not_ready_count":
            int(
                len(readiness)
                - ready_count
            ),

        "historical_dataset":
            str(
                HISTORICAL_TRAJECTORY_PATH
            ),

        "operational_dataset":
            str(
                OPERATIONAL_HISTORY_PATH
            ),
    }


def get_operational_readiness_summary() -> Dict:

    readiness = (
        assess_operational_icebergs()
    )

    if readiness.empty:
        return {
            "current_iceberg_count": 0,
            "operational_member2_ready_count": 0,
            "current_only_count": 0,
        }

    ready_count = int(
        readiness[
            "operational_member2_ready"
        ].sum()
    )

    return {
        "current_iceberg_count":
            int(
                len(readiness)
            ),

        "operational_member2_ready_count":
            ready_count,

        "current_only_count":
            int(
                len(readiness)
                - ready_count
            ),
    }


# ============================================================
# TERMINAL TEST
# ============================================================

def main():

    print()
    print("=" * 76)
    print(
        "POLARGUARD - ICEBERG HISTORY SERVICE"
    )
    print("=" * 76)

    print()

    history_summary = (
        get_history_service_summary()
    )

    for key, value in (
        history_summary.items()
    ):
        print(
            f"{key}: {value}"
        )

    print()
    print("-" * 76)
    print(
        "CURRENT OPERATIONAL READINESS"
    )
    print("-" * 76)

    operational_summary = (
        get_operational_readiness_summary()
    )

    for key, value in (
        operational_summary.items()
    ):
        print(
            f"{key}: {value}"
        )

    print()
    print("-" * 76)

    example = (
        find_operational_four_day_sequence(
            "A76C"
        )
    )

    print(
        "A76C:"
    )

    for key in [
        "iceberg_id",
        "operational_member2_ready",
        "latest_operational_date",
        "missing_date",
        "reason",
    ]:
        print(
            f"  {key}: "
            f"{example.get(key)}"
        )

    print()
    print("=" * 76)
    print(
        "Iceberg history service: READY"
    )
    print("=" * 76)
    print()


if __name__ == "__main__":
    main()