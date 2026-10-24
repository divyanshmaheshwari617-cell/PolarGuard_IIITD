from pathlib import Path
import pandas as pd
import numpy as np


BASE = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps146_2025_stage1_scan"
    / "ps146_2025_all_candidate_windows.csv"
)

OUTPUT_DIR = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps146_2025_validation"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "ps146_2025_selected_validation_windows.csv"
)


# ============================================================
# SETTINGS
# ============================================================

HORIZONS = [24, 48, 72]

CASES_PER_HORIZON = 5

# Require useful actual ice exposure
MIN_ACTUAL_MEAN_SIC_PCT = 15.0
MIN_ACTUAL_MAX_SIC_PCT = 30.0

# Require high SIC coverage
MIN_VALID_COVERAGE_PCT = 95.0

# Require useful route geometry
MIN_DIRECT_DISTANCE_KM = {
    24: 30.0,
    48: 60.0,
    72: 90.0,
}

MIN_GEOMETRIC_EFFICIENCY_PCT = 20.0

# Timing quality
MAX_START_DELAY_MIN = 30.0
MAX_END_SHORTFALL_MIN = 30.0
MAX_DURATION_ERROR_MIN = 30.0


# ============================================================
# HELPERS
# ============================================================

def overlap_hours(
    start_a,
    end_a,
    start_b,
    end_b,
):
    latest_start = max(
        start_a,
        start_b,
    )

    earliest_end = min(
        end_a,
        end_b,
    )

    overlap = (
        earliest_end
        -
        latest_start
    ).total_seconds() / 3600.0

    return max(
        0.0,
        overlap,
    )


