from pathlib import Path
import sys
import io

BASE = Path(__file__).resolve().parent.parent

if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt

from pyproj import Transformer

from sea_ice_service import predict_sea_ice


# ============================================================
# CONFIGURATION
# ============================================================

HORIZONS = [24, 48, 72]

SEA_ICE_HISTORY_FILE = (
    BASE
    / "data"
    / "processed"
    / "sea_ice_2019_2025.nc"
)

MEMBER2_FILE = (
    BASE
    / "iceberg"
    / "data"
    / "processed"
    / "iceberg_features_environment_ml_ready_2019_2025.csv"
)

CASE_DIR = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps124_validation"
    / "selected_cases"
)

CASE_DEFINITION_FILE = (
    CASE_DIR
    / "ps124_selected_case_definitions.csv"
)

POLARGUARD_DIR = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps124_validation"
    / "polarguard_results"
)

OUTPUT_DIR = (
    BASE
    / "iceberg"
    / "outputs"
    / "ais_route_validation"
    / "ps124_validation"
    / "validation_maps"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# MEMBER 1 FORECAST
# ============================================================

def load_member1_forecast(
    initialization_date,
    horizon,
):
    """
    Load the historical Member-1 state and generate
    the requested 24h / 48h / 72h SIC forecast.
    """

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
            f"No Member-1 history for "
            f"{initialization_date}"
        )

    idx = int(
        matches[0]
    )

    if idx < 3:
        raise RuntimeError(
            "Insufficient previous sea-ice maps."
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
        date=target_date,
    )

    sic = np.asarray(
        forecasts[
            f"{horizon}h"
        ],
        dtype=float,
    )

    try:
        ds.close()
    except Exception:
        pass

    return (
        sic,
        x,
        y,
    )


# ============================================================
# GRID -> LAT/LON
# ============================================================

