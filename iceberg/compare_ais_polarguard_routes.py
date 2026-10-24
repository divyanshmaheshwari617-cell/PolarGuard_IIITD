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

from risk_engine import build_risk_grid


# ============================================================
# CONFIGURATION
# ============================================================

INITIALIZATION_DATE = np.datetime64(
    "2024-11-29",
    "D",
)

HORIZONS = [48, 72]

SEA_ICE_HISTORY_FILE = (
    BASE
    / "data"
    / "processed"
    / "sea_ice_2019_2025.nc"
)

AIS_DIR = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
)

POLARGUARD_DIR = (
    AIS_DIR
    / "polarguard_results"
)

ICEBERG_FILE = (
    AIS_DIR
    / "historical_iceberg_positions_2024-11-29.csv"
)

OUTPUT_DIR = (
    AIS_DIR
    / "stage4_route_comparison"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
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

    return (
        2.0
        *
        R
        *
        np.arcsin(
            np.sqrt(
                np.clip(
                    a,
                    0.0,
                    1.0,
                )
            )
        )
    )


# ============================================================
# ROUTE DISTANCE
# ============================================================

def route_distance_km(df):

    if len(df) < 2:
        return 0.0

    lat = df["lat"].to_numpy(
        dtype=float
    )

    lon = df["lon"].to_numpy(
        dtype=float
    )

    distances = haversine_km(
        lat[:-1],
        lon[:-1],
        lat[1:],
        lon[1:],
    )

    return float(
        np.nansum(distances)
    )


# ============================================================
# AIS -> POLARGUARD DEVIATION
# ============================================================

def nearest_route_distances(
    source_df,
    target_df,
):

    target_lat = (
        target_df["lat"]
        .to_numpy(dtype=float)
    )

    target_lon = (
        target_df["lon"]
        .to_numpy(dtype=float)
    )

    distances = []

    for _, row in source_df.iterrows():

        d = haversine_km(
            float(row["lat"]),
            float(row["lon"]),
            target_lat,
            target_lon,
        )

        distances.append(
            float(
                np.nanmin(d)
            )
        )

    return np.asarray(
        distances,
        dtype=float,
    )


# ============================================================
# MEMBER 1
# ============================================================

def load_member1():

    ds = xr.open_dataarray(
        SEA_ICE_HISTORY_FILE
    )

    dates = (
        ds.time.values
        .astype("datetime64[D]")
    )

    matches = np.where(
        dates == INITIALIZATION_DATE
    )[0]

    if len(matches) == 0:
        raise RuntimeError(
            "Initialization date not found."
        )

    idx = int(matches[0])

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
        date=INITIALIZATION_DATE,
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
        np.asarray(x, dtype=float),
        np.asarray(y, dtype=float),
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
        - float(lat)
    )

    dlon = (
        (
            grid_lon
            - float(lon)
            + 180.0
        )
        %
        360.0
    ) - 180.0

    # Approximate local geographic distance.
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
# SAMPLE GRID ALONG ROUTE
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
            point["lat"],
            point["lon"],
        )

        rows.append(
            {
                "lat":
                    float(point["lat"]),

                "lon":
                    float(point["lon"]),

                "grid_lat":
                    float(
                        grid_lat[r, c]
                    ),

                "grid_lon":
                    float(
                        grid_lon[r, c]
                    ),

                "sic":
                    float(
                        sic[r, c]
                    ),

                "uncertainty_risk":
                    float(
                        uncertainty_risk[
                            r, c
                        ]
                    ),

                "iceberg_risk":
                    float(
                        iceberg_risk[
                            r, c
                        ]
                    ),

                "combined_risk":
                    float(
                        combined_risk[
                            r, c
                        ]
                    ),
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# SAFE STATISTICS
# ============================================================

def safe_mean(values):

    values = np.asarray(
        values,
        dtype=float,
    )

    values = values[
        np.isfinite(values)
    ]

    if len(values) == 0:
        return np.nan

    return float(
        np.mean(values)
    )


def safe_max(values):

    values = np.asarray(
        values,
        dtype=float,
    )

    values = values[
        np.isfinite(values)
    ]

    if len(values) == 0:
        return np.nan

    return float(
        np.max(values)
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 100)
    print("POLARGUARD")
    print("STAGE 4 - AIS VS POLARGUARD ROUTE COMPARISON")
    print("=" * 100)

    forecasts, uncertainty, x, y = (
        load_member1()
    )

    grid_lat, grid_lon = (
        grid_to_latlon(
            x,
            y,
        )
    )

    iceberg_df = pd.read_csv(
        ICEBERG_FILE
    )

    iceberg_positions = [
        {
            "latitude":
                float(row["latitude"]),

            "longitude":
                float(row["longitude"]),
        }
        for _, row
        in iceberg_df.iterrows()
    ]

    summary_rows = []

    for horizon in HORIZONS:

        print()
        print("=" * 100)
        print(
            f"{horizon}H COMPARISON"
        )
        print("=" * 100)

        ais_file = (
            AIS_DIR
            /
            f"oceannova_actual_{horizon}h.csv"
        )

        pg_file = (
            POLARGUARD_DIR
            /
            f"polarguard_route_{horizon}h.csv"
        )

        if not ais_file.exists():
            raise FileNotFoundError(
                ais_file
            )

        if not pg_file.exists():
            raise FileNotFoundError(
                pg_file
            )

        ais = pd.read_csv(
            ais_file
        )

        pg = pd.read_csv(
            pg_file
        )

        # Normalize route column names.
        ais = ais.rename(
            columns={
                "latitude": "lat",
                "longitude": "lon",
            }
        )

        pg = pg.rename(
            columns={
                "latitude": "lat",
                "longitude": "lon",
            }
        )

        if (
            "lat" not in ais.columns
            or
            "lon" not in ais.columns
        ):
            raise RuntimeError(
                f"AIS {horizon}h file does "
                "not contain lat/lon columns."
            )

        if (
            "lat" not in pg.columns
            or
            "lon" not in pg.columns
        ):
            raise RuntimeError(
                f"PolarGuard {horizon}h file "
                "does not contain lat/lon columns."
            )

        # --------------------------------------------
        # DISTANCE
        # --------------------------------------------

        ais_distance = (
            route_distance_km(ais)
        )

        pg_distance = (
            route_distance_km(pg)
        )

        # --------------------------------------------
        # GEOMETRIC DEVIATION
        # --------------------------------------------

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
            np.mean(ais_to_pg)
        )

        median_deviation = float(
            np.median(ais_to_pg)
        )

        p90_deviation = float(
            np.percentile(
                ais_to_pg,
                90,
            )
        )

        max_deviation = float(
            np.max(ais_to_pg)
        )

        within_10 = float(
            np.mean(
                ais_to_pg <= 10.0
            )
            *
            100.0
        )

        within_25 = float(
            np.mean(
                ais_to_pg <= 25.0
            )
            *
            100.0
        )

        within_50 = float(
            np.mean(
                ais_to_pg <= 50.0
            )
            *
            100.0
        )

        symmetric_mean = float(
            (
                np.mean(ais_to_pg)
                +
                np.mean(pg_to_ais)
            )
            /
            2.0
        )

        # --------------------------------------------
        # ENVIRONMENT / RISK
        # --------------------------------------------

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

        risk = build_risk_grid(
            sic=sic,
            uncertainty=unc,
            grid_lat=grid_lat,
            grid_lon=grid_lon,
            iceberg_positions=
                iceberg_positions,
            safety_radius_km=10.0,
            influence_radius_km=30.0,
        )

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

        # --------------------------------------------
        # SAVE POINT LEVEL DATA
        # --------------------------------------------

        ais_env[
            "distance_to_polarguard_km"
        ] = ais_to_pg

        ais_env.to_csv(
            OUTPUT_DIR
            /
            f"ais_{horizon}h_environment.csv",
            index=False,
        )

        pg_env[
            "distance_to_ais_km"
        ] = pg_to_ais

        pg_env.to_csv(
            OUTPUT_DIR
            /
            f"polarguard_{horizon}h_environment.csv",
            index=False,
        )

        # --------------------------------------------
        # SUMMARY
        # --------------------------------------------

        summary = {
            "horizon_hours":
                horizon,

            "ais_points":
                len(ais),

            "polarguard_points":
                len(pg),

            "ais_distance_km":
                ais_distance,

            "polarguard_distance_km":
                pg_distance,

            "distance_saved_km":
                ais_distance
                -
                pg_distance,

            "distance_saved_pct":
                (
                    (
                        ais_distance
                        -
                        pg_distance
                    )
                    /
                    ais_distance
                    *
                    100.0
                ),

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
                safe_mean(
                    ais_env["sic"]
                )
                *
                100.0,

            "pg_mean_sic_pct":
                safe_mean(
                    pg_env["sic"]
                )
                *
                100.0,

            "ais_max_sic_pct":
                safe_max(
                    ais_env["sic"]
                )
                *
                100.0,

            "pg_max_sic_pct":
                safe_max(
                    pg_env["sic"]
                )
                *
                100.0,

            "ais_mean_iceberg_risk":
                safe_mean(
                    ais_env[
                        "iceberg_risk"
                    ]
                ),

            "pg_mean_iceberg_risk":
                safe_mean(
                    pg_env[
                        "iceberg_risk"
                    ]
                ),

            "ais_mean_uncertainty_risk":
                safe_mean(
                    ais_env[
                        "uncertainty_risk"
                    ]
                ),

            "pg_mean_uncertainty_risk":
                safe_mean(
                    pg_env[
                        "uncertainty_risk"
                    ]
                ),

            "ais_mean_combined_risk":
                safe_mean(
                    ais_env[
                        "combined_risk"
                    ]
                ),

            "pg_mean_combined_risk":
                safe_mean(
                    pg_env[
                        "combined_risk"
                    ]
                ),
        }

        summary_rows.append(
            summary
        )

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
            f"{summary['distance_saved_pct']:.2f}%"
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
            f"{summary['ais_mean_sic_pct']:.2f}%"
        )

        print(
            f"PolarGuard mean SIC      : "
            f"{summary['pg_mean_sic_pct']:.2f}%"
        )

        print(
            f"AIS max SIC              : "
            f"{summary['ais_max_sic_pct']:.2f}%"
        )

        print(
            f"PolarGuard max SIC       : "
            f"{summary['pg_max_sic_pct']:.2f}%"
        )

        print()
        print(
            f"AIS mean combined risk   : "
            f"{summary['ais_mean_combined_risk']:.4f}"
        )

        print(
            f"PG mean combined risk    : "
            f"{summary['pg_mean_combined_risk']:.4f}"
        )


    # ========================================================
    # 24H STATUS ROW
    # ========================================================

    summary_rows.insert(
        0,
        {
            "horizon_hours":
                24,

            "status":
                "NOT_EVALUABLE",

            "reason":
                (
                    "AIS endpoint maps to "
                    "invalid Member 1 SIC cell"
                ),
        }
    )


    # ========================================================
    # SAVE FINAL SUMMARY
    # ========================================================

    summary_df = pd.DataFrame(
        summary_rows
    )

    summary_file = (
        OUTPUT_DIR
        /
        "stage4_route_comparison_summary.csv"
    )

    summary_df.to_csv(
        summary_file,
        index=False,
    )

    print()
    print("=" * 100)
    print("FINAL STAGE 4 SUMMARY")
    print("=" * 100)

    print(
        summary_df.round(3).to_string(
            index=False
        )
    )

    print()
    print("=" * 100)
    print("FILES CREATED")
    print("=" * 100)

    print(summary_file)

    print(
        OUTPUT_DIR
        /
        "ais_48h_environment.csv"
    )

    print(
        OUTPUT_DIR
        /
        "polarguard_48h_environment.csv"
    )

    print(
        OUTPUT_DIR
        /
        "ais_72h_environment.csv"
    )

    print(
        OUTPUT_DIR
        /
        "polarguard_72h_environment.csv"
    )

    print()
    print("=" * 100)
    print("STAGE 4 COMPLETE")
    print("=" * 100)


if __name__ == "__main__":
    main()