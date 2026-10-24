import numpy as np

from satellite_data_service import load_latest_satellite_input
from sea_ice_service import predict_sea_ice


print("=" * 72)
print("POLARGUARD SATELLITE -> SEA-ICE AI FORECAST TEST")
print("=" * 72)

print("\nLoading latest near-real-time Antarctic satellite data...")

bundle = load_latest_satellite_input()

print("\nRunning frozen PolarGuard Sea-Ice model...")

forecast = predict_sea_ice(
    current=bundle["current"],
    lag1=bundle["lag1"],
    lag2=bundle["lag2"],
    lag3=bundle["lag3"],
    x_coords=bundle["x"],
    y_coords=bundle["y"],
    date=bundle["date"],
)

print("\n" + "=" * 72)
print("FORECAST SERVICE RETURNED SUCCESSFULLY")
print("=" * 72)

print(
    "Initialization date:",
    bundle["date"],
)

print(
    "Satellite source:",
    bundle["provider"],
    bundle["dataset_id"],
    "Version",
    bundle["dataset_version"],
)

print(
    "Current SIC shape:",
    bundle["current"].shape,
)

print(
    "Current valid cells:",
    int(
        np.isfinite(
            bundle["current"]
        ).sum()
    ),
)

print("\nReturned object type:")
print(type(forecast))

print("\nReturned keys:")

if isinstance(forecast, dict):

    for key in forecast.keys():
        print(" ", key)

else:
    print(
        "Forecast result is not a dictionary."
    )

print("\n" + "-" * 72)
print("CHECKING FORECAST ARRAYS")
print("-" * 72)


def inspect_array(name, value):

    array = np.asarray(value)

    print(
        f"\n{name}"
    )

    print(
        "  shape:",
        array.shape,
    )

    print(
        "  valid cells:",
        int(
            np.isfinite(array).sum()
        ),
    )

    if np.isfinite(array).any():

        print(
            "  min:",
            round(
                float(
                    np.nanmin(array)
                ),
                6,
            ),
        )

        print(
            "  mean:",
            round(
                float(
                    np.nanmean(array)
                ),
                6,
            ),
        )

        print(
            "  max:",
            round(
                float(
                    np.nanmax(array)
                ),
                6,
            ),
        )


if isinstance(forecast, dict):

    candidate_keys = [
        "forecast_24h",
        "forecast_48h",
        "forecast_72h",
        "24h",
        "48h",
        "72h",
        "sic_24h",
        "sic_48h",
        "sic_72h",
    ]

    found_any = False

    for key in candidate_keys:

        if key in forecast:

            inspect_array(
                key,
                forecast[key],
            )

            found_any = True

    if not found_any:

        print(
            "\nNo standard forecast-key names "
            "were detected automatically."
        )

        print(
            "That is okay — the keys printed above "
            "will tell us the exact service structure."
        )

print("\n" + "=" * 72)
print("STEP 5 TEST FINISHED")
print("=" * 72)

print(
    "\nIf +24h / +48h / +72h arrays are returned, "
    "the real satellite-to-ML pipeline is connected."
)