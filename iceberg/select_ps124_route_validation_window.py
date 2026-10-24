from pathlib import Path
import pandas as pd
import numpy as np


BASE = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps124_stage1_ice_scan"
    / "ps124_all_candidate_windows.csv"
)

OUTPUT_DIR = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps124_validation"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# SELECTION RULES
# ============================================================

# We want:
# 1. substantial sea ice
# 2. good Member-1 coverage
# 3. meaningful start-to-destination displacement
# 4. not an extreme loop / station-keeping pattern
# 5. actual AIS duration close to requested horizon

MIN_MEAN_SIC_PCT = 30.0
MIN_MAX_SIC_PCT = 55.0
MIN_VALID_COVERAGE_PCT = 95.0

MIN_DIRECT_DISTANCE_KM = {
    24: 40.0,
    48: 80.0,
    72: 100.0,
}

MIN_GEOMETRIC_EFFICIENCY_PCT = 25.0

# Maximum allowed difference between actual AIS duration
# and requested 24h / 48h / 72h horizon.
MAX_DURATION_ERROR_MINUTES = 30.0

# Also prevent a candidate whose first AIS point starts too late.
MAX_START_DELAY_MINUTES = 30.0

# Prevent the final AIS point from ending too early.
MAX_END_SHORTFALL_MINUTES = 30.0


