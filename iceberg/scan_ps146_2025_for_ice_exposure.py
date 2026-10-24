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
    / "polarstern_ps146_2025"
    / "analysis"
    / "polarstern_ps146_2025_cleaned_track.csv"
)

FORECAST_HISTORY_FILE = (
    BASE
    / "data"
    / "processed"
    / "sea_ice_2019_2025.nc"
)

ACTUAL_2025_FILE = (
    BASE
    / "data"
    / "processed"
    / "test_2025.nc"
)

OUTPUT_DIR = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps146_2025_stage1_scan"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

ALL_FILE = (
    OUTPUT_DIR
    / "ps146_2025_all_candidate_windows.csv"
)

TOP_FILE = (
    OUTPUT_DIR
    / "ps146_2025_top_validation_windows.csv"
)

DAILY_FORECAST_FILE = (
    OUTPUT_DIR
    / "ps146_2025_daily_sic_forecast_metrics.csv"
)


# ============================================================
# SETTINGS
# ============================================================

HORIZONS = [24, 48, 72]

# Daily SIC is initialized at 00:00 UTC.
# Therefore use daily route windows for clean alignment.
WINDOW_STEP_HOURS = 24

MIN_POINTS = 5

ICE_THRESHOLD = 0.15

MAX_START_DELAY_MIN = 30.0
MAX_END_SHORTFALL_MIN = 30.0
MAX_DURATION_ERROR_MIN = 30.0

MIN_VALID_SIC_COVERAGE_PCT = 95.0

MIN_DIRECT_DISTANCE_KM = {
    24: 30.0,
    48: 60.0,
    72: 90.0,
}

MIN_GEOMETRIC_EFFICIENCY_PCT = 20.0


# ============================================================
# GRID CONVERSION
# ============================================================

def projected_grid_to_latlon(
    x_coords,
    y_coords,
):

    x_grid, y_grid = np.meshgrid(
        np.asarray(
            x_coords,
            dtype=float,
        ),
        np.asarray(
            y_coords,
            dtype=float,
        ),
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
        np.asarray(
            grid_lat,
            dtype=float,
        ),
        np.asarray(
            grid_lon,
            dtype=float,
        ),
    )


# ============================================================
# HAVERSINE DISTANCE
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

    dlat = (
        lat2
        -
        lat1
    )

    dlon = (
        lon2
        -
        lon1
        +
        np.pi
    ) % (2.0 * np.pi) - np.pi

    a = (
        np.sin(
            dlat / 2.0
        ) ** 2
        +
        np.cos(lat1)
        *
        np.cos(lat2)
        *
        np.sin(
            dlon / 2.0
        ) ** 2
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
# NEAREST MEMBER-1 GRID CELL
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

    index = np.argmin(
        metric
    )

    return np.unravel_index(
        index,
        grid_lat.shape,
    )


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
        .to_numpy(
            dtype=float
        )
    )

    lon = (
        segment["lon"]
        .to_numpy(
            dtype=float
        )
    )

    distance = haversine_km(
        lat[:-1],
        lon[:-1],
        lat[1:],
        lon[1:],
    )

    return float(
        np.nansum(
            distance
        )
    )


# ============================================================
# MEMBER 1 FORECAST
# ============================================================

def get_forecast_for_date(
    history,
    target_date,
):

    target_date = np.datetime64(
        str(target_date),
        "D",
    )

    dates = (
        history.time.values
        .astype(
            "datetime64[D]"
        )
    )

    matches = np.where(
        dates
        ==
        target_date
    )[0]

    if len(matches) == 0:
        return None

    idx = int(
        matches[0]
    )

    if idx < 3:
        return None

    current = np.asarray(
        history.isel(
            time=idx
        ).values,
        dtype=np.float32,
    )

    lag1 = np.asarray(
        history.isel(
            time=idx - 1
        ).values,
        dtype=np.float32,
    )

    lag2 = np.asarray(
        history.isel(
            time=idx - 2
        ).values,
        dtype=np.float32,
    )

    lag3 = np.asarray(
        history.isel(
            time=idx - 3
        ).values,
        dtype=np.float32,
    )

    x = np.asarray(
        history.x.values
    )

    y = np.asarray(
        history.y.values
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
        "24":
            np.asarray(
                forecasts["24h"],
                dtype=np.float32,
            ),

        "48":
            np.asarray(
                forecasts["48h"],
                dtype=np.float32,
            ),

        "72":
            np.asarray(
                forecasts["72h"],
                dtype=np.float32,
            ),
    }


