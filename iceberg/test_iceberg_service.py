from iceberg_service import predict_iceberg_trajectory


print("=" * 75)
print("ICEBERG SERVICE AUTOMATED TEST")
print("=" * 75)


result = predict_iceberg_trajectory(
    lat_tm3=-75.75435,
    lon_tm3=-41.10950,

    lat_tm2=-75.69135,
    lon_tm2=-41.09485,

    lat_tm1=-75.63525,
    lon_tm1=-41.08170,

    current_latitude=-75.61100,
    current_longitude=-41.07600,

    day_of_year=4
)


# ------------------------------------------------------------
# BASIC STRUCTURE
# ------------------------------------------------------------

assert "current_position" in result
assert "forecast" in result
assert "model" in result


# ------------------------------------------------------------
# HORIZON TESTS
# ------------------------------------------------------------

for horizon in [
    "24h",
    "48h",
    "72h"
]:

    assert horizon in result["forecast"]

    forecast = result["forecast"][horizon]

    assert "latitude" in forecast
    assert "longitude" in forecast

    assert "displacement_east_km" in forecast
    assert "displacement_north_km" in forecast
    assert "displacement_distance_km" in forecast


    lat = forecast["latitude"]
    lon = forecast["longitude"]

    distance = forecast[
        "displacement_distance_km"
    ]


    # Geographic validity

    assert -90.0 <= lat <= 90.0

    assert -180.0 <= lon <= 180.0


    # Distance must not be negative

    assert distance >= 0.0


    print(
        f"\n{horizon} PASS"
    )

    print(
        f"Latitude  : {lat:.6f}"
    )

    print(
        f"Longitude : {lon:.6f}"
    )

    print(
        f"Movement  : {distance:.3f} km"
    )


# ------------------------------------------------------------
# MODEL METADATA
# ------------------------------------------------------------

assert (
    result["model"]["input_days"]
    == 4
)

assert (
    result["model"][
        "forecast_horizons_hours"
    ]
    == [24, 48, 72]
)

assert (
    result["model"][
        "environmental_inputs"
    ]
    is False
)


print("\n" + "=" * 75)

print(
    "ALL ICEBERG SERVICE TESTS PASSED"
)

print("=" * 75)