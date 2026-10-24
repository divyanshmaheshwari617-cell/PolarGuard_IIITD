from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent.parent

if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

import numpy as np
import pandas as pd
import xarray as xr

from pyproj import Transformer
from sea_ice_service import predict_sea_ice


# ============================================================
# PATHS
# ============================================================

AIS_FILE = (
    BASE
    / "data"
    / "ais"
    / "polarstern_ps124_2021"
    / "analysis"
    / "polarstern_ps124_cleaned_track.csv"
)

SEA_ICE_HISTORY_FILE = (
    BASE
    / "data"
    / "processed"
    / "sea_ice_2019_2025.nc"
)

OUTPUT_DIR = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps124_stage1_ice_scan"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# SETTINGS
# ============================================================

HORIZONS = [24, 48, 72]

WINDOW_STEP_HOURS = 6

MIN_POINTS = 5


# ============================================================
# GRID CONVERSION
# ============================================================

def projected_grid_to_latlon(
    x_coords,
    y_coords,
):
    """
    Convert Member-1 EPSG:3412 grid coordinates
    to WGS84 latitude/longitude.
    """

    x_grid, y_grid = np.meshgrid(
        np.asarray(x_coords, dtype=float),
        np.asarray(y_coords, dtype=float),
    )

    transformer = Transformer.from_crs(
        "EPSG:3412",
        "EPSG:4326",
        always_xy=True,
    )

    grid_lon, grid_lat = transformer.transform(
        x_grid,
        y_grid,
    )

    return (
        np.asarray(grid_lat, dtype=float),
        np.asarray(grid_lon, dtype=float),
    )


# ============================================================
# HAVERSINE
# ============================================================

def haversine_km(
    lat1,
    lon1,
    lat2,
    lon2,
):
    """
    Great-circle distance in kilometres.
    """

    R = 6371.0088

    lat1 = np.radians(lat1)
    lon1 = np.radians(lon1)

    lat2 = np.radians(lat2)
    lon2 = np.radians(lon2)

    dlat = lat2 - lat1

    dlon = (
        lon2
        - lon1
        + np.pi
    ) % (2 * np.pi) - np.pi

    a = (
        np.sin(dlat / 2.0) ** 2
        +
        np.cos(lat1)
        *
        np.cos(lat2)
        *
        np.sin(dlon / 2.0) ** 2
    )

    a = np.clip(
        a,
        0.0,
        1.0,
    )

    return (
        2.0
        *
        R
        *
        np.arcsin(
            np.sqrt(a)
        )
    )


# ============================================================
# NEAREST GRID CELL
# ============================================================

def nearest_cell(
    grid_lat,
    grid_lon,
    lat,
    lon,
):
    """
    Find nearest Member-1 grid cell.
    """

    lat = float(lat)
    lon = float(lon)

    dlat = (
        grid_lat
        -
        lat
    )

    dlon = (
        (
            grid_lon
            -
            lon
            +
            180.0
        )
        %
        360.0
    ) - 180.0

    metric = (
        dlat ** 2
        +
        (
            dlon
            *
            np.cos(
                np.radians(lat)
            )
        ) ** 2
    )

    metric[
        ~np.isfinite(metric)
    ] = np.inf

    idx = np.argmin(
        metric
    )

    return np.unravel_index(
        idx,
        grid_lat.shape,
    )


# ============================================================
# MEMBER 1 FORECAST
# ============================================================

