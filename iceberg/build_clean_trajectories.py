from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# PATHS
# ============================================================

DATA_DIR = Path(
    "iceberg/data/byu/consolidated_database_v8.0 (1)/updated7_consol"
)

OUTPUT_DIR = Path("iceberg/data/processed")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# SENSOR SOURCES PRESENT IN BYU DATABASE
# ============================================================

SENSORS = [
    "nic",
    "ascat",
    "oscat",
    "qscat",
    "seawinds",
    "nscat",
    "ers",
    "sass",
]


# ============================================================
# DATE PARSER
# ============================================================

def parse_byu_date(value):
    """
    Parse date formats found in the BYU iceberg database.

    Supported formats:

    1. YYYYDDD
       Example:
       2019123 = year 2019, day-of-year 123

    2. YYDDD
       Example:
       92226 = year 1992, day-of-year 226
    """

    try:
        # Convert values such as 2019123.0 safely to "2019123"
        s = str(int(float(value))).strip()

        # Normal YYYYDDD format
        if len(s) == 7:
            year = int(s[:4])
            doy = int(s[4:])

        # Older YYDDD format
        elif len(s) == 5:
            yy = int(s[:2])
            doy = int(s[2:])

            # Historical records such as 92 -> 1992
            if yy >= 70:
                year = 1900 + yy
            else:
                year = 2000 + yy

        else:
            return pd.NaT

        # Basic validation
        if doy < 1 or doy > 366:
            return pd.NaT

        if year < 1970 or year > 2030:
            return pd.NaT

        return pd.to_datetime(
            f"{year}{doy:03d}",
            format="%Y%j",
            errors="coerce",
        )

    except (ValueError, TypeError, OverflowError):
        return pd.NaT


# ============================================================
# POSITION VALIDATION
# ============================================================

def valid_position(lat, lon):
    """
    Check whether a candidate position looks like a realistic
    Antarctic / Southern Ocean iceberg position.
    """

    if pd.isna(lat) or pd.isna(lon):
        return False

    try:
        lat = float(lat)
        lon = float(lon)
    except (ValueError, TypeError):
        return False

    return (
        -90 <= lat <= -40
        and -180 <= lon <= 180
    )


# ============================================================
# CIRCULAR LONGITUDE MEAN
# ============================================================

def circular_mean_longitude(longitudes):
    """
    Calculate longitude mean correctly across the ±180° dateline.

    Example:
        +179° and -179°

    Arithmetic mean:
        0°       <- wrong

    Circular mean:
        ±180°    <- correct
    """

    lons = np.asarray(longitudes, dtype=float)

    lon_rad = np.radians(lons)

    mean_sin = np.mean(np.sin(lon_rad))
    mean_cos = np.mean(np.cos(lon_rad))

    mean_lon = np.degrees(
        np.arctan2(mean_sin, mean_cos)
    )

    # Normalize to [-180, 180]
    mean_lon = ((mean_lon + 180) % 360) - 180

    return float(mean_lon)


# ============================================================
# READ ALL ICEBERG FILES
# ============================================================

rows = []

files = sorted(DATA_DIR.glob("*.csv"))

print("=" * 70)
print("BUILDING CLEAN BYU ICEBERG TRAJECTORIES")
print("=" * 70)

print(f"CSV files found: {len(files):,}")


for i, file in enumerate(files, start=1):

    try:
        df = pd.read_csv(file)

        iceberg_id = file.stem.lower()

        for _, row in df.iterrows():

            # ------------------------------------------------
            # DATE
            # ------------------------------------------------

            date = parse_byu_date(row.get("date"))

            if pd.isna(date):
                continue

            # ------------------------------------------------
            # FIND ALL AVAILABLE SENSOR POSITIONS FOR THIS DAY
            # ------------------------------------------------

            candidates = []

            for sensor in SENSORS:

                lat_col = f"{sensor}_1"
                lon_col = f"{sensor}_2"
                flag_col = f"{sensor}_3"

                if (
                    lat_col not in df.columns
                    or lon_col not in df.columns
                ):
                    continue

                lat = row.get(lat_col)
                lon = row.get(lon_col)

                if not valid_position(lat, lon):
                    continue

                flag = (
                    row.get(flag_col)
                    if flag_col in df.columns
                    else np.nan
                )

                candidates.append(
                    {
                        "sensor": sensor,
                        "lat": float(lat),
                        "lon": float(lon),
                        "flag": flag,
                    }
                )

            # No valid position available on this date
            if len(candidates) == 0:
                continue

            # ------------------------------------------------
            # COMBINE SENSOR POSITIONS
            # ------------------------------------------------

            latitudes = [
                candidate["lat"]
                for candidate in candidates
            ]

            longitudes = [
                candidate["lon"]
                for candidate in candidates
            ]

            # Latitude can use standard arithmetic mean
            latitude = float(
                np.mean(latitudes)
            )

            # Longitude needs circular mean because Antarctica
            # crosses the international dateline.
            longitude = circular_mean_longitude(
                longitudes
            )

            sensors_used = "+".join(
                sorted(
                    {
                        candidate["sensor"]
                        for candidate in candidates
                    }
                )
            )

            # ------------------------------------------------
            # STORE STANDARDIZED RECORD
            # ------------------------------------------------

            rows.append(
                {
                    "iceberg_id": iceberg_id,
                    "date": date,
                    "latitude": latitude,
                    "longitude": longitude,
                    "sensors_used": sensors_used,
                    "sensor_count": len(candidates),
                }
            )

    except Exception as e:
        print(f"FAILED: {file.name}: {e}")

    if i % 50 == 0:
        print(
            f"Processed {i}/{len(files)} files"
        )


