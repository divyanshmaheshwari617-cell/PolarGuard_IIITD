from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent.parent

if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

import numpy as np
import pandas as pd


# ============================================================
# PATHS
# ============================================================

CASE_DIR = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps124_validation"
    / "selected_cases"
)

POLARGUARD_DIR = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps124_validation"
    / "polarguard_results"
)

MEMBER2_FILE = (
    BASE
    / "iceberg"
    / "data"
    / "processed"
    / "iceberg_features_environment_ml_ready_2019_2025.csv"
)

OUTPUT_DIR = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps124_validation"
    / "iceberg_proximity"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

HORIZONS = [24, 48, 72]

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
# LOAD HISTORICAL ICEBERGS
# ============================================================

def load_icebergs(
    initialization_date,
    horizon,
):

    df = pd.read_csv(
        MEMBER2_FILE
    )

    dates = pd.to_datetime(
        df["init_date"],
        errors="coerce",
    )

    rows = df[
        dates.dt.strftime("%Y-%m-%d")
        ==
        initialization_date
    ].copy()

    lat_col = f"true_lat_{horizon}h"
    lon_col = f"true_lon_{horizon}h"

    icebergs = []

    for _, row in rows.iterrows():

        lat = row[lat_col]
        lon = row[lon_col]

        if (
            np.isfinite(lat)
            and
            np.isfinite(lon)
        ):

            icebergs.append(
                {
                    "iceberg_id":
                        str(
                            row["iceberg_id"]
                        ),

                    "latitude":
                        float(lat),

                    "longitude":
                        float(lon),
                }
            )

    return pd.DataFrame(
        icebergs
    )


# ============================================================
# NORMALIZE ROUTE
# ============================================================

def load_route(
    path,
):

    df = pd.read_csv(
        path
    )

    df = df.rename(
        columns={
            "latitude":
                "lat",

            "longitude":
                "lon",
        }
    )

    if (
        "lat" not in df.columns
        or
        "lon" not in df.columns
    ):

        raise RuntimeError(
            f"Route file does not contain "
            f"lat/lon columns: {path}"
        )

    return df


# ============================================================
# ROUTE -> ICEBERG DISTANCES
# ============================================================

