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

from risk_engine import (
    build_risk_grid,
)


# ============================================================
# CONFIGURATION
# ============================================================

HORIZONS = [24, 48, 72]

SEA_ICE_HISTORY_FILE = (
    BASE
    / "data"
    / "processed"
    / "sea_ice_2019_2025.nc"
)

MEMBER2_FILE = (
    BASE
    / "iceberg"
    / "data"
    / "processed"
    / "iceberg_features_environment_ml_ready_2019_2025.csv"
)

CASE_DIR = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps124_validation"
    / "selected_cases"
)

CASE_DEFINITION_FILE = (
    CASE_DIR
    / "ps124_selected_case_definitions.csv"
)

POLARGUARD_DIR = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps124_validation"
    / "polarguard_results"
)

OUTPUT_DIR = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps124_validation"
    / "stage4_route_comparison"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

SAFETY_RADIUS_KM = 10.0
INFLUENCE_RADIUS_KM = 30.0


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
    ) % (2.0 * np.pi) - np.pi

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
# ROUTE DISTANCE
# ============================================================

def route_distance_km(
    df,
):

    if len(df) < 2:
        return 0.0

    lat = df[
        "lat"
    ].to_numpy(
        dtype=float
    )

    lon = df[
        "lon"
    ].to_numpy(
        dtype=float
    )

    distances = haversine_km(
        lat[:-1],
        lon[:-1],
        lat[1:],
        lon[1:],
    )

    return float(
        np.nansum(
            distances
        )
    )


# ============================================================
# ROUTE DEVIATION
# ============================================================

