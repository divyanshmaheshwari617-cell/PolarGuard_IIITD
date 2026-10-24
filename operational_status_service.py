from __future__ import annotations

from datetime import datetime, timezone

from environmental_data_service import (
    load_environmental_inputs,
    to_member2_environment,
)


def _utc_now_string():
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def build_environmental_status(
    *,
    date,
    latitude,
    longitude,
):
    """
    Build PolarGuard near-real-time environmental status.

    This uses the real automatic providers already connected:

        ECMWF IFS           -> wind U/V
        Copernicus Marine   -> ocean current U/V
        NOAA/NSIDC G10016   -> sea-ice concentration

    No synthetic automatic environmental values are created.
    """

    env = load_environmental_inputs(
        mode="near_real_time",
        date=date,
        latitude=latitude,
        longitude=longitude,
    )

    member2 = to_member2_environment(
        env
    )

    return {
        "success": True,

        "mode": "near_real_time",

        "requested_date": (
            env.requested_date
        ),

        "latitude": float(
            env.latitude
        ),

        "longitude": float(
            env.longitude
        ),

        # ----------------------------------------------------
        # Wind
        # ----------------------------------------------------

        "wind": {
            "available": True,

            "source": (
                env.wind_source
            ),

            "timestamp": (
                env.wind_timestamp
            ),

            "u10": float(
                env.wind_u10
            ),

            "v10": float(
                env.wind_v10
            ),

            "speed_ms": float(
                env.wind_speed_ms
            ),
        },

        # ----------------------------------------------------
        # Ocean
        # ----------------------------------------------------

        "ocean": {
            "available": True,

            "source": (
                env.ocean_source
            ),

            "timestamp": (
                env.ocean_timestamp
            ),

            "uo": float(
                env.ocean_uo
            ),

            "vo": float(
                env.ocean_vo
            ),

            "speed_ms": float(
                env.ocean_speed_ms
            ),
        },

        # ----------------------------------------------------
        # Sea ice
        # ----------------------------------------------------

        "sea_ice": {
            "available": bool(
                env.sea_ice_available
            ),

            "source": (
                env.sea_ice_source
            ),

            "timestamp": (
                str(
                    env.sea_ice_timestamp
                )
                if env.sea_ice_timestamp
                is not None
                else None
            ),

            "sic": float(
                env.sea_ice_sic
            ),
        },

        # ----------------------------------------------------
        # Frozen Member-2 features
        # ----------------------------------------------------

        "member2_environment": {
            key: (
                float(value)
                if key
                != "sea_ice_available"
                else int(value)
            )
            for key, value
            in member2.items()
        },

        # ----------------------------------------------------
        # Synchronization
        # ----------------------------------------------------

        "environment_synchronized": bool(
            env.synchronized
        ),

        "environment_sync_note": (
            env.synchronization_note
        ),

        # ----------------------------------------------------
        # Operational interpretation
        # ----------------------------------------------------

        "current_routing": {
            "status": (
                "LATEST_AVAILABLE_NRT"
            ),

            "ready": True,

            "label": (
                "Latest-Available "
                "Near-Real-Time Current Routing"
            ),

            "note": (
                "Uses the latest available "
                "provider observations. "
                "Provider timestamps may differ."
            ),
        },

        "forecast_routing": {
            "status": (
                "ENVIRONMENT_READY"
            ),

            "environment_ready": True,

            "fully_synchronized": False,

            "label": (
                "Forecast Routing "
                "Requires Synchronized "
                "Iceberg History"
            ),

            "note": (
                "Wind, ocean current and SIC "
                "are connected. Fully synchronized "
                "Member-2 forecasting still requires "
                "four consecutive real daily iceberg "
                "positions for the forecast "
                "initialization."
            ),
        },

        "generated_at_utc": (
            _utc_now_string()
        ),
    }


def print_operational_status(
    status,
):
    """
    Human-readable terminal summary.
    """

    print()
    print("=" * 70)
    print(
        "POLARGUARD OPERATIONAL DATA STATUS"
    )
    print("=" * 70)

    print(
        f"Requested date : "
        f"{status['requested_date']}"
    )

    print(
        f"Position       : "
        f"{status['latitude']:.4f}, "
        f"{status['longitude']:.4f}"
    )

    print()

    wind = status["wind"]

    print("WIND")
    print(
        f"  Source       : "
        f"{wind['source']}"
    )
    print(
        f"  Timestamp    : "
        f"{wind['timestamp']}"
    )
    print(
        f"  U10 / V10    : "
        f"{wind['u10']:.4f}, "
        f"{wind['v10']:.4f} m/s"
    )

    print()

    ocean = status["ocean"]

    print("OCEAN CURRENT")
    print(
        f"  Source       : "
        f"{ocean['source']}"
    )
    print(
        f"  Timestamp    : "
        f"{ocean['timestamp']}"
    )
    print(
        f"  UO / VO      : "
        f"{ocean['uo']:.4f}, "
        f"{ocean['vo']:.4f} m/s"
    )

    print()

    sea_ice = status["sea_ice"]

    print("SEA ICE")
    print(
        f"  Source       : "
        f"{sea_ice['source']}"
    )
    print(
        f"  Timestamp    : "
        f"{sea_ice['timestamp']}"
    )
    print(
        f"  SIC          : "
        f"{sea_ice['sic']:.4f}"
    )
    print(
        f"  Available    : "
        f"{sea_ice['available']}"
    )

    print()

    print("SYNCHRONIZATION")
    print(
        f"  Environmental inputs fully "
        f"synchronized : "
        f"{status['environment_synchronized']}"
    )
    print(
        f"  Note : "
        f"{status['environment_sync_note']}"
    )

    print()

    print("ROUTING STATUS")
    print(
        "  CURRENT : "
        f"{status['current_routing']['status']}"
    )
    print(
        "  FUTURE  : "
        f"{status['forecast_routing']['status']}"
    )

    print()

    print("Frozen Member-2 environmental features:")

    for key, value in (
        status[
            "member2_environment"
        ].items()
    ):
        print(
            f"  {key}: {value}"
        )

    print("=" * 70)


if __name__ == "__main__":

    status = build_environmental_status(
        date="2026-09-04",
        latitude=-53.55,
        longitude=-29.95,
    )

    print_operational_status(
        status
    )