def get_forecast_for_date(
    ds,
    target_date,
):
    """
    Build historical Member-1 24h/48h/72h SIC
    forecasts for one initialization date.
    """

    target_date = np.datetime64(
        str(target_date),
        "D",
    )

    dates = (
        ds.time.values
        .astype("datetime64[D]")
    )

    matches = np.where(
        dates == target_date
    )[0]

    if len(matches) == 0:
        return None

    idx = int(
        matches[0]
    )

    if idx < 3:
        return None

    current = np.asarray(
        ds.values[idx],
        dtype=np.float32,
    )

    lag1 = np.asarray(
        ds.values[idx - 1],
        dtype=np.float32,
    )

    lag2 = np.asarray(
        ds.values[idx - 2],
        dtype=np.float32,
    )

    lag3 = np.asarray(
        ds.values[idx - 3],
        dtype=np.float32,
    )

    x = np.asarray(
        ds.x.values
    )

    y = np.asarray(
        ds.y.values
    )

    forecasts = predict_sea_ice(
        current=current,
        lag1=lag1,
        lag2=lag2,
        lag3=lag3,
        x_coords=x,
        y_coords=y,
        date=target_date,
    )

    return {
        "current":
            current,

        "24":
            np.asarray(
                forecasts["24h"]
            ),

        "48":
            np.asarray(
                forecasts["48h"]
            ),

        "72":
            np.asarray(
                forecasts["72h"]
            ),

        "x":
            x,

        "y":
            y,
    }


# ============================================================
# ROUTE DISTANCE
# ============================================================

def route_distance_km(
    segment,
):
    """
    Calculate accumulated point-to-point AIS distance.
    """

    if len(segment) < 2:
        return 0.0

    lat = (
        segment["lat"]
        .to_numpy(dtype=float)
    )

    lon = (
        segment["lon"]
        .to_numpy(dtype=float)
    )

    d = haversine_km(
        lat[:-1],
        lon[:-1],
        lat[1:],
        lon[1:],
    )

    return float(
        np.nansum(d)
    )


# ============================================================
# SIC EXPOSURE
# ============================================================