def nearest_route_distances(
    source_df,
    target_df,
):

    target_lat = (
        target_df[
            "lat"
        ]
        .to_numpy(
            dtype=float
        )
    )

    target_lon = (
        target_df[
            "lon"
        ]
        .to_numpy(
            dtype=float
        )
    )

    distances = []

    for _, row in source_df.iterrows():

        d = haversine_km(
            float(
                row["lat"]
            ),
            float(
                row["lon"]
            ),
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
# MEMBER 1
# ============================================================

def load_member1(
    initialization_date,
):

    ds = xr.open_dataarray(
        SEA_ICE_HISTORY_FILE
    )

    target_date = np.datetime64(
        initialization_date,
        "D",
    )

    dates = (
        ds.time.values
        .astype(
            "datetime64[D]"
        )
    )

    matches = np.where(
        dates == target_date
    )[0]

    if len(matches) == 0:

        raise RuntimeError(
            f"Initialization date "
            f"{initialization_date} not found."
        )

    idx = int(
        matches[0]
    )

    if idx < 3:

        raise RuntimeError(
            "Insufficient historical lag maps."
        )

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

    uncertainty = (
        load_uncertainty()
    )

    return (
        forecasts,
        uncertainty,
        x,
        y,
    )


# ============================================================
# GRID LAT/LON
# ============================================================

def grid_to_latlon(
    x,
    y,
):

    x_grid, y_grid = np.meshgrid(
        np.asarray(
            x,
            dtype=float,
        ),
        np.asarray(
            y,
            dtype=float,
        ),
    )

    transformer = (
        Transformer.from_crs(
            "EPSG:3412",
            "EPSG:4326",
            always_xy=True,
        )
    )

    grid_lon, grid_lat = (
        transformer.transform(
            x_grid,
            y_grid,
        )
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

    dlat = (
        grid_lat
        -
        float(lat)
    )

    dlon = (
        (
            grid_lon
            -
            float(lon)
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
                np.radians(
                    float(lat)
                )
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
# HISTORICAL ICEBERGS
# ============================================================

def load_historical_icebergs(
    initialization_date,
    horizon,
):

    df = pd.read_csv(
        MEMBER2_FILE
    )

    dates = pd.to_datetime(
        df[
            "init_date"
        ],
        errors="coerce",
    )

    rows = df[
        dates.dt.strftime(
            "%Y-%m-%d"
        )
        ==
        initialization_date
    ].copy()

    lat_col = (
        f"true_lat_{horizon}h"
    )

    lon_col = (
        f"true_lon_{horizon}h"
    )

    iceberg_positions = []

    for _, row in rows.iterrows():

        lat = row[
            lat_col
        ]

        lon = row[
            lon_col
        ]

        if (
            np.isfinite(lat)
            and
            np.isfinite(lon)
        ):

            iceberg_positions.append(
                {
                    "latitude":
                        float(lat),

                    "longitude":
                        float(lon),

                    "iceberg_id":
                        str(
                            row[
                                "iceberg_id"
                            ]
                        ),
                }
            )

    return iceberg_positions


# ============================================================
# SAMPLE ENVIRONMENT ALONG ROUTE
# ============================================================

def sample_route_environment(
    route_df,
    sic,
    uncertainty_risk,
    iceberg_risk,
    combined_risk,
    grid_lat,
    grid_lon,
):

    rows = []

    for _, point in route_df.iterrows():

        r, c = nearest_cell(
            grid_lat,
            grid_lon,
            point[
                "lat"
            ],
            point[
                "lon"
            ],
        )

        rows.append(
            {
                "lat":
                    float(
                        point["lat"]
                    ),

                "lon":
                    float(
                        point["lon"]
                    ),

                "grid_lat":
                    float(
                        grid_lat[
                            r,
                            c
                        ]
                    ),

                "grid_lon":
                    float(
                        grid_lon[
                            r,
                            c
                        ]
                    ),

                "sic":
                    float(
                        sic[
                            r,
                            c
                        ]
                    ),

                "uncertainty_risk":
                    float(
                        uncertainty_risk[
                            r,
                            c
                        ]
                    ),

                "iceberg_risk":
                    float(
                        iceberg_risk[
                            r,
                            c
                        ]
                    ),

                "combined_risk":
                    float(
                        combined_risk[
                            r,
                            c
                        ]
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


# ============================================================
# SAFE STATISTICS
# ============================================================

def safe_mean(
    values,
):

    values = np.asarray(
        values,
        dtype=float,
    )

    values = values[
        np.isfinite(
            values
        )
    ]

    if len(values) == 0:
        return np.nan

    return float(
        np.mean(
            values
        )
    )


def safe_max(
    values,
):

    values = np.asarray(
        values,
        dtype=float,
    )

    values = values[
        np.isfinite(
            values
        )
    ]

    if len(values) == 0:
        return np.nan

    return float(
        np.max(
            values
        )
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 105)
    print("POLARGUARD")
    print(
        "PS124 - AIS VS POLARGUARD "
        "ROUTE COMPARISON"
    )
    print("=" * 105)

    tests = pd.read_csv(
        CASE_DEFINITION_FILE
    )

    tests[
        "horizon_hours"
    ] = pd.to_numeric(
        tests[
            "horizon_hours"
        ],
        errors="coerce",
    )

    summary_rows = []

    for horizon in HORIZONS:

        print()
        print("=" * 105)
        print(
            f"{horizon}H COMPARISON"
        )
        print("=" * 105)

        test_rows = tests[
            tests[
                "horizon_hours"
            ]
            ==
            horizon
        ]

        if test_rows.empty:

            print(
                "No frozen test definition found."
            )

            continue

        test = (
            test_rows.iloc[0]
        )

        initialization_date = str(
            test[
                "initialization_date"
            ]
        )

        # ----------------------------------------------------
        # FILES
        # ----------------------------------------------------

        ais_file = (
            CASE_DIR
            /
            f"ps124_selected_{horizon}h_actual.csv"
        )

        pg_file = (
            POLARGUARD_DIR
            /
            f"ps124_polarguard_route_{horizon}h.csv"
        )

        if not ais_file.exists():

            raise FileNotFoundError(
                ais_file
            )

        if not pg_file.exists():

            raise FileNotFoundError(
                pg_file
            )

        # ----------------------------------------------------
        # LOAD ROUTES
        # ----------------------------------------------------

        ais = pd.read_csv(
            ais_file
        )

        pg = pd.read_csv(
            pg_file
        )

        ais = ais.rename(
            columns={
                "latitude":
                    "lat",
                "longitude":
                    "lon",
            }
        )

        pg = pg.rename(
            columns={
                "latitude":
                    "lat",
                "longitude":
                    "lon",
            }
        )

        if (
            "lat" not in ais.columns
            or
            "lon" not in ais.columns
        ):

            raise RuntimeError(
                f"AIS {horizon}h file "
                "does not contain lat/lon."
            )

        if (
            "lat" not in pg.columns
            or
            "lon" not in pg.columns
        ):

            raise RuntimeError(
                f"PolarGuard {horizon}h "
                "file does not contain lat/lon."
            )

        # ----------------------------------------------------
        # MEMBER 1 FOR THIS EXACT CASE DATE
        # ----------------------------------------------------

        forecasts, uncertainty, x, y = (
            load_member1(
                initialization_date
            )
        )

        grid_lat, grid_lon = (
            grid_to_latlon(
                x,
                y,
            )
        )

        sic = np.asarray(
            forecasts[
                f"{horizon}h"
            ],
            dtype=float,
        )

        unc = np.asarray(
            uncertainty[
                f"{horizon}h"
            ],
            dtype=float,
        )

        # ----------------------------------------------------
        # HISTORICAL ICEBERGS
        # ----------------------------------------------------

        iceberg_positions = (
            load_historical_icebergs(
                initialization_date,
                horizon,
            )
        )

        # ----------------------------------------------------
        # RISK GRID
        # ----------------------------------------------------

        risk = build_risk_grid(
            sic=sic,
            uncertainty=unc,
            grid_lat=grid_lat,
            grid_lon=grid_lon,
            iceberg_positions=
                iceberg_positions,
            safety_radius_km=
                SAFETY_RADIUS_KM,
            influence_radius_km=
                INFLUENCE_RADIUS_KM,
        )

        # ----------------------------------------------------
        # DISTANCES
        # ----------------------------------------------------

        ais_distance = (
            route_distance_km(
                ais
            )
        )

        pg_distance = (
            route_distance_km(
                pg
            )
        )

        distance_saved = (
            ais_distance
            -
            pg_distance
        )

        distance_saved_pct = (
            (
                distance_saved
                /
                ais_distance
            )
            *
            100.0
            if ais_distance > 0
            else np.nan
        )

        # ----------------------------------------------------
        # GEOMETRIC DEVIATION
        # ----------------------------------------------------

        ais_to_pg = (
            nearest_route_distances(
                ais,
                pg,
            )
        )

        pg_to_ais = (
            nearest_route_distances(
                pg,
                ais,
            )
        )

        mean_deviation = float(
            np.mean(
                ais_to_pg
            )
        )

        median_deviation = float(
            np.median(
                ais_to_pg
            )
        )

        p90_deviation = float(
            np.percentile(
                ais_to_pg,
                90,
            )
        )

        max_deviation = float(
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

        # ----------------------------------------------------
        # SAMPLE ROUTE ENVIRONMENTS
        # ----------------------------------------------------

        ais_env = (
            sample_route_environment(
                ais,
                sic,
                risk[
                    "uncertainty_risk"
                ],
                risk[
                    "iceberg_risk"
                ],
                risk[
                    "combined_risk"
                ],
                grid_lat,
                grid_lon,
            )
        )

        pg_env = (
            sample_route_environment(
                pg,
                sic,
                risk[
                    "uncertainty_risk"
                ],
                risk[
                    "iceberg_risk"
                ],
                risk[
                    "combined_risk"
                ],
                grid_lat,
                grid_lon,
            )
        )

        # ----------------------------------------------------
        # METRICS
        # ----------------------------------------------------

        ais_mean_sic = (
            safe_mean(
                ais_env[
                    "sic"
                ]
            )
            *
            100.0
        )

        pg_mean_sic = (
            safe_mean(
                pg_env[
                    "sic"
                ]
            )
            *
            100.0
        )

        ais_max_sic = (
            safe_max(
                ais_env[
                    "sic"
                ]
            )
            *
            100.0
        )

        pg_max_sic = (
            safe_max(
                pg_env[
                    "sic"
                ]
            )
            *
            100.0
        )

        ais_mean_iceberg = (
            safe_mean(
                ais_env[
                    "iceberg_risk"
                ]
            )
        )

        pg_mean_iceberg = (
            safe_mean(
                pg_env[
                    "iceberg_risk"
                ]
            )
        )

        ais_mean_uncertainty = (
            safe_mean(
                ais_env[
                    "uncertainty_risk"
                ]
            )
        )

        pg_mean_uncertainty = (
            safe_mean(
                pg_env[
                    "uncertainty_risk"
                ]
            )
        )

        ais_mean_combined = (
            safe_mean(
                ais_env[
                    "combined_risk"
                ]
            )
        )

        pg_mean_combined = (
            safe_mean(
                pg_env[
                    "combined_risk"
                ]
            )
        )

        ais_max_combined = (
            safe_max(
                ais_env[
                    "combined_risk"
                ]
            )
        )

        pg_max_combined = (
            safe_max(
                pg_env[
                    "combined_risk"
                ]
            )
        )

        # ----------------------------------------------------
        # PRINT
        # ----------------------------------------------------

        print(
            "Initialization date      :",
            initialization_date,
        )

        print(
            "Historical iceberg count:",
            len(
                iceberg_positions
            ),
        )

        print()

        print(
            f"AIS distance             : "
            f"{ais_distance:.2f} km"
        )

        print(
            f"PolarGuard distance      : "
            f"{pg_distance:.2f} km"
        )

        print(
            f"Distance reduction       : "
            f"{distance_saved_pct:.2f}%"
        )

        print()

        print(
            f"Mean AIS -> PG deviation : "
            f"{mean_deviation:.2f} km"
        )

        print(
            f"Median deviation         : "
            f"{median_deviation:.2f} km"
        )

        print(
            f"P90 deviation            : "
            f"{p90_deviation:.2f} km"
        )

        print(
            f"Maximum deviation        : "
            f"{max_deviation:.2f} km"
        )

        print()

        print(
            f"AIS points within 10 km  : "
            f"{within_10:.2f}%"
        )

        print(
            f"AIS points within 25 km  : "
            f"{within_25:.2f}%"
        )

        print(
            f"AIS points within 50 km  : "
            f"{within_50:.2f}%"
        )

        print()

        print(
            f"AIS mean SIC             : "
            f"{ais_mean_sic:.2f}%"
        )

        print(
            f"PolarGuard mean SIC      : "
            f"{pg_mean_sic:.2f}%"
        )

        print(
            f"AIS max SIC              : "
            f"{ais_max_sic:.2f}%"
        )

        print(
            f"PolarGuard max SIC       : "
            f"{pg_max_sic:.2f}%"
        )

        print()

        print(
            f"AIS mean uncertainty     : "
            f"{ais_mean_uncertainty:.4f}"
        )

        print(
            f"PG mean uncertainty      : "
            f"{pg_mean_uncertainty:.4f}"
        )

        print()

        print(
            f"AIS mean iceberg risk    : "
            f"{ais_mean_iceberg:.4f}"
        )

        print(
            f"PG mean iceberg risk     : "
            f"{pg_mean_iceberg:.4f}"
        )

        print()

        print(
            f"AIS mean combined risk   : "
            f"{ais_mean_combined:.4f}"
        )

        print(
            f"PG mean combined risk    : "
            f"{pg_mean_combined:.4f}"
        )

        print(
            f"AIS max combined risk    : "
            f"{ais_max_combined:.4f}"
        )

        print(
            f"PG max combined risk     : "
            f"{pg_max_combined:.4f}"
        )

        # ----------------------------------------------------
        # SAVE ROUTE ENVIRONMENT FILES
        # ----------------------------------------------------

        ais_environment_file = (
            OUTPUT_DIR
            /
            f"ps124_ais_{horizon}h_environment.csv"
        )

        pg_environment_file = (
            OUTPUT_DIR
            /
            f"ps124_polarguard_{horizon}h_environment.csv"
        )

        ais_env.to_csv(
            ais_environment_file,
            index=False,
        )

        pg_env.to_csv(
            pg_environment_file,
            index=False,
        )

        # ----------------------------------------------------
        # SUMMARY
        # ----------------------------------------------------

        summary_rows.append(
            {
                "horizon_hours":
                    horizon,

                "initialization_date":
                    initialization_date,

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

                "polarguard_distance_km":
                    pg_distance,

                "distance_saved_km":
                    distance_saved,

                "distance_saved_pct":
                    distance_saved_pct,

                "mean_ais_to_pg_km":
                    mean_deviation,

                "median_ais_to_pg_km":
                    median_deviation,

                "p90_ais_to_pg_km":
                    p90_deviation,

                "max_ais_to_pg_km":
                    max_deviation,

                "within_10km_pct":
                    within_10,

                "within_25km_pct":
                    within_25,

                "within_50km_pct":
                    within_50,

                "symmetric_mean_deviation_km":
                    symmetric_mean,

                "ais_mean_sic_pct":
                    ais_mean_sic,

                "pg_mean_sic_pct":
                    pg_mean_sic,

                "ais_max_sic_pct":
                    ais_max_sic,

                "pg_max_sic_pct":
                    pg_max_sic,

                "ais_mean_iceberg_risk":
                    ais_mean_iceberg,

                "pg_mean_iceberg_risk":
                    pg_mean_iceberg,

                "ais_mean_uncertainty_risk":
                    ais_mean_uncertainty,

                "pg_mean_uncertainty_risk":
                    pg_mean_uncertainty,

                "ais_mean_combined_risk":
                    ais_mean_combined,

                "pg_mean_combined_risk":
                    pg_mean_combined,

                "ais_max_combined_risk":
                    ais_max_combined,

                "pg_max_combined_risk":
                    pg_max_combined,

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
    # FINAL SUMMARY
    # ========================================================

    summary = pd.DataFrame(
        summary_rows
    )

    summary = summary.sort_values(
        "horizon_hours"
    )

    summary_file = (
        OUTPUT_DIR
        /
        "ps124_route_comparison_summary.csv"
    )

    summary.to_csv(
        summary_file,
        index=False,
    )

    print()
    print("=" * 105)
    print("FINAL PS124 ROUTE COMPARISON SUMMARY")
    print("=" * 105)

    print()

    print(
        summary
        .round(3)
        .to_string(
            index=False
        )
    )

    print()
    print("=" * 105)
    print("FILES CREATED")
    print("=" * 105)

    print(
        summary_file
    )

    for horizon in HORIZONS:

        print(
            OUTPUT_DIR
            /
            f"ps124_ais_{horizon}h_environment.csv"
        )

        print(
            OUTPUT_DIR
            /
            f"ps124_polarguard_{horizon}h_environment.csv"
        )

    print()
    print("=" * 105)
    print(
        "PS124 ROUTE COMPARISON COMPLETE"
    )
    print("=" * 105)


if __name__ == "__main__":
    main()