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
    / "oceannova_2024"
    / "analysis"
    / "oceannova_cleaned_track.csv"
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
    / "stage5_ice_scan"
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

    lat = float(lat)
    lon = float(lon)

    dlat = (
        grid_lat
        - lat
    )

    dlon = (
        (
            grid_lon
            - lon
            + 180.0
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

    index = np.argmin(
        metric
    )

    return np.unravel_index(
        index,
        grid_lat.shape,
    )


# ============================================================
# LOAD HISTORICAL MEMBER 1 FORECAST
# ============================================================

def get_forecast_for_date(
    ds,
    target_date,
):

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
# SAMPLE SIC
# ============================================================

def sample_sic_along_route(
    segment,
    sic,
    grid_lat,
    grid_lon,
):

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

    if not values:

        return {
            "mean_sic":
                np.nan,

            "max_sic":
                np.nan,

            "ice_15_pct":
                np.nan,

            "ice_30_pct":
                np.nan,

            "ice_55_pct":
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

        "valid_points":
            valid_count,

        "invalid_points":
            invalid_count,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 100)
    print("POLARGUARD")
    print("STAGE 5 - OCEANNOVA AIS ICE-EXPOSURE SCAN")
    print("=" * 100)

    ais = pd.read_csv(
        AIS_FILE
    )

    ais["timestamp"] = pd.to_datetime(
        ais["timestamp"],
        utc=True,
    )

    ais = (
        ais
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

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

    start_min = (
        ais["timestamp"].min()
        .floor("6h")
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

    rows = []

    forecast_cache = {}

    for start_time in candidate_starts:

        init_date = (
            start_time
            .date()
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

        for horizon in HORIZONS:

            end_time = (
                start_time
                +
                pd.Timedelta(
                    hours=horizon
                )
            )

            segment = ais[
                (
                    ais["timestamp"]
                    >= start_time
                )
                &
                (
                    ais["timestamp"]
                    <= end_time
                )
            ].copy()

            if len(segment) < MIN_POINTS:
                continue

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

            start_point = (
                segment.iloc[0]
            )

            end_point = (
                segment.iloc[-1]
            )

            distance = (
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

            valid_total = (
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
                valid_total
                *
                100.0
                if valid_total > 0
                else 0.0
            )

            # Stronger score = actual ice exposure +
            # good environmental coverage.
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

            score += (
                valid_pct
                *
                0.10
            )

            rows.append(
                {
                    "start_time":
                        start_time,

                    "end_time":
                        end_time,

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
                        distance,

                    "direct_distance_km":
                        direct_distance,

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

                    "points_above_medium_limit_pct":
                        exposure[
                            "ice_55_pct"
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

    results = pd.DataFrame(
        rows
    )

    if results.empty:
        raise RuntimeError(
            "No candidate windows were generated."
        )

    results = results.sort_values(
        [
            "ice_exposure_score",
            "max_sic_pct",
            "mean_sic_pct",
        ],
        ascending=False,
    ).reset_index(
        drop=True
    )

    output_file = (
        OUTPUT_DIR
        /
        "oceannova_all_candidate_windows.csv"
    )

    results.to_csv(
        output_file,
        index=False,
    )

    top = (
        results
        .head(30)
        .copy()
    )

    top_file = (
        OUTPUT_DIR
        /
        "oceannova_top_ice_exposure_windows.csv"
    )

    top.to_csv(
        top_file,
        index=False,
    )

    print()
    print("=" * 100)
    print("TOP ICE-EXPOSURE WINDOWS")
    print("=" * 100)

    print()

    print(
        top[
            [
                "start_time",
                "horizon_hours",
                "ais_points",
                "ais_distance_km",
                "mean_sic_pct",
                "max_sic_pct",
                "points_in_ice_ge_15_pct",
                "points_in_ice_ge_30_pct",
                "points_above_medium_limit_pct",
                "valid_sic_coverage_pct",
                "ice_exposure_score",
            ]
        ]
        .round(3)
        .to_string(
            index=False
        )
    )

    print()
    print("=" * 100)
    print("SUMMARY")
    print("=" * 100)

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
        "Windows with maximum SIC >= 30%:",
        int(
            (
                results[
                    "max_sic_pct"
                ]
                >=
                30
            ).sum()
        ),
    )

    print(
        "Windows with maximum SIC >= 55%:",
        int(
            (
                results[
                    "max_sic_pct"
                ]
                >=
                55
            ).sum()
        ),
    )

    print()
    print("=" * 100)
    print("FILES CREATED")
    print("=" * 100)

    print(output_file)
    print(top_file)

    print()
    print("=" * 100)
    print("STAGE 5 COMPLETE")
    print("=" * 100)


if __name__ == "__main__":
    main()