def route_iceberg_distances(
    route,
    icebergs,
):

    rows = []

    if icebergs.empty:

        return pd.DataFrame(
            columns=[
                "route_index",
                "route_lat",
                "route_lon",
                "nearest_iceberg_id",
                "nearest_iceberg_lat",
                "nearest_iceberg_lon",
                "min_distance_km",
            ]
        )

    iceberg_lat = (
        icebergs[
            "latitude"
        ]
        .to_numpy(
            dtype=float
        )
    )

    iceberg_lon = (
        icebergs[
            "longitude"
        ]
        .to_numpy(
            dtype=float
        )
    )

    for idx, point in route.iterrows():

        distances = haversine_km(
            float(
                point["lat"]
            ),
            float(
                point["lon"]
            ),
            iceberg_lat,
            iceberg_lon,
        )

        nearest_index = int(
            np.nanargmin(
                distances
            )
        )

        nearest = icebergs.iloc[
            nearest_index
        ]

        rows.append(
            {
                "route_index":
                    int(idx),

                "route_lat":
                    float(
                        point["lat"]
                    ),

                "route_lon":
                    float(
                        point["lon"]
                    ),

                "nearest_iceberg_id":
                    nearest[
                        "iceberg_id"
                    ],

                "nearest_iceberg_lat":
                    float(
                        nearest[
                            "latitude"
                        ]
                    ),

                "nearest_iceberg_lon":
                    float(
                        nearest[
                            "longitude"
                        ]
                    ),

                "min_distance_km":
                    float(
                        distances[
                            nearest_index
                        ]
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


# ============================================================
# SUMMARY
# ============================================================

def summarize_distances(
    distances,
):

    if distances.empty:

        return {
            "minimum_km":
                np.nan,

            "mean_km":
                np.nan,

            "median_km":
                np.nan,

            "within_10km_pct":
                np.nan,

            "within_30km_pct":
                np.nan,

            "within_50km_pct":
                np.nan,

            "within_100km_pct":
                np.nan,
        }

    values = (
        distances[
            "min_distance_km"
        ]
        .to_numpy(
            dtype=float
        )
    )

    return {
        "minimum_km":
            float(
                np.min(values)
            ),

        "mean_km":
            float(
                np.mean(values)
            ),

        "median_km":
            float(
                np.median(values)
            ),

        "within_10km_pct":
            float(
                np.mean(
                    values <= 10.0
                )
                *
                100.0
            ),

        "within_30km_pct":
            float(
                np.mean(
                    values <= 30.0
                )
                *
                100.0
            ),

        "within_50km_pct":
            float(
                np.mean(
                    values <= 50.0
                )
                *
                100.0
            ),

        "within_100km_pct":
            float(
                np.mean(
                    values <= 100.0
                )
                *
                100.0
            ),
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 105)
    print("POLARGUARD")
    print("PS124 ICEBERG PROXIMITY DIAGNOSTIC")
    print("=" * 105)

    definitions_file = (
        CASE_DIR
        /
        "ps124_selected_case_definitions.csv"
    )

    definitions = pd.read_csv(
        definitions_file
    )

    summary_rows = []

    for horizon in HORIZONS:

        print()
        print("=" * 105)
        print(
            f"{horizon}H ICEBERG PROXIMITY"
        )
        print("=" * 105)

        test = definitions[
            definitions[
                "horizon_hours"
            ]
            ==
            horizon
        ].iloc[0]

        initialization_date = str(
            test[
                "initialization_date"
            ]
        )

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

        ais = load_route(
            ais_file
        )

        pg = load_route(
            pg_file
        )

        icebergs = load_icebergs(
            initialization_date,
            horizon,
        )

        print(
            "Initialization date:",
            initialization_date,
        )

        print(
            "Historical icebergs:",
            len(
                icebergs
            ),
        )

        ais_distances = (
            route_iceberg_distances(
                ais,
                icebergs,
            )
        )

        pg_distances = (
            route_iceberg_distances(
                pg,
                icebergs,
            )
        )

        ais_summary = (
            summarize_distances(
                ais_distances
            )
        )

        pg_summary = (
            summarize_distances(
                pg_distances
            )
        )

        print()
        print("AIS ROUTE")
        print("-" * 105)

        print(
            f"Minimum iceberg distance : "
            f"{ais_summary['minimum_km']:.2f} km"
        )

        print(
            f"Mean iceberg distance    : "
            f"{ais_summary['mean_km']:.2f} km"
        )

        print(
            f"Median iceberg distance  : "
            f"{ais_summary['median_km']:.2f} km"
        )

        print(
            f"Points within 10 km      : "
            f"{ais_summary['within_10km_pct']:.2f}%"
        )

        print(
            f"Points within 30 km      : "
            f"{ais_summary['within_30km_pct']:.2f}%"
        )

        print(
            f"Points within 50 km      : "
            f"{ais_summary['within_50km_pct']:.2f}%"
        )

        print(
            f"Points within 100 km     : "
            f"{ais_summary['within_100km_pct']:.2f}%"
        )

        print()
        print("POLARGUARD ROUTE")
        print("-" * 105)

        print(
            f"Minimum iceberg distance : "
            f"{pg_summary['minimum_km']:.2f} km"
        )

        print(
            f"Mean iceberg distance    : "
            f"{pg_summary['mean_km']:.2f} km"
        )

        print(
            f"Median iceberg distance  : "
            f"{pg_summary['median_km']:.2f} km"
        )

        print(
            f"Points within 10 km      : "
            f"{pg_summary['within_10km_pct']:.2f}%"
        )

        print(
            f"Points within 30 km      : "
            f"{pg_summary['within_30km_pct']:.2f}%"
        )

        print(
            f"Points within 50 km      : "
            f"{pg_summary['within_50km_pct']:.2f}%"
        )

        print(
            f"Points within 100 km     : "
            f"{pg_summary['within_100km_pct']:.2f}%"
        )

        ais_output = (
            OUTPUT_DIR
            /
            f"ps124_ais_{horizon}h_iceberg_proximity.csv"
        )

        pg_output = (
            OUTPUT_DIR
            /
            f"ps124_polarguard_{horizon}h_iceberg_proximity.csv"
        )

        ais_distances.to_csv(
            ais_output,
            index=False,
        )

        pg_distances.to_csv(
            pg_output,
            index=False,
        )

        summary_rows.append(
            {
                "horizon_hours":
                    horizon,

                "initialization_date":
                    initialization_date,

                "historical_icebergs":
                    len(
                        icebergs
                    ),

                "ais_min_iceberg_distance_km":
                    ais_summary[
                        "minimum_km"
                    ],

                "pg_min_iceberg_distance_km":
                    pg_summary[
                        "minimum_km"
                    ],

                "ais_mean_iceberg_distance_km":
                    ais_summary[
                        "mean_km"
                    ],

                "pg_mean_iceberg_distance_km":
                    pg_summary[
                        "mean_km"
                    ],

                "ais_within_30km_pct":
                    ais_summary[
                        "within_30km_pct"
                    ],

                "pg_within_30km_pct":
                    pg_summary[
                        "within_30km_pct"
                    ],

                "ais_within_50km_pct":
                    ais_summary[
                        "within_50km_pct"
                    ],

                "pg_within_50km_pct":
                    pg_summary[
                        "within_50km_pct"
                    ],

                "ais_within_100km_pct":
                    ais_summary[
                        "within_100km_pct"
                    ],

                "pg_within_100km_pct":
                    pg_summary[
                        "within_100km_pct"
                    ],
            }
        )

    summary = pd.DataFrame(
        summary_rows
    )

    summary_file = (
        OUTPUT_DIR
        /
        "ps124_iceberg_proximity_summary.csv"
    )

    summary.to_csv(
        summary_file,
        index=False,
    )

    print()
    print("=" * 105)
    print("FINAL ICEBERG PROXIMITY SUMMARY")
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
    print("OUTPUT")
    print("=" * 105)

    print(
        summary_file
    )

    print()
    print("=" * 105)
    print("ICEBERG PROXIMITY DIAGNOSTIC COMPLETE")
    print("=" * 105)


if __name__ == "__main__":
    main()