# ============================================================
# CREATE DATAFRAME
# ============================================================

clean = pd.DataFrame(rows)

print("\n" + "=" * 70)
print("INITIAL RESULT")
print("=" * 70)

print(
    f"Raw unified observations: {len(clean):,}"
)


# ============================================================
# BASIC CLEANING
# ============================================================

clean = clean.dropna(
    subset=[
        "iceberg_id",
        "date",
        "latitude",
        "longitude",
    ]
)

clean = clean.sort_values(
    [
        "iceberg_id",
        "date",
    ]
)

# Remove accidental duplicate iceberg/date observations
clean = clean.drop_duplicates(
    subset=[
        "iceberg_id",
        "date",
    ],
    keep="first",
)

clean = clean.reset_index(drop=True)


# ============================================================
# SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("CLEAN DATABASE SUMMARY")
print("=" * 70)

print(
    f"Observations after cleaning: {len(clean):,}"
)

print(
    f"Unique icebergs: "
    f"{clean['iceberg_id'].nunique():,}"
)

print("\nDate range:")

print(
    "Start:",
    clean["date"].min()
)

print(
    "End:  ",
    clean["date"].max()
)


print("\nLatitude range:")

print(
    clean["latitude"].min(),
    "to",
    clean["latitude"].max(),
)


print("\nLongitude range:")

print(
    clean["longitude"].min(),
    "to",
    clean["longitude"].max(),
)


# ============================================================
# SENSOR STATISTICS
# ============================================================

print("\nTop sensor combinations:")

print(
    clean["sensors_used"]
    .value_counts()
    .head(20)
)


# ============================================================
# YEAR STATISTICS
# ============================================================

print("\nObservations by year:")

year_counts = (
    clean["date"]
    .dt.year
    .value_counts()
    .sort_index()
)

print(
    year_counts.tail(20)
)


# ============================================================
# 2019-2025 OVERLAP
# ============================================================

overlap = clean[
    (clean["date"].dt.year >= 2019)
    & (clean["date"].dt.year <= 2025)
].copy()

print("\n" + "=" * 70)
print("2019-2025 OVERLAP")
print("=" * 70)

print(
    f"Observations: {len(overlap):,}"
)

print(
    f"Unique icebergs: "
    f"{overlap['iceberg_id'].nunique():,}"
)

print("\nObservations by year:")

print(
    overlap["date"]
    .dt.year
    .value_counts()
    .sort_index()
)


# ============================================================
# SAVE FULL CLEAN DATABASE
# ============================================================

full_output = (
    OUTPUT_DIR
    / "byu_clean_trajectories.csv"
)

clean.to_csv(
    full_output,
    index=False,
)


# ============================================================
# SAVE 2019-2025 SUBSET
# ============================================================

overlap_output = (
    OUTPUT_DIR
    / "byu_trajectories_2019_2025.csv"
)

overlap.to_csv(
    overlap_output,
    index=False,
)


# ============================================================
# FINAL OUTPUT
# ============================================================

print("\n" + "=" * 70)
print("FILES SAVED")
print("=" * 70)

print(full_output)
print(overlap_output)


print("\nSample records:")

print(
    clean.head(20).to_string(
        index=False
    )
)


print("\n" + "=" * 70)
print("CLEAN TRAJECTORY BUILD COMPLETE")
print("=" * 70)