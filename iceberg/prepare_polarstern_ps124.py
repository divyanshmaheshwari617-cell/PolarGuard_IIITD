from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    BASE
    / "data"
    / "ais"
    / "polarstern_ps124_2021"
    / "PS124_mastertrack_generalized.txt"
)

OUTPUT_DIR = (
    BASE
    / "data"
    / "ais"
    / "polarstern_ps124_2021"
    / "analysis"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "polarstern_ps124_cleaned_track.csv"
)


def main():

    print("=" * 90)
    print("POLARGUARD")
    print("POLARSTERN PS124 TRACK PREPARATION")
    print("=" * 90)

    df = pd.read_csv(
        INPUT_FILE,
        sep="\t",
        usecols=[
            "Date/Time (UTC)",
            "Latitude",
            "Longitude",
        ],
    )

    df = df.rename(
        columns={
            "Date/Time (UTC)": "timestamp",
            "Latitude": "lat",
            "Longitude": "lon",
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

    df = (
        df
        .dropna(
            subset=[
                "timestamp",
                "lat",
                "lon",
            ]
        )
        .drop_duplicates(
            subset=[
                "timestamp",
                "lat",
                "lon",
            ]
        )
        .sort_values(
            "timestamp"
        )
        .reset_index(
            drop=True
        )
    )

    print()
    print(
        "Rows:",
        f"{len(df):,}",
    )

    print(
        "Start:",
        df["timestamp"].min(),
    )

    print(
        "End:",
        df["timestamp"].max(),
    )

    print()
    print(
        "Latitude range:",
        f"{df['lat'].min():.4f}",
        "to",
        f"{df['lat'].max():.4f}",
    )

    print(
        "Longitude range:",
        f"{df['lon'].min():.4f}",
        "to",
        f"{df['lon'].max():.4f}",
    )

    print()
    print("FIRST 5 ROWS")
    print("-" * 90)

    print(
        df.head(5).to_string(
            index=False
        )
    )

    print()
    print("LAST 5 ROWS")
    print("-" * 90)

    print(
        df.tail(5).to_string(
            index=False
        )
    )

    df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print()
    print("=" * 90)
    print("OUTPUT")
    print("=" * 90)

    print(OUTPUT_FILE)

    print()
    print("=" * 90)
    print("PS124 PREPARATION COMPLETE")
    print("=" * 90)


if __name__ == "__main__":
    main()