def choose_non_overlapping(
    subset,
    count,
):
    """
    Greedy selection:
    highest validation score first,
    but avoid windows that overlap already-selected cases.
    """

    selected = []

    for _, row in subset.iterrows():

        row_start = pd.Timestamp(
            row["actual_start_time"]
        )

        row_end = pd.Timestamp(
            row["actual_end_time"]
        )

        acceptable = True

        for chosen in selected:

            chosen_start = pd.Timestamp(
                chosen["actual_start_time"]
            )

            chosen_end = pd.Timestamp(
                chosen["actual_end_time"]
            )

            if overlap_hours(
                row_start,
                row_end,
                chosen_start,
                chosen_end,
            ) > 0:

                acceptable = False
                break

        if acceptable:

            selected.append(
                row.copy()
            )

        if len(selected) >= count:
            break

    return selected


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 110)
    print("POLARGUARD")
    print("PS146 2025 REPRESENTATIVE ROUTE-VALIDATION WINDOW SELECTION")
    print("=" * 110)

    df = pd.read_csv(
        INPUT_FILE
    )

    # --------------------------------------------------------
    # NORMALIZE TYPES
    # --------------------------------------------------------

    datetime_columns = [
        "start_time",
        "end_time",
        "actual_start_time",
        "actual_end_time",
    ]

    for col in datetime_columns:

        df[col] = pd.to_datetime(
            df[col],
            utc=True,
            errors="coerce",
        )

    numeric_columns = [
        "horizon_hours",
        "start_delay_minutes",
        "end_shortfall_minutes",
        "duration_error_minutes",
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

    for col in numeric_columns:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    print()
    print(
        "Candidate rows loaded:",
        len(df),
    )

    selected_rows = []

    # ========================================================
    # SELECT PER HORIZON
    # ========================================================

    for horizon in HORIZONS:

        print()
        print("=" * 110)
        print(
            f"{horizon}H FILTERING"
        )
        print("=" * 110)

        subset = df[
            df["horizon_hours"]
            ==
            horizon
        ].copy()

        print(
            "Total candidates:",
            len(subset),
        )

        # ----------------------------------------------------
        # TIMING FILTER
        # ----------------------------------------------------

        subset = subset[
            (
                subset[
                    "start_delay_minutes"
                ]
                <=
                MAX_START_DELAY_MIN
            )
            &
            (
                subset[
                    "end_shortfall_minutes"
                ]
                <=
                MAX_END_SHORTFALL_MIN
            )
            &
            (
                subset[
                    "duration_error_minutes"
                ]
                <=
                MAX_DURATION_ERROR_MIN
            )
        ].copy()

        print(
            "After timing filter:",
            len(subset),
        )

        # ----------------------------------------------------
        # COVERAGE FILTER
        # ----------------------------------------------------

        subset = subset[
            subset[
                "valid_sic_coverage_pct"
            ]
            >=
            MIN_VALID_COVERAGE_PCT
        ].copy()

        print(
            "After coverage filter:",
            len(subset),
        )

        # ----------------------------------------------------
        # ICE FILTER
        # ----------------------------------------------------

        subset = subset[
            (
                subset[
                    "actual_mean_sic_pct"
                ]
                >=
                MIN_ACTUAL_MEAN_SIC_PCT
            )
            &
            (
                subset[
                    "actual_max_sic_pct"
                ]
                >=
                MIN_ACTUAL_MAX_SIC_PCT
            )
        ].copy()

        print(
            "After actual-SIC filter:",
            len(subset),
        )

        # ----------------------------------------------------
        # ROUTE QUALITY FILTER
        # ----------------------------------------------------

        subset = subset[
            (
                subset[
                    "direct_distance_km"
                ]
                >=
                MIN_DIRECT_DISTANCE_KM[
                    horizon
                ]
            )
            &
            (
                subset[
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

        if subset.empty:

            print(
                "No suitable candidates."
            )

            continue

        # ----------------------------------------------------
        # REPRESENTATIVE SCORE
        # ----------------------------------------------------
        #
        # IMPORTANT:
        # Do not rank using low prediction error.
        #
        # We reward:
        # actual ice exposure,
        # endpoint displacement,
        # route efficiency,
        # coverage,
        # timing quality.
        # ----------------------------------------------------

        subset[
            "selection_score"
        ] = (
            subset[
                "actual_mean_sic_pct"
            ]
            *
            1.0
            +
            subset[
                "actual_max_sic_pct"
            ]
            *
            0.40
            +
            np.minimum(
                subset[
                    "direct_distance_km"
                ],
                500.0,
            )
            *
            0.10
            +
            subset[
                "geometric_efficiency_pct"
            ]
            *
            0.50
            +
            subset[
                "valid_sic_coverage_pct"
            ]
            *
            0.20
            -
            subset[
                "duration_error_minutes"
            ]
            *
            0.10
        )

        subset = subset.sort_values(
            [
                "selection_score",
                "actual_mean_sic_pct",
                "direct_distance_km",
                "geometric_efficiency_pct",
            ],
            ascending=False,
        )

        # ----------------------------------------------------
        # NON-OVERLAPPING SELECTION
        # ----------------------------------------------------

        chosen = choose_non_overlapping(
            subset,
            CASES_PER_HORIZON,
        )

        print(
            "Selected non-overlapping cases:",
            len(chosen),
        )

        for rank, row in enumerate(
            chosen,
            start=1,
        ):

            row[
                "selection_rank"
            ] = rank

            selected_rows.append(
                row
            )

            print()
            print(
                f"CASE {rank}"
            )

            print(
                "Start:",
                row[
                    "actual_start_time"
                ],
            )

            print(
                "End:",
                row[
                    "actual_end_time"
                ],
            )

            print(
                f"AIS distance: "
                f"{row['ais_distance_km']:.2f} km"
            )

            print(
                f"Direct distance: "
                f"{row['direct_distance_km']:.2f} km"
            )

            print(
                f"Actual mean SIC: "
                f"{row['actual_mean_sic_pct']:.2f}%"
            )

            print(
                f"Actual max SIC: "
                f"{row['actual_max_sic_pct']:.2f}%"
            )

            print(
                f"Predicted mean SIC: "
                f"{row['predicted_mean_sic_pct']:.2f}%"
            )

            print(
                f"Route SIC MAE: "
                f"{row['route_sic_mae_pct']:.2f}%"
            )

            print(
                f"Map SIC MAE: "
                f"{row['map_mae_pct']:.2f}%"
            )

    # ========================================================
    # BUILD FINAL TABLE
    # ========================================================

    if not selected_rows:

        raise RuntimeError(
            "No PS146 2025 validation windows selected."
        )

    selected = pd.DataFrame(
        selected_rows
    )

    selected = selected.sort_values(
        [
            "horizon_hours",
            "selection_rank",
        ]
    ).reset_index(
        drop=True
    )

    selected[
        "case_id"
    ] = selected.apply(
        lambda row:
            (
                f"PS146_2025_"
                f"{int(row['horizon_hours'])}H_"
                f"C{int(row['selection_rank'])}"
            ),
        axis=1,
    )

    # Put useful identifiers first.
    first_columns = [
        "case_id",
        "horizon_hours",
        "selection_rank",
        "actual_start_time",
        "actual_end_time",
        "initialization_date",
        "target_date",
        "start_latitude",
        "start_longitude",
        "destination_latitude",
        "destination_longitude",
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
        "selection_score",
    ]

    remaining_columns = [
        col
        for col in selected.columns
        if col not in first_columns
    ]

    selected = selected[
        first_columns
        +
        remaining_columns
    ]

    selected.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print()
    print("=" * 110)
    print("FINAL SELECTED PS146 2025 VALIDATION CASES")
    print("=" * 110)

    display_columns = [
        "case_id",
        "horizon_hours",
        "actual_start_time",
        "actual_end_time",
        "ais_distance_km",
        "direct_distance_km",
        "geometric_efficiency_pct",
        "actual_mean_sic_pct",
        "actual_max_sic_pct",
        "predicted_mean_sic_pct",
        "route_sic_mae_pct",
        "map_mae_pct",
        "map_correlation",
    ]

    print()

    print(
        selected[
            display_columns
        ]
        .round(3)
        .to_string(
            index=False
        )
    )

    print()
    print("=" * 110)
    print("SELECTION SUMMARY")
    print("=" * 110)

    for horizon in HORIZONS:

        count = int(
            (
                selected[
                    "horizon_hours"
                ]
                ==
                horizon
            ).sum()
        )

        print(
            f"{horizon}H selected:",
            count,
        )

    print(
        "Total selected cases:",
        len(
            selected
        ),
    )

    print()
    print("=" * 110)
    print("OUTPUT")
    print("=" * 110)

    print(
        OUTPUT_FILE
    )

    print()
    print("=" * 110)
    print(
        "PS146 2025 VALIDATION WINDOW SELECTION COMPLETE"
    )
    print("=" * 110)


if __name__ == "__main__":
    main()