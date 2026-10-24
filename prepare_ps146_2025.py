from pathlib import Path
import pandas as pd


BASE = Path(__file__).resolve().parent

INPUT_FILE = (
    BASE
    / "data"
    / "ais"
    / "polarstern_ps146_2025"
    / "PS146_mastertrack.tab"
)

OUTPUT_DIR = (
    BASE
    / "data"
    / "ais"
    / "polarstern_ps146_2025"
    / "analysis"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "polarstern_ps146_2025_cleaned_track.csv"
)


def main():

    print("=" * 90)
    print("POLARGUARD")
    print("POLARSTERN PS146 2025 TRACK PREPARATION")
    print("=" * 90)

    # PANGAEA .tab file has a metadata block between /* and */
    # Pandas can skip comment lines beginning with /
    # but the metadata contains many non-tabular lines,
    # so we detect the header manually.

    with INPUT_FILE.open(
        "r",
        encoding="utf-8",
        errors="replace",
    ) as f:

        lines = f.readlines()

    header_index = None

    for i, line in enumerate(lines):

        if (
            line.startswith("Date/Time")
            and
            "Latitude" in line
            and
            "Longitude" in line
        ):

            header_index = i
            break

    if header_index is None:

        raise RuntimeError(
            "Could not find PS146 table header."
        )

    df = pd.read_csv(
        INPUT_FILE,
        sep="\t",
        skiprows=header_index,
    )

    required = [
        "Date/Time",
        "Latitude",
        "Longitude",
    ]

    missing = [
        col
        for col in required
        if col not in df.columns
    ]

    if missing:

        raise RuntimeError(
            "Missing expected columns: "
            +
            ", ".join(missing)
        )

    df = df.rename(
        columns={
            "Date/Time":
                "timestamp",

            "Latitude":
                "lat",

            "Longitude":
                "lon",

            "Speed [kn]":
                "speed_kn",

            "Course [deg]":
                "course_deg",
        }
    )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        utc=True,
        errors="coerce",
    )

    df["lat"] = pd.to_numeric(
        df["lat"],
        errors="coerce",
    )

    df["lon"] = pd.to_numeric(
        df["lon"],
        errors="coerce",
    )

    if "speed_kn" in df.columns:

        df["speed_kn"] = pd.to_numeric(
            df["speed_kn"],
            errors="coerce",
        )

    if "course_deg" in df.columns:

        df["course_deg"] = pd.to_numeric(
            df["course_deg"],
            errors="coerce",
        )

    df = df.dropna(
        subset=[
            "timestamp",
            "lat",
            "lon",
        ]
    ).copy()

    # --------------------------------------------------------
    # KEEP ONLY 2025
    # --------------------------------------------------------

    df = df[
        df["timestamp"].dt.year
        ==
        2025
    ].copy()

    df = df.sort_values(
        "timestamp"
    ).reset_index(
        drop=True
    )

    if df.empty:

        raise RuntimeError(
            "No 2025 PS146 observations found."
        )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print()
    print(
        f"Rows: {len(df):,}"
    )

    print(
        "Start:",
        df[
            "timestamp"
        ].iloc[0],
    )

    print(
        "End:",
        df[
            "timestamp"
        ].iloc[-1],
    )

    print()

    print(
        f"Latitude range: "
        f"{df['lat'].min():.4f} "
        f"to {df['lat'].max():.4f}"
    )

    print(
        f"Longitude range: "
        f"{df['lon'].min():.4f} "
        f"to {df['lon'].max():.4f}"
    )

    if "speed_kn" in df.columns:

        print(
            f"Speed range: "
            f"{df['speed_kn'].min():.2f} "
            f"to {df['speed_kn'].max():.2f} kn"
        )

    print()
    print("=" * 90)
    print("FIRST 5 ROWS")
    print("=" * 90)

    print(
        df.head()
        .to_string(
            index=False
        )
    )

    print()
    print("=" * 90)
    print("LAST 5 ROWS")
    print("=" * 90)

    print(
        df.tail()
        .to_string(
            index=False
        )
    )

    print()
    print("=" * 90)
    print("OUTPUT")
    print("=" * 90)

    print(
        OUTPUT_FILE
    )

    print()
    print("=" * 90)
    print("PS146 2025 TRACK PREPARATION COMPLETE")
    print("=" * 90)


if __name__ == "__main__":
    main()