def main():

    print("=" * 110)
    print("POLARGUARD")
    print("PS124 ROUTE-VALIDATION WINDOW SELECTION - TIME FILTERED")
    print("=" * 110)

    # ========================================================
    # LOAD SCAN RESULTS
    # ========================================================

    df = pd.read_csv(
        INPUT_FILE
    )

    required = [
        "start_time",
        "actual_start_time",
        "actual_end_time",
        "horizon_hours",
        "start_delay_minutes",
        "end_shortfall_minutes",
        "effective_duration_hours",
        "duration_error_minutes",
        "ais_distance_km",
        "direct_distance_km",
        "geometric_efficiency_pct",
        "mean_sic_pct",
        "max_sic_pct",
        "points_in_ice_ge_15_pct",
        "valid_sic_coverage_pct",
        "start_latitude",
        "start_longitude",
        "destination_latitude",
        "destination_longitude",
    ]

    missing = [
        column
        for column in required
        if column not in df.columns
    ]

    if missing:

        raise RuntimeError(
            "Missing required columns: "
            +
            ", ".join(missing)
            +
            "\nRun the updated "
            "scan_ps124_for_ice_exposure.py first."
        )

    # ========================================================
    # CLEAN NUMERIC VALUES
    # ========================================================

    numeric_columns = [
        "horizon_hours",
        "start_delay_minutes",
        "end_shortfall_minutes",
        "effective_duration_hours",
        "duration_error_minutes",
        "ais_distance_km",
        "direct_distance_km",
        "geometric_efficiency_pct",
        "mean_sic_pct",
        "max_sic_pct",
        "points_in_ice_ge_15_pct",
        "valid_sic_coverage_pct",
        "start_latitude",
        "start_longitude",
        "destination_latitude",
        "destination_longitude",
    ]

    for column in numeric_columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df["start_time"] = pd.to_datetime(
        df["start_time"],
        utc=True,
        errors="coerce",
    )

    df["actual_start_time"] = pd.to_datetime(
        df["actual_start_time"],
        utc=True,
        errors="coerce",
    )

    df["actual_end_time"] = pd.to_datetime(
        df["actual_end_time"],
        utc=True,
        errors="coerce",
    )

    df = df.dropna(
        subset=required
    ).copy()

    print()
    print(
        "Candidate windows loaded:",
        len(df),
    )

    print(
        "Maximum duration error allowed:",
        f"{MAX_DURATION_ERROR_MINUTES:.1f} min",
    )

    print(
        "Maximum start delay allowed:",
        f"{MAX_START_DELAY_MINUTES:.1f} min",
    )

    print(
        "Maximum end shortfall allowed:",
        f"{MAX_END_SHORTFALL_MINUTES:.1f} min",
    )

    # ========================================================
    # SELECT ONE WINDOW PER HORIZON
    # ========================================================

    selected_rows = []

    for horizon in [24, 48, 72]:

        print()
        print("=" * 110)
        print(
            f"{horizon}H CANDIDATE FILTERING"
        )
        print("=" * 110)

        all_horizon = df[
            df["horizon_hours"]
            ==
            horizon
        ].copy()

        print(
            "Total horizon candidates:",
            len(all_horizon),
        )

        # ----------------------------------------------------
        # TIMING FILTER
        # ----------------------------------------------------

        timing_ok = all_horizon[
            (
                all_horizon[
                    "duration_error_minutes"
                ]
                <=
                MAX_DURATION_ERROR_MINUTES
            )
            &
            (
                all_horizon[
                    "start_delay_minutes"
                ]
                <=
                MAX_START_DELAY_MINUTES
            )
            &
            (
                all_horizon[
                    "end_shortfall_minutes"
                ]
                <=
                MAX_END_SHORTFALL_MINUTES
            )
        ].copy()

        print(
            "After timing filter:",
            len(timing_ok),
        )

        # ----------------------------------------------------
        # SEA ICE FILTER
        # ----------------------------------------------------

        ice_ok = timing_ok[
            (
                timing_ok[
                    "mean_sic_pct"
                ]
                >=
                MIN_MEAN_SIC_PCT
            )
            &
            (
                timing_ok[
                    "max_sic_pct"
                ]
                >=
                MIN_MAX_SIC_PCT
            )
            &
            (
                timing_ok[
                    "valid_sic_coverage_pct"
                ]
                >=
                MIN_VALID_COVERAGE_PCT
            )
        ].copy()

        print(
            "After SIC/coverage filter:",
            len(ice_ok),
        )

        # ----------------------------------------------------
        # ROUTE GEOMETRY FILTER
        # ----------------------------------------------------

        subset = ice_ok[
            (
                ice_ok[
                    "direct_distance_km"
                ]
                >=
                MIN_DIRECT_DISTANCE_KM[
                    horizon
                ]
            )
            &
            (
                ice_ok[
                    "geometric_efficiency_pct"
                ]
                >=
                MIN_GEOMETRIC_EFFICIENCY_PCT
            )
        ].copy()

        print(
            "After route-quality filter:",
            len(subset),
        )

        # ----------------------------------------------------
        # FALLBACK DIAGNOSTIC
        # ----------------------------------------------------

        if subset.empty:

            print()
            print(
                f"No {horizon}h candidate "
                "satisfies every strict rule."
            )

            print(
                "Showing strongest timing-valid "
                "candidates for diagnosis:"
            )

            diagnostic = timing_ok.copy()

            if diagnostic.empty:

                print(
                    "No timing-valid candidates "
                    "exist for this horizon."
                )

                continue

            diagnostic["diagnostic_score"] = (
                diagnostic[
                    "mean_sic_pct"
                ]
                +
                diagnostic[
                    "max_sic_pct"
                ] * 0.5
                +
                diagnostic[
                    "geometric_efficiency_pct"
                ] * 0.5
                +
                np.minimum(
                    diagnostic[
                        "direct_distance_km"
                    ],
                    500.0,
                ) * 0.10
            )

            diagnostic = (
                diagnostic
                .sort_values(
                    [
                        "diagnostic_score",
                        "duration_error_minutes",
                    ],
                    ascending=[
                        False,
                        True,
                    ],
                )
                .head(10)
            )

            print()

            print(
                diagnostic[
                    [
                        "start_time",
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

            continue

        # ====================================================
        # VALIDATION SCORE
        # ====================================================
        #
        # Score rewards:
        #
        # - high mean SIC
        # - high maximum SIC
        # - substantial fraction of AIS in ice
        # - strong environmental coverage
        # - meaningful endpoint displacement
        # - high geometric efficiency
        #
        # It also penalizes timing error.
        # ====================================================

        subset[
            "validation_score"
        ] = (
            subset[
                "mean_sic_pct"
            ] * 1.00
            +
            subset[
                "max_sic_pct"
            ] * 0.50
            +
            subset[
                "points_in_ice_ge_15_pct"
            ] * 0.50
            +
            subset[
                "valid_sic_coverage_pct"
            ] * 0.25
            +
            np.minimum(
                subset[
                    "direct_distance_km"
                ],
                500.0,
            ) * 0.10
            +
            subset[
                "geometric_efficiency_pct"
            ] * 0.75
            -
            subset[
                "duration_error_minutes"
            ] * 0.20
        )

        subset = subset.sort_values(
            [
                "validation_score",
                "duration_error_minutes",
                "geometric_efficiency_pct",
                "direct_distance_km",
                "mean_sic_pct",
            ],
            ascending=[
                False,
                True,
                False,
                False,
                False,
            ],
        )

        best = subset.iloc[
            0
        ].copy()

        selected_rows.append(
            best
        )

        # ====================================================
        # PRINT BEST WINDOW
        # ====================================================

        print()
        print("=" * 110)
        print(
            f"BEST {horizon}H WINDOW"
        )
        print("=" * 110)

        print(
            "Requested start :",
            best[
                "start_time"
            ],
        )

        print(
            "Actual AIS start:",
            best[
                "actual_start_time"
            ],
        )

        print(
            "Actual AIS end  :",
            best[
                "actual_end_time"
            ],
        )

        print()

        print(
            f"Effective duration : "
            f"{best['effective_duration_hours']:.3f} h"
        )

        print(
            f"Duration error     : "
            f"{best['duration_error_minutes']:.2f} min"
        )

        print(
            f"Start delay        : "
            f"{best['start_delay_minutes']:.2f} min"
        )

        print(
            f"End shortfall      : "
            f"{best['end_shortfall_minutes']:.2f} min"
        )

        print()

        print(
            f"AIS distance       : "
            f"{best['ais_distance_km']:.2f} km"
        )

        print(
            f"Direct distance    : "
            f"{best['direct_distance_km']:.2f} km"
        )

        print(
            f"Route efficiency   : "
            f"{best['geometric_efficiency_pct']:.2f}%"
        )

        print()

        print(
            f"Mean SIC           : "
            f"{best['mean_sic_pct']:.2f}%"
        )

        print(
            f"Maximum SIC        : "
            f"{best['max_sic_pct']:.2f}%"
        )

        print(
            f"AIS points >=15%   : "
            f"{best['points_in_ice_ge_15_pct']:.2f}%"
        )

        print(
            f"Valid SIC coverage : "
            f"{best['valid_sic_coverage_pct']:.2f}%"
        )

        print()

        print(
            f"Start position     : "
            f"{best['start_latitude']:.6f}, "
            f"{best['start_longitude']:.6f}"
        )

        print(
            f"Destination        : "
            f"{best['destination_latitude']:.6f}, "
            f"{best['destination_longitude']:.6f}"
        )

        print()

        print(
            f"Validation score   : "
            f"{best['validation_score']:.3f}"
        )

    # ========================================================
    # ENSURE ALL HORIZONS FOUND
    # ========================================================

    if not selected_rows:

        raise RuntimeError(
            "No suitable PS124 validation "
            "windows found."
        )

    selected = pd.DataFrame(
        selected_rows
    )

    selected = selected.sort_values(
        "horizon_hours"
    ).reset_index(
        drop=True
    )

    # ========================================================
    # SAVE
    # ========================================================

    output_file = (
        OUTPUT_DIR
        /
        "ps124_selected_route_validation_windows.csv"
    )

    selected.to_csv(
        output_file,
        index=False,
    )

    # ========================================================
    # FINAL TABLE
    # ========================================================

    print()
    print("=" * 110)
    print("FINAL SELECTED VALIDATION WINDOWS")
    print("=" * 110)

    columns = [
        "start_time",
        "actual_start_time",
        "actual_end_time",
        "horizon_hours",
        "effective_duration_hours",
        "duration_error_minutes",
        "start_delay_minutes",
        "end_shortfall_minutes",
        "ais_distance_km",
        "direct_distance_km",
        "geometric_efficiency_pct",
        "mean_sic_pct",
        "max_sic_pct",
        "points_in_ice_ge_15_pct",
        "valid_sic_coverage_pct",
        "validation_score",
    ]

    print()

    print(
        selected[
            columns
        ]
        .round(3)
        .to_string(
            index=False
        )
    )

    # ========================================================
    # QUALITY CHECK
    # ========================================================

    selected_horizons = set(
        selected[
            "horizon_hours"
        ]
        .astype(int)
        .tolist()
    )

    expected_horizons = {
        24,
        48,
        72,
    }

    missing_horizons = (
        expected_horizons
        -
        selected_horizons
    )

    print()
    print("=" * 110)
    print("SELECTION QUALITY CHECK")
    print("=" * 110)

    if not missing_horizons:

        print(
            "PASS: valid 24h, 48h and 72h "
            "PS124 validation windows selected."
        )

    else:

        print(
            "WARNING: no strict candidate "
            "selected for horizon(s):",
            sorted(
                missing_horizons
            ),
        )

        print(
            "Do not continue to routing "
            "until these horizons are reviewed."
        )

    # ========================================================
    # OUTPUT
    # ========================================================

    print()
    print("=" * 110)
    print("OUTPUT")
    print("=" * 110)

    print(
        output_file
    )

    print()
    print("=" * 110)
    print(
        "TIME-FILTERED WINDOW SELECTION COMPLETE"
    )
    print("=" * 110)


if __name__ == "__main__":
    main()