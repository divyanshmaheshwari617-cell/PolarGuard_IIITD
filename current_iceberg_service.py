"""
PolarGuard - Current Antarctic Iceberg Service
------------------------------------------------
Purpose:
    Retrieve the latest available large Antarctic iceberg positions
    published by the BYU Scatterometer Climate Pathfinder (SCP).

Important:
    - This is near-real-time, NOT a continuous live feed.
    - BYU states that the page is normally updated once or twice weekly.
    - USNIC should be considered authoritative if sources disagree.
    - These current positions are NOT automatically sufficient for the
      frozen PolarGuard Member-2 trajectory model, which requires four
      consecutive daily positions.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

from iceberg_observation_store import append_observations


# ============================================================
# CONFIGURATION
# ============================================================

BYU_CURRENT_ICEBERG_URL = (
    "https://www.scp.byu.edu/current_icebergs.html"
)

REQUEST_TIMEOUT_SECONDS = 30

# Prototype freshness categories.
# These are PolarGuard UI/decision-support thresholds, not BYU/NIC standards.
FRESH_DAYS = 7
STALE_DAYS = 14


# ============================================================
# BASIC HELPERS
# ============================================================

def _normalize_text(value: str) -> str:
    """Collapse repeated whitespace and non-breaking spaces."""
    return " ".join(
        str(value)
        .replace("\xa0", " ")
        .split()
    )


def _safe_int(value) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


# ============================================================
# COORDINATE PARSING
# ============================================================

def parse_degree_minute_coordinate(
    value: str,
) -> float:
    """
    Convert BYU coordinates such as:

        29 57'W
        53 33'S
        143 13'E

    into signed decimal degrees.

    South and West are negative.
    North and East are positive.
    """

    value = _normalize_text(value).upper()

    pattern = re.compile(
        r"""
        ^\s*
        (?P<degrees>\d+(?:\.\d+)?)
        \s+
        (?P<minutes>\d+(?:\.\d+)?)
        \s*['′]?
        \s*
        (?P<hemisphere>[NSEW])
        \s*$
        """,
        re.VERBOSE,
    )

    match = pattern.match(value)

    if match is None:
        raise ValueError(
            f"Could not parse coordinate: {value!r}"
        )

    degrees = float(match.group("degrees"))
    minutes = float(match.group("minutes"))
    hemisphere = match.group("hemisphere")

    if not 0.0 <= minutes < 60.0:
        raise ValueError(
            f"Invalid coordinate minutes: {minutes}"
        )

    decimal = degrees + minutes / 60.0

    if hemisphere in ("S", "W"):
        decimal = -decimal

    if hemisphere in ("N", "S"):
        if not -90.0 <= decimal <= 90.0:
            raise ValueError(
                f"Latitude outside valid range: {decimal}"
            )

    if hemisphere in ("E", "W"):
        if not -180.0 <= decimal <= 180.0:
            raise ValueError(
                f"Longitude outside valid range: {decimal}"
            )

    return float(decimal)


# ============================================================
# PAGE REVISION DATE
# ============================================================

def _parse_last_revised(
    page_text: str,
) -> Optional[datetime]:
    """
    Parse text similar to:

        Last revised: 16:26:28 09/02/26

    The BYU page does not state a timezone beside this field,
    so this timestamp is used mainly as provenance metadata.
    """

    match = re.search(
        r"Last\s+revised:\s*"
        r"(\d{1,2}:\d{2}:\d{2})\s+"
        r"(\d{1,2}/\d{1,2}/\d{2,4})",
        page_text,
        flags=re.IGNORECASE,
    )

    if match is None:
        return None

    time_text = match.group(1)
    date_text = match.group(2)

    combined = f"{time_text} {date_text}"

    formats = (
        "%H:%M:%S %m/%d/%y",
        "%H:%M:%S %m/%d/%Y",
    )

    for fmt in formats:
        try:
            return datetime.strptime(
                combined,
                fmt,
            )
        except ValueError:
            continue

    return None


# ============================================================
# DAY-OF-YEAR CONVERSION
# ============================================================

def day_of_year_to_date(
    year: int,
    day_of_year: int,
) -> datetime:
    """
    Convert year + UTC day-of-year to a date.

    Example:
        year=2026, day_of_year=235
    """

    if day_of_year < 1 or day_of_year > 366:
        raise ValueError(
            f"Invalid day of year: {day_of_year}"
        )

    return (
        datetime(
            int(year),
            1,
            1,
            tzinfo=timezone.utc,
        )
        + timedelta(days=int(day_of_year) - 1)
    )


# ============================================================
# FRESHNESS
# ============================================================

def classify_freshness(
    observation_date: datetime,
    now: Optional[datetime] = None,
) -> Dict:
    """
    Classify observation age for PolarGuard.

    These thresholds are prototype UI categories only.
    """

    if now is None:
        now = datetime.now(timezone.utc)

    if observation_date.tzinfo is None:
        observation_date = observation_date.replace(
            tzinfo=timezone.utc
        )

    age_days = (
        now.date() - observation_date.date()
    ).days

    age_days = max(int(age_days), 0)

    if age_days <= FRESH_DAYS:
        status = "FRESH"
        route_readiness = True

    elif age_days <= STALE_DAYS:
        status = "AGING"
        route_readiness = True

    else:
        status = "STALE"
        route_readiness = False

    return {
        "age_days": age_days,
        "freshness_status": status,
        "route_readiness": route_readiness,
    }


# ============================================================
# DOWNLOAD PAGE
# ============================================================

def download_current_iceberg_page() -> str:
    """
    Download the current BYU Antarctic iceberg page.
    """

    headers = {
        "User-Agent": (
            "PolarGuard-SIH/1.0 "
            "(Antarctic decision-support research prototype)"
        )
    }

    response = requests.get(
        BYU_CURRENT_ICEBERG_URL,
        headers=headers,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    response.raise_for_status()

    return response.text


# ============================================================
# TABLE EXTRACTION
# ============================================================

def _find_iceberg_table(
    soup: BeautifulSoup,
):
    """
    Find the table containing:
        Iceberg
        Longitude
        Latitude
        Most recent observation
    """

    tables = soup.find_all("table")

    for table in tables:

        text = _normalize_text(
            table.get_text(" ", strip=True)
        ).lower()

        if (
            "iceberg" in text
            and "longitude" in text
            and "latitude" in text
            and "observation" in text
        ):
            return table

    raise RuntimeError(
        "Could not locate the BYU current iceberg table. "
        "The provider page layout may have changed."
    )


def _extract_rows_from_html_table(
    table,
) -> List[Dict]:
    """
    Extract raw rows from the BYU table.
    """

    records = []

    for row in table.find_all("tr"):

        cells = [
            _normalize_text(
                cell.get_text(" ", strip=True)
            )
            for cell in row.find_all(
                ["td", "th"]
            )
        ]

        if len(cells) < 4:
            continue

        iceberg_id = cells[0].strip().lower()

        # Skip header rows.
        if iceberg_id in (
            "iceberg",
            "iceberg***",
        ):
            continue

        # Iceberg names should contain at least
        # one alphabetical character.
        if not re.search(
            r"[a-zA-Z]",
            iceberg_id,
        ):
            continue

        longitude_text = cells[1]
        latitude_text = cells[2]

        observation_text = cells[3]

        observation_match = re.search(
            r"\b(\d{1,3})\b",
            observation_text,
        )

        if observation_match is None:
            continue

        observation_doy = int(
            observation_match.group(1)
        )

        try:
            longitude = (
                parse_degree_minute_coordinate(
                    longitude_text
                )
            )

            latitude = (
                parse_degree_minute_coordinate(
                    latitude_text
                )
            )

        except ValueError:
            continue

        records.append(
            {
                "iceberg_id": iceberg_id,
                "longitude": longitude,
                "latitude": latitude,
                "longitude_source": longitude_text,
                "latitude_source": latitude_text,
                "observation_day_of_year":
                    observation_doy,
            }
        )

    return records


# ============================================================
# MAIN LOADER
# ============================================================

def load_current_icebergs() -> Dict:
    """
    Retrieve and parse the latest BYU current iceberg list.

    Returns
    -------
    dict
        {
            source,
            source_url,
            retrieved_at_utc,
            page_last_revised,
            iceberg_count,
            icebergs,
            dataframe
        }
    """

    html = download_current_iceberg_page()

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    page_text = _normalize_text(
        soup.get_text(" ", strip=True)
    )

    page_last_revised = (
        _parse_last_revised(page_text)
    )

    table = _find_iceberg_table(soup)

    records = _extract_rows_from_html_table(
        table
    )

    if not records:
        raise RuntimeError(
            "BYU page downloaded successfully, but no "
            "current iceberg records could be parsed."
        )

    # The observation column contains day-of-year but not
    # the year. Use the page revision year as the observation
    # year because the table is the current-position product.
    if page_last_revised is not None:
        observation_year = (
            page_last_revised.year
        )
    else:
        observation_year = (
            datetime.now(
                timezone.utc
            ).year
        )

    now = datetime.now(timezone.utc)

    processed_records = []

    for record in records:

        observation_date = (
            day_of_year_to_date(
                observation_year,
                record[
                    "observation_day_of_year"
                ],
            )
        )

        freshness = classify_freshness(
            observation_date,
            now=now,
        )

        processed = {
            **record,

            "observation_date":
                observation_date
                .date()
                .isoformat(),

            "observation_year":
                observation_year,

            **freshness,

            "source":
                "BYU Scatterometer Climate Pathfinder",

            "source_type":
                "Near-real-time ASCAT / OSCAT-2",

            "authoritative_reference":
                "U.S. National Ice Center",
        }

        processed_records.append(
            processed
        )

    dataframe = pd.DataFrame(
        processed_records
    )

    dataframe = dataframe.sort_values(
        [
            "observation_date",
            "iceberg_id",
        ],
        ascending=[
            False,
            True,
        ],
    ).reset_index(drop=True)

    # ========================================================
    # POLARGUARD OPERATIONAL OBSERVATION HISTORY
    # ========================================================
    #
    # Persist every genuine observation returned by BYU.
    #
    # The observation store de-duplicates records using:
    #
    #     iceberg_id + observation_date
    #
    # Therefore repeatedly refreshing the application does not
    # create duplicate observations.
    #
    # IMPORTANT:
    # No interpolation, repeated positions or synthetic
    # observations are created here.
    # ========================================================

    history_input = dataframe.copy()

    history_input["retrieved_at_utc"] = (
        now.isoformat()
    )

    history_input["page_last_revised"] = (
        page_last_revised.isoformat()
        if page_last_revised
        else ""
    )

    history_result = append_observations(
        history_input
    )

    return {
        "source":
            "BYU Scatterometer Climate Pathfinder",

        "source_type":
            "Near-real-time Antarctic large iceberg positions",

        "source_url":
            BYU_CURRENT_ICEBERG_URL,

        "authoritative_reference":
            "U.S. National Ice Center (USNIC)",

        "retrieved_at_utc":
            now.isoformat(),

        "page_last_revised": (
            page_last_revised.isoformat()
            if page_last_revised
            else None
        ),

        "iceberg_count":
            int(len(dataframe)),

        "icebergs":
            dataframe.to_dict(
                orient="records"
            ),

        "dataframe":
            dataframe,
    }


# ============================================================
# FIND ONE ICEBERG
# ============================================================

def get_current_iceberg(
    iceberg_id: str,
    bundle: Optional[Dict] = None,
) -> Dict:
    """
    Return one current iceberg by ID.

    Matching is case-insensitive.

    Example:
        get_current_iceberg("A81")
    """

    if bundle is None:
        bundle = load_current_icebergs()

    target = (
        str(iceberg_id)
        .strip()
        .lower()
    )

    dataframe = bundle["dataframe"]

    match = dataframe[
        dataframe["iceberg_id"]
        .str.lower()
        .eq(target)
    ]

    if match.empty:
        available = ", ".join(
            dataframe[
                "iceberg_id"
            ]
            .head(15)
            .tolist()
        )

        raise KeyError(
            f"Iceberg {iceberg_id!r} is not present "
            f"in the current BYU list. "
            f"Example available IDs: {available}"
        )

    return match.iloc[0].to_dict()


# ============================================================
# MEMBER-2 READINESS
# ============================================================

def assess_member2_readiness(
    iceberg_record: Dict,
) -> Dict:
    """
    Assess whether the current-position product alone is sufficient
    for the frozen PolarGuard Member-2 model.

    The frozen Member-2 service requires four consecutive daily
    iceberg positions. The BYU current page supplies only the latest
    position per listed iceberg.

    Therefore this function MUST NOT claim trajectory readiness from
    the current page alone.
    """

    freshness_status = iceberg_record[
        "freshness_status"
    ]

    return {
        "latest_position_available": True,

        "latest_position_freshness":
            freshness_status,

        "required_daily_positions": 4,

        "positions_available_from_current_page": 1,

        "trajectory_model_ready": False,

        "navigation_fully_synchronized": False,

        "reason": (
            "The frozen PolarGuard Member-2 trajectory model "
            "requires four consecutive real daily positions. "
            "The BYU current-position page provides the latest "
            "position only. Additional real observations are "
            "required before trajectory prediction."
        ),
    }


# ============================================================
# TERMINAL TEST
# ============================================================

def main():

    print()
    print("=" * 72)
    print("POLARGUARD - CURRENT ANTARCTIC ICEBERG SERVICE")
    print("=" * 72)

    print()
    print(
        "Downloading latest BYU current iceberg positions..."
    )

    bundle = load_current_icebergs()

    print()
    print(
        f"Source: {bundle['source']}"
    )

    print(
        f"Type: {bundle['source_type']}"
    )

    print(
        f"Page last revised: "
        f"{bundle['page_last_revised']}"
    )

    print(
        f"Retrieved UTC: "
        f"{bundle['retrieved_at_utc']}"
    )

    print(
        f"Icebergs parsed: "
        f"{bundle['iceberg_count']}"
    )

    dataframe = bundle["dataframe"]

    print()
    print("LATEST ICEBERGS")
    print("-" * 72)

    display_columns = [
        "iceberg_id",
        "latitude",
        "longitude",
        "observation_date",
        "age_days",
        "freshness_status",
    ]

    print(
        dataframe[
            display_columns
        ]
        .head(15)
        .to_string(
            index=False
        )
    )

    print()
    print("-" * 72)

    if len(dataframe) > 0:

        example_id = dataframe.iloc[0][
            "iceberg_id"
        ]

        example = get_current_iceberg(
            example_id,
            bundle=bundle,
        )

        readiness = (
            assess_member2_readiness(
                example
            )
        )

        print()
        print(
            f"Example iceberg: "
            f"{example['iceberg_id'].upper()}"
        )

        print(
            f"Latitude: "
            f"{example['latitude']:.4f}"
        )

        print(
            f"Longitude: "
            f"{example['longitude']:.4f}"
        )

        print(
            f"Observation date: "
            f"{example['observation_date']}"
        )

        print(
            f"Freshness: "
            f"{example['freshness_status']}"
        )

        print()
        print("MEMBER-2 READINESS")

        for key, value in (
            readiness.items()
        ):
            print(
                f"  {key}: {value}"
            )

    print()
    print("=" * 72)
    print(
        "Current iceberg ingestion: READY"
    )
    print(
        "Frozen Member-2 trajectory: "
        "requires additional real daily history"
    )
    print("=" * 72)
    print()


if __name__ == "__main__":
    main()