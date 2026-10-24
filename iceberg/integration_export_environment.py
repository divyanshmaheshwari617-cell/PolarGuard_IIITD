from pathlib import Path
import json

from iceberg_service import predict_iceberg_trajectory


BASE = Path(__file__).resolve().parent

OUTPUT_DIR = (
    BASE / "outputs" / "integration"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

OUTPUT_FILE = (
    OUTPUT_DIR /
    "iceberg_environment_forecast_demo.json"
)


def main():

    # --------------------------------------------------------
    # Demo iceberg history
    # --------------------------------------------------------

    iceberg_id = "a23a"

    initialization_date = "2019-01-04"

    lat_tm3 = -75.75435
    lon_tm3 = -41.10950

    lat_tm2 = -75.69135
    lon_tm2 = -41.09485

    lat_tm1 = -75.63525
    lon_tm1 = -41.08170

    current_latitude = -75.611
    current_longitude = -41.076

    day_of_year = 4

    # --------------------------------------------------------
    # Example environmental forcing
    #
    # These values are DEMO inputs only.
    # They are NOT the official 2025 test result.
    # --------------------------------------------------------

    wind_u10 = -3.0
    wind_v10 = 2.0

    ocean_uo = -0.05
    ocean_vo = 0.03

    sea_ice_sic = 0.80

    # --------------------------------------------------------
    # Run frozen Member 2 service
    # --------------------------------------------------------

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

        sea_ice_sic=sea_ice_sic,
    )

    # --------------------------------------------------------
    # Integration package
    # --------------------------------------------------------

    integration = {

        "module":
            "PolarGuard Member 2 - Iceberg Trajectory Forecast",

        "version":
            "environment-v1-frozen",

        "iceberg_id":
            iceberg_id,

        "initialization_date":
            initialization_date,

        "input_history": {

            "t_minus_3": {
                "latitude": lat_tm3,
                "longitude": lon_tm3,
            },

            "t_minus_2": {
                "latitude": lat_tm2,
                "longitude": lon_tm2,
            },

            "t_minus_1": {
                "latitude": lat_tm1,
                "longitude": lon_tm1,
            },

            "current": {
                "latitude": current_latitude,
                "longitude": current_longitude,
            },
        },

        "environmental_inputs": {

            "era5_wind": {
                "u10_mps": wind_u10,
                "v10_mps": wind_v10,
            },

            "glorys_ocean_current": {
                "uo_mps": ocean_uo,
                "vo_mps": ocean_vo,
            },

            "nsidc_sea_ice": {
                "concentration": sea_ice_sic,
                "scale": "0_to_1",
            },
        },

        "forecast": result["forecast"],

        "model_information": {

            "model_family":
                "HistGradientBoostingRegressor",

            "forecast_horizons_hours":
                [24, 48, 72],

            "feature_count":
                26,

            "environmental_forcing":
                True,

            "frozen_after_validation":
                True,
        },

        "held_out_2025_performance": {

            "24h": {
                "rmse_km": 3.744,
                "within_5km_pct": 92.23,
                "baseline_rmse_km": 4.366,
                "rmse_improvement_pct": 14.23,
            },

            "48h": {
                "rmse_km": 6.389,
                "within_5km_pct": 80.33,
                "baseline_rmse_km": 7.913,
                "rmse_improvement_pct": 19.25,
            },

            "72h": {
                "rmse_km": 9.389,
                "within_5km_pct": 69.48,
                "baseline_rmse_km": 11.828,
                "rmse_improvement_pct": 20.61,
            },
        },

        "notes": [
            "2025 was used only as the final held-out test set.",
            "Demo environmental values in this export are illustrative inputs.",
            "Model selection was performed using 2019-2023 training data and 2024 validation data.",
            "The output is intended for downstream risk and navigation modules."
        ]
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            integration,
            f,
            indent=2
        )

    print("=" * 75)
    print("POLARGUARD MEMBER 2 INTEGRATION EXPORT")
    print("=" * 75)

    print("\nOutput:")
    print(OUTPUT_FILE)

    print("\nForecast:")

    for horizon, forecast in result[
        "forecast"
    ].items():

        print(
            f"{horizon}: "
            f"lat={forecast['latitude']:.6f}, "
            f"lon={forecast['longitude']:.6f}, "
            f"distance="
            f"{forecast['predicted_displacement_km']:.3f} km"
        )

    print()
    print("=" * 75)
    print("INTEGRATION EXPORT COMPLETE")
    print("=" * 75)


if __name__ == "__main__":
    main()