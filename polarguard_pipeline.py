from pathlib import Path
import streamlit as st
from huggingface_hub import hf_hub_download
import numpy as np
import xarray as xr
from pyproj import Transformer

from iceberg.iceberg_service import predict_iceberg_trajectory


BASE = Path(__file__).resolve().parent

HF_REPO_ID = "divyanshmahesh/PolarGuard-Data"
HF_DATASET_FILENAME = "sea_ice_2019_2025.nc"

SEA_ICE_FILE = (
    BASE / "data" / "processed" / HF_DATASET_FILENAME
)


def resolve_sea_ice_file():
    if SEA_ICE_FILE.exists():
        return SEA_ICE_FILE

    return Path(
        hf_hub_download(
            repo_id=HF_REPO_ID,
            filename=HF_DATASET_FILENAME,
            repo_type="dataset",
            token=st.secrets["HF_TOKEN"],
        )
    )
HF_REPO_ID = "divyanshmahesh/PolarGuard-Data"
HF_DATASET_FILENAME = "sea_ice_2019_2025.nc"


def _resolve_sea_ice_file() -> Path:
    """Find the local SIC file or retrieve it from Hugging Face."""
    if SEA_ICE_FILE.is_file():
        return SEA_ICE_FILE

    try:
        import streamlit as st
        from huggingface_hub import hf_hub_download

        downloaded_path = hf_hub_download(
            repo_id=HF_REPO_ID,
            filename=HF_DATASET_FILENAME,
            repo_type="dataset",
            token=st.secrets["HF_TOKEN"],
        )

        return Path(downloaded_path)

    except Exception as exc:
        raise FileNotFoundError(
            "The historical sea-ice file is missing locally, and the "
            "Hugging Face download failed. Check the HF_TOKEN secret "
            "in Streamlit and its access to the PolarGuard-Data dataset."
        ) from exc


# WGS84 latitude/longitude → NSIDC Antarctic grid EPSG:3412
TRANSFORMER = Transformer.from_crs(
    "EPSG:4326",
    "EPSG:3412",
    always_xy=True,
)


def get_local_sea_ice(
    latitude,
    longitude,
    date,
):
    """
    Extract sea-ice concentration from the
    Member 1 NSIDC grid at the iceberg position.
    """
    dataset_path = _resolve_sea_ice_file()
    ds = xr.open_dataset(resolve_sea_ice_file())

    try:
        # Select requested date
        daily = ds.sel(
            time=np.datetime64(date),
            method="nearest",
        )

        # Convert iceberg latitude/longitude to NSIDC x/y
        x_pos, y_pos = TRANSFORMER.transform(
            longitude,
            latitude,
        )

        # Find nearest grid cell
        cell = daily[
            "sea_ice_concentration"
        ].sel(
            x=x_pos,
            y=y_pos,
            method="nearest",
        )

        sic = float(cell.values)

        if np.isfinite(sic):
            return {
                "sic": sic,
                "available": 1,
                "grid_x": float(cell["x"].values),
                "grid_y": float(cell["y"].values),
            }

        # Preserve the existing missing-SIC policy.
        return {
            "sic": None,
            "available": 0,
            "grid_x": float(cell["x"].values),
            "grid_y": float(cell["y"].values),
        }

    finally:
        ds.close()


def run_polarguard(
    lat_tm3,
    lon_tm3,
    lat_tm2,
    lon_tm2,
    lat_tm1,
    lon_tm1,
    current_latitude,
    current_longitude,
    date,
    wind_u10,
    wind_v10,
    ocean_uo,
    ocean_vo,
):
    # ========================================================
    # MEMBER 1 -> LOCAL SEA ICE
    # ========================================================

    sea_ice = get_local_sea_ice(
        latitude=current_latitude,
        longitude=current_longitude,
        date=date,
    )

    print("\nMEMBER 1 -> MEMBER 2")
    print("--------------------")

    if sea_ice["available"]:
        print(
            "Local sea-ice concentration:",
            sea_ice["sic"],
        )
    else:
        print(
            "Local SIC unavailable; "
            "Member 2 will use its frozen "
            "missing-SIC handling."
        )

    # ========================================================
    # MEMBER 2
    # ========================================================

    day_of_year = (
        np.datetime64(date, "D")
        .astype(object)
        .timetuple()
        .tm_yday
    )

    result = predict_iceberg_trajectory(
        lat_tm3=lat_tm3,
        lon_tm3=lon_tm3,
        lat_tm2=lat_tm2,
        lon_tm2=lon_tm2,
        lat_tm1=lat_tm1,
        lon_tm1=lon_tm1,
        current_latitude=current_latitude,
        current_longitude=current_longitude,
        day_of_year=day_of_year,
        wind_u10=wind_u10,
        wind_v10=wind_v10,
        ocean_uo=ocean_uo,
        ocean_vo=ocean_vo,
        sea_ice_sic=sea_ice["sic"],
        sea_ice_available=sea_ice["available"],
    )

    return {
        "initialization_date": str(date),
        "sea_ice": sea_ice,
        "iceberg": result,
    }


if __name__ == "__main__":
    result = run_polarguard(
        # Example historical iceberg positions
        lat_tm3=-75.75435,
        lon_tm3=-41.10950,
        lat_tm2=-75.69135,
        lon_tm2=-41.09485,
        lat_tm1=-75.63525,
        lon_tm1=-41.08170,
        current_latitude=-75.611,
        current_longitude=-41.076,

        # Historical date available in Member 1 dataset
        date="2019-01-04",

        # Demo environment values for now
        wind_u10=-3.0,
        wind_v10=2.0,
        ocean_uo=-0.05,
        ocean_vo=0.03,
    )

    print("\nICEBERG FORECAST")
    print("----------------")

    for horizon, forecast in result["iceberg"]["forecast"].items():
        print(
            f"{horizon}: "
            f"lat={forecast['latitude']:.6f}, "
            f"lon={forecast['longitude']:.6f}, "
            f"distance="
            f"{forecast['predicted_displacement_km']:.3f} km"
        )

    print("\nPOLARGUARD PIPELINE TEST COMPLETE")