# ============================================================
# ACTUAL 2025 SIC
# ============================================================

def get_actual_sic(
    actual_da,
    target_date,
):

    target_date = np.datetime64(
        str(target_date),
        "D",
    )

    dates = (
        actual_da.time.values
        .astype(
            "datetime64[D]"
        )
    )

    matches = np.where(
        dates
        ==
        target_date
    )[0]

    if len(matches) == 0:
        return None

    idx = int(
        matches[0]
    )

    return np.asarray(
        actual_da.isel(
            time=idx
        ).values,
        dtype=np.float32,
    )


# ============================================================
# FULL-GRID ACTUAL VS PREDICTED METRICS
# ============================================================

def compute_map_metrics(
    predicted,
    actual,
):

    valid = (
        np.isfinite(predicted)
        &
        np.isfinite(actual)
    )

    valid_cells = int(
        np.count_nonzero(
            valid
        )
    )

    if valid_cells == 0:

        return {
            "valid_cells": 0,
            "mae": np.nan,
            "rmse": np.nan,
            "bias": np.nan,
            "correlation": np.nan,
            "ice_accuracy_pct": np.nan,
        }

    predicted_values = (
        predicted[
            valid
        ].astype(float)
    )

    actual_values = (
        actual[
            valid
        ].astype(float)
    )

    error = (
        predicted_values
        -
        actual_values
    )

    mae = float(
        np.mean(
            np.abs(error)
        )
    )

    rmse = float(
        np.sqrt(
            np.mean(
                error ** 2
            )
        )
    )

    bias = float(
        np.mean(
            error
        )
    )

    if (
        len(predicted_values) > 1
        and
        np.std(predicted_values) > 0
        and
        np.std(actual_values) > 0
    ):

        correlation = float(
            np.corrcoef(
                predicted_values,
                actual_values,
            )[0, 1]
        )

    else:

        correlation = np.nan

    predicted_ice = (
        predicted_values
        >=
        ICE_THRESHOLD
    )

    actual_ice = (
        actual_values
        >=
        ICE_THRESHOLD
    )

    ice_accuracy_pct = float(
        np.mean(
            predicted_ice
            ==
            actual_ice
        )
        *
        100.0
    )

    return {
        "valid_cells":
            valid_cells,

        "mae":
            mae,

        "rmse":
            rmse,

        "bias":
            bias,

        "correlation":
            correlation,

        "ice_accuracy_pct":
            ice_accuracy_pct,
    }


# ============================================================
# SAMPLE ACTUAL + PREDICTED SIC ALONG AIS ROUTE
# ============================================================

