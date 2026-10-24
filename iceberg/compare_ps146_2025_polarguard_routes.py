from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent.parent

if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

import numpy as np
import pandas as pd
import xarray as xr

from pyproj import Transformer

from sea_ice_service import (
    predict_sea_ice,
    load_uncertainty,
)


# ============================================================
# PATHS
# ============================================================

VALIDATION_ROOT = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps146_2025_validation"
)

FROZEN_CASES_FILE = (
    VALIDATION_ROOT
    / "selected_cases"
    / "ps146_2025_frozen_case_definitions.csv"
)

ROUTING_SUMMARY_FILE = (
    VALIDATION_ROOT
    / "polarguard_results"
    / "ps146_2025_ais_vs_polarguard_summary.csv"
)

SEA_ICE_HISTORY_FILE = (
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

MEMBER2_FILE = (
    BASE
    / "iceberg"
    / "data"
    / "processed"
    / "iceberg_features_environment_ml_ready_2019_2025.csv"
)

OUTPUT_DIR = (
    VALIDATION_ROOT
    / "stage4_route_comparison"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

SUMMARY_FILE = (
    OUTPUT_DIR
    / "ps146_2025_route_comparison_summary.csv"
)

SUCCESS_FILE = (
    OUTPUT_DIR
    / "ps146_2025_successful_route_comparisons.csv"
)


# ============================================================
# SETTINGS
# ============================================================

ICE_THRESHOLD = 0.15


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
# ROUTE DISTANCE
# ============================================================

def route_distance_km(
    lat,
    lon,
):

    lat = np.asarray(
        lat,
        dtype=float,
    )

    lon = np.asarray(
        lon,
        dtype=float,
    )

    if len(lat) < 2:
        return 0.0

    d = haversine_km(
        lat[:-1],
        lon[:-1],
        lat[1:],
        lon[1:],
    )

    return float(
        np.nansum(
            d
        )
    )


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
# MEMBER 1 FORECAST
# ============================================================

def load_forecast_bundle(
    history,
    initialization_date,
):

    target_date = np.datetime64(
        initialization_date,
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

        raise RuntimeError(
            f"No historical SIC for "
            f"{initialization_date}"
        )

    idx = int(
        matches[0]
    )

    if idx < 3:

        raise RuntimeError(
            "Not enough lag maps."
        )

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

    uncertainty = load_uncertainty()

    return {
        "x":
            x,

        "y":
            y,

        "forecast_24h":
            np.asarray(
                forecasts["24h"]
            ),

        "forecast_48h":
            np.asarray(
                forecasts["48h"]
            ),

        "forecast_72h":
            np.asarray(
                forecasts["72h"]
            ),

        "uncertainty_24h":
            np.asarray(
                uncertainty["24h"]
            ),

        "uncertainty_48h":
            np.asarray(
                uncertainty["48h"]
            ),

        "uncertainty_72h":
            np.asarray(
                uncertainty["72h"]
            ),
    }


# ============================================================
# ACTUAL SIC
# ============================================================

def load_actual_sic(
    actual_da,
    target_date,
):

    target_date = np.datetime64(
        target_date,
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

    return np.asarray(
        actual_da.isel(
            time=int(
                matches[0]
            )
        ).values,
        dtype=np.float32,
    )


# ============================================================
# SAMPLE GRID ALONG ROUTE
# ============================================================

def sample_grid_along_route(
    latitudes,
    longitudes,
    grid_values,
    grid_lat,
    grid_lon,
):

    values = []

    for lat, lon in zip(
        latitudes,
        longitudes,
    ):

        row, col = nearest_cell(
            grid_lat,
            grid_lon,
            lat,
            lon,
        )

        value = float(
            grid_values[
                row,
                col
            ]
        )

        if np.isfinite(
            value
        ):
            values.append(
                value
            )

    return np.asarray(
        values,
        dtype=float,
    )


# ============================================================
# ROUTE-TO-ROUTE DEVIATION
# ============================================================

def nearest_route_distances(
    source_lat,
    source_lon,
    target_lat,
    target_lon,
):
    """
    For every source point, calculate distance
    to nearest target-route point.
    """

    source_lat = np.asarray(
        source_lat,
        dtype=float,
    )

    source_lon = np.asarray(
        source_lon,
        dtype=float,
    )

    target_lat = np.asarray(
        target_lat,
        dtype=float,
    )

    target_lon = np.asarray(
        target_lon,
        dtype=float,
    )

    distances = []

    for lat, lon in zip(
        source_lat,
        source_lon,
    ):

        d = haversine_km(
            lat,
            lon,
            target_lat,
            target_lon,
        )

        distances.append(
            float(
                np.nanmin(
                    d
                )
            )
        )

    return np.asarray(
        distances,
        dtype=float,
    )


# ============================================================
# MEMBER 2 ICEBERGS
# ============================================================

def load_iceberg_positions(
    member2,
    initialization_date,
    horizon,
):

    dates = pd.to_datetime(
        member2[
            "init_date"
        ],
        errors="coerce",
    )

    subset = member2[
        dates.dt.strftime(
            "%Y-%m-%d"
        )
        ==
        initialization_date
    ].copy()

    if subset.empty:
        return []

    lat_column = (
        f"true_lat_{horizon}h"
    )

    lon_column = (
        f"true_lon_{horizon}h"
    )

    if (
        lat_column not in subset.columns
        or
        lon_column not in subset.columns
    ):
        return []

    positions = []

    for _, row in subset.iterrows():

        lat = row[
            lat_column
        ]

        lon = row[
            lon_column
        ]

        if (
            np.isfinite(lat)
            and
            np.isfinite(lon)
        ):

            positions.append(
                (
                    float(lat),
                    float(lon),
                )
            )

    return positions


# ============================================================
# ICEBERG PROXIMITY
# ============================================================

def iceberg_proximity(
    route_lat,
    route_lon,
    iceberg_positions,
):

    if not iceberg_positions:

        return {
            "min_km":
                np.nan,

            "mean_km":
                np.nan,

            "within_10_pct":
                np.nan,

            "within_30_pct":
                np.nan,

            "within_50_pct":
                np.nan,

            "within_100_pct":
                np.nan,
        }

    iceberg_lat = np.asarray(
        [
            p[0]
            for p in iceberg_positions
        ],
        dtype=float,
    )

    iceberg_lon = np.asarray(
        [
            p[1]
            for p in iceberg_positions
        ],
        dtype=float,
    )

    minimum_distances = []

    for lat, lon in zip(
        route_lat,
        route_lon,
    ):

        d = haversine_km(
            lat,
            lon,
            iceberg_lat,
            iceberg_lon,
        )

        minimum_distances.append(
            float(
                np.nanmin(
                    d
                )
            )
        )

    minimum_distances = np.asarray(
        minimum_distances,
        dtype=float,
    )

    return {
        "min_km":
            float(
                np.min(
                    minimum_distances
                )
            ),

        "mean_km":
            float(
                np.mean(
                    minimum_distances
                )
            ),

        "within_10_pct":
            float(
                np.mean(
                    minimum_distances
                    <=
                    10.0
                )
                *
                100.0
            ),

        "within_30_pct":
            float(
                np.mean(
                    minimum_distances
                    <=
                    30.0
                )
                *
                100.0
            ),

        "within_50_pct":
            float(
                np.mean(
                    minimum_distances
                    <=
                    50.0
                )
                *
                100.0
            ),

        "within_100_pct":
            float(
                np.mean(
                    minimum_distances
                    <=
                    100.0
                )
                *
                100.0
            ),
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 115)
    print("POLARGUARD")
    print(
        "PS146 2025 - ACTUAL AIS VS "
        "POLARGUARD ROUTE COMPARISON"
    )
    print("=" * 115)

    frozen = pd.read_csv(
        FROZEN_CASES_FILE
    )

    routing = pd.read_csv(
        ROUTING_SUMMARY_FILE
    )

    history = xr.open_dataarray(
        SEA_ICE_HISTORY_FILE
    )

    actual_ds = xr.open_dataset(
        ACTUAL_2025_FILE
    )

    actual_da = actual_ds[
        "sea_ice_concentration"
    ]

    member2 = pd.read_csv(
        MEMBER2_FILE
    )

    comparison_rows = []

    forecast_cache = {}

    # ========================================================
    # EVERY FROZEN CASE
    # ========================================================

    for _, case in frozen.iterrows():

        case_id = str(
            case[
                "case_id"
            ]
        )

        horizon = int(
            case[
                "horizon_hours"
            ]
        )

        initialization_date = str(
            case[
                "initialization_date"
            ]
        )

        routing_match = routing[
            routing[
                "case_id"
            ]
            ==
            case_id
        ]

        print()
        print("=" * 115)
        print(case_id)
        print("=" * 115)

        if routing_match.empty:

            print(
                "No routing result found."
            )

            comparison_rows.append(
                {
                    "case_id":
                        case_id,

                    "horizon_hours":
                        horizon,

                    "initialization_date":
                        initialization_date,

                    "routing_success":
                        False,

                    "reason":
                        "Missing routing result",
                }
            )

            continue

        routing_row = (
            routing_match.iloc[0]
        )

        success = bool(
            routing_row[
                "success"
            ]
        )

        # ----------------------------------------------------
        # KEEP FAILED CASES
        # ----------------------------------------------------

        if not success:

            reason = str(
                routing_row.get(
                    "reason",
                    "Routing failed",
                )
            )

            print(
                "Routing status: REJECTED"
            )

            print(
                "Reason:",
                reason,
            )

            comparison_rows.append(
                {
                    "case_id":
                        case_id,

                    "horizon_hours":
                        horizon,

                    "initialization_date":
                        initialization_date,

                    "routing_success":
                        False,

                    "reason":
                        reason,

                    "ais_distance_km":
                        float(
                            case[
                                "ais_distance_km"
                            ]
                        ),

                    "actual_mean_sic_pct":
                        float(
                            case[
                                "actual_mean_sic_pct"
                            ]
                        ),

                    "predicted_mean_sic_pct":
                        float(
                            case[
                                "predicted_mean_sic_pct"
                            ]
                        ),
                }
            )

            continue

        # ====================================================
        # LOAD ACTUAL AIS
        # ====================================================

        ais_file = Path(
            case[
                "route_file"
            ]
        )

        ais = pd.read_csv(
            ais_file
        )

        ais_lat = (
            ais[
                "lat"
            ]
            .to_numpy(
                dtype=float
            )
        )

        ais_lon = (
            ais[
                "lon"
            ]
            .to_numpy(
                dtype=float
            )
        )

        # ====================================================
        # LOAD POLARGUARD ROUTE
        # ====================================================

        pg_file = (
            VALIDATION_ROOT
            / "polarguard_results"
            / f"{case_id}_polarguard_route.csv"
        )

        if not pg_file.exists():

            print(
                "Missing PolarGuard route file."
            )

            comparison_rows.append(
                {
                    "case_id":
                        case_id,

                    "horizon_hours":
                        horizon,

                    "initialization_date":
                        initialization_date,

                    "routing_success":
                        False,

                    "reason":
                        "Missing PolarGuard route CSV",
                }
            )

            continue

        pg = pd.read_csv(
            pg_file
        )

        pg_lat = (
            pg[
                "latitude"
            ]
            .to_numpy(
                dtype=float
            )
        )

        pg_lon = (
            pg[
                "longitude"
            ]
            .to_numpy(
                dtype=float
            )
        )

        # ====================================================
        # GEOMETRIC DISTANCES
        # ====================================================

        ais_distance = (
            route_distance_km(
                ais_lat,
                ais_lon,
            )
        )

        # Grid-cell-center route distance returned by PolarGuard.
        pg_grid_distance = (
            route_distance_km(
                pg_lat,
                pg_lon,
            )
        )

        # PolarGuard stores its route as routing-grid cell centres.
        # For a fair distance comparison against AIS, include the
        # connector from the exact vessel start to the first routed
        # grid cell and the connector from the final routed grid cell
        # to the exact AIS destination.
        exact_start_lat = float(
            case["start_latitude"]
        )

        exact_start_lon = float(
            case["start_longitude"]
        )

        exact_destination_lat = float(
            case["destination_latitude"]
        )

        exact_destination_lon = float(
            case["destination_longitude"]
        )

        start_snap_km = float(
            haversine_km(
                exact_start_lat,
                exact_start_lon,
                float(pg_lat[0]),
                float(pg_lon[0]),
            )
        )

        destination_snap_km = float(
            haversine_km(
                float(pg_lat[-1]),
                float(pg_lon[-1]),
                exact_destination_lat,
                exact_destination_lon,
            )
        )

        # Corrected complete PolarGuard route distance.
        pg_distance = (
            start_snap_km
            +
            pg_grid_distance
            +
            destination_snap_km
        )

        distance_saved_km = (
            ais_distance
            -
            pg_distance
        )

        distance_saved_pct = (
            distance_saved_km
            /
            ais_distance
            *
            100.0
            if ais_distance > 0
            else np.nan
        )

        # ====================================================
        # ROUTE DEVIATION
        # ====================================================

        ais_to_pg = (
            nearest_route_distances(
                ais_lat,
                ais_lon,
                pg_lat,
                pg_lon,
            )
        )

        pg_to_ais = (
            nearest_route_distances(
                pg_lat,
                pg_lon,
                ais_lat,
                ais_lon,
            )
        )

        mean_ais_to_pg = float(
            np.mean(
                ais_to_pg
            )
        )

        median_ais_to_pg = float(
            np.median(
                ais_to_pg
            )
        )

        p90_ais_to_pg = float(
            np.percentile(
                ais_to_pg,
                90
            )
        )

        max_ais_to_pg = float(
            np.max(
                ais_to_pg
            )
        )

        within_10 = float(
            np.mean(
                ais_to_pg
                <=
                10.0
            )
            *
            100.0
        )

        within_25 = float(
            np.mean(
                ais_to_pg
                <=
                25.0
            )
            *
            100.0
        )

        within_50 = float(
            np.mean(
                ais_to_pg
                <=
                50.0
            )
            *
            100.0
        )

        symmetric_mean = float(
            (
                np.mean(
                    ais_to_pg
                )
                +
                np.mean(
                    pg_to_ais
                )
            )
            /
            2.0
        )

        # ====================================================
        # LOAD MEMBER 1 FORECAST
        # ====================================================

        if initialization_date not in forecast_cache:

            forecast_cache[
                initialization_date
            ] = load_forecast_bundle(
                history,
                initialization_date,
            )

        bundle = forecast_cache[
            initialization_date
        ]

        grid_lat, grid_lon = (
            projected_grid_to_latlon(
                bundle[
                    "x"
                ],
                bundle[
                    "y"
                ],
            )
        )

        predicted_sic = bundle[
            f"forecast_{horizon}h"
        ]

        uncertainty = bundle[
            f"uncertainty_{horizon}h"
        ]

        # ====================================================
        # ACTUAL TARGET SIC
        # ====================================================

        target_date = str(
            case[
                "target_date"
            ]
        )

        actual_sic = load_actual_sic(
            actual_da,
            target_date,
        )

        # ====================================================
        # SIC EXPOSURE
        # ====================================================

        ais_actual_sic = (
            sample_grid_along_route(
                ais_lat,
                ais_lon,
                actual_sic,
                grid_lat,
                grid_lon,
            )
        )

        ais_predicted_sic = (
            sample_grid_along_route(
                ais_lat,
                ais_lon,
                predicted_sic,
                grid_lat,
                grid_lon,
            )
        )

        pg_predicted_sic = (
            sample_grid_along_route(
                pg_lat,
                pg_lon,
                predicted_sic,
                grid_lat,
                grid_lon,
            )
        )

        pg_actual_sic = (
            sample_grid_along_route(
                pg_lat,
                pg_lon,
                actual_sic,
                grid_lat,
                grid_lon,
            )
        )

        # ====================================================
        # UNCERTAINTY
        # ====================================================

        ais_uncertainty = (
            sample_grid_along_route(
                ais_lat,
                ais_lon,
                uncertainty,
                grid_lat,
                grid_lon,
            )
        )

        pg_uncertainty = (
            sample_grid_along_route(
                pg_lat,
                pg_lon,
                uncertainty,
                grid_lat,
                grid_lon,
            )
        )

        # ====================================================
        # ICEBERG PROXIMITY
        # ====================================================

        iceberg_positions = (
            load_iceberg_positions(
                member2,
                initialization_date,
                horizon,
            )
        )

        ais_icebergs = (
            iceberg_proximity(
                ais_lat,
                ais_lon,
                iceberg_positions,
            )
        )

        pg_icebergs = (
            iceberg_proximity(
                pg_lat,
                pg_lon,
                iceberg_positions,
            )
        )

        # ====================================================
        # PRINT CASE
        # ====================================================

        print(
            "Routing status          : SUCCESS"
        )

        print(
            f"AIS distance            : "
            f"{ais_distance:.2f} km"
        )

        print(
            f"PG grid-route distance  : "
            f"{pg_grid_distance:.2f} km"
        )

        print(
            f"Start grid snap         : "
            f"{start_snap_km:.2f} km"
        )

        print(
            f"Destination grid snap   : "
            f"{destination_snap_km:.2f} km"
        )

        print(
            f"Corrected PG distance   : "
            f"{pg_distance:.2f} km"
        )

        print(
            f"Modeled reduction       : "
            f"{distance_saved_pct:.2f}%"
        )

        print()

        print(
            f"Mean AIS -> PG deviation: "
            f"{mean_ais_to_pg:.2f} km"
        )

        print(
            f"Median deviation        : "
            f"{median_ais_to_pg:.2f} km"
        )

        print(
            f"P90 deviation           : "
            f"{p90_ais_to_pg:.2f} km"
        )

        print(
            f"Maximum deviation       : "
            f"{max_ais_to_pg:.2f} km"
        )

        print()

        print(
            f"AIS within 10 km        : "
            f"{within_10:.2f}%"
        )

        print(
            f"AIS within 25 km        : "
            f"{within_25:.2f}%"
        )

        print(
            f"AIS within 50 km        : "
            f"{within_50:.2f}%"
        )

        print()

        if len(
            ais_actual_sic
        ) > 0:

            print(
                f"AIS actual mean SIC     : "
                f"{np.mean(ais_actual_sic) * 100.0:.2f}%"
            )

        if len(
            pg_actual_sic
        ) > 0:

            print(
                f"PG actual mean SIC      : "
                f"{np.mean(pg_actual_sic) * 100.0:.2f}%"
            )

        if len(
            pg_predicted_sic
        ) > 0:

            print(
                f"PG predicted mean SIC   : "
                f"{np.mean(pg_predicted_sic) * 100.0:.2f}%"
            )

        print()

        print(
            f"AIS minimum iceberg dist: "
            f"{ais_icebergs['min_km']:.2f} km"
        )

        print(
            f"PG minimum iceberg dist : "
            f"{pg_icebergs['min_km']:.2f} km"
        )

        # ====================================================
        # SAVE ENVIRONMENT SAMPLES
        # ====================================================

        ais_environment_file = (
            OUTPUT_DIR
            /
            f"{case_id}_ais_environment.csv"
        )

        pg_environment_file = (
            OUTPUT_DIR
            /
            f"{case_id}_polarguard_environment.csv"
        )

        ais_env = pd.DataFrame(
            {
                "latitude":
                    ais_lat,

                "longitude":
                    ais_lon,
            }
        )

        # Sample individually so array length always matches
        ais_actual_values = []

        ais_pred_values = []

        ais_unc_values = []

        for lat, lon in zip(
            ais_lat,
            ais_lon,
        ):

            row, col = nearest_cell(
                grid_lat,
                grid_lon,
                lat,
                lon,
            )

            ais_actual_values.append(
                actual_sic[
                    row,
                    col
                ]
            )

            ais_pred_values.append(
                predicted_sic[
                    row,
                    col
                ]
            )

            ais_unc_values.append(
                uncertainty[
                    row,
                    col
                ]
            )

        ais_env[
            "actual_sic"
        ] = ais_actual_values

        ais_env[
            "predicted_sic"
        ] = ais_pred_values

        ais_env[
            "uncertainty"
        ] = ais_unc_values

        ais_env.to_csv(
            ais_environment_file,
            index=False,
        )

        pg_env = pd.DataFrame(
            {
                "latitude":
                    pg_lat,

                "longitude":
                    pg_lon,
            }
        )

        pg_actual_values = []

        pg_pred_values = []

        pg_unc_values = []

        for lat, lon in zip(
            pg_lat,
            pg_lon,
        ):

            row, col = nearest_cell(
                grid_lat,
                grid_lon,
                lat,
                lon,
            )

            pg_actual_values.append(
                actual_sic[
                    row,
                    col
                ]
            )

            pg_pred_values.append(
                predicted_sic[
                    row,
                    col
                ]
            )

            pg_unc_values.append(
                uncertainty[
                    row,
                    col
                ]
            )

        pg_env[
            "actual_sic"
        ] = pg_actual_values

        pg_env[
            "predicted_sic"
        ] = pg_pred_values

        pg_env[
            "uncertainty"
        ] = pg_unc_values

        pg_env.to_csv(
            pg_environment_file,
            index=False,
        )

        # ====================================================
        # SUMMARY ROW
        # ====================================================

        comparison_rows.append(
            {
                "case_id":
                    case_id,

                "horizon_hours":
                    horizon,

                "initialization_date":
                    initialization_date,

                "target_date":
                    target_date,

                "routing_success":
                    True,

                "reason":
                    None,

                "ais_points":
                    len(
                        ais
                    ),

                "polarguard_points":
                    len(
                        pg
                    ),

                "iceberg_hazards":
                    len(
                        iceberg_positions
                    ),

                "ais_distance_km":
                    ais_distance,

                "pg_grid_distance_km":
                    pg_grid_distance,

                "start_snap_km":
                    start_snap_km,

                "destination_snap_km":
                    destination_snap_km,

                "polarguard_distance_km":
                    pg_distance,

                "distance_saved_km":
                    distance_saved_km,

                "distance_saved_pct":
                    distance_saved_pct,

                "mean_ais_to_pg_km":
                    mean_ais_to_pg,

                "median_ais_to_pg_km":
                    median_ais_to_pg,

                "p90_ais_to_pg_km":
                    p90_ais_to_pg,

                "max_ais_to_pg_km":
                    max_ais_to_pg,

                "within_10km_pct":
                    within_10,

                "within_25km_pct":
                    within_25,

                "within_50km_pct":
                    within_50,

                "symmetric_mean_deviation_km":
                    symmetric_mean,

                "ais_actual_mean_sic_pct":
                    (
                        np.mean(
                            ais_actual_sic
                        )
                        *
                        100.0
                        if len(
                            ais_actual_sic
                        ) > 0
                        else np.nan
                    ),

                "ais_predicted_mean_sic_pct":
                    (
                        np.mean(
                            ais_predicted_sic
                        )
                        *
                        100.0
                        if len(
                            ais_predicted_sic
                        ) > 0
                        else np.nan
                    ),

                "pg_actual_mean_sic_pct":
                    (
                        np.mean(
                            pg_actual_sic
                        )
                        *
                        100.0
                        if len(
                            pg_actual_sic
                        ) > 0
                        else np.nan
                    ),

                "pg_predicted_mean_sic_pct":
                    (
                        np.mean(
                            pg_predicted_sic
                        )
                        *
                        100.0
                        if len(
                            pg_predicted_sic
                        ) > 0
                        else np.nan
                    ),

                "ais_mean_uncertainty":
                    (
                        np.mean(
                            ais_uncertainty
                        )
                        if len(
                            ais_uncertainty
                        ) > 0
                        else np.nan
                    ),

                "pg_mean_uncertainty":
                    (
                        np.mean(
                            pg_uncertainty
                        )
                        if len(
                            pg_uncertainty
                        ) > 0
                        else np.nan
                    ),

                "ais_min_iceberg_distance_km":
                    ais_icebergs[
                        "min_km"
                    ],

                "pg_min_iceberg_distance_km":
                    pg_icebergs[
                        "min_km"
                    ],

                "ais_mean_iceberg_distance_km":
                    ais_icebergs[
                        "mean_km"
                    ],

                "pg_mean_iceberg_distance_km":
                    pg_icebergs[
                        "mean_km"
                    ],

                "ais_within_30km_iceberg_pct":
                    ais_icebergs[
                        "within_30_pct"
                    ],

                "pg_within_30km_iceberg_pct":
                    pg_icebergs[
                        "within_30_pct"
                    ],

                "ais_within_50km_iceberg_pct":
                    ais_icebergs[
                        "within_50_pct"
                    ],

                "pg_within_50km_iceberg_pct":
                    pg_icebergs[
                        "within_50_pct"
                    ],

                "ais_environment_file":
                    str(
                        ais_environment_file
                    ),

                "pg_environment_file":
                    str(
                        pg_environment_file
                    ),
            }
        )

    # ========================================================
    # SAVE
    # ========================================================

    summary = pd.DataFrame(
        comparison_rows
    )

    summary.to_csv(
        SUMMARY_FILE,
        index=False,
    )

    successful = summary[
        summary[
            "routing_success"
        ]
        ==
        True
    ].copy()

    successful.to_csv(
        SUCCESS_FILE,
        index=False,
    )

    # ========================================================
    # FINAL CASE TABLE
    # ========================================================

    print()
    print("=" * 115)
    print("FINAL PS146 2025 ROUTE COMPARISON SUMMARY")
    print("=" * 115)

    if successful.empty:

        print(
            "No successful routes available."
        )

    else:

        display_columns = [
            "case_id",
            "horizon_hours",
            "ais_distance_km",
            "pg_grid_distance_km",
            "start_snap_km",
            "destination_snap_km",
            "polarguard_distance_km",
            "distance_saved_pct",
            "mean_ais_to_pg_km",
            "within_25km_pct",
            "ais_actual_mean_sic_pct",
            "pg_actual_mean_sic_pct",
            "ais_min_iceberg_distance_km",
            "pg_min_iceberg_distance_km",
        ]

        print()

        print(
            successful[
                display_columns
            ]
            .round(
                3
            )
            .to_string(
                index=False
            )
        )

    # ========================================================
    # AGGREGATE
    # ========================================================

    print()
    print("=" * 115)
    print("2025 ROUTE VALIDATION AGGREGATE RESULTS")
    print("=" * 115)

    print(
        "Total frozen cases:",
        len(
            summary
        ),
    )

    print(
        "Successful routes:",
        len(
            successful
        ),
    )

    print(
        "Safety-rejected / failed:",
        len(
            summary
        )
        -
        len(
            successful
        ),
    )

    if not successful.empty:

        print()

        print(
            f"Mean modeled distance reduction : "
            f"{successful['distance_saved_pct'].mean():.2f}%"
        )

        print(
            f"Median modeled distance reduction: "
            f"{successful['distance_saved_pct'].median():.2f}%"
        )

        print(
            f"Mean AIS -> PG deviation        : "
            f"{successful['mean_ais_to_pg_km'].mean():.2f} km"
        )

        print(
            f"Median AIS -> PG deviation      : "
            f"{successful['median_ais_to_pg_km'].mean():.2f} km"
        )

        print(
            f"Mean AIS actual SIC             : "
            f"{successful['ais_actual_mean_sic_pct'].mean():.2f}%"
        )

        print(
            f"Mean PG actual SIC              : "
            f"{successful['pg_actual_mean_sic_pct'].mean():.2f}%"
        )

        print(
            f"Mean PG predicted SIC           : "
            f"{successful['pg_predicted_mean_sic_pct'].mean():.2f}%"
        )

        print(
            f"Mean AIS uncertainty            : "
            f"{successful['ais_mean_uncertainty'].mean():.4f}"
        )

        print(
            f"Mean PG uncertainty             : "
            f"{successful['pg_mean_uncertainty'].mean():.4f}"
        )

        print()

        print(
            "BY HORIZON"
        )

        for horizon in [
            24,
            48,
            72,
        ]:

            subset = successful[
                successful[
                    "horizon_hours"
                ]
                ==
                horizon
            ]

            if subset.empty:
                continue

            print(
                f"{horizon}H: "
                f"{len(subset)} routes | "
                f"distance reduction="
                f"{subset['distance_saved_pct'].mean():.2f}% | "
                f"mean deviation="
                f"{subset['mean_ais_to_pg_km'].mean():.2f} km"
            )

    # ========================================================
    # OUTPUT
    # ========================================================

    print()
    print("=" * 115)
    print("FILES CREATED")
    print("=" * 115)

    print(
        SUMMARY_FILE
    )

    print(
        SUCCESS_FILE
    )

    print()
    print("=" * 115)
    print(
        "PS146 2025 ROUTE COMPARISON COMPLETE"
    )
    print("=" * 115)

    history.close()
    actual_ds.close()


if __name__ == "__main__":
    main()