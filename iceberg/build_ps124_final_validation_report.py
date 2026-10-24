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

VALIDATION_ROOT = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps124_validation"
)

SELECTED_CASES_FILE = (
    VALIDATION_ROOT
    / "selected_cases"
    / "ps124_selected_case_definitions.csv"
)

ROUTING_SUMMARY_FILE = (
    VALIDATION_ROOT
    / "polarguard_results"
    / "ps124_ais_vs_polarguard_summary.csv"
)

ROUTE_COMPARISON_FILE = (
    VALIDATION_ROOT
    / "stage4_route_comparison"
    / "ps124_route_comparison_summary.csv"
)

ICEBERG_PROXIMITY_FILE = (
    VALIDATION_ROOT
    / "iceberg_proximity"
    / "ps124_iceberg_proximity_summary.csv"
)

OUTPUT_DIR = (
    VALIDATION_ROOT
    / "final_validation"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

FINAL_CSV = (
    OUTPUT_DIR
    / "ps124_final_validation_summary.csv"
)

FINAL_TXT = (
    OUTPUT_DIR
    / "ps124_final_validation_report.txt"
)


# ============================================================
# HELPERS
# ============================================================

def require_file(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Required validation file not found:\n{path}"
        )


def safe_pct_change(
    old_value,
    new_value,
):
    """
    Percentage reduction from old_value to new_value.
    Positive means the new value is lower.
    """
    if (
        not np.isfinite(old_value)
        or
        not np.isfinite(new_value)
        or
        old_value == 0
    ):
        return np.nan

    return (
        (old_value - new_value)
        /
        old_value
        *
        100.0
    )


def build_interpretation(row):
    """
    Create a concise, scientifically careful interpretation
    for each validation horizon.
    """

    horizon = int(
        row["horizon_hours"]
    )

    reduction = float(
        row["distance_saved_pct"]
    )

    mean_deviation = float(
        row["mean_ais_to_pg_km"]
    )

    ais_sic = float(
        row["ais_mean_sic_pct"]
    )

    pg_sic = float(
        row["pg_mean_sic_pct"]
    )

    ais_combined = float(
        row["ais_mean_combined_risk"]
    )

    pg_combined = float(
        row["pg_mean_combined_risk"]
    )

    ais_iceberg = float(
        row["ais_min_iceberg_distance_km"]
    )

    pg_iceberg = float(
        row["pg_min_iceberg_distance_km"]
    )

    statements = []

    statements.append(
        f"{horizon}h route completed successfully"
    )

    statements.append(
        f"PolarGuard route was {reduction:.1f}% shorter"
    )

    statements.append(
        f"mean geometric deviation was {mean_deviation:.1f} km"
    )

    if (
        np.isfinite(ais_sic)
        and
        np.isfinite(pg_sic)
    ):
        if pg_sic < ais_sic:
            statements.append(
                f"mean SIC decreased from "
                f"{ais_sic:.1f}% to {pg_sic:.1f}%"
            )
        else:
            statements.append(
                f"mean SIC remained similar "
                f"({ais_sic:.1f}% AIS vs "
                f"{pg_sic:.1f}% PolarGuard)"
            )

    if (
        np.isfinite(ais_combined)
        and
        np.isfinite(pg_combined)
    ):
        if pg_combined < ais_combined:
            statements.append(
                "modeled combined risk was lower"
            )
        else:
            statements.append(
                "modeled combined risk was comparable"
            )

    if (
        np.isfinite(ais_iceberg)
        and
        np.isfinite(pg_iceberg)
    ):
        statements.append(
            f"minimum iceberg clearance was "
            f"{ais_iceberg:.1f} km AIS vs "
            f"{pg_iceberg:.1f} km PolarGuard"
        )

    return "; ".join(statements) + "."


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 110)
    print("POLARGUARD")
    print("PS124 FINAL HISTORICAL VALIDATION REPORT")
    print("=" * 110)

    # --------------------------------------------------------
    # VERIFY INPUT FILES
    # --------------------------------------------------------

    for path in [
        SELECTED_CASES_FILE,
        ROUTING_SUMMARY_FILE,
        ROUTE_COMPARISON_FILE,
        ICEBERG_PROXIMITY_FILE,
    ]:
        require_file(
            path
        )

    # --------------------------------------------------------
    # LOAD DATA
    # --------------------------------------------------------

    selected = pd.read_csv(
        SELECTED_CASES_FILE
    )

    routing = pd.read_csv(
        ROUTING_SUMMARY_FILE
    )

    comparison = pd.read_csv(
        ROUTE_COMPARISON_FILE
    )

    proximity = pd.read_csv(
        ICEBERG_PROXIMITY_FILE
    )

    # --------------------------------------------------------
    # NORMALIZE HORIZONS
    # --------------------------------------------------------

    for df in [
        selected,
        routing,
        comparison,
        proximity,
    ]:
        df["horizon_hours"] = pd.to_numeric(
            df["horizon_hours"],
            errors="coerce",
        )

    # --------------------------------------------------------
    # SELECT NEEDED COLUMNS
    # --------------------------------------------------------

    selected_cols = [
        "horizon_hours",
        "initialization_date",
        "effective_duration_hours",
        "end_shortfall_minutes",
        "actual_route_distance_km",
        "direct_distance_km",
        "geometric_efficiency_pct",
        "scan_mean_sic_pct",
        "scan_max_sic_pct",
    ]

    routing_cols = [
        "horizon_hours",
        "success",
        "polarguard_distance_km",
        "distance_difference_km",
        "distance_difference_pct",
        "route_cells",
        "iceberg_hazards",
        "accumulated_cost",
    ]

    comparison_cols = [
        "horizon_hours",
        "ais_distance_km",
        "polarguard_distance_km",
        "distance_saved_km",
        "distance_saved_pct",
        "mean_ais_to_pg_km",
        "median_ais_to_pg_km",
        "p90_ais_to_pg_km",
        "max_ais_to_pg_km",
        "within_10km_pct",
        "within_25km_pct",
        "within_50km_pct",
        "symmetric_mean_deviation_km",
        "ais_mean_sic_pct",
        "pg_mean_sic_pct",
        "ais_max_sic_pct",
        "pg_max_sic_pct",
        "ais_mean_uncertainty_risk",
        "pg_mean_uncertainty_risk",
        "ais_mean_combined_risk",
        "pg_mean_combined_risk",
        "ais_max_combined_risk",
        "pg_max_combined_risk",
    ]

    proximity_cols = [
        "horizon_hours",
        "historical_icebergs",
        "ais_min_iceberg_distance_km",
        "pg_min_iceberg_distance_km",
        "ais_mean_iceberg_distance_km",
        "pg_mean_iceberg_distance_km",
        "ais_within_30km_pct",
        "pg_within_30km_pct",
        "ais_within_50km_pct",
        "pg_within_50km_pct",
        "ais_within_100km_pct",
        "pg_within_100km_pct",
    ]

    # --------------------------------------------------------
    # CHECK REQUIRED COLUMNS
    # --------------------------------------------------------

    for name, df, cols in [
        (
            "selected cases",
            selected,
            selected_cols,
        ),
        (
            "routing summary",
            routing,
            routing_cols,
        ),
        (
            "route comparison",
            comparison,
            comparison_cols,
        ),
        (
            "iceberg proximity",
            proximity,
            proximity_cols,
        ),
    ]:

        missing = [
            col
            for col in cols
            if col not in df.columns
        ]

        if missing:
            raise RuntimeError(
                f"Missing columns in {name}: "
                + ", ".join(
                    missing
                )
            )

    # --------------------------------------------------------
    # MERGE
    # --------------------------------------------------------

    final = (
        selected[
            selected_cols
        ]
        .merge(
            routing[
                routing_cols
            ],
            on="horizon_hours",
            how="left",
            suffixes=(
                "_selected",
                "_routing",
            ),
        )
        .merge(
            comparison[
                comparison_cols
            ],
            on="horizon_hours",
            how="left",
            suffixes=(
                "",
                "_comparison",
            ),
        )
        .merge(
            proximity[
                proximity_cols
            ],
            on="horizon_hours",
            how="left",
        )
    )

    final = final.sort_values(
        "horizon_hours"
    ).reset_index(
        drop=True
    )

    # --------------------------------------------------------
    # ADD DERIVED METRICS
    # --------------------------------------------------------

    final[
        "sic_change_pct_points"
    ] = (
        final[
            "pg_mean_sic_pct"
        ]
        -
        final[
            "ais_mean_sic_pct"
        ]
    )

    final[
        "combined_risk_reduction_pct"
    ] = final.apply(
        lambda row:
            safe_pct_change(
                row[
                    "ais_mean_combined_risk"
                ],
                row[
                    "pg_mean_combined_risk"
                ],
            ),
        axis=1,
    )

    final[
        "uncertainty_reduction_pct"
    ] = final.apply(
        lambda row:
            safe_pct_change(
                row[
                    "ais_mean_uncertainty_risk"
                ],
                row[
                    "pg_mean_uncertainty_risk"
                ],
            ),
        axis=1,
    )

    final[
        "iceberg_clearance_change_km"
    ] = (
        final[
            "pg_min_iceberg_distance_km"
        ]
        -
        final[
            "ais_min_iceberg_distance_km"
        ]
    )

    final[
        "validation_interpretation"
    ] = final.apply(
        build_interpretation,
        axis=1,
    )

    # --------------------------------------------------------
    # VALIDATION STATUS
    # --------------------------------------------------------

    final[
        "validation_status"
    ] = np.where(
        final[
            "success"
        ]
        ==
        True,
        "PASS",
        "FAIL",
    )

    # --------------------------------------------------------
    # SAVE DETAILED CSV
    # --------------------------------------------------------

    final.to_csv(
        FINAL_CSV,
        index=False,
    )

    # ========================================================
    # PRESENTATION TABLE
    # ========================================================

    presentation_columns = [
        "horizon_hours",
        "validation_status",
        "ais_distance_km",
        "polarguard_distance_km",
        "distance_saved_pct",
        "mean_ais_to_pg_km",
        "within_25km_pct",
        "ais_mean_sic_pct",
        "pg_mean_sic_pct",
        "ais_mean_combined_risk",
        "pg_mean_combined_risk",
        "ais_min_iceberg_distance_km",
        "pg_min_iceberg_distance_km",
    ]

    presentation = final[
        presentation_columns
    ].copy()

    # ========================================================
    # OVERALL METRICS
    # ========================================================

    successful = final[
        final[
            "validation_status"
        ]
        ==
        "PASS"
    ].copy()

    total_cases = len(
        final
    )

    successful_cases = len(
        successful
    )

    mean_distance_reduction = float(
        successful[
            "distance_saved_pct"
        ].mean()
    )

    min_distance_reduction = float(
        successful[
            "distance_saved_pct"
        ].min()
    )

    max_distance_reduction = float(
        successful[
            "distance_saved_pct"
        ].max()
    )

    mean_route_deviation = float(
        successful[
            "mean_ais_to_pg_km"
        ].mean()
    )

    mean_ais_sic = float(
        successful[
            "ais_mean_sic_pct"
        ].mean()
    )

    mean_pg_sic = float(
        successful[
            "pg_mean_sic_pct"
        ].mean()
    )

    mean_ais_combined_risk = float(
        successful[
            "ais_mean_combined_risk"
        ].mean()
    )

    mean_pg_combined_risk = float(
        successful[
            "pg_mean_combined_risk"
        ].mean()
    )

    # ========================================================
    # CONSOLE OUTPUT
    # ========================================================

    print()
    print("=" * 110)
    print("FINAL VALIDATION TABLE")
    print("=" * 110)

    print()

    print(
        presentation
        .round(3)
        .to_string(
            index=False
        )
    )

    print()
    print("=" * 110)
    print("OVERALL VALIDATION RESULTS")
    print("=" * 110)

    print(
        f"Successful routing cases       : "
        f"{successful_cases}/{total_cases}"
    )

    print(
        f"Mean distance reduction        : "
        f"{mean_distance_reduction:.2f}%"
    )

    print(
        f"Distance reduction range       : "
        f"{min_distance_reduction:.2f}% "
        f"to {max_distance_reduction:.2f}%"
    )

    print(
        f"Mean AIS -> PG deviation       : "
        f"{mean_route_deviation:.2f} km"
    )

    print(
        f"Mean AIS SIC across cases      : "
        f"{mean_ais_sic:.2f}%"
    )

    print(
        f"Mean PolarGuard SIC            : "
        f"{mean_pg_sic:.2f}%"
    )

    print(
        f"Mean AIS combined risk         : "
        f"{mean_ais_combined_risk:.4f}"
    )

    print(
        f"Mean PolarGuard combined risk  : "
        f"{mean_pg_combined_risk:.4f}"
    )

    # ========================================================
    # TEXT REPORT
    # ========================================================

    report_lines = []

    report_lines.append(
        "POLARGUARD PS124 HISTORICAL VALIDATION REPORT"
    )

    report_lines.append(
        "=" * 70
    )

    report_lines.append("")

    report_lines.append(
        "Validation source:"
    )

    report_lines.append(
        "Historical RV Polarstern PS124 AIS trajectory "
        "with historical PolarGuard sea-ice, uncertainty, "
        "iceberg and vessel-constrained routing."
    )

    report_lines.append("")

    report_lines.append(
        f"Successful cases: "
        f"{successful_cases}/{total_cases}"
    )

    report_lines.append(
        f"Mean modeled route-distance reduction: "
        f"{mean_distance_reduction:.2f}%"
    )

    report_lines.append(
        f"Reduction range: "
        f"{min_distance_reduction:.2f}% - "
        f"{max_distance_reduction:.2f}%"
    )

    report_lines.append(
        f"Mean AIS-to-PolarGuard geometric deviation: "
        f"{mean_route_deviation:.2f} km"
    )

    report_lines.append("")

    report_lines.append(
        "HORIZON RESULTS"
    )

    report_lines.append(
        "-" * 70
    )

    for _, row in final.iterrows():

        report_lines.append("")

        report_lines.append(
            f"{int(row['horizon_hours'])}H"
        )

        report_lines.append(
            f"Initialization: "
            f"{row['initialization_date']}"
        )

        report_lines.append(
            f"AIS distance: "
            f"{row['ais_distance_km']:.2f} km"
        )

        report_lines.append(
            f"PolarGuard distance: "
            f"{row['polarguard_distance_km']:.2f} km"
        )

        report_lines.append(
            f"Distance reduction: "
            f"{row['distance_saved_pct']:.2f}%"
        )

        report_lines.append(
            f"Mean route deviation: "
            f"{row['mean_ais_to_pg_km']:.2f} km"
        )

        report_lines.append(
            f"AIS mean SIC: "
            f"{row['ais_mean_sic_pct']:.2f}%"
        )

        report_lines.append(
            f"PolarGuard mean SIC: "
            f"{row['pg_mean_sic_pct']:.2f}%"
        )

        report_lines.append(
            f"AIS mean combined risk: "
            f"{row['ais_mean_combined_risk']:.4f}"
        )

        report_lines.append(
            f"PolarGuard mean combined risk: "
            f"{row['pg_mean_combined_risk']:.4f}"
        )

        report_lines.append(
            f"AIS minimum iceberg distance: "
            f"{row['ais_min_iceberg_distance_km']:.2f} km"
        )

        report_lines.append(
            f"PolarGuard minimum iceberg distance: "
            f"{row['pg_min_iceberg_distance_km']:.2f} km"
        )

        report_lines.append(
            "Interpretation: "
            +
            row[
                "validation_interpretation"
            ]
        )

    report_lines.append("")

    report_lines.append(
        "=" * 70
    )

    report_lines.append(
        "INTERPRETATION LIMITATION"
    )

    report_lines.append(
        "=" * 70
    )

    report_lines.append("")

    report_lines.append(
        "These results compare PolarGuard-generated feasible "
        "routes with recorded historical AIS trajectories "
        "between matched start and destination locations."
    )

    report_lines.append(
        "A shorter modeled route should not be interpreted "
        "as proof that the historical vessel route was "
        "incorrect or inefficient."
    )

    report_lines.append(
        "The real Polarstern trajectory may include scientific "
        "operations, station keeping, maneuvering requirements, "
        "weather information, operational decisions, and other "
        "constraints not represented by this prototype."
    )

    report_lines.append("")

    report_lines.append(
        "The validation demonstrates end-to-end historical "
        "route generation and comparison under PolarGuard's "
        "modeled sea-ice, uncertainty, iceberg, and vessel "
        "constraint framework."
    )

    FINAL_TXT.write_text(
        "\n".join(
            report_lines
        ),
        encoding="utf-8",
    )

    # ========================================================
    # OUTPUT
    # ========================================================

    print()
    print("=" * 110)
    print("FILES CREATED")
    print("=" * 110)

    print(
        FINAL_CSV
    )

    print(
        FINAL_TXT
    )

    print()
    print("=" * 110)
    print(
        "FINAL PS124 VALIDATION REPORT COMPLETE"
    )
    print("=" * 110)


if __name__ == "__main__":
    main()