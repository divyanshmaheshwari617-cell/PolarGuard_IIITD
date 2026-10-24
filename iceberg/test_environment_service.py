from iceberg_service import predict_iceberg_trajectory


result = predict_iceberg_trajectory(

    lat_tm3=-75.75435,
    lon_tm3=-41.10950,

    lat_tm2=-75.69135,
    lon_tm2=-41.09485,

    lat_tm1=-75.63525,
    lon_tm1=-41.08170,

    current_latitude=-75.611,
    current_longitude=-41.076,

    day_of_year=4,

    # Example environmental values only
    wind_u10=-3.0,
    wind_v10=2.0,

    ocean_uo=-0.05,
    ocean_vo=0.03,

    sea_ice_sic=0.80,
)

print("\nMODEL:")
print(result["model"])

print("\nVERSION:")
print(result["version"])

print("\nCURRENT:")
print(result["current_position"])

for horizon, forecast in result["forecast"].items():

    print(f"\n{horizon}")

    print(
        "Latitude:",
        forecast["latitude"]
    )

    print(
        "Longitude:",
        forecast["longitude"]
    )

    print(
        "Displacement:",
        forecast[
            "predicted_displacement_km"
        ],
        "km"
    )

print("\nSERVICE TEST COMPLETE")