def sample_actual_predicted_along_route(
    segment,
    predicted_sic,
    actual_sic,
    grid_lat,
    grid_lon,
):

    predicted_values = []
    actual_values = []

    valid_count = 0
    invalid_count = 0

    for _, point in segment.iterrows():

        row, col = nearest_cell(
            grid_lat,
            grid_lon,
            point["lat"],
            point["lon"],
        )

        predicted = float(
            predicted_sic[
                row,
                col
            ]
        )

        actual = float(
            actual_sic[
                row,
                col
            ]
        )

        if (
            np.isfinite(predicted)
            and
            np.isfinite(actual)
        ):

            predicted_values.append(
                predicted
            )

            actual_values.append(
                actual
            )

            valid_count += 1

        else:

            invalid_count += 1

    if valid_count == 0:

        return {
            "valid_points": 0,
            "invalid_points":
                invalid_count,

            "pred_mean_sic": np.nan,
            "pred_median_sic": np.nan,
            "pred_max_sic": np.nan,

            "actual_mean_sic": np.nan,
            "actual_median_sic": np.nan,
            "actual_max_sic": np.nan,

            "actual_ice_15_pct": np.nan,
            "actual_ice_30_pct": np.nan,
            "actual_ice_55_pct": np.nan,
            "actual_ice_80_pct": np.nan,

            "pred_ice_15_pct": np.nan,

            "route_sic_mae": np.nan,
            "route_sic_rmse": np.nan,
            "route_sic_bias": np.nan,
            "route_sic_correlation": np.nan,
        }

    predicted_values = np.asarray(
        predicted_values,
        dtype=float,
    )

    actual_values = np.asarray(
        actual_values,
        dtype=float,
    )

    errors = (
        predicted_values
        -
        actual_values
    )

    if (
        len(predicted_values) > 1
        and
        np.std(predicted_values) > 0
        and
        np.std(actual_values) > 0
    ):

        correlation = float(
            np.corrcoef(
                predicted_values,
                actual_values,
            )[0, 1]
        )

    else:

        correlation = np.nan

    return {
        "valid_points":
            valid_count,

        "invalid_points":
            invalid_count,

        "pred_mean_sic":
            float(
                np.mean(
                    predicted_values
                )
            ),

        "pred_median_sic":
            float(
                np.median(
                    predicted_values
                )
            ),

        "pred_max_sic":
            float(
                np.max(
                    predicted_values
                )
            ),

        "actual_mean_sic":
            float(
                np.mean(
                    actual_values
                )
            ),

        "actual_median_sic":
            float(
                np.median(
                    actual_values
                )
            ),

        "actual_max_sic":
            float(
                np.max(
                    actual_values
                )
            ),

        "actual_ice_15_pct":
            float(
                np.mean(
                    actual_values >= 0.15
                )
                *
                100.0
            ),

        "actual_ice_30_pct":
            float(
                np.mean(
                    actual_values >= 0.30
                )
                *
                100.0
            ),

        "actual_ice_55_pct":
            float(
                np.mean(
                    actual_values >= 0.55
                )
                *
                100.0
            ),

        "actual_ice_80_pct":
            float(
                np.mean(
                    actual_values >= 0.80
                )
                *
                100.0
            ),

        "pred_ice_15_pct":
            float(
                np.mean(
                    predicted_values >= 0.15
                )
                *
                100.0
            ),

        "route_sic_mae":
            float(
                np.mean(
                    np.abs(
                        errors
                    )
                )
            ),

        "route_sic_rmse":
            float(
                np.sqrt(
                    np.mean(
                        errors ** 2
                    )
                )
            ),

        "route_sic_bias":
            float(
                np.mean(
                    errors
                )
            ),

        "route_sic_correlation":
            correlation,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 115)
    print("POLARGUARD")
    print(
        "POLARSTERN PS146 2025 "
        "ACTUAL VS PREDICTED SIC + ROUTE-WINDOW SCAN"
    )
    print("=" * 115)

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

    # Keep 2025 only.
    ais = ais[
        ais[
            "timestamp"
        ].dt.year
        ==
        2025
    ].copy()

    # --------------------------------------------------------
    # LOAD FORECAST HISTORY
    # --------------------------------------------------------

    history = xr.open_dataarray(
        FORECAST_HISTORY_FILE
    )

    x = np.asarray(
        history.x.values
    )

    y = np.asarray(
        history.y.values
    )

    grid_lat, grid_lon = (
        projected_grid_to_latlon(
            x,
            y,
        )
    )

    # --------------------------------------------------------
    # LOAD ACTUAL 2025 TEST DATA
    # --------------------------------------------------------

    actual_ds = xr.open_dataset(
        ACTUAL_2025_FILE
    )

    actual_da = actual_ds[
        "sea_ice_concentration"
    ]

    # --------------------------------------------------------
    # CANDIDATE STARTS
    # --------------------------------------------------------

    start_min = (
        ais[
            "timestamp"
        ]
        .min()
        .ceil(
            "1D"
        )
    )

    start_max = (
        ais[
            "timestamp"
        ].max()
        -
        pd.Timedelta(
            hours=max(
                HORIZONS
            )
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
        ais[
            "timestamp"
        ].min(),
    )

    print(
        "AIS end  :",
        ais[
            "timestamp"
        ].max(),
    )

    print()

    print(
        "Candidate daily starts:",
        len(
            candidate_starts
        ),
    )

    print(
        "Horizon tests/start:",
        len(
            HORIZONS
        ),
    )

    print(
        "Maximum theoretical tests:",
        len(
            candidate_starts
        )
        *
        len(
            HORIZONS
        ),
    )

    # --------------------------------------------------------
    # CACHES
    # --------------------------------------------------------

    forecast_cache = {}
    actual_cache = {}
    map_metric_cache = {}

    candidate_rows = []
    daily_metric_rows = []

    # ========================================================
    # SCAN
    # ========================================================

    for number, start_time in enumerate(
        candidate_starts,
        start=1,
    ):

        print(
            f"Scanning "
            f"{number}/"
            f"{len(candidate_starts)} "
            f"({start_time})"
        )

        init_date = (
            start_time.date()
        )

        init_key = str(
            init_date
        )

        if init_key not in forecast_cache:

            forecast_cache[
                init_key
            ] = get_forecast_for_date(
                history,
                init_date,
            )

        bundle = forecast_cache[
            init_key
        ]

        if bundle is None:
            continue

        # ----------------------------------------------------
        # EACH HORIZON
        # ----------------------------------------------------

        for horizon in HORIZONS:

            target_date = (
                pd.Timestamp(
                    start_time
                )
                +
                pd.Timedelta(
                    hours=horizon
                )
            ).date()

            target_key = str(
                target_date
            )

            if target_key not in actual_cache:

                actual_cache[
                    target_key
                ] = get_actual_sic(
                    actual_da,
                    target_date,
                )

            actual_sic = actual_cache[
                target_key
            ]

            if actual_sic is None:
                continue

            predicted_sic = bundle[
                str(
                    horizon
                )
            ]

            # ------------------------------------------------
            # FULL GRID FORECAST METRICS
            # ------------------------------------------------

            metric_key = (
                init_key,
                horizon,
            )

            if metric_key not in map_metric_cache:

                map_metrics = (
                    compute_map_metrics(
                        predicted_sic,
                        actual_sic,
                    )
                )

                map_metric_cache[
                    metric_key
                ] = map_metrics

                daily_metric_rows.append(
                    {
                        "initialization_date":
                            init_key,

                        "target_date":
                            target_key,

                        "horizon_hours":
                            horizon,

                        "valid_cells":
                            map_metrics[
                                "valid_cells"
                            ],

                        "map_mae_pct":
                            map_metrics[
                                "mae"
                            ]
                            *
                            100.0,

                        "map_rmse_pct":
                            map_metrics[
                                "rmse"
                            ]
                            *
                            100.0,

                        "map_bias_pct":
                            map_metrics[
                                "bias"
                            ]
                            *
                            100.0,

                        "map_correlation":
                            map_metrics[
                                "correlation"
                            ],

                        "map_ice_accuracy_pct":
                            map_metrics[
                                "ice_accuracy_pct"
                            ],
                    }
                )

            map_metrics = map_metric_cache[
                metric_key
            ]

            # ------------------------------------------------
            # AIS ROUTE WINDOW
            # ------------------------------------------------

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

            segment = ais[
                (
                    ais[
                        "timestamp"
                    ]
                    >=
                    requested_start_time
                )
                &
                (
                    ais[
                        "timestamp"
                    ]
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
                float(
                    horizon
                )
            ) * 60.0

            # ------------------------------------------------
            # SAMPLE ACTUAL + PREDICTED SIC
            # ------------------------------------------------

            exposure = (
                sample_actual_predicted_along_route(
                    segment,
                    predicted_sic,
                    actual_sic,
                    grid_lat,
                    grid_lon,
                )
            )

            total_points = (
                exposure[
                    "valid_points"
                ]
                +
                exposure[
                    "invalid_points"
                ]
            )

            valid_coverage_pct = (
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

            # ------------------------------------------------
            # ROUTE GEOMETRY
            # ------------------------------------------------

            start_point = (
                segment.iloc[0]
            )

            end_point = (
                segment.iloc[-1]
            )

            ais_distance = (
                route_distance_km(
                    segment
                )
            )

            direct_distance = float(
                haversine_km(
                    float(
                        start_point[
                            "lat"
                        ]
                    ),
                    float(
                        start_point[
                            "lon"
                        ]
                    ),
                    float(
                        end_point[
                            "lat"
                        ]
                    ),
                    float(
                        end_point[
                            "lon"
                        ]
                    ),
                )
            )

            geometric_efficiency_pct = (
                direct_distance
                /
                ais_distance
                *
                100.0
                if ais_distance > 0
                else np.nan
            )

            # =================================================
            # VALIDATION CANDIDATE SCORE
            # =================================================
            #
            # IMPORTANT:
            # We rank using ACTUAL sea-ice exposure and
            # route quality.
            #
            # We deliberately DO NOT reward low forecast error.
            # Otherwise we would cherry-pick cases where the
            # model happened to perform best.
            # =================================================

            score = 0.0

            if np.isfinite(
                exposure[
                    "actual_mean_sic"
                ]
            ):
                score += (
                    exposure[
                        "actual_mean_sic"
                    ]
                    *
                    100.0
                )

            if np.isfinite(
                exposure[
                    "actual_max_sic"
                ]
            ):
                score += (
                    exposure[
                        "actual_max_sic"
                    ]
                    *
                    50.0
                )

            if np.isfinite(
                exposure[
                    "actual_ice_15_pct"
                ]
            ):
                score += (
                    exposure[
                        "actual_ice_15_pct"
                    ]
                    *
                    0.50
                )

            score += (
                min(
                    direct_distance,
                    500.0,
                )
                *
                0.10
            )

            if np.isfinite(
                geometric_efficiency_pct
            ):
                score += (
                    geometric_efficiency_pct
                    *
                    0.50
                )

            score += (
                valid_coverage_pct
                *
                0.20
            )

            # ------------------------------------------------
            # TIME QUALITY FLAGS
            # ------------------------------------------------

            timing_pass = (
                start_delay_minutes
                <=
                MAX_START_DELAY_MIN
                and
                end_shortfall_minutes
                <=
                MAX_END_SHORTFALL_MIN
                and
                duration_error_minutes
                <=
                MAX_DURATION_ERROR_MIN
            )

            route_quality_pass = (
                direct_distance
                >=
                MIN_DIRECT_DISTANCE_KM[
                    horizon
                ]
                and
                geometric_efficiency_pct
                >=
                MIN_GEOMETRIC_EFFICIENCY_PCT
            )

            coverage_pass = (
                valid_coverage_pct
                >=
                MIN_VALID_SIC_COVERAGE_PCT
            )

            validation_candidate = (
                timing_pass
                and
                route_quality_pass
                and
                coverage_pass
            )

            # ------------------------------------------------
            # SAVE
            # ------------------------------------------------

            candidate_rows.append(
                {
                    "start_time":
                        requested_start_time,

                    "end_time":
                        requested_end_time,

                    "actual_start_time":
                        actual_start_time,

                    "actual_end_time":
                        actual_end_time,

                    "initialization_date":
                        init_key,

                    "target_date":
                        target_key,

                    "horizon_hours":
                        horizon,

                    "ais_points":
                        len(
                            segment
                        ),

                    "start_delay_minutes":
                        start_delay_minutes,

                    "end_shortfall_minutes":
                        end_shortfall_minutes,

                    "effective_duration_hours":
                        effective_duration_hours,

                    "duration_error_minutes":
                        duration_error_minutes,

                    "start_latitude":
                        float(
                            start_point[
                                "lat"
                            ]
                        ),

                    "start_longitude":
                        float(
                            start_point[
                                "lon"
                            ]
                        ),

                    "destination_latitude":
                        float(
                            end_point[
                                "lat"
                            ]
                        ),

                    "destination_longitude":
                        float(
                            end_point[
                                "lon"
                            ]
                        ),

                    "ais_distance_km":
                        ais_distance,

                    "direct_distance_km":
                        direct_distance,

                    "geometric_efficiency_pct":
                        geometric_efficiency_pct,

                    # ------------------------------
                    # ACTUAL ROUTE SIC
                    # ------------------------------

                    "actual_mean_sic_pct":
                        exposure[
                            "actual_mean_sic"
                        ]
                        *
                        100.0,

                    "actual_median_sic_pct":
                        exposure[
                            "actual_median_sic"
                        ]
                        *
                        100.0,

                    "actual_max_sic_pct":
                        exposure[
                            "actual_max_sic"
                        ]
                        *
                        100.0,

                    "actual_points_in_ice_ge_15_pct":
                        exposure[
                            "actual_ice_15_pct"
                        ],

                    "actual_points_in_ice_ge_30_pct":
                        exposure[
                            "actual_ice_30_pct"
                        ],

                    "actual_points_in_ice_ge_55_pct":
                        exposure[
                            "actual_ice_55_pct"
                        ],

                    "actual_points_in_ice_ge_80_pct":
                        exposure[
                            "actual_ice_80_pct"
                        ],

                    # ------------------------------
                    # PREDICTED ROUTE SIC
                    # ------------------------------

                    "predicted_mean_sic_pct":
                        exposure[
                            "pred_mean_sic"
                        ]
                        *
                        100.0,

                    "predicted_median_sic_pct":
                        exposure[
                            "pred_median_sic"
                        ]
                        *
                        100.0,

                    "predicted_max_sic_pct":
                        exposure[
                            "pred_max_sic"
                        ]
                        *
                        100.0,

                    "predicted_points_in_ice_ge_15_pct":
                        exposure[
                            "pred_ice_15_pct"
                        ],

                    # ------------------------------
                    # ROUTE-LEVEL SIC ERROR
                    # ------------------------------

                    "route_sic_mae_pct":
                        exposure[
                            "route_sic_mae"
                        ]
                        *
                        100.0,

                    "route_sic_rmse_pct":
                        exposure[
                            "route_sic_rmse"
                        ]
                        *
                        100.0,

                    "route_sic_bias_pct":
                        exposure[
                            "route_sic_bias"
                        ]
                        *
                        100.0,

                    "route_sic_correlation":
                        exposure[
                            "route_sic_correlation"
                        ],

                    # ------------------------------
                    # FULL-GRID SIC ERROR
                    # ------------------------------

                    "map_mae_pct":
                        map_metrics[
                            "mae"
                        ]
                        *
                        100.0,

                    "map_rmse_pct":
                        map_metrics[
                            "rmse"
                        ]
                        *
                        100.0,

                    "map_bias_pct":
                        map_metrics[
                            "bias"
                        ]
                        *
                        100.0,

                    "map_correlation":
                        map_metrics[
                            "correlation"
                        ],

                    "map_ice_accuracy_pct":
                        map_metrics[
                            "ice_accuracy_pct"
                        ],

                    # ------------------------------
                    # QUALITY
                    # ------------------------------

                    "valid_sic_points":
                        exposure[
                            "valid_points"
                        ],

                    "invalid_sic_points":
                        exposure[
                            "invalid_points"
                        ],

                    "valid_sic_coverage_pct":
                        valid_coverage_pct,

                    "timing_pass":
                        timing_pass,

                    "route_quality_pass":
                        route_quality_pass,

                    "coverage_pass":
                        coverage_pass,

                    "validation_candidate":
                        validation_candidate,

                    "validation_score":
                        score,
                }
            )

    # ========================================================
    # SAVE RESULTS
    # ========================================================

    results = pd.DataFrame(
        candidate_rows
    )

    if results.empty:

        raise RuntimeError(
            "No PS146 2025 candidate windows generated."
        )

    results = (
        results
        .sort_values(
            [
                "validation_candidate",
                "validation_score",
                "actual_mean_sic_pct",
                "direct_distance_km",
            ],
            ascending=[
                False,
                False,
                False,
                False,
            ],
        )
        .reset_index(
            drop=True
        )
    )

    results.to_csv(
        ALL_FILE,
        index=False,
    )

    daily_metrics = pd.DataFrame(
        daily_metric_rows
    )

    daily_metrics = (
        daily_metrics
        .sort_values(
            [
                "initialization_date",
                "horizon_hours",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    daily_metrics.to_csv(
        DAILY_FORECAST_FILE,
        index=False,
    )

    # ========================================================
    # TOP CANDIDATES
    # ========================================================

    valid_candidates = results[
        results[
            "validation_candidate"
        ]
        ==
        True
    ].copy()

    top_parts = []

    for horizon in HORIZONS:

        subset = valid_candidates[
            valid_candidates[
                "horizon_hours"
            ]
            ==
            horizon
        ].copy()

        subset = (
            subset
            .sort_values(
                "validation_score",
                ascending=False,
            )
            .head(10)
        )

        top_parts.append(
            subset
        )

    if top_parts:

        top = pd.concat(
            top_parts,
            ignore_index=True,
        )

    else:

        top = pd.DataFrame()

    top.to_csv(
        TOP_FILE,
        index=False,
    )

    # ========================================================
    # PRINT SUMMARY
    # ========================================================

    print()
    print("=" * 115)
    print("PS146 2025 SCAN SUMMARY")
    print("=" * 115)

    print(
        "Total candidate windows:",
        len(
            results
        ),
    )

    print(
        "Timing-valid windows:",
        int(
            results[
                "timing_pass"
            ].sum()
        ),
    )

    print(
        "Route-quality-valid windows:",
        int(
            results[
                "route_quality_pass"
            ].sum()
        ),
    )

    print(
        "Coverage-valid windows:",
        int(
            results[
                "coverage_pass"
            ].sum()
        ),
    )

    print(
        "Final validation candidates:",
        int(
            results[
                "validation_candidate"
            ].sum()
        ),
    )

    print()
    print("=" * 115)
    print("VALIDATION CANDIDATES BY HORIZON")
    print("=" * 115)

    for horizon in HORIZONS:

        subset = results[
            results[
                "horizon_hours"
            ]
            ==
            horizon
        ]

        valid_subset = subset[
            subset[
                "validation_candidate"
            ]
            ==
            True
        ]

        print()
        print(
            f"{horizon}H"
        )

        print(
            "  All windows:",
            len(
                subset
            ),
        )

        print(
            "  Valid candidates:",
            len(
                valid_subset
            ),
        )

        if not valid_subset.empty:

            print(
                "  Mean actual SIC:",
                f"{valid_subset['actual_mean_sic_pct'].mean():.2f}%"
            )

            print(
                "  Mean route SIC MAE:",
                f"{valid_subset['route_sic_mae_pct'].mean():.2f}%"
            )

            print(
                "  Mean map SIC MAE:",
                f"{valid_subset['map_mae_pct'].mean():.2f}%"
            )

    # ========================================================
    # PRINT TOP WINDOWS
    # ========================================================

    print()
    print("=" * 115)
    print("TOP PS146 2025 VALIDATION WINDOWS")
    print("=" * 115)

    display_columns = [
        "start_time",
        "horizon_hours",
        "ais_points",
        "ais_distance_km",
        "direct_distance_km",
        "geometric_efficiency_pct",
        "actual_mean_sic_pct",
        "actual_max_sic_pct",
        "predicted_mean_sic_pct",
        "route_sic_mae_pct",
        "map_mae_pct",
        "map_correlation",
        "valid_sic_coverage_pct",
        "validation_score",
    ]

    if top.empty:

        print(
            "No windows passed all validation filters."
        )

    else:

        print(
            top[
                display_columns
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
    print("=" * 115)
    print("FILES CREATED")
    print("=" * 115)

    print(
        ALL_FILE
    )

    print(
        TOP_FILE
    )

    print(
        DAILY_FORECAST_FILE
    )

    print()
    print("=" * 115)
    print(
        "PS146 2025 ACTUAL VS PREDICTED "
        "SIC + ROUTE-WINDOW SCAN COMPLETE"
    )
    print("=" * 115)

    history.close()
    actual_ds.close()


if __name__ == "__main__":
    main()