from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr

BASE = Path(__file__).resolve().parent

INPUT = (
    BASE / "data" / "processed" /
    "iceberg_features_with_wind_current_2019_2025.csv"
)

OUTPUT = (
    BASE / "data" / "processed" /
    "iceberg_features_with_wind_current_recovered_2019_2025.csv"
)

OCEAN_DIR = BASE / "data" / "environment" / "ocean_current"

FILES = {
    2019: OCEAN_DIR / "ocean_current_2019.nc",
    2020: OCEAN_DIR / "ocean_current_2020.nc",
    2021: OCEAN_DIR / "ocean_current_2021.nc",
    2022: OCEAN_DIR / "ocean_current_2022.nc",
    2023: OCEAN_DIR / "ocean_current_2023.nc",
    2024: OCEAN_DIR / "ocean_current_2024.nc",
    2025: OCEAN_DIR / "ocean_current_2025.nc",
}

FILE_2019_NORTH = OCEAN_DIR / "ocean_current_2019_north.nc"

# Search up to this many grid cells away
MAX_RADIUS = 12


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0088

    lat1 = np.radians(lat1)
    lon1 = np.radians(lon1)
    lat2 = np.radians(lat2)
    lon2 = np.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(lat1)
        * np.cos(lat2)
        * np.sin(dlon / 2) ** 2
    )

    return 2 * R * np.arcsin(np.sqrt(a))


def normalize_lon(lon):
    return ((lon + 180.0) % 360.0) - 180.0


def get_dataset(year, lat):
    if year == 2019 and lat > -50.0:
        return xr.open_dataset(FILE_2019_NORTH)

    return xr.open_dataset(FILES[year])


def nearest_index(values, target):
    values = np.asarray(values)
    return int(np.abs(values - target).argmin())


def recover_one(ds, date, lat, lon):
    lon = normalize_lon(lon)

    # Select the exact daily field first
    field = ds.sel(
        time=np.datetime64(date),
        method="nearest"
    )

    if "depth" in field.dims:
        field = field.squeeze("depth", drop=True)

    lats = field["latitude"].values
    lons = field["longitude"].values

    lat_idx = nearest_index(lats, lat)
    lon_idx = nearest_index(lons, lon)

    # Expand outward from nearest grid cell
    for radius in range(1, MAX_RADIUS + 1):

        lat_start = max(0, lat_idx - radius)
        lat_end = min(len(lats), lat_idx + radius + 1)

        lon_indices = [
            (lon_idx + offset) % len(lons)
            for offset in range(-radius, radius + 1)
        ]

        sub = field.isel(
            latitude=slice(lat_start, lat_end),
            longitude=lon_indices
        )

        u = np.asarray(sub["uo"].values)
        v = np.asarray(sub["vo"].values)

        valid = np.isfinite(u) & np.isfinite(v)

        if not valid.any():
            continue

        sub_lats = np.asarray(sub["latitude"].values)
        sub_lons = np.asarray(sub["longitude"].values)

        lat_grid, lon_grid = np.meshgrid(
            sub_lats,
            sub_lons,
            indexing="ij"
        )

        distances = haversine_km(
            lat,
            lon,
            lat_grid,
            lon_grid
        )

        distances[~valid] = np.inf

        flat_idx = np.argmin(distances)
        iy, ix = np.unravel_index(flat_idx, distances.shape)

        return {
            "uo": float(u[iy, ix]),
            "vo": float(v[iy, ix]),
            "distance_km": float(distances[iy, ix]),
            "radius": radius,
            "grid_lat": float(lat_grid[iy, ix]),
            "grid_lon": float(lon_grid[iy, ix]),
        }

    return None


def main():

    print("=" * 75)
    print("POLARGUARD OCEAN CURRENT RECOVERY")
    print("=" * 75)

    df = pd.read_csv(INPUT, parse_dates=["init_date"])

    if "ocean_recovered" not in df.columns:
        df["ocean_recovered"] = False

    if "ocean_recovery_distance_km" not in df.columns:
        df["ocean_recovery_distance_km"] = np.nan

    if "ocean_recovery_radius" not in df.columns:
        df["ocean_recovery_radius"] = np.nan

    missing_mask = (
        df["ocean_uo"].isna()
        | df["ocean_vo"].isna()
    )

    missing_indices = df.index[missing_mask].to_numpy()

    print(f"\nTotal rows: {len(df)}")
    print(f"Rows needing recovery: {len(missing_indices)}")

    recovered = 0
    failed = 0

    current_year = None
    ds_south = None
    ds_north = None

    try:
        for n, idx in enumerate(missing_indices, start=1):

            row = df.loc[idx]

            year = row["init_date"].year
            lat = float(row["current_latitude"])
            lon = float(row["current_longitude"])

            # Handle yearly file opening efficiently
            if year != current_year:

                if ds_south is not None:
                    ds_south.close()
                    ds_south = None

                if ds_north is not None:
                    ds_north.close()
                    ds_north = None

                current_year = year

                ds_south = xr.open_dataset(FILES[year])

                if year == 2019:
                    ds_north = xr.open_dataset(FILE_2019_NORTH)

            if year == 2019 and lat > -50:
                ds = ds_north
            else:
                ds = ds_south

            result = recover_one(
                ds,
                row["init_date"],
                lat,
                lon
            )

            if result is not None:

                df.at[idx, "ocean_uo"] = result["uo"]
                df.at[idx, "ocean_vo"] = result["vo"]

                df.at[idx, "ocean_recovered"] = True
                df.at[
                    idx,
                    "ocean_recovery_distance_km"
                ] = result["distance_km"]

                df.at[
                    idx,
                    "ocean_recovery_radius"
                ] = result["radius"]

                recovered += 1

            else:
                failed += 1

            if n % 100 == 0 or n == len(missing_indices):
                print(
                    f"{n}/{len(missing_indices)} | "
                    f"recovered={recovered} | "
                    f"failed={failed}"
                )

    finally:

        if ds_south is not None:
            ds_south.close()

        if ds_north is not None:
            ds_north.close()

    df["ocean_speed"] = np.sqrt(
        df["ocean_uo"] ** 2
        + df["ocean_vo"] ** 2
    )

    print()
    print("=" * 75)
    print("RECOVERY QUALITY CHECK")
    print("=" * 75)

    missing_after = (
        df["ocean_uo"].isna()
        | df["ocean_vo"].isna()
    ).sum()

    print(f"\nInitially missing: {len(missing_indices)}")
    print(f"Recovered: {recovered}")
    print(f"Still missing: {missing_after}")

    recovered_rows = df[df["ocean_recovered"] == True]

    if len(recovered_rows) > 0:

        print("\nRecovery distance statistics (km):")
        print(
            recovered_rows[
                "ocean_recovery_distance_km"
            ].describe()
        )

        print("\nRecovery radius statistics:")
        print(
            recovered_rows[
                "ocean_recovery_radius"
            ].describe()
        )

        print("\nRecovered farther than 25 km:")
        print(
            (
                recovered_rows[
                    "ocean_recovery_distance_km"
                ] > 25
            ).sum()
        )

        print("\nRecovered farther than 50 km:")
        print(
            (
                recovered_rows[
                    "ocean_recovery_distance_km"
                ] > 50
            ).sum()
        )

    df.to_csv(OUTPUT, index=False)

    print("\nSaved:")
    print(OUTPUT)

    print()
    print("=" * 75)
    print("RECOVERY COMPLETE")
    print("=" * 75)


if __name__ == "__main__":
    main()