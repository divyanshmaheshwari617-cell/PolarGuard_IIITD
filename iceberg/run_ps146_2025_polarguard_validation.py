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

from navigation_service import (
    build_navigation_route,
)


# ============================================================
# PATHS
# ============================================================

SEA_ICE_HISTORY_FILE = (
    BASE
    / "data"
    / "processed"
    / "sea_ice_2019_2025.nc"
)

PS146_TEST_FILE = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps146_2025_validation"
    / "selected_cases"
    / "ps146_2025_frozen_case_definitions.csv"
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
    / "ps146_2025_validation"
    / "polarguard_results"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

SUMMARY_FILE = (
    OUTPUT_DIR
    / "ps146_2025_ais_vs_polarguard_summary.csv"
)


# ============================================================
# SETTINGS
# ============================================================

VESSEL_PROFILE = "HIGH_ICE_CAPABILITY"

SAFETY_RADIUS_KM = 10.0
INFLUENCE_RADIUS_KM = 30.0


# ============================================================
# MEMBER 1 HISTORICAL BUNDLE
# ============================================================

def load_member1_bundle(
    initialization_date,
):

    ds = xr.open_dataarray(
        SEA_ICE_HISTORY_FILE
    )

    target_date = np.datetime64(
        initialization_date,
        "D",
    )

    dates = ds.time.values.astype(
        "datetime64[D]"
    )

    matches = np.where(
        dates == target_date
    )[0]

    if len(matches) == 0:

        ds.close()

        raise RuntimeError(
            f"No sea-ice history found for "
            f"{initialization_date}"
        )

    current_index = int(
        matches[0]
    )

    if current_index < 3:

        ds.close()

        raise RuntimeError(
            "At least three prior sea-ice maps are required."
        )

    current = np.asarray(
        ds.values[current_index],
        dtype=np.float32,
    )

    lag1 = np.asarray(
        ds.values[current_index - 1],
        dtype=np.float32,
    )

    lag2 = np.asarray(
        ds.values[current_index - 2],
        dtype=np.float32,
    )

    lag3 = np.asarray(
        ds.values[current_index - 3],
        dtype=np.float32,
    )

    x_coords = np.asarray(
        ds.x.values
    )

    y_coords = np.asarray(
        ds.y.values
    )

    forecasts = predict_sea_ice(
        current=current,
        lag1=lag1,
        lag2=lag2,
        lag3=lag3,
        x_coords=x_coords,
        y_coords=y_coords,
        date=target_date,
    )

    uncertainty = load_uncertainty()

    result = {
        "date":
            str(target_date),

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

        "x":
            x_coords,

        "y":
            y_coords,
    }

    ds.close()

    return result


# ============================================================
# GRID COORDINATES
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
# MEMBER 2 HISTORICAL ICEBERG HAZARDS
# ============================================================

def load_member2_historical_rows(
    initialization_date,
):

    df = pd.read_csv(
        MEMBER2_FILE
    )

    dates = pd.to_datetime(
        df["init_date"],
        errors="coerce",
    )

    rows = df[
        dates.dt.strftime(
            "%Y-%m-%d"
        )
        ==
        initialization_date
    ].copy()

    return rows