def grid_to_latlon(
    x,
    y,
):
    """
    Convert the EPSG:3412 Member-1 grid to WGS84.
    """

    x_grid, y_grid = np.meshgrid(
        np.asarray(
            x,
            dtype=float,
        ),
        np.asarray(
            y,
            dtype=float,
        ),
    )

    transformer = Transformer.from_crs(
        "EPSG:3412",
        "EPSG:4326",
        always_xy=True,
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
# HISTORICAL ICEBERGS
# ============================================================

def load_historical_icebergs(
    initialization_date,
    horizon,
):
    """
    Load historical Member-2 iceberg positions for the
    same initialization date and forecast horizon.
    """

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

    lat_col = (
        f"true_lat_{horizon}h"
    )

    lon_col = (
        f"true_lon_{horizon}h"
    )

    if (
        lat_col not in rows.columns
        or
        lon_col not in rows.columns
    ):
        raise RuntimeError(
            f"Missing Member-2 columns: "
            f"{lat_col}, {lon_col}"
        )

    rows[lat_col] = pd.to_numeric(
        rows[lat_col],
        errors="coerce",
    )

    rows[lon_col] = pd.to_numeric(
        rows[lon_col],
        errors="coerce",
    )

    rows = rows[
        np.isfinite(
            rows[lat_col]
        )
        &
        np.isfinite(
            rows[lon_col]
        )
    ].copy()

    return pd.DataFrame(
        {
            "iceberg_id":
                rows[
                    "iceberg_id"
                ].astype(str),

            "lat":
                rows[
                    lat_col
                ].astype(float),

            "lon":
                rows[
                    lon_col
                ].astype(float),
        }
    )


# ============================================================
# ROUTE LOADER
# ============================================================

def load_route(
    path,
):
    """
    Load AIS or PolarGuard route and normalize coordinates
    to columns named lat / lon.
    """

    if not path.exists():
        raise FileNotFoundError(
            path
        )

    df = pd.read_csv(
        path
    )

    df = df.rename(
        columns={
            "latitude": "lat",
            "longitude": "lon",
        }
    )

    if (
        "lat" not in df.columns
        or
        "lon" not in df.columns
    ):
        raise RuntimeError(
            f"Route file missing lat/lon: "
            f"{path}"
        )

    df["lat"] = pd.to_numeric(
        df["lat"],
        errors="coerce",
    )

    df["lon"] = pd.to_numeric(
        df["lon"],
        errors="coerce",
    )

    df = df[
        np.isfinite(
            df["lat"]
        )
        &
        np.isfinite(
            df["lon"]
        )
    ].copy()

    df = df.reset_index(
        drop=True
    )

    if df.empty:
        raise RuntimeError(
            f"Route contains no valid coordinates: "
            f"{path}"
        )

    return df


# ============================================================
# MAP BOUNDS
# ============================================================

def calculate_bounds(
    ais,
    pg,
):
    """
    Calculate plotting limits using AIS and PolarGuard routes.

    Icebergs are deliberately NOT used to set the extent because
    distant historical icebergs would make the route unreadably
    small on the map.
    """

    route_lat = np.concatenate(
        [
            ais["lat"].to_numpy(
                dtype=float
            ),
            pg["lat"].to_numpy(
                dtype=float
            ),
        ]
    )

    route_lon = np.concatenate(
        [
            ais["lon"].to_numpy(
                dtype=float
            ),
            pg["lon"].to_numpy(
                dtype=float
            ),
        ]
    )

    lat_min = float(
        np.nanmin(
            route_lat
        )
    )

    lat_max = float(
        np.nanmax(
            route_lat
        )
    )

    lon_min = float(
        np.nanmin(
            route_lon
        )
    )

    lon_max = float(
        np.nanmax(
            route_lon
        )
    )

    lat_span = (
        lat_max
        -
        lat_min
    )

    lon_span = (
        lon_max
        -
        lon_min
    )

    lat_margin = max(
        0.8,
        lat_span * 0.35,
    )

    lon_margin = max(
        1.5,
        lon_span * 0.35,
    )

    return (
        lon_min - lon_margin,
        lon_max + lon_margin,
        lat_min - lat_margin,
        lat_max + lat_margin,
    )


# ============================================================
# ICEBERGS INSIDE MAP WINDOW
# ============================================================

def icebergs_in_bounds(
    icebergs,
    lon_min,
    lon_max,
    lat_min,
    lat_max,
):
    """
    Only plot historical icebergs close enough to appear
    inside the current route map.
    """

    if icebergs.empty:
        return icebergs.copy()

    return icebergs[
        (
            icebergs["lon"]
            >=
            lon_min
        )
        &
        (
            icebergs["lon"]
            <=
            lon_max
        )
        &
        (
            icebergs["lat"]
            >=
            lat_min
        )
        &
        (
            icebergs["lat"]
            <=
            lat_max
        )
    ].copy()


# ============================================================
# SAFE FIGURE SAVE
# ============================================================

def save_figure_safely(
    fig,
    output_file,
):
    """
    Save the PNG through memory first.

    This avoids handing the Path object directly to PIL and
    makes Windows file-save behaviour more predictable.
    """

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = Path(
        output_file
    )

    buffer = io.BytesIO()

    fig.savefig(
        buffer,
        format="png",
        dpi=220,
        bbox_inches="tight",
    )

    buffer.seek(0)

    png_bytes = buffer.read()

    buffer.close()

    try:
        output_file.write_bytes(
            png_bytes
        )

        return output_file

    except OSError as exc:
        print()
        print(
            "WARNING: Could not save to primary "
            "validation_maps directory."
        )

        print(
            "Reason:",
            exc,
        )

        fallback_dir = (
            BASE
            / "ps124_validation_maps"
        )

        fallback_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        fallback_file = (
            fallback_dir
            /
            output_file.name
        )

        fallback_file.write_bytes(
            png_bytes
        )

        print(
            "Used fallback location:",
            fallback_file,
        )

        return fallback_file


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 105)
    print("POLARGUARD")
    print("PS124 VALIDATION MAP GENERATION")
    print("=" * 105)

    if not CASE_DEFINITION_FILE.exists():
        raise FileNotFoundError(
            CASE_DEFINITION_FILE
        )

    definitions = pd.read_csv(
        CASE_DEFINITION_FILE
    )

    definitions[
        "horizon_hours"
    ] = pd.to_numeric(
        definitions[
            "horizon_hours"
        ],
        errors="coerce",
    )

    for horizon in HORIZONS:

        print()
        print("=" * 105)
        print(
            f"{horizon}H MAP"
        )
        print("=" * 105)

        test_rows = definitions[
            definitions[
                "horizon_hours"
            ]
            ==
            horizon
        ]

        if test_rows.empty:
            raise RuntimeError(
                f"No frozen {horizon}h "
                "validation case found."
            )

        test = test_rows.iloc[0]

        initialization_date = str(
            test[
                "initialization_date"
            ]
        )

        # ----------------------------------------------------
        # FILES
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # ROUTES
        # ----------------------------------------------------

        ais = load_route(
            ais_file
        )

        pg = load_route(
            pg_file
        )

        # ----------------------------------------------------
        # MEMBER 1
        # ----------------------------------------------------

        sic, x, y = (
            load_member1_forecast(
                initialization_date,
                horizon,
            )
        )

        grid_lat, grid_lon = (
            grid_to_latlon(
                x,
                y,
            )
        )

        # ----------------------------------------------------
        # MEMBER 2
        # ----------------------------------------------------

        icebergs = (
            load_historical_icebergs(
                initialization_date,
                horizon,
            )
        )

        # ----------------------------------------------------
        # MAP BOUNDS
        # ----------------------------------------------------

        (
            lon_min,
            lon_max,
            lat_min,
            lat_max,
        ) = calculate_bounds(
            ais,
            pg,
        )

        visible_icebergs = (
            icebergs_in_bounds(
                icebergs,
                lon_min,
                lon_max,
                lat_min,
                lat_max,
            )
        )

        # ----------------------------------------------------
        # FIGURE
        # ----------------------------------------------------

        fig, ax = plt.subplots(
            figsize=(
                12,
                9,
            )
        )

        # ====================================================
        # SEA ICE BACKGROUND
        # ====================================================

        valid = (
            np.isfinite(
                sic
            )
            &
            np.isfinite(
                grid_lat
            )
            &
            np.isfinite(
                grid_lon
            )
        )

        sic_plot = np.where(
            valid,
            sic * 100.0,
            np.nan,
        )

        sic_masked = (
            np.ma.masked_invalid(
                sic_plot
            )
        )

        # Use contourf rather than pcolormesh because the
        # EPSG:3412 -> WGS84 grid is curvilinear.
        levels = np.linspace(
            0.0,
            100.0,
            21,
        )

        mesh = ax.contourf(
            grid_lon,
            grid_lat,
            sic_masked,
            levels=levels,
            cmap="Blues",
            vmin=0.0,
            vmax=100.0,
            extend="neither",
            zorder=1,
        )

        colorbar = fig.colorbar(
            mesh,
            ax=ax,
            pad=0.02,
        )

        colorbar.set_label(
            "Sea-Ice Concentration (%)"
        )

        colorbar.set_ticks(
            [
                0,
                20,
                40,
                60,
                80,
                100,
            ]
        )

        # ====================================================
        # AIS ROUTE
        # ====================================================

        ax.plot(
            ais["lon"],
            ais["lat"],
            linewidth=2.8,
            label="Actual Polarstern AIS",
            zorder=6,
        )

        # ====================================================
        # POLARGUARD ROUTE
        # ====================================================

        ax.plot(
            pg["lon"],
            pg["lat"],
            linewidth=3.0,
            linestyle="--",
            label="PolarGuard Route",
            zorder=7,
        )

        # ====================================================
        # START
        # ====================================================

        start_lon = float(
            ais.iloc[0][
                "lon"
            ]
        )

        start_lat = float(
            ais.iloc[0][
                "lat"
            ]
        )

        ax.scatter(
            [
                start_lon
            ],
            [
                start_lat
            ],
            s=120,
            marker="o",
            label="Start",
            zorder=10,
        )

        # ====================================================
        # DESTINATION
        # ====================================================

        destination_lon = float(
            ais.iloc[-1][
                "lon"
            ]
        )

        destination_lat = float(
            ais.iloc[-1][
                "lat"
            ]
        )

        ax.scatter(
            [
                destination_lon
            ],
            [
                destination_lat
            ],
            s=150,
            marker="*",
            label="Destination",
            zorder=10,
        )

        # ====================================================
        # HISTORICAL ICEBERGS
        # ====================================================

        if not visible_icebergs.empty:

            ax.scatter(
                visible_icebergs[
                    "lon"
                ],
                visible_icebergs[
                    "lat"
                ],
                s=40,
                marker="^",
                alpha=0.80,
                label="Historical Icebergs",
                zorder=8,
            )

        # ====================================================
        # MAP LIMITS
        # ====================================================

        ax.set_xlim(
            lon_min,
            lon_max,
        )

        ax.set_ylim(
            lat_min,
            lat_max,
        )

        # ====================================================
        # LABELS
        # ====================================================

        ax.set_xlabel(
            "Longitude"
        )

        ax.set_ylabel(
            "Latitude"
        )

        ax.set_title(
            (
                "PolarGuard PS124 Historical Validation "
                f"- {horizon}h\n"
                f"Initialization: "
                f"{initialization_date}"
            )
        )

        ax.grid(
            True,
            alpha=0.25,
        )

        ax.legend(
            loc="best"
        )

        fig.tight_layout()

        # ====================================================
        # SAVE
        # ====================================================

        requested_output_file = (
            OUTPUT_DIR
            /
            f"ps124_validation_map_{horizon}h.png"
        )

        print(
            "Requested output:",
            str(
                requested_output_file
            ),
        )

        actual_output_file = (
            save_figure_safely(
                fig,
                requested_output_file,
            )
        )

        plt.close(
            fig
        )

        # ====================================================
        # SUMMARY
        # ====================================================

        print(
            "Initialization:",
            initialization_date,
        )

        print(
            "AIS points:",
            len(
                ais
            ),
        )

        print(
            "PolarGuard points:",
            len(
                pg
            ),
        )

        print(
            "Historical icebergs:",
            len(
                icebergs
            ),
        )

        print(
            "Icebergs visible on map:",
            len(
                visible_icebergs
            ),
        )

        print(
            "Saved:",
            str(
                actual_output_file
            ),
        )

    print()
    print("=" * 105)
    print(
        "VALIDATION MAP GENERATION COMPLETE"
    )
    print("=" * 105)


if __name__ == "__main__":
    main()