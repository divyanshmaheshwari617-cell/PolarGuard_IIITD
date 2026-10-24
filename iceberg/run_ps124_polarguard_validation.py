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

PS124_TEST_FILE = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps124_validation"
    / "selected_cases"
    / "ps124_selected_case_definitions.csv"
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
    / "polarguard_results"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# SETTINGS
# ============================================================

HORIZONS = [24, 48, 72]

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

        raise RuntimeError(
            f"No sea-ice history found for "
            f"{initialization_date}"
        )

    current_index = int(
        matches[0]
    )

    if current_index < 3:

        raise RuntimeError(
            "At least three prior sea-ice "
            "maps are required."
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

    return {
        "date":
            str(target_date),

        "current":
            current,

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

    if rows.empty:

        raise RuntimeError(
            "No Member 2 historical rows "
            f"for {initialization_date}"
        )

    return rows


def build_historical_iceberg_positions(
    member2_rows,
    horizon,
):

    lat_column = (
        f"true_lat_{horizon}h"
    )

    lon_column = (
        f"true_lon_{horizon}h"
    )

    positions = []

    for _, row in (
        member2_rows.iterrows()
    ):

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

    print("=" * 100)
    print("POLARGUARD")
    print("PS124 AIS VS HISTORICAL ROUTING VALIDATION")
    print("=" * 100)

    tests = pd.read_csv(
        PS124_TEST_FILE
    )

    # Ensure horizon is numeric
    tests["horizon_hours"] = pd.to_numeric(
        tests["horizon_hours"],
        errors="coerce",
    )

    tests = tests.dropna(
        subset=[
            "horizon_hours",
            "initialization_date",
            "start_latitude",
            "start_longitude",
            "destination_latitude",
            "destination_longitude",
            "actual_route_distance_km",
        ]
    ).copy()

    results = []

    for horizon in HORIZONS:

        print()
        print("=" * 100)
        print(
            f"{horizon}H ROUTING TEST"
        )
        print("=" * 100)

        horizon_tests = tests[
            tests[
                "horizon_hours"
            ]
            ==
            horizon
        ]

        if horizon_tests.empty:

            print(
                "TEST SKIPPED: "
                f"No frozen {horizon}h case found."
            )

            results.append(
                {
                    "horizon_hours":
                        horizon,

                    "success":
                        False,

                    "reason":
                        "No frozen test case found.",
                }
            )

            continue

        test = horizon_tests.iloc[0]

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
                "actual_route_distance_km"
            ]
        )

        # ====================================================
        # LOAD HISTORICAL ENVIRONMENT FOR THIS EXACT CASE
        # ====================================================

        member1 = load_member1_bundle(
            initialization_date
        )

        member2_rows = (
            load_member2_historical_rows(
                initialization_date
            )
        )

        grid_lat, grid_lon = (
            projected_grid_to_latlon(
                member1["x"],
                member1["y"],
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
            "Historical initialization:",
            initialization_date,
        )

        print(
            "Member 2 iceberg rows:",
            len(member2_rows),
        )

        print(
            "Historical iceberg hazards:",
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

        print()

        print(
            "Running existing PolarGuard "
            "navigation engine..."
        )

        # ====================================================
        # RUN EXISTING POLARGUARD NAVIGATION
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
                    start_lat=start_lat,
                    start_lon=start_lon,
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
        # HANDLE ROUTE FAILURE
        # ====================================================

        if not navigation_result[
            "success"
        ]:

            reason = (
                navigation_result[
                    "route"
                ]
                .get(
                    "reason",
                    "Unknown routing failure",
                )
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
        # SUCCESSFUL ROUTE
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

        percent_difference = (
            (
                polarguard_distance
                -
                actual_distance
            )
            /
            actual_distance
            *
            100.0
        )

        print()
        print(
            f"Actual AIS distance      : "
            f"{actual_distance:.2f} km"
        )

        print(
            f"PolarGuard route distance: "
            f"{polarguard_distance:.2f} km"
        )

        print(
            f"Distance difference      : "
            f"{distance_difference:+.2f} km"
        )

        print(
            f"Percent difference       : "
            f"{percent_difference:+.2f}%"
        )

        # ====================================================
        # SAVE ROUTE
        # ====================================================

        path_coordinates = (
            route[
                "path_coordinates"
            ]
        )

        route_file = (
            OUTPUT_DIR
            /
            f"ps124_polarguard_route_{horizon}h.csv"
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

        print(
            "Saved route:",
            route_file,
        )

        # ====================================================
        # SAVE SUMMARY ROW
        # ====================================================

        results.append(
            {
                "horizon_hours":
                    horizon,

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
                    percent_difference,

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

    output_file = (
        OUTPUT_DIR
        /
        "ps124_ais_vs_polarguard_summary.csv"
    )

    results_df.to_csv(
        output_file,
        index=False,
    )

    print()
    print("=" * 100)
    print("FINAL PS124 ROUTING VALIDATION SUMMARY")
    print("=" * 100)

    print()

    print(
        results_df.to_string(
            index=False
        )
    )

    print()
    print("=" * 100)
    print("OUTPUT")
    print("=" * 100)

    print(
        output_file
    )

    print()
    print("=" * 100)
    print("PS124 ROUTING VALIDATION COMPLETE")
    print("=" * 100)


if __name__ == "__main__":
    main()