def build_historical_iceberg_positions(
    member2_rows,
    horizon,
):

    if member2_rows.empty:
        return []

    lat_column = (
        f"true_lat_{horizon}h"
    )

    lon_column = (
        f"true_lon_{horizon}h"
    )

    if (
        lat_column not in member2_rows.columns
        or
        lon_column not in member2_rows.columns
    ):
        return []

    positions = []

    for _, row in member2_rows.iterrows():

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

    return positions


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 105)
    print("POLARGUARD")
    print("PS146 2025 AIS VS POLARGUARD ROUTING VALIDATION")
    print("=" * 105)

    tests = pd.read_csv(
        PS146_TEST_FILE
    )

    numeric_columns = [
        "horizon_hours",
        "ais_distance_km",
        "start_latitude",
        "start_longitude",
        "destination_latitude",
        "destination_longitude",
    ]

    for col in numeric_columns:

        tests[col] = pd.to_numeric(
            tests[col],
            errors="coerce",
        )

    tests = tests.dropna(
        subset=[
            "case_id",
            "horizon_hours",
            "initialization_date",
            "start_latitude",
            "start_longitude",
            "destination_latitude",
            "destination_longitude",
            "ais_distance_km",
        ]
    ).copy()

    tests = (
        tests
        .sort_values(
            [
                "horizon_hours",
                "selection_rank",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    print()
    print(
        "Frozen cases loaded:",
        len(
            tests
        ),
    )

    results = []

    member1_cache = {}
    member2_cache = {}

    # ========================================================
    # RUN EVERY FROZEN CASE
    # ========================================================

    for case_number, (_, test) in enumerate(
        tests.iterrows(),
        start=1,
    ):

        case_id = str(
            test[
                "case_id"
            ]
        )

        horizon = int(
            test[
                "horizon_hours"
            ]
        )

        initialization_date = str(
            test[
                "initialization_date"
            ]
        )

        start_lat = float(
            test[
                "start_latitude"
            ]
        )

        start_lon = float(
            test[
                "start_longitude"
            ]
        )

        destination_lat = float(
            test[
                "destination_latitude"
            ]
        )

        destination_lon = float(
            test[
                "destination_longitude"
            ]
        )

        actual_distance = float(
            test[
                "ais_distance_km"
            ]
        )

        print()
        print("=" * 105)
        print(
            f"CASE {case_number}/{len(tests)}"
        )
        print(
            case_id
        )
        print("=" * 105)

        print(
            "Horizon:",
            f"{horizon}h",
        )

        print(
            "Initialization:",
            initialization_date,
        )

        print(
            "Start:",
            start_lat,
            start_lon,
        )

        print(
            "Destination:",
            destination_lat,
            destination_lon,
        )

        print(
            f"Actual AIS distance: "
            f"{actual_distance:.2f} km"
        )

        # ====================================================
        # MEMBER 1 CACHE
        # ====================================================

        if initialization_date not in member1_cache:

            try:

                member1_cache[
                    initialization_date
                ] = load_member1_bundle(
                    initialization_date
                )

            except Exception as exc:

                print()
                print(
                    "MEMBER 1 ERROR:"
                )
                print(
                    str(exc)
                )

                results.append(
                    {
                        "case_id":
                            case_id,

                        "horizon_hours":
                            horizon,

                        "initialization_date":
                            initialization_date,

                        "success":
                            False,

                        "reason":
                            f"Member 1: {exc}",

                        "actual_ais_distance_km":
                            actual_distance,
                    }
                )

                continue

        member1 = member1_cache[
            initialization_date
        ]

        # ====================================================
        # MEMBER 2 CACHE
        # ====================================================

        if initialization_date not in member2_cache:

            member2_cache[
                initialization_date
            ] = load_member2_historical_rows(
                initialization_date
            )

        member2_rows = member2_cache[
            initialization_date
        ]

        grid_lat, grid_lon = (
            projected_grid_to_latlon(
                member1[
                    "x"
                ],
                member1[
                    "y"
                ],
            )
        )

        sic = member1[
            f"forecast_{horizon}h"
        ]

        uncertainty = member1[
            f"uncertainty_{horizon}h"
        ]

        iceberg_positions = (
            build_historical_iceberg_positions(
                member2_rows,
                horizon,
            )
        )

        print(
            "Member 2 rows:",
            len(
                member2_rows
            ),
        )

        print(
            "Iceberg hazards:",
            len(
                iceberg_positions
            ),
        )

        print(
            "Routing grid shape:",
            grid_lat.shape,
        )

        print()
        print(
            "Running PolarGuard..."
        )

        # ====================================================
        # ROUTING
        # ====================================================

        try:

            navigation_result = (
                build_navigation_route(
                    sic=sic,
                    uncertainty=uncertainty,
                    grid_lat=grid_lat,
                    grid_lon=grid_lon,
                    iceberg_positions=
                        iceberg_positions,
                    start_lat=
                        start_lat,
                    start_lon=
                        start_lon,
                    destination_lat=
                        destination_lat,
                    destination_lon=
                        destination_lon,
                    vessel_profile=
                        VESSEL_PROFILE,
                    safety_radius_km=
                        SAFETY_RADIUS_KM,
                    influence_radius_km=
                        INFLUENCE_RADIUS_KM,
                )
            )

        except Exception as exc:

            print()
            print(
                "ROUTING ERROR:"
            )

            print(
                str(exc)
            )

            results.append(
                {
                    "case_id":
                        case_id,

                    "horizon_hours":
                        horizon,

                    "initialization_date":
                        initialization_date,

                    "success":
                        False,

                    "reason":
                        str(exc),

                    "actual_ais_distance_km":
                        actual_distance,

                    "iceberg_hazards":
                        len(
                            iceberg_positions
                        ),
                }
            )

            continue

        # ====================================================
        # HANDLE FAILURE
        # ====================================================

        if not navigation_result[
            "success"
        ]:

            route_info = navigation_result.get(
                "route",
                {},
            )

            reason = route_info.get(
                "reason",
                "Unknown routing failure",
            )

            print()
            print(
                "ROUTE FAILED:"
            )

            print(
                reason
            )

            results.append(
                {
                    "case_id":
                        case_id,

                    "horizon_hours":
                        horizon,

                    "initialization_date":
                        initialization_date,

                    "success":
                        False,

                    "reason":
                        reason,

                    "actual_ais_distance_km":
                        actual_distance,

                    "iceberg_hazards":
                        len(
                            iceberg_positions
                        ),
                }
            )

            continue

        # ====================================================
        # SUCCESS
        # ====================================================

        route = navigation_result[
            "route"
        ]

        polarguard_distance = float(
            route[
                "total_distance_km"
            ]
        )

        distance_difference = (
            polarguard_distance
            -
            actual_distance
        )

        distance_difference_pct = (
            (
                polarguard_distance
                -
                actual_distance
            )
            /
            actual_distance
            *
            100.0
            if actual_distance > 0
            else np.nan
        )

        distance_saved_km = (
            actual_distance
            -
            polarguard_distance
        )

        distance_saved_pct = (
            (
                actual_distance
                -
                polarguard_distance
            )
            /
            actual_distance
            *
            100.0
            if actual_distance > 0
            else np.nan
        )

        path_coordinates = route[
            "path_coordinates"
        ]

        route_file = (
            OUTPUT_DIR
            /
            f"{case_id}_polarguard_route.csv"
        )

        pd.DataFrame(
            path_coordinates,
            columns=[
                "latitude",
                "longitude",
            ],
        ).to_csv(
            route_file,
            index=False,
        )

        print()
        print(
            f"Actual AIS distance       : "
            f"{actual_distance:.2f} km"
        )

        print(
            f"PolarGuard route distance : "
            f"{polarguard_distance:.2f} km"
        )

        print(
            f"Distance difference       : "
            f"{distance_difference:+.2f} km"
        )

        print(
            f"Modeled distance saved    : "
            f"{distance_saved_km:.2f} km"
        )

        print(
            f"Modeled reduction         : "
            f"{distance_saved_pct:.2f}%"
        )

        print(
            "Route cells:",
            len(
                route[
                    "path_indices"
                ]
            ),
        )

        print(
            "Saved:",
            route_file,
        )

        results.append(
            {
                "case_id":
                    case_id,

                "horizon_hours":
                    horizon,

                "selection_rank":
                    int(
                        test[
                            "selection_rank"
                        ]
                    ),

                "initialization_date":
                    initialization_date,

                "success":
                    True,

                "reason":
                    None,

                "actual_ais_distance_km":
                    actual_distance,

                "polarguard_distance_km":
                    polarguard_distance,

                "distance_difference_km":
                    distance_difference,

                "distance_difference_pct":
                    distance_difference_pct,

                "distance_saved_km":
                    distance_saved_km,

                "distance_saved_pct":
                    distance_saved_pct,

                "route_cells":
                    len(
                        route[
                            "path_indices"
                        ]
                    ),

                "iceberg_hazards":
                    len(
                        iceberg_positions
                    ),

                "accumulated_cost":
                    float(
                        route[
                            "accumulated_cost"
                        ]
                    ),

                "actual_mean_sic_pct":
                    test.get(
                        "actual_mean_sic_pct",
                        np.nan,
                    ),

                "predicted_mean_sic_pct":
                    test.get(
                        "predicted_mean_sic_pct",
                        np.nan,
                    ),

                "route_sic_mae_pct":
                    test.get(
                        "route_sic_mae_pct",
                        np.nan,
                    ),

                "route_file":
                    str(
                        route_file
                    ),
            }
        )

    # ========================================================
    # SAVE SUMMARY
    # ========================================================

    results_df = pd.DataFrame(
        results
    )

    results_df.to_csv(
        SUMMARY_FILE,
        index=False,
    )

    print()
    print("=" * 105)
    print("FINAL PS146 2025 ROUTING VALIDATION SUMMARY")
    print("=" * 105)

    print()

    if results_df.empty:

        print(
            "No routing results produced."
        )

    else:

        display_columns = [
            col
            for col in [
                "case_id",
                "horizon_hours",
                "initialization_date",
                "success",
                "reason",
                "actual_ais_distance_km",
                "polarguard_distance_km",
                "distance_saved_km",
                "distance_saved_pct",
                "route_cells",
                "iceberg_hazards",
            ]
            if col in results_df.columns
        ]

        print(
            results_df[
                display_columns
            ]
            .round(3)
            .to_string(
                index=False
            )
        )

    # ========================================================
    # AGGREGATE SUCCESS METRICS
    # ========================================================

    if (
        not results_df.empty
        and
        "success" in results_df.columns
    ):

        successful = results_df[
            results_df[
                "success"
            ]
            ==
            True
        ].copy()

        print()
        print("=" * 105)
        print("AGGREGATE ROUTING RESULTS")
        print("=" * 105)

        print(
            "Successful cases:",
            f"{len(successful)}/{len(results_df)}",
        )

        if not successful.empty:

            print(
                f"Mean modeled distance reduction: "
                f"{successful['distance_saved_pct'].mean():.2f}%"
            )

            print(
                f"Median modeled distance reduction: "
                f"{successful['distance_saved_pct'].median():.2f}%"
            )

            print(
                f"Minimum modeled reduction: "
                f"{successful['distance_saved_pct'].min():.2f}%"
            )

            print(
                f"Maximum modeled reduction: "
                f"{successful['distance_saved_pct'].max():.2f}%"
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
                    f"{len(subset)} successful, "
                    f"mean reduction="
                    f"{subset['distance_saved_pct'].mean():.2f}%"
                )

    print()
    print("=" * 105)
    print("OUTPUT")
    print("=" * 105)

    print(
        SUMMARY_FILE
    )

    print()
    print("=" * 105)
    print(
        "PS146 2025 ROUTING VALIDATION COMPLETE"
    )
    print("=" * 105)


if __name__ == "__main__":
    main()