def sample_sic_along_route(
    segment,
    sic,
    grid_lat,
    grid_lon,
):
    """
    Sample forecast SIC along an AIS segment.
    """

    values = []

    valid_count = 0
    invalid_count = 0

    for _, point in segment.iterrows():

        r, c = nearest_cell(
            grid_lat,
            grid_lon,
            point["lat"],
            point["lon"],
        )

        value = float(
            sic[r, c]
        )

        if np.isfinite(value):

            values.append(
                value
            )

            valid_count += 1

        else:

            invalid_count += 1

    if len(values) == 0:

        return {
            "mean_sic":
                np.nan,

            "median_sic":
                np.nan,

            "max_sic":
                np.nan,

            "ice_15_pct":
                np.nan,

            "ice_30_pct":
                np.nan,

            "ice_55_pct":
                np.nan,

            "ice_80_pct":
                np.nan,

            "valid_points":
                valid_count,

            "invalid_points":
                invalid_count,
        }

    values = np.asarray(
        values,
        dtype=float,
    )

    return {
        "mean_sic":
            float(
                np.mean(values)
            ),

        "median_sic":
            float(
                np.median(values)
            ),

        "max_sic":
            float(
                np.max(values)
            ),

        "ice_15_pct":
            float(
                np.mean(
                    values >= 0.15
                )
                *
                100.0
            ),

        "ice_30_pct":
            float(
                np.mean(
                    values >= 0.30
                )
                *
                100.0
            ),

        "ice_55_pct":
            float(
                np.mean(
                    values >= 0.55
                )
                *
                100.0
            ),

        "ice_80_pct":
            float(
                np.mean(
                    values >= 0.80
                )
                *
                100.0
            ),

        "valid_points":
            valid_count,

        "invalid_points":
            invalid_count,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 110)
    print("POLARGUARD")
    print(
        "POLARSTERN PS124 HISTORICAL "
        "SEA-ICE EXPOSURE + TIME-COVERAGE SCAN"
    )
    print("=" * 110)

    # --------------------------------------------------------
    # LOAD AIS
    # --------------------------------------------------------

    ais = pd.read_csv(
        AIS_FILE
    )

    ais["timestamp"] = pd.to_datetime(
        ais["timestamp"],
        utc=True,
        errors="coerce",
    )

    ais["lat"] = pd.to_numeric(
        ais["lat"],
        errors="coerce",
    )

    ais["lon"] = pd.to_numeric(
        ais["lon"],
        errors="coerce",
    )

    ais = (
        ais
        .dropna(
            subset=[
                "timestamp",
                "lat",
                "lon",
            ]
        )
        .sort_values(
            "timestamp"
        )
        .reset_index(
            drop=True
        )
    )

    # --------------------------------------------------------
    # LOAD MEMBER 1 HISTORY
    # --------------------------------------------------------

    ds = xr.open_dataarray(
        SEA_ICE_HISTORY_FILE
    )

    x = np.asarray(
        ds.x.values
    )

    y = np.asarray(
        ds.y.values
    )

    grid_lat, grid_lon = (
        projected_grid_to_latlon(
            x,
            y,
        )
    )

    # --------------------------------------------------------
    # CANDIDATE START TIMES
    # --------------------------------------------------------

    start_min = (
        ais["timestamp"]
        .min()
        .ceil(
            f"{WINDOW_STEP_HOURS}h"
        )
    )

    start_max = (
        ais["timestamp"].max()
        -
        pd.Timedelta(
            hours=max(HORIZONS)
        )
    )

    candidate_starts = pd.date_range(
        start=start_min,
        end=start_max,
        freq=f"{WINDOW_STEP_HOURS}h",
        tz="UTC",
    )

    print()
    print(
        "AIS rows:",
        f"{len(ais):,}",
    )

    print(
        "AIS start:",
        ais["timestamp"].min(),
    )

    print(
        "AIS end  :",
        ais["timestamp"].max(),
    )

    print()
    print(
        "Candidate start times:",
        len(candidate_starts),
    )

    print(
        "Horizon tests per start:",
        len(HORIZONS),
    )

    print(
        "Maximum theoretical tests:",
        len(candidate_starts)
        *
        len(HORIZONS),
    )

    rows = []

    forecast_cache = {}

    # ========================================================
    # SCAN ALL WINDOWS
    # ========================================================

    for number, start_time in enumerate(
        candidate_starts,
        start=1,
    ):

        if (
            number == 1
            or
            number % 20 == 0
        ):

            print(
                f"Scanning start "
                f"{number:,}/"
                f"{len(candidate_starts):,} "
                f"({start_time})"
            )

        init_date = (
            start_time.date()
        )

        key = str(
            init_date
        )

        if key not in forecast_cache:

            forecast_cache[key] = (
                get_forecast_for_date(
                    ds,
                    init_date,
                )
            )

        bundle = (
            forecast_cache[key]
        )

        if bundle is None:
            continue

        # ----------------------------------------------------
        # 24 / 48 / 72
        # ----------------------------------------------------

        for horizon in HORIZONS:

            requested_start_time = (
                start_time
            )

            requested_end_time = (
                start_time
                +
                pd.Timedelta(
                    hours=horizon
                )
            )

            # ------------------------------------------------
            # AIS observations strictly inside requested range
            # ------------------------------------------------

            segment = ais[
                (
                    ais["timestamp"]
                    >=
                    requested_start_time
                )
                &
                (
                    ais["timestamp"]
                    <=
                    requested_end_time
                )
            ].copy()

            if len(segment) < MIN_POINTS:
                continue

            segment = (
                segment
                .sort_values(
                    "timestamp"
                )
                .reset_index(
                    drop=True
                )
            )

            # =================================================
            # ACTUAL AIS TIME-COVERAGE DIAGNOSTICS
            # =================================================

            actual_start_time = pd.Timestamp(
                segment.iloc[0][
                    "timestamp"
                ]
            )

            actual_end_time = pd.Timestamp(
                segment.iloc[-1][
                    "timestamp"
                ]
            )

            start_delay_minutes = (
                (
                    actual_start_time
                    -
                    requested_start_time
                )
                .total_seconds()
                /
                60.0
            )

            end_shortfall_minutes = (
                (
                    requested_end_time
                    -
                    actual_end_time
                )
                .total_seconds()
                /
                60.0
            )

            effective_duration_hours = (
                (
                    actual_end_time
                    -
                    actual_start_time
                )
                .total_seconds()
                /
                3600.0
            )

            duration_error_minutes = abs(
                effective_duration_hours
                -
                float(horizon)
            ) * 60.0

            # ------------------------------------------------
            # MEMBER 1 SIC FOR HORIZON
            # ------------------------------------------------

            sic = bundle[
                str(horizon)
            ]

            exposure = (
                sample_sic_along_route(
                    segment,
                    sic,
                    grid_lat,
                    grid_lon,
                )
            )

            # ------------------------------------------------
            # START / END POSITIONS
            # ------------------------------------------------

            start_point = (
                segment.iloc[0]
            )

            end_point = (
                segment.iloc[-1]
            )

            # ------------------------------------------------
            # ROUTE DISTANCES
            # ------------------------------------------------

            actual_distance = (
                route_distance_km(
                    segment
                )
            )

            direct_distance = float(
                haversine_km(
                    float(
                        start_point["lat"]
                    ),
                    float(
                        start_point["lon"]
                    ),
                    float(
                        end_point["lat"]
                    ),
                    float(
                        end_point["lon"]
                    ),
                )
            )

            geometric_efficiency_pct = (
                direct_distance
                /
                actual_distance
                *
                100.0
                if actual_distance > 0
                else np.nan
            )

            # ------------------------------------------------
            # SIC COVERAGE
            # ------------------------------------------------

            total_points = (
                exposure[
                    "valid_points"
                ]
                +
                exposure[
                    "invalid_points"
                ]
            )

            valid_pct = (
                exposure[
                    "valid_points"
                ]
                /
                total_points
                *
                100.0
                if total_points > 0
                else 0.0
            )

            # =================================================
            # ICE EXPOSURE SCORE
            # =================================================
            #
            # Keep original environmental scoring.
            #
            # IMPORTANT:
            # Timing is stored separately and will be enforced
            # during route-validation candidate selection.
            # =================================================

            score = 0.0

            if np.isfinite(
                exposure[
                    "mean_sic"
                ]
            ):

                score += (
                    exposure[
                        "mean_sic"
                    ]
                    *
                    100.0
                )

            if np.isfinite(
                exposure[
                    "max_sic"
                ]
            ):

                score += (
                    exposure[
                        "max_sic"
                    ]
                    *
                    75.0
                )

            if np.isfinite(
                exposure[
                    "ice_15_pct"
                ]
            ):

                score += (
                    exposure[
                        "ice_15_pct"
                    ]
                    *
                    0.75
                )

            if np.isfinite(
                exposure[
                    "ice_30_pct"
                ]
            ):

                score += (
                    exposure[
                        "ice_30_pct"
                    ]
                    *
                    0.50
                )

            score += (
                valid_pct
                *
                0.10
            )

            # =================================================
            # SAVE CANDIDATE
            # =================================================

            rows.append(
                {
                    "start_time":
                        requested_start_time,

                    "end_time":
                        requested_end_time,

                    "requested_start_time":
                        requested_start_time,

                    "actual_start_time":
                        actual_start_time,

                    "requested_end_time":
                        requested_end_time,

                    "actual_end_time":
                        actual_end_time,

                    "start_delay_minutes":
                        start_delay_minutes,

                    "end_shortfall_minutes":
                        end_shortfall_minutes,

                    "effective_duration_hours":
                        effective_duration_hours,

                    "duration_error_minutes":
                        duration_error_minutes,

                    "initialization_date":
                        key,

                    "horizon_hours":
                        horizon,

                    "ais_points":
                        len(segment),

                    "start_latitude":
                        float(
                            start_point["lat"]
                        ),

                    "start_longitude":
                        float(
                            start_point["lon"]
                        ),

                    "destination_latitude":
                        float(
                            end_point["lat"]
                        ),

                    "destination_longitude":
                        float(
                            end_point["lon"]
                        ),

                    "ais_distance_km":
                        actual_distance,

                    "direct_distance_km":
                        direct_distance,

                    "geometric_efficiency_pct":
                        geometric_efficiency_pct,

                    "mean_sic_pct":
                        (
                            exposure[
                                "mean_sic"
                            ]
                            *
                            100.0
                            if np.isfinite(
                                exposure[
                                    "mean_sic"
                                ]
                            )
                            else np.nan
                        ),

                    "median_sic_pct":
                        (
                            exposure[
                                "median_sic"
                            ]
                            *
                            100.0
                            if np.isfinite(
                                exposure[
                                    "median_sic"
                                ]
                            )
                            else np.nan
                        ),

                    "max_sic_pct":
                        (
                            exposure[
                                "max_sic"
                            ]
                            *
                            100.0
                            if np.isfinite(
                                exposure[
                                    "max_sic"
                                ]
                            )
                            else np.nan
                        ),

                    "points_in_ice_ge_15_pct":
                        exposure[
                            "ice_15_pct"
                        ],

                    "points_in_ice_ge_30_pct":
                        exposure[
                            "ice_30_pct"
                        ],

                    "points_in_ice_ge_55_pct":
                        exposure[
                            "ice_55_pct"
                        ],

                    "points_in_ice_ge_80_pct":
                        exposure[
                            "ice_80_pct"
                        ],

                    "valid_sic_points":
                        exposure[
                            "valid_points"
                        ],

                    "invalid_sic_points":
                        exposure[
                            "invalid_points"
                        ],

                    "valid_sic_coverage_pct":
                        valid_pct,

                    "ice_exposure_score":
                        score,
                }
            )

    # ========================================================
    # BUILD RESULT DATAFRAME
    # ========================================================

    results = pd.DataFrame(
        rows
    )

    if results.empty:

        raise RuntimeError(
            "No PS124 candidate "
            "windows generated."
        )

    results = (
        results
        .sort_values(
            [
                "ice_exposure_score",
                "mean_sic_pct",
                "max_sic_pct",
            ],
            ascending=False,
        )
        .reset_index(
            drop=True
        )
    )

    # ========================================================
    # SAVE ALL CANDIDATES
    # ========================================================

    all_file = (
        OUTPUT_DIR
        /
        "ps124_all_candidate_windows.csv"
    )

    results.to_csv(
        all_file,
        index=False,
    )

    # ========================================================
    # STRONG ICE WINDOWS
    # ========================================================

    strong = results[
        results[
            "valid_sic_coverage_pct"
        ]
        >=
        90.0
    ].copy()

    top = (
        strong
        .head(40)
        .copy()
    )

    top_file = (
        OUTPUT_DIR
        /
        "ps124_top_ice_windows.csv"
    )

    top.to_csv(
        top_file,
        index=False,
    )

    # ========================================================
    # PRINT TOP ICE WINDOWS
    # ========================================================

    print()
    print("=" * 110)
    print("TOP PS124 ICE-EXPOSURE WINDOWS")
    print("=" * 110)

    top_columns = [
        "start_time",
        "horizon_hours",
        "ais_points",
        "effective_duration_hours",
        "duration_error_minutes",
        "end_shortfall_minutes",
        "ais_distance_km",
        "direct_distance_km",
        "geometric_efficiency_pct",
        "mean_sic_pct",
        "max_sic_pct",
        "points_in_ice_ge_15_pct",
        "points_in_ice_ge_55_pct",
        "valid_sic_coverage_pct",
        "ice_exposure_score",
    ]

    print()

    print(
        top[
            top_columns
        ]
        .round(3)
        .to_string(
            index=False
        )
    )

    # ========================================================
    # TIMING QUALITY SUMMARY
    # ========================================================

    print()
    print("=" * 110)
    print("TIME-COVERAGE SUMMARY")
    print("=" * 110)

    for horizon in HORIZONS:

        h = results[
            results[
                "horizon_hours"
            ]
            ==
            horizon
        ]

        print()

        print(
            f"{horizon}H candidates:",
            len(h),
        )

        print(
            "  Duration error <= 30 min:",
            int(
                (
                    h[
                        "duration_error_minutes"
                    ]
                    <=
                    30.0
                ).sum()
            ),
        )

        print(
            "  Duration error <= 60 min:",
            int(
                (
                    h[
                        "duration_error_minutes"
                    ]
                    <=
                    60.0
                ).sum()
            ),
        )

        print(
            "  Duration error <= 90 min:",
            int(
                (
                    h[
                        "duration_error_minutes"
                    ]
                    <=
                    90.0
                ).sum()
            ),
        )

    # ========================================================
    # ICE SUMMARY
    # ========================================================

    print()
    print("=" * 110)
    print("ICE-EXPOSURE SUMMARY")
    print("=" * 110)

    print(
        "Candidate windows:",
        len(results),
    )

    print(
        "Windows with any SIC >= 15%:",
        int(
            (
                results[
                    "points_in_ice_ge_15_pct"
                ]
                >
                0
            ).sum()
        ),
    )

    print(
        "Windows with max SIC >= 30%:",
        int(
            (
                results[
                    "max_sic_pct"
                ]
                >=
                30.0
            ).sum()
        ),
    )

    print(
        "Windows with max SIC >= 55%:",
        int(
            (
                results[
                    "max_sic_pct"
                ]
                >=
                55.0
            ).sum()
        ),
    )

    print(
        "Windows with max SIC >= 80%:",
        int(
            (
                results[
                    "max_sic_pct"
                ]
                >=
                80.0
            ).sum()
        ),
    )

    print(
        "Windows with mean SIC >= 15%:",
        int(
            (
                results[
                    "mean_sic_pct"
                ]
                >=
                15.0
            ).sum()
        ),
    )

    print(
        "Windows with >=50% AIS "
        "points in SIC >=15%:",
        int(
            (
                results[
                    "points_in_ice_ge_15_pct"
                ]
                >=
                50.0
            ).sum()
        ),
    )

    # ========================================================
    # BEST TIME-COVERED WINDOWS
    # ========================================================

    print()
    print("=" * 110)
    print("BEST TIME-COVERED WINDOWS BY HORIZON")
    print("=" * 110)

    for horizon in HORIZONS:

        h = results[
            results[
                "horizon_hours"
            ]
            ==
            horizon
        ].copy()

        h = h.sort_values(
            [
                "duration_error_minutes",
                "ice_exposure_score",
            ],
            ascending=[
                True,
                False,
            ],
        )

        best = (
            h
            .head(10)
            .copy()
        )

        print()
        print(
            f"{horizon}H - "
            "10 LOWEST DURATION ERRORS"
        )

        print(
            "-" * 110
        )

        print(
            best[
                [
                    "start_time",
                    "actual_start_time",
                    "actual_end_time",
                    "effective_duration_hours",
                    "duration_error_minutes",
                    "start_delay_minutes",
                    "end_shortfall_minutes",
                    "ais_distance_km",
                    "direct_distance_km",
                    "geometric_efficiency_pct",
                    "mean_sic_pct",
                    "max_sic_pct",
                    "valid_sic_coverage_pct",
                ]
            ]
            .round(3)
            .to_string(
                index=False
            )
        )

    # ========================================================
    # OUTPUT
    # ========================================================

    print()
    print("=" * 110)
    print("FILES CREATED")
    print("=" * 110)

    print(all_file)
    print(top_file)

    print()
    print("=" * 110)
    print("PS124 ICE + TIME-COVERAGE SCAN COMPLETE")
    print("=" * 110)


if __name__ == "__main__":
    main()
