"""
PolarGuard - Operational Iceberg Trajectory Service
----------------------------------------------------

Connects:

    genuine iceberg observation history
              +
    environmental forcing
              +
    frozen Member-2 trajectory model
              ↓
       +24h / +48h / +72h

Modes
-----
1. OPERATIONAL
   Uses four genuine consecutive observations ending exactly
   on the latest operational BYU observation.

2. HISTORICAL_DEMO
   Uses an exact row from the frozen Member-2 ML-ready dataset,
   including the historical wind, ocean current and sea-ice SIC
   associated with that initialization.

Scientific rules
----------------
- Never fabricate iceberg positions.
- Never repeat a current position to create fake history.
- Never interpolate missing observations for Member 2.
- Never retrain or modify the frozen Member-2 model.
- Future Member-1 SIC forecasts are NOT fed into Member 2.
- Historical/demo forecasts use historical environmental forcing,
  not today's near-real-time environmental data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from iceberg_history_service import (
    find_operational_four_day_sequence,
)

from iceberg.iceberg_service import (
    predict_from_date,
)

from environmental_data_service import (
    load_near_real_time_environment,
    to_member2_environment,
)


# ============================================================
# CONFIGURATION
# ============================================================

HISTORICAL_MEMBER2_DATASET = Path(
    "iceberg/data/processed/"
    "iceberg_features_environment_ml_ready_2019_2025.csv"
)

FORECAST_HORIZONS = (
    24,
    48,
    72,
)


# ============================================================
# BASIC HELPERS
# ============================================================

def _normalize_id(value) -> str:
    if value is None:
        return ""

    return str(value).strip().upper()


def _safe_float(value):
    try:
        if value is None:
            return None

        if pd.isna(value):
            return None

        return float(value)

    except (TypeError, ValueError):
        return None


def _first_present(
    mapping: Dict,
    names,
    default=None,
):
    if not isinstance(mapping, dict):
        return default

    for name in names:
        if name in mapping:
            value = mapping[name]

            if value is not None:
                return value

    return default


# ============================================================
# MEMBER-2 OUTPUT NORMALIZATION
# ============================================================

def _extract_horizon_position(
    prediction: Dict,
    horizon_hours: int,
) -> Optional[Dict]:
    """
    Extract one predicted position from the frozen Member-2
    output.

    Confirmed frozen Member-2 output:

        {
            "forecast": {
                "24h": {
                    "latitude": ...,
                    "longitude": ...,
                    "dx_km": ...,
                    "dy_km": ...,
                    "predicted_displacement_km": ...
                },
                "48h": {...},
                "72h": {...}
            }
        }

    A small fallback is retained for older/direct layouts.
    """

    if not isinstance(
        prediction,
        dict,
    ):
        return None

    horizon_key = (
        f"{int(horizon_hours)}h"
    )

    # --------------------------------------------------------
    # PRIMARY / CONFIRMED FROZEN MODEL STRUCTURE
    # --------------------------------------------------------

    forecast = prediction.get(
        "forecast"
    )

    if isinstance(
        forecast,
        dict,
    ):
        horizon_data = forecast.get(
            horizon_key
        )

        if isinstance(
            horizon_data,
            dict,
        ):
            latitude = _safe_float(
                horizon_data.get(
                    "latitude"
                )
            )

            longitude = _safe_float(
                horizon_data.get(
                    "longitude"
                )
            )

            if (
                latitude is not None
                and longitude is not None
            ):
                result = {
                    "latitude":
                        latitude,

                    "longitude":
                        longitude,
                }

                dx_km = _safe_float(
                    horizon_data.get(
                        "dx_km"
                    )
                )

                dy_km = _safe_float(
                    horizon_data.get(
                        "dy_km"
                    )
                )

                displacement_km = _safe_float(
                    horizon_data.get(
                        "predicted_displacement_km"
                    )
                )

                if dx_km is not None:
                    result[
                        "dx_km"
                    ] = dx_km

                if dy_km is not None:
                    result[
                        "dy_km"
                    ] = dy_km

                if displacement_km is not None:
                    result[
                        "predicted_displacement_km"
                    ] = displacement_km

                return result

    # --------------------------------------------------------
    # FALLBACK: DIRECT HORIZON DICTIONARIES
    # --------------------------------------------------------

    horizon_names = [
        f"{horizon_hours}h",
        f"{horizon_hours}H",
        f"+{horizon_hours}h",
        f"+{horizon_hours}H",
        f"forecast_{horizon_hours}",
        f"forecast_{horizon_hours}h",
        f"forecast_{horizon_hours}H",
        f"prediction_{horizon_hours}",
        f"prediction_{horizon_hours}h",
        f"prediction_{horizon_hours}H",
    ]

    latitude_keys = [
        "latitude",
        "lat",
        "predicted_latitude",
        "predicted_lat",
        "forecast_latitude",
        "forecast_lat",
    ]

    longitude_keys = [
        "longitude",
        "lon",
        "predicted_longitude",
        "predicted_lon",
        "forecast_longitude",
        "forecast_lon",
    ]

    for key in horizon_names:

        value = prediction.get(
            key
        )

        if not isinstance(
            value,
            dict,
        ):
            continue

        latitude = _safe_float(
            _first_present(
                value,
                latitude_keys,
            )
        )

        longitude = _safe_float(
            _first_present(
                value,
                longitude_keys,
            )
        )

        if (
            latitude is None
            or longitude is None
        ):
            continue

        result = {
            "latitude":
                latitude,

            "longitude":
                longitude,
        }

        dx_km = _safe_float(
            value.get(
                "dx_km"
            )
        )

        dy_km = _safe_float(
            value.get(
                "dy_km"
            )
        )

        displacement_km = _safe_float(
            value.get(
                "predicted_displacement_km"
            )
        )

        if dx_km is not None:
            result[
                "dx_km"
            ] = dx_km

        if dy_km is not None:
            result[
                "dy_km"
            ] = dy_km

        if displacement_km is not None:
            result[
                "predicted_displacement_km"
            ] = displacement_km

        return result

    # --------------------------------------------------------
    # FALLBACK: FLAT OUTPUT
    # --------------------------------------------------------

    flat_latitude_keys = [
        f"latitude_{horizon_hours}h",
        f"latitude_{horizon_hours}H",
        f"lat_{horizon_hours}h",
        f"lat_{horizon_hours}H",
        f"predicted_latitude_{horizon_hours}h",
        f"predicted_latitude_{horizon_hours}H",
        f"predicted_lat_{horizon_hours}h",
        f"predicted_lat_{horizon_hours}H",
        f"forecast_latitude_{horizon_hours}h",
        f"forecast_latitude_{horizon_hours}H",
        f"forecast_lat_{horizon_hours}h",
        f"forecast_lat_{horizon_hours}H",
    ]

    flat_longitude_keys = [
        f"longitude_{horizon_hours}h",
        f"longitude_{horizon_hours}H",
        f"lon_{horizon_hours}h",
        f"lon_{horizon_hours}H",
        f"predicted_longitude_{horizon_hours}h",
        f"predicted_longitude_{horizon_hours}H",
        f"predicted_lon_{horizon_hours}h",
        f"predicted_lon_{horizon_hours}H",
        f"forecast_longitude_{horizon_hours}h",
        f"forecast_longitude_{horizon_hours}H",
        f"forecast_lon_{horizon_hours}h",
        f"forecast_lon_{horizon_hours}H",
    ]

    latitude = _safe_float(
        _first_present(
            prediction,
            flat_latitude_keys,
        )
    )

    longitude = _safe_float(
        _first_present(
            prediction,
            flat_longitude_keys,
        )
    )

    if (
        latitude is not None
        and longitude is not None
    ):
        return {
            "latitude":
                latitude,

            "longitude":
                longitude,
        }

    return None


def normalize_member2_prediction(
    iceberg_id: str,
    initialization_date,
    prediction: Dict,
) -> Dict:
    """
    Convert frozen Member-2 output into the standard PolarGuard
    horizon structure:

        {
            "+24H": {...},
            "+48H": {...},
            "+72H": {...}
        }
    """

    iceberg_id = _normalize_id(
        iceberg_id
    )

    initialization_date = pd.Timestamp(
        initialization_date
    )

    positions = {}

    for horizon in FORECAST_HORIZONS:

        position = (
            _extract_horizon_position(
                prediction,
                horizon,
            )
        )

        if position is None:
            continue

        forecast_date = (
            initialization_date
            + pd.Timedelta(
                hours=horizon
            )
        )

        normalized_position = {
            "iceberg_id":
                iceberg_id,

            "latitude":
                float(
                    position[
                        "latitude"
                    ]
                ),

            "longitude":
                float(
                    position[
                        "longitude"
                    ]
                ),

            "horizon_hours":
                int(
                    horizon
                ),

            "initialization_date":
                initialization_date.strftime(
                    "%Y-%m-%d"
                ),

            "forecast_date":
                forecast_date.strftime(
                    "%Y-%m-%d"
                ),

            "position_type":
                "MEMBER2_PREDICTED",
        }

        if (
            "dx_km"
            in position
        ):
            normalized_position[
                "dx_km"
            ] = float(
                position[
                    "dx_km"
                ]
            )

        if (
            "dy_km"
            in position
        ):
            normalized_position[
                "dy_km"
            ] = float(
                position[
                    "dy_km"
                ]
            )

        if (
            "predicted_displacement_km"
            in position
        ):
            normalized_position[
                "predicted_displacement_km"
            ] = float(
                position[
                    "predicted_displacement_km"
                ]
            )

        positions[
            f"+{horizon}H"
        ] = normalized_position

    return positions


# ============================================================
# NEAR-REAL-TIME ENVIRONMENT
# ============================================================

def load_member2_environment(
    *,
    date,
    latitude: float,
    longitude: float,
) -> Dict:
    """
    Load latest-available environmental forcing for an
    OPERATIONAL Member-2 initialization.

    Provider timestamps may be asynchronous.

    Future Member-1 SIC forecasts are NOT supplied to Member 2.
    """

    environment = (
        load_near_real_time_environment(
            date=date,
            latitude=float(
                latitude
            ),
            longitude=float(
                longitude
            ),
        )
    )

    member2_environment = (
        to_member2_environment(
            environment
        )
    )

    if not isinstance(
        member2_environment,
        dict,
    ):
        raise TypeError(
            "to_member2_environment() did not return "
            "a dictionary."
        )

    return {
        "raw_environment":
            environment,

        "member2_environment":
            member2_environment,

        "environment_mode":
            "NEAR_REAL_TIME",
    }


# ============================================================
# GENERIC FROZEN MEMBER-2 EXECUTION
# ============================================================

def _run_member2(
    *,
    iceberg_id: str,
    position_input: Dict,
    environment_bundle: Dict,
) -> Dict:
    """
    Execute frozen Member-2 with genuine position history and
    environmental forcing.
    """

    env = environment_bundle[
        "member2_environment"
    ]

    wind_u10 = _safe_float(
        _first_present(
            env,
            [
                "wind_u10",
                "u10",
            ],
        )
    )

    wind_v10 = _safe_float(
        _first_present(
            env,
            [
                "wind_v10",
                "v10",
            ],
        )
    )

    ocean_uo = _safe_float(
        _first_present(
            env,
            [
                "ocean_uo",
                "uo",
            ],
        )
    )

    ocean_vo = _safe_float(
        _first_present(
            env,
            [
                "ocean_vo",
                "vo",
            ],
        )
    )

    sea_ice_sic = _safe_float(
        _first_present(
            env,
            [
                "sea_ice_sic",
                "sic",
            ],
            default=None,
        )
    )

    required_environment = {
        "wind_u10":
            wind_u10,

        "wind_v10":
            wind_v10,

        "ocean_uo":
            ocean_uo,

        "ocean_vo":
            ocean_vo,
    }

    missing = [
        key
        for key, value
        in required_environment.items()
        if value is None
    ]

    if missing:
        raise RuntimeError(
            "Member-2 environmental forcing is incomplete. "
            "Missing: "
            + ", ".join(
                missing
            )
        )

    prediction = predict_from_date(
        position_input[
            "lat_tm3"
        ],
        position_input[
            "lon_tm3"
        ],

        position_input[
            "lat_tm2"
        ],
        position_input[
            "lon_tm2"
        ],

        position_input[
            "lat_tm1"
        ],
        position_input[
            "lon_tm1"
        ],

        position_input[
            "current_latitude"
        ],
        position_input[
            "current_longitude"
        ],

        position_input[
            "date"
        ],

        float(
            wind_u10
        ),
        float(
            wind_v10
        ),

        float(
            ocean_uo
        ),
        float(
            ocean_vo
        ),

        (
            float(
                sea_ice_sic
            )
            if sea_ice_sic is not None
            else None
        ),
    )

    positions = (
        normalize_member2_prediction(
            iceberg_id=
                iceberg_id,

            initialization_date=
                position_input[
                    "date"
                ],

            prediction=
                prediction,
        )
    )

    return {
        "raw_prediction":
            prediction,

        "positions":
            positions,

        "member2_environment_used": {
            "wind_u10":
                wind_u10,

            "wind_v10":
                wind_v10,

            "ocean_uo":
                ocean_uo,

            "ocean_vo":
                ocean_vo,

            "sea_ice_sic":
                sea_ice_sic,
        },
    }


# ============================================================
# OPERATIONAL FORECAST
# ============================================================

def forecast_operational_iceberg(
    iceberg_id: str,
) -> Dict:
    """
    Attempt a genuine CURRENT operational Member-2 forecast.

    Member 2 runs only when four consecutive genuine positions
    ending exactly on the latest operational observation exist.

    Otherwise the iceberg remains CURRENT_ONLY.
    """

    iceberg_id = _normalize_id(
        iceberg_id
    )

    readiness = (
        find_operational_four_day_sequence(
            iceberg_id
        )
    )

    if not readiness[
        "operational_member2_ready"
    ]:
        return {
            "iceberg_id":
                iceberg_id,

            "mode":
                "OPERATIONAL",

            "status":
                "CURRENT_ONLY",

            "trajectory_available":
                False,

            "readiness":
                readiness,

            "environment":
                None,

            "positions":
                {},

            "raw_prediction":
                None,

            "reason":
                readiness[
                    "reason"
                ],
        }

    position_input = readiness[
        "member2_input"
    ]

    environment_bundle = (
        load_member2_environment(
            date=
                position_input[
                    "date"
                ],

            latitude=
                position_input[
                    "current_latitude"
                ],

            longitude=
                position_input[
                    "current_longitude"
                ],
        )
    )

    result = _run_member2(
        iceberg_id=
            iceberg_id,

        position_input=
            position_input,

        environment_bundle=
            environment_bundle,
    )

    positions = result[
        "positions"
    ]

    expected_horizons = {
        "+24H",
        "+48H",
        "+72H",
    }

    complete = (
        expected_horizons
        == set(
            positions.keys()
        )
    )

    return {
        "iceberg_id":
            iceberg_id,

        "mode":
            "OPERATIONAL",

        "status":
            (
                "TRAJECTORY_READY"
                if complete
                else
                "TRAJECTORY_PARTIAL"
            ),

        "trajectory_available":
            bool(
                positions
            ),

        "trajectory_complete":
            complete,

        "readiness":
            readiness,

        "environment":
            environment_bundle,

        "positions":
            positions,

        "raw_prediction":
            result[
                "raw_prediction"
            ],

        "member2_environment_used":
            result[
                "member2_environment_used"
            ],

        "reason":
            (
                "Frozen Member-2 trajectory generated "
                "from four genuine current-aligned "
                "observations."
                if complete
                else
                "Frozen Member-2 executed, but one or more "
                "forecast horizons could not be normalized."
            ),
    }


# ============================================================
# HISTORICAL MEMBER-2 CASE LOADER
# ============================================================

def load_historical_member2_case(
    iceberg_id: str,
    init_date: Optional[str] = None,
) -> Dict:
    """
    Load one exact historical Member-2 initialization row.

    The row already contains:
        t-3
        t-2
        t-1
        current
        wind_u10
        wind_v10
        ocean_uo
        ocean_vo
        sea_ice_sic
        true +24/+48/+72 positions

    Today's environmental conditions are therefore never mixed
    with a historical trajectory.
    """

    iceberg_id = _normalize_id(
        iceberg_id
    )

    if not HISTORICAL_MEMBER2_DATASET.exists():
        raise FileNotFoundError(
            "Historical Member-2 dataset not found: "
            f"{HISTORICAL_MEMBER2_DATASET}"
        )

    dataframe = pd.read_csv(
        HISTORICAL_MEMBER2_DATASET
    )

    required_columns = [
        "iceberg_id",
        "init_date",

        "current_latitude",
        "current_longitude",

        "lat_tm1",
        "lon_tm1",

        "lat_tm2",
        "lon_tm2",

        "lat_tm3",
        "lon_tm3",

        "wind_u10",
        "wind_v10",

        "ocean_uo",
        "ocean_vo",

        "sea_ice_available",
        "sea_ice_sic_filled",

        "true_lat_24h",
        "true_lon_24h",

        "true_lat_48h",
        "true_lon_48h",

        "true_lat_72h",
        "true_lon_72h",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise RuntimeError(
            "Historical Member-2 dataset is missing columns: "
            + ", ".join(
                missing_columns
            )
        )

    dataframe[
        "iceberg_id"
    ] = (
        dataframe[
            "iceberg_id"
        ]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    dataframe[
        "init_date"
    ] = pd.to_datetime(
        dataframe[
            "init_date"
        ],
        errors="coerce",
    )

    dataframe = dataframe.dropna(
        subset=[
            "init_date",
        ]
    )

    subset = dataframe[
        dataframe[
            "iceberg_id"
        ]
        == iceberg_id
    ].copy()

    if subset.empty:
        raise KeyError(
            f"No historical Member-2 rows found "
            f"for iceberg {iceberg_id}."
        )

    if init_date is not None:

        requested_date = pd.Timestamp(
            init_date
        ).normalize()

        subset = subset[
            subset[
                "init_date"
            ].dt.normalize()
            == requested_date
        ].copy()

        if subset.empty:
            raise KeyError(
                f"No historical Member-2 row found "
                f"for {iceberg_id} on "
                f"{requested_date.strftime('%Y-%m-%d')}."
            )

    subset = subset.sort_values(
        "init_date"
    )

    row = subset.iloc[-1]

    # --------------------------------------------------------
    # SEA-ICE INITIALIZATION INPUT
    # --------------------------------------------------------

    sea_ice_sic = _safe_float(
        row[
            "sea_ice_sic_filled"
        ]
    )

    if sea_ice_sic is None:
        sea_ice_sic = _safe_float(
            row.get(
                "sea_ice_sic"
            )
        )

    sea_ice_available = int(
        row[
            "sea_ice_available"
        ]
    )

    # --------------------------------------------------------
    # POSITION INPUT
    # --------------------------------------------------------

    position_input = {
        "lat_tm3":
            float(
                row[
                    "lat_tm3"
                ]
            ),

        "lon_tm3":
            float(
                row[
                    "lon_tm3"
                ]
            ),

        "lat_tm2":
            float(
                row[
                    "lat_tm2"
                ]
            ),

        "lon_tm2":
            float(
                row[
                    "lon_tm2"
                ]
            ),

        "lat_tm1":
            float(
                row[
                    "lat_tm1"
                ]
            ),

        "lon_tm1":
            float(
                row[
                    "lon_tm1"
                ]
            ),

        "current_latitude":
            float(
                row[
                    "current_latitude"
                ]
            ),

        "current_longitude":
            float(
                row[
                    "current_longitude"
                ]
            ),

        "date":
            pd.Timestamp(
                row[
                    "init_date"
                ]
            ).strftime(
                "%Y-%m-%d"
            ),
    }

    # --------------------------------------------------------
    # MATCHING HISTORICAL ENVIRONMENT
    # --------------------------------------------------------

    environment = {
        "wind_u10":
            float(
                row[
                    "wind_u10"
                ]
            ),

        "wind_v10":
            float(
                row[
                    "wind_v10"
                ]
            ),

        "ocean_uo":
            float(
                row[
                    "ocean_uo"
                ]
            ),

        "ocean_vo":
            float(
                row[
                    "ocean_vo"
                ]
            ),

        "sea_ice_sic":
            sea_ice_sic,

        "sea_ice_available":
            sea_ice_available,
    }

    # --------------------------------------------------------
    # GROUND TRUTH
    # --------------------------------------------------------

    truth = {
        "+24H": {
            "latitude":
                float(
                    row[
                        "true_lat_24h"
                    ]
                ),

            "longitude":
                float(
                    row[
                        "true_lon_24h"
                    ]
                ),
        },

        "+48H": {
            "latitude":
                float(
                    row[
                        "true_lat_48h"
                    ]
                ),

            "longitude":
                float(
                    row[
                        "true_lon_48h"
                    ]
                ),
        },

        "+72H": {
            "latitude":
                float(
                    row[
                        "true_lat_72h"
                    ]
                ),

            "longitude":
                float(
                    row[
                        "true_lon_72h"
                    ]
                ),
        },
    }

    return {
        "iceberg_id":
            iceberg_id,

        "init_date":
            position_input[
                "date"
            ],

        "position_input":
            position_input,

        "environment":
            environment,

        "truth":
            truth,

        "data_split":
            str(
                row.get(
                    "data_split",
                    "",
                )
            ),

        "source":
            str(
                HISTORICAL_MEMBER2_DATASET
            ),
    }


# ============================================================
# HISTORICAL MEMBER-2 EXECUTION
# ============================================================

def run_historical_member2_case(
    iceberg_id: str,
    init_date: Optional[str] = None,
) -> Dict:
    """
    Run frozen Member-2 using one exact historical ML-ready
    initialization row.
    """

    case = (
        load_historical_member2_case(
            iceberg_id=
                iceberg_id,

            init_date=
                init_date,
        )
    )

    position = case[
        "position_input"
    ]

    environment = case[
        "environment"
    ]

    raw_prediction = predict_from_date(
        position[
            "lat_tm3"
        ],
        position[
            "lon_tm3"
        ],

        position[
            "lat_tm2"
        ],
        position[
            "lon_tm2"
        ],

        position[
            "lat_tm1"
        ],
        position[
            "lon_tm1"
        ],

        position[
            "current_latitude"
        ],
        position[
            "current_longitude"
        ],

        position[
            "date"
        ],

        float(
            environment[
                "wind_u10"
            ]
        ),

        float(
            environment[
                "wind_v10"
            ]
        ),

        float(
            environment[
                "ocean_uo"
            ]
        ),

        float(
            environment[
                "ocean_vo"
            ]
        ),

        (
            float(
                environment[
                    "sea_ice_sic"
                ]
            )
            if environment[
                "sea_ice_sic"
            ] is not None
            else None
        ),
    )

    normalized = (
        normalize_member2_prediction(
            iceberg_id=
                case[
                    "iceberg_id"
                ],

            initialization_date=
                case[
                    "init_date"
                ],

            prediction=
                raw_prediction,
        )
    )

    expected_horizons = {
        "+24H",
        "+48H",
        "+72H",
    }

    complete = (
        expected_horizons
        == set(
            normalized.keys()
        )
    )

    return {
        "iceberg_id":
            case[
                "iceberg_id"
            ],

        "mode":
            "HISTORICAL_DEMO",

        "status":
            (
                "TRAJECTORY_READY"
                if complete
                else
                "TRAJECTORY_PARTIAL"
            ),

        "trajectory_available":
            bool(
                normalized
            ),

        "trajectory_complete":
            complete,

        "initialization_date":
            case[
                "init_date"
            ],

        "data_split":
            case[
                "data_split"
            ],

        "position_input":
            case[
                "position_input"
            ],

        "environment":
            case[
                "environment"
            ],

        "positions":
            normalized,

        "truth":
            case[
                "truth"
            ],

        "raw_prediction":
            raw_prediction,

        "reason":
            (
                "Frozen Member-2 trajectory generated "
                "from an exact genuine historical "
                "ML-ready initialization row."
                if complete
                else
                "Frozen Member-2 executed, but one or more "
                "forecast horizons could not be normalized."
            ),
    }


def forecast_historical_iceberg(
    iceberg_id: str,
    init_date: Optional[str] = None,
) -> Dict:
    """
    Public historical/demo forecast interface.
    """

    return run_historical_member2_case(
        iceberg_id=
            iceberg_id,

        init_date=
            init_date,
    )


# ============================================================
# OPERATIONAL READINESS TEST
# ============================================================

def test_operational_readiness(
    iceberg_id: str,
) -> Dict:
    """
    Test CURRENT operational readiness without downloading
    environmental data and without running Member 2.
    """

    iceberg_id = _normalize_id(
        iceberg_id
    )

    readiness = (
        find_operational_four_day_sequence(
            iceberg_id
        )
    )

    return {
        "iceberg_id":
            iceberg_id,

        "operational_member2_ready":
            readiness[
                "operational_member2_ready"
            ],

        "latest_operational_date":
            readiness.get(
                "latest_operational_date"
            ),

        "missing_date":
            readiness.get(
                "missing_date"
            ),

        "reason":
            readiness[
                "reason"
            ],
    }


# ============================================================
# TERMINAL TEST
# ============================================================

def main():

    print()
    print("=" * 76)
    print(
        "POLARGUARD - OPERATIONAL TRAJECTORY SERVICE"
    )
    print("=" * 76)

    # --------------------------------------------------------
    # CURRENT OPERATIONAL SAFETY TEST
    # --------------------------------------------------------

    operational_id = "A76C"

    print()
    print(
        "CURRENT OPERATIONAL READINESS"
    )
    print("-" * 76)

    operational = (
        test_operational_readiness(
            operational_id
        )
    )

    for key, value in (
        operational.items()
    ):
        print(
            f"{key}: {value}"
        )

    print()

    if operational[
        "operational_member2_ready"
    ]:
        print(
            "Four current-aligned genuine observations "
            "are available."
        )

    else:
        print(
            "Current position remains usable as a "
            "CURRENT navigation hazard."
        )

        print(
            "Future Member-2 trajectory is intentionally "
            "not generated."
        )

    # --------------------------------------------------------
    # HISTORICAL MODEL TEST
    # --------------------------------------------------------

    print()
    print("=" * 76)
    print(
        "HISTORICAL MEMBER-2 MODEL TEST"
    )
    print("-" * 76)

    historical_id = "A23A"
    historical_date = "2025-12-28"

    try:
        result = (
            run_historical_member2_case(
                historical_id,
                historical_date,
            )
        )

        print(
            f"iceberg_id: "
            f"{result['iceberg_id']}"
        )

        print(
            f"initialization_date: "
            f"{result['initialization_date']}"
        )

        print(
            f"data_split: "
            f"{result['data_split']}"
        )

        print(
            f"status: "
            f"{result['status']}"
        )

        print(
            f"trajectory_available: "
            f"{result['trajectory_available']}"
        )

        print(
            f"trajectory_complete: "
            f"{result['trajectory_complete']}"
        )

        print()
        print(
            "MODEL PREDICTIONS"
        )

        for horizon in [
            "+24H",
            "+48H",
            "+72H",
        ]:

            prediction = (
                result[
                    "positions"
                ].get(
                    horizon
                )
            )

            if prediction is None:
                print(
                    f"  {horizon}: unavailable"
                )
                continue

            print(
                f"  {horizon}: "
                f"lat={prediction['latitude']:.6f}, "
                f"lon={prediction['longitude']:.6f}, "
                f"displacement="
                f"{prediction.get('predicted_displacement_km', float('nan')):.3f} km"
            )

        print()
        print(
            "HELD-OUT TRUTH"
        )

        for horizon in [
            "+24H",
            "+48H",
            "+72H",
        ]:

            truth = result[
                "truth"
            ][
                horizon
            ]

            print(
                f"  {horizon}: "
                f"lat={truth['latitude']:.6f}, "
                f"lon={truth['longitude']:.6f}"
            )

    except Exception as exc:

        print(
            "Historical Member-2 test failed:"
        )

        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )

    print()
    print("=" * 76)
    print(
        "Operational trajectory service: READY"
    )
    print("=" * 76)
    print()


if __name__ == "__main__":
    main()