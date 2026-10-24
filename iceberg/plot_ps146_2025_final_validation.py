from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent.parent

if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


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

COMPARISON_FILE = (
    VALIDATION_ROOT
    / "stage4_route_comparison"
    / "ps146_2025_route_comparison_summary.csv"
)

SUCCESS_FILE = (
    VALIDATION_ROOT
    / "stage4_route_comparison"
    / "ps146_2025_successful_route_comparisons.csv"
)

FROZEN_CASES_FILE = (
    VALIDATION_ROOT
    / "selected_cases"
    / "ps146_2025_frozen_case_definitions.csv"
)

POLARGUARD_DIR = (
    VALIDATION_ROOT
    / "polarguard_results"
)

OUTPUT_DIR = (
    VALIDATION_ROOT
    / "final_validation_figures"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# SETTINGS
# ============================================================

DPI = 220


# ============================================================
# HELPERS
# ============================================================

def save_figure(
    fig,
    filename,
):

    output_file = (
        OUTPUT_DIR
        /
        filename
    )

    fig.savefig(
        output_file,
        dpi=DPI,
        bbox_inches="tight",
    )

    plt.close(
        fig
    )

    print(
        "Saved:",
        output_file,
    )


def clean_case_label(
    case_id,
):

    return (
        str(case_id)
        .replace(
            "PS146_2025_",
            "",
        )
        .replace(
            "_",
            " ",
        )
    )


# ============================================================
# FIGURE 1
# DISTANCE REDUCTION
# ============================================================

def plot_distance_reduction(
    successful,
):

    data = successful.copy()

    data = data.sort_values(
        [
            "horizon_hours",
            "case_id",
        ]
    )

    labels = [
        clean_case_label(
            x
        )
        for x in data[
            "case_id"
        ]
    ]

    values = (
        data[
            "distance_saved_pct"
        ]
        .to_numpy(
            dtype=float
        )
    )

    fig, ax = plt.subplots(
        figsize=(
            12,
            6,
        )
    )

    x = np.arange(
        len(
            data
        )
    )

    bars = ax.bar(
        x,
        values,
    )

    ax.axhline(
        0.0,
        linewidth=1.2,
    )

    ax.set_xticks(
        x
    )

    ax.set_xticklabels(
        labels,
        rotation=45,
        ha="right",
    )

    ax.set_ylabel(
        "Modeled Distance Reduction (%)"
    )

    ax.set_xlabel(
        "PS146 2025 Validation Case"
    )

    ax.set_title(
        "PolarGuard vs Actual AIS Route Distance\n"
        "PS146 2025 Frozen Validation Cases"
    )

    ax.grid(
        axis="y",
        alpha=0.25,
    )

    for bar, value in zip(
        bars,
        values,
    ):

        y = (
            value
            +
            1.0
            if value >= 0
            else
            value
            -
            2.5
        )

        ax.text(
            bar.get_x()
            +
            bar.get_width()
            /
            2.0,
            y,
            f"{value:.1f}%",
            ha="center",
            va=(
                "bottom"
                if value >= 0
                else
                "top"
            ),
            fontsize=9,
        )

    fig.tight_layout()

    save_figure(
        fig,
        "01_distance_reduction_by_case.png",
    )


# ============================================================
# FIGURE 2
# ACTUAL SIC AIS VS POLARGUARD
# ============================================================

def plot_actual_sic(
    successful,
):

    data = successful.copy()

    data = data.sort_values(
        [
            "horizon_hours",
            "case_id",
        ]
    )

    labels = [
        clean_case_label(
            x
        )
        for x in data[
            "case_id"
        ]
    ]

    ais = (
        data[
            "ais_actual_mean_sic_pct"
        ]
        .to_numpy(
            dtype=float
        )
    )

    pg = (
        data[
            "pg_actual_mean_sic_pct"
        ]
        .to_numpy(
            dtype=float
        )
    )

    x = np.arange(
        len(
            data
        )
    )

    width = 0.38

    fig, ax = plt.subplots(
        figsize=(
            13,
            6.5,
        )
    )

    ax.bar(
        x
        -
        width / 2,
        ais,
        width,
        label="Actual AIS Route",
    )

    ax.bar(
        x
        +
        width / 2,
        pg,
        width,
        label="PolarGuard Route",
    )

    ax.set_xticks(
        x
    )

    ax.set_xticklabels(
        labels,
        rotation=45,
        ha="right",
    )

    ax.set_ylabel(
        "Observed Mean Sea-Ice Concentration (%)"
    )

    ax.set_xlabel(
        "PS146 2025 Validation Case"
    )

    ax.set_title(
        "Observed 2025 Sea-Ice Exposure\n"
        "Actual AIS Route vs PolarGuard Recommended Route"
    )

    ax.legend()

    ax.grid(
        axis="y",
        alpha=0.25,
    )

    fig.tight_layout()

    save_figure(
        fig,
        "02_actual_sic_ais_vs_polarguard.png",
    )


# ============================================================
# FIGURE 3
# ICEBERG CLEARANCE
# ============================================================

def plot_iceberg_clearance(
    successful,
):

    data = successful.copy()

    data = data.sort_values(
        [
            "horizon_hours",
            "case_id",
        ]
    )

    labels = [
        clean_case_label(
            x
        )
        for x in data[
            "case_id"
        ]
    ]

    ais = (
        data[
            "ais_min_iceberg_distance_km"
        ]
        .to_numpy(
            dtype=float
        )
    )

    pg = (
        data[
            "pg_min_iceberg_distance_km"
        ]
        .to_numpy(
            dtype=float
        )
    )

    x = np.arange(
        len(
            data
        )
    )

    width = 0.38

    fig, ax = plt.subplots(
        figsize=(
            13,
            6.5,
        )
    )

    ax.bar(
        x
        -
        width / 2,
        ais,
        width,
        label="Actual AIS Route",
    )

    ax.bar(
        x
        +
        width / 2,
        pg,
        width,
        label="PolarGuard Route",
    )

    ax.set_xticks(
        x
    )

    ax.set_xticklabels(
        labels,
        rotation=45,
        ha="right",
    )

    ax.set_ylabel(
        "Minimum Distance to Historical Iceberg (km)"
    )

    ax.set_xlabel(
        "PS146 2025 Validation Case"
    )

    ax.set_title(
        "Historical Iceberg Clearance\n"
        "Actual AIS Route vs PolarGuard Route"
    )

    ax.legend()

    ax.grid(
        axis="y",
        alpha=0.25,
    )

    fig.tight_layout()

    save_figure(
        fig,
        "03_iceberg_clearance_comparison.png",
    )


# ============================================================
# FIGURE 4
# ROUTE DEVIATION
# ============================================================

def plot_route_deviation(
    successful,
):

    data = successful.copy()

    data = data.sort_values(
        [
            "horizon_hours",
            "case_id",
        ]
    )

    labels = [
        clean_case_label(
            x
        )
        for x in data[
            "case_id"
        ]
    ]

    mean_dev = (
        data[
            "mean_ais_to_pg_km"
        ]
        .to_numpy(
            dtype=float
        )
    )

    p90_dev = (
        data[
            "p90_ais_to_pg_km"
        ]
        .to_numpy(
            dtype=float
        )
    )

    x = np.arange(
        len(
            data
        )
    )

    width = 0.38

    fig, ax = plt.subplots(
        figsize=(
            13,
            6.5,
        )
    )

    ax.bar(
        x
        -
        width / 2,
        mean_dev,
        width,
        label="Mean Deviation",
    )

    ax.bar(
        x
        +
        width / 2,
        p90_dev,
        width,
        label="P90 Deviation",
    )

    ax.set_xticks(
        x
    )

    ax.set_xticklabels(
        labels,
        rotation=45,
        ha="right",
    )

    ax.set_ylabel(
        "Distance (km)"
    )

    ax.set_xlabel(
        "PS146 2025 Validation Case"
    )

    ax.set_title(
        "Geometric Deviation Between Actual AIS "
        "and PolarGuard Routes"
    )

    ax.legend()

    ax.grid(
        axis="y",
        alpha=0.25,
    )

    fig.tight_layout()

    save_figure(
        fig,
        "04_route_deviation_by_case.png",
    )


# ============================================================
# FIGURE 5
# WITHIN 25 KM
# ============================================================

def plot_route_similarity(
    successful,
):

    data = successful.copy()

    data = data.sort_values(
        [
            "horizon_hours",
            "case_id",
        ]
    )

    labels = [
        clean_case_label(
            x
        )
        for x in data[
            "case_id"
        ]
    ]

    values = (
        data[
            "within_25km_pct"
        ]
        .to_numpy(
            dtype=float
        )
    )

    fig, ax = plt.subplots(
        figsize=(
            12,
            6,
        )
    )

    x = np.arange(
        len(
            data
        )
    )

    bars = ax.bar(
        x,
        values,
    )

    ax.set_ylim(
        0,
        105,
    )

    ax.set_xticks(
        x
    )

    ax.set_xticklabels(
        labels,
        rotation=45,
        ha="right",
    )

    ax.set_ylabel(
        "AIS Points Within 25 km of PolarGuard Route (%)"
    )

    ax.set_xlabel(
        "PS146 2025 Validation Case"
    )

    ax.set_title(
        "Actual AIS vs PolarGuard Route Similarity"
    )

    ax.grid(
        axis="y",
        alpha=0.25,
    )

    for bar, value in zip(
        bars,
        values,
    ):

        ax.text(
            bar.get_x()
            +
            bar.get_width()
            /
            2.0,
            value
            +
            2.0,
            f"{value:.0f}%",
            ha="center",
            fontsize=9,
        )

    fig.tight_layout()

    save_figure(
        fig,
        "05_route_similarity_within_25km.png",
    )


# ============================================================
# FIGURE 6
# OUTCOME — 15 FROZEN CASES
# ============================================================

def plot_validation_outcomes(
    summary,
):

    total = len(
        summary
    )

    success_count = int(
        summary[
            "routing_success"
        ]
        .fillna(
            False
        )
        .astype(
            bool
        )
        .sum()
    )

    rejected_count = (
        total
        -
        success_count
    )

    values = [
        success_count,
        rejected_count,
    ]

    labels = [
        "Feasible Routes",
        "Safety-Rejected / Failed",
    ]

    fig, ax = plt.subplots(
        figsize=(
            8,
            6,
        )
    )

    bars = ax.bar(
        labels,
        values,
    )

    ax.set_ylabel(
        "Number of Frozen Cases"
    )

    ax.set_title(
        "PS146 2025 PolarGuard Validation Outcomes\n"
        f"{total} Frozen Independent Cases"
    )

    ax.set_ylim(
        0,
        max(
            values
        )
        +
        3,
    )

    ax.grid(
        axis="y",
        alpha=0.25,
    )

    for bar, value in zip(
        bars,
        values,
    ):

        percentage = (
            value
            /
            total
            *
            100.0
            if total > 0
            else 0.0
        )

        ax.text(
            bar.get_x()
            +
            bar.get_width()
            /
            2.0,
            value
            +
            0.25,
            f"{value}/{total}\n({percentage:.1f}%)",
            ha="center",
            va="bottom",
            fontsize=11,
        )

    fig.tight_layout()

    save_figure(
        fig,
        "06_validation_outcomes.png",
    )


# ============================================================
# FIGURE 7
# FORECAST VS OBSERVED SIC ON POLARGUARD ROUTE
# ============================================================

def plot_predicted_vs_actual_pg_sic(
    successful,
):

    data = successful.copy()

    actual = (
        data[
            "pg_actual_mean_sic_pct"
        ]
        .to_numpy(
            dtype=float
        )
    )

    predicted = (
        data[
            "pg_predicted_mean_sic_pct"
        ]
        .to_numpy(
            dtype=float
        )
    )

    fig, ax = plt.subplots(
        figsize=(
            7,
            7,
        )
    )

    ax.scatter(
        actual,
        predicted,
        s=70,
    )

    valid = (
        np.isfinite(
            actual
        )
        &
        np.isfinite(
            predicted
        )
    )

    if np.any(
        valid
    ):

        maximum = max(
            float(
                np.nanmax(
                    actual[
                        valid
                    ]
                )
            ),
            float(
                np.nanmax(
                    predicted[
                        valid
                    ]
                )
            ),
            1.0,
        )

        ax.plot(
            [
                0,
                maximum,
            ],
            [
                0,
                maximum,
            ],
            linestyle="--",
            linewidth=1.5,
            label="Perfect forecast",
        )

    for _, row in data.iterrows():

        ax.annotate(
            clean_case_label(
                row[
                    "case_id"
                ]
            ),
            (
                row[
                    "pg_actual_mean_sic_pct"
                ],
                row[
                    "pg_predicted_mean_sic_pct"
                ],
            ),
            xytext=(
                4,
                4,
            ),
            textcoords="offset points",
            fontsize=8,
        )

    ax.set_xlabel(
        "Observed Mean SIC on PolarGuard Route (%)"
    )

    ax.set_ylabel(
        "Predicted Mean SIC on PolarGuard Route (%)"
    )

    ax.set_title(
        "PolarGuard Sea-Ice Forecast\n"
        "Predicted vs Subsequently Observed Route SIC"
    )

    ax.legend()

    ax.grid(
        alpha=0.25,
    )

    fig.tight_layout()

    save_figure(
        fig,
        "07_predicted_vs_observed_pg_sic.png",
    )


# ============================================================
# FIGURE 8
# REPRESENTATIVE ROUTE MAPS
# ============================================================

def plot_route_map(
    case,
):

    case_id = str(
        case[
            "case_id"
        ]
    )

    ais_file = Path(
        case[
            "route_file"
        ]
    )

    pg_file = (
        POLARGUARD_DIR
        /
        f"{case_id}_polarguard_route.csv"
    )

    if not ais_file.exists():

        print(
            "AIS route missing:",
            ais_file,
        )

        return

    if not pg_file.exists():

        print(
            "PolarGuard route missing:",
            pg_file,
        )

        return

    ais = pd.read_csv(
        ais_file
    )

    pg = pd.read_csv(
        pg_file
    )

    fig, ax = plt.subplots(
        figsize=(
            9,
            8,
        )
    )

    ax.plot(
        ais[
            "lon"
        ],
        ais[
            "lat"
        ],
        linewidth=2.3,
        label="Actual Polarstern AIS",
    )

    ax.plot(
        pg[
            "longitude"
        ],
        pg[
            "latitude"
        ],
        linewidth=2.8,
        label="PolarGuard Route",
    )

    ax.scatter(
        [
            float(
                case[
                    "start_longitude"
                ]
            )
        ],
        [
            float(
                case[
                    "start_latitude"
                ]
            )
        ],
        s=90,
        marker="o",
        label="Start",
        zorder=5,
    )

    ax.scatter(
        [
            float(
                case[
                    "destination_longitude"
                ]
            )
        ],
        [
            float(
                case[
                    "destination_latitude"
                ]
            )
        ],
        s=110,
        marker="*",
        label="Destination",
        zorder=5,
    )

    ax.set_xlabel(
        "Longitude"
    )

    ax.set_ylabel(
        "Latitude"
    )

    ax.set_title(
        f"{case_id}\n"
        f"{int(case['horizon_hours'])}h "
        "Actual AIS vs PolarGuard"
    )

    ax.legend()

    ax.grid(
        alpha=0.25,
    )

    fig.tight_layout()

    save_figure(
        fig,
        f"route_map_{case_id}.png",
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 110)
    print("POLARGUARD")
    print(
        "PS146 2025 FINAL VALIDATION VISUALIZATION"
    )
    print("=" * 110)

    summary = pd.read_csv(
        COMPARISON_FILE
    )

    successful = pd.read_csv(
        SUCCESS_FILE
    )

    frozen = pd.read_csv(
        FROZEN_CASES_FILE
    )

    # Ensure correct bool interpretation
    summary[
        "routing_success"
    ] = (
        summary[
            "routing_success"
        ]
        .astype(
            str
        )
        .str.lower()
        .map(
            {
                "true":
                    True,

                "false":
                    False,
            }
        )
        .fillna(
            False
        )
    )

    print()
    print(
        "Frozen cases:",
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

    print()

    # ========================================================
    # AGGREGATE FIGURES
    # ========================================================

    plot_distance_reduction(
        successful
    )

    plot_actual_sic(
        successful
    )

    plot_iceberg_clearance(
        successful
    )

    plot_route_deviation(
        successful
    )

    plot_route_similarity(
        successful
    )

    plot_validation_outcomes(
        summary
    )

    plot_predicted_vs_actual_pg_sic(
        successful
    )

    # ========================================================
    # REPRESENTATIVE ROUTE MAPS
    #
    # Chosen from successful cases:
    # 24h C5 = safety trade-off example
    # 48h C3 = strong mid-horizon case
    # 72h C4 = strong long-horizon case
    # 72h C5 = largest modeled distance reduction
    # ========================================================

    representative_cases = [
        "PS146_2025_24H_C5",
        "PS146_2025_48H_C3",
        "PS146_2025_72H_C4",
        "PS146_2025_72H_C5",
    ]

    for case_id in representative_cases:

        match = frozen[
            frozen[
                "case_id"
            ]
            ==
            case_id
        ]

        if match.empty:

            print(
                "Frozen case not found:",
                case_id,
            )

            continue

        plot_route_map(
            match.iloc[
                0
            ]
        )

    # ========================================================
    # FINAL TEXT SUMMARY
    # ========================================================

    mean_distance_reduction = (
        successful[
            "distance_saved_pct"
        ]
        .mean()
    )

    median_distance_reduction = (
        successful[
            "distance_saved_pct"
        ]
        .median()
    )

    mean_ais_sic = (
        successful[
            "ais_actual_mean_sic_pct"
        ]
        .mean()
    )

    mean_pg_sic = (
        successful[
            "pg_actual_mean_sic_pct"
        ]
        .mean()
    )

    mean_deviation = (
        successful[
            "mean_ais_to_pg_km"
        ]
        .mean()
    )

    print()
    print("=" * 110)
    print("FINAL VALIDATION METRICS")
    print("=" * 110)

    print(
        f"Successful routes              : "
        f"{len(successful)}/{len(summary)}"
    )

    print(
        f"Mean modeled distance reduction: "
        f"{mean_distance_reduction:.2f}%"
    )

    print(
        f"Median distance reduction      : "
        f"{median_distance_reduction:.2f}%"
    )

    print(
        f"Mean AIS -> PG deviation       : "
        f"{mean_deviation:.2f} km"
    )

    print(
        f"Mean observed AIS SIC          : "
        f"{mean_ais_sic:.2f}%"
    )

    print(
        f"Mean observed PolarGuard SIC   : "
        f"{mean_pg_sic:.2f}%"
    )

    if (
        np.isfinite(
            mean_ais_sic
        )
        and
        mean_ais_sic > 0
    ):

        relative_sic_reduction = (
            (
                mean_ais_sic
                -
                mean_pg_sic
            )
            /
            mean_ais_sic
            *
            100.0
        )

        print(
            f"Relative observed SIC reduction: "
            f"{relative_sic_reduction:.2f}%"
        )

    print()
    print("=" * 110)
    print("FIGURES CREATED")
    print("=" * 110)

    for file in sorted(
        OUTPUT_DIR.glob(
            "*.png"
        )
    ):

        print(
            file
        )

    print()
    print("=" * 110)
    print(
        "PS146 2025 FINAL VALIDATION VISUALIZATION COMPLETE"
    )
    print("=" * 110)


if __name__ == "__main__":
    main()