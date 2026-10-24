# # from typing import List, Optional
# # from cesium_data_service import build_sea_ice_visualization
# # import numpy as np

# # from fastapi import FastAPI, HTTPException
# # from fastapi.middleware.cors import CORSMiddleware
# # from pydantic import BaseModel, Field

# # from sea_ice_service import (
# #     predict_sea_ice,
# #     load_uncertainty,
# # )

# # from polarguard_pipeline import (
# #     run_polarguard,
# # )

# # from risk_engine import (
# #     build_risk_grid,
# # )

# # from navigation_service import (
# #     build_navigation_route,
# # )


# # # ============================================================
# # # FASTAPI APP
# # # ============================================================

# # app = FastAPI(
# #     title="PolarGuard Cesium API",
# #     version="1.0.0",
# #     description=(
# #         "PolarGuard Antarctic sea-ice, iceberg, "
# #         "risk and navigation decision-support API."
# #     ),
# # )


# # # ============================================================
# # # CORS
# # # ============================================================

# # app.add_middleware(
# #     CORSMiddleware,

# #     allow_origins=[
# #         "http://127.0.0.1:5500",
# #         "http://localhost:5500",
# #     ],

# #     allow_credentials=False,
# #     allow_methods=["*"],
# #     allow_headers=["*"],
# # )


# # # ============================================================
# # # REQUEST MODELS
# # # ============================================================

# # class SeaIceRequest(BaseModel):

# #     current: List[List[Optional[float]]]

# #     lag1: List[List[Optional[float]]]
# #     lag2: List[List[Optional[float]]]
# #     lag3: List[List[Optional[float]]]

# #     x_coords: List[float]
# #     y_coords: List[float]

# #     date: str

# #     include_grids: bool = False


# # class IcebergRequest(BaseModel):

# #     lat_tm3: float
# #     lon_tm3: float

# #     lat_tm2: float
# #     lon_tm2: float

# #     lat_tm1: float
# #     lon_tm1: float

# #     current_latitude: float
# #     current_longitude: float

# #     date: str

# #     wind_u10: float
# #     wind_v10: float

# #     ocean_uo: float
# #     ocean_vo: float


# # class IcebergPosition(BaseModel):

# #     latitude: float
# #     longitude: float


# # class RiskRequest(BaseModel):

# #     sic: List[List[Optional[float]]]

# #     uncertainty: List[List[Optional[float]]]

# #     grid_lat: List[List[float]]
# #     grid_lon: List[List[float]]

# #     iceberg_positions: List[IcebergPosition] = (
# #         Field(default_factory=list)
# #     )

# #     safety_radius_km: float = 8.0
# #     influence_radius_km: float = 24.0


# # class RouteRequest(RiskRequest):

# #     start_lat: float
# #     start_lon: float

# #     destination_lat: float
# #     destination_lon: float

# #     vessel_profile: str = "MEDIUM"


# # # ============================================================
# # # HELPERS
# # # ============================================================

# # def array(values):

# #     return np.asarray(
# #         values,
# #         dtype=float,
# #     )


# # def finite_stats(values):

# #     arr = np.asarray(
# #         values,
# #         dtype=float,
# #     )

# #     valid = arr[
# #         np.isfinite(arr)
# #     ]

# #     if valid.size == 0:

# #         return {
# #             "valid_cells": 0,
# #             "mean": None,
# #             "min": None,
# #             "max": None,
# #         }

# #     return {

# #         "valid_cells":
# #             int(valid.size),

# #         "mean":
# #             float(np.mean(valid)),

# #         "min":
# #             float(np.min(valid)),

# #         "max":
# #             float(np.max(valid)),
# #     }


# # # ============================================================
# # # ROOT
# # # ============================================================

# # @app.get("/")
# # def root():

# #     return {

# #         "system":
# #             "PolarGuard",

# #         "status":
# #             "online",

# #         "mode":
# #             "prototype decision support",

# #         "frontend":
# #             "CesiumJS",

# #         "endpoints": [

# #             "/health",
# #             "/models",

# #             "/sea-ice",
# #             "/iceberg",

# #             "/risk",
# #             "/route",
# #         ],

# #         "disclaimer": (
# #             "Prototype decision-support system. "
# #             "Not certified for operational vessel navigation."
# #         ),
# #     }


# # # ============================================================
# # # HEALTH
# # # ============================================================

# # @app.get("/health")
# # def health():

# #     return {

# #         "status":
# #             "healthy",

# #         "service":
# #             "PolarGuard Cesium API",

# #         "sea_ice_service":
# #             "connected",

# #         "iceberg_pipeline":
# #             "connected",

# #         "risk_engine":
# #             "connected",

# #         "navigation_engine":
# #             "connected",
# #     }


# # # ============================================================
# # # MODEL INFORMATION
# # # ============================================================

# # @app.get("/models")
# # def models():

# #     return {

# #         "sea_ice": {

# #             "version":
# #                 "Hybrid v1 - Frozen",

# #             "horizons": [
# #                 "24h",
# #                 "48h",
# #                 "72h",
# #             ],

# #             "status":
# #                 "ready",
# #         },


# #         "iceberg": {

# #             "version":
# #                 "Environment v1 - Frozen",

# #             "horizons": [
# #                 "24h",
# #                 "48h",
# #                 "72h",
# #             ],

# #             "status":
# #                 "ready",
# #         },


# #         "navigation": {

# #             "algorithm":
# #                 "A* + PolarGuard Risk Engine",

# #             "status":
# #                 "ready",
# #         },


# #         "risk": {

# #             "mode":
# #                 "prototype weighted risk",

# #             "status":
# #                 "ready",
# #         },


# #         "disclaimer":
# #             "Not certified operational navigation.",
# #     }


# # # ============================================================
# # # SEA-ICE FORECAST
# # # ============================================================

# # @app.post("/sea-ice")
# # def sea_ice(
# #     request: SeaIceRequest
# # ):

# #     try:

# #         forecasts = predict_sea_ice(

# #             current=array(
# #                 request.current
# #             ),

# #             lag1=array(
# #                 request.lag1
# #             ),

# #             lag2=array(
# #                 request.lag2
# #             ),

# #             lag3=array(
# #                 request.lag3
# #             ),

# #             x_coords=np.asarray(
# #                 request.x_coords,
# #                 dtype=float,
# #             ),

# #             y_coords=np.asarray(
# #                 request.y_coords,
# #                 dtype=float,
# #             ),

# #             # IMPORTANT:
# #             # sea_ice_service expects numpy datetime64.
# #             date=np.datetime64(
# #                 request.date
# #             ),
# #         )


# #         uncertainty = (
# #             load_uncertainty()
# #         )


# #         response = {

# #             "initialization_date":
# #                 request.date,

# #             "model_version":
# #                 "hybrid-v1-frozen",


# #             "forecast_summary": {

# #                 "24h":
# #                     finite_stats(
# #                         forecasts["24h"]
# #                     ),

# #                 "48h":
# #                     finite_stats(
# #                         forecasts["48h"]
# #                     ),

# #                 "72h":
# #                     finite_stats(
# #                         forecasts["72h"]
# #                     ),
# #             },


# #             "uncertainty_summary": {

# #                 "24h":
# #                     finite_stats(
# #                         uncertainty["24h"]
# #                     ),

# #                 "48h":
# #                     finite_stats(
# #                         uncertainty["48h"]
# #                     ),

# #                 "72h":
# #                     finite_stats(
# #                         uncertainty["72h"]
# #                     ),
# #             },
# #         }


# #         if request.include_grids:

# #             response[
# #                 "forecast_grids"
# #             ] = {

# #                 "24h":
# #                     np.asarray(
# #                         forecasts["24h"]
# #                     ).tolist(),

# #                 "48h":
# #                     np.asarray(
# #                         forecasts["48h"]
# #                     ).tolist(),

# #                 "72h":
# #                     np.asarray(
# #                         forecasts["72h"]
# #                     ).tolist(),
# #             }


# #             response[
# #                 "uncertainty_grids"
# #             ] = {

# #                 "24h":
# #                     np.asarray(
# #                         uncertainty["24h"]
# #                     ).tolist(),

# #                 "48h":
# #                     np.asarray(
# #                         uncertainty["48h"]
# #                     ).tolist(),

# #                 "72h":
# #                     np.asarray(
# #                         uncertainty["72h"]
# #                     ).tolist(),
# #             }


# #         return response


# #     except Exception as exc:

# #         raise HTTPException(
# #             status_code=400,
# #             detail=str(exc),
# #         ) from exc


# # # ============================================================
# # # ICEBERG FORECAST
# # # ============================================================

# # @app.post("/iceberg")
# # def iceberg(
# #     request: IcebergRequest
# # ):

# #     try:

# #         result = run_polarguard(

# #             lat_tm3=
# #                 request.lat_tm3,

# #             lon_tm3=
# #                 request.lon_tm3,

# #             lat_tm2=
# #                 request.lat_tm2,

# #             lon_tm2=
# #                 request.lon_tm2,

# #             lat_tm1=
# #                 request.lat_tm1,

# #             lon_tm1=
# #                 request.lon_tm1,

# #             current_latitude=
# #                 request.current_latitude,

# #             current_longitude=
# #                 request.current_longitude,

# #             date=
# #                 request.date,

# #             wind_u10=
# #                 request.wind_u10,

# #             wind_v10=
# #                 request.wind_v10,

# #             ocean_uo=
# #                 request.ocean_uo,

# #             ocean_vo=
# #                 request.ocean_vo,
# #         )


# #         return result


# #     except Exception as exc:

# #         raise HTTPException(
# #             status_code=400,
# #             detail=str(exc),
# #         ) from exc


# # # ============================================================
# # # RISK GRID
# # # ============================================================

# # @app.post("/risk")
# # def risk(
# #     request: RiskRequest
# # ):

# #     try:

# #         result = build_risk_grid(

# #             sic=array(
# #                 request.sic
# #             ),

# #             uncertainty=array(
# #                 request.uncertainty
# #             ),

# #             grid_lat=array(
# #                 request.grid_lat
# #             ),

# #             grid_lon=array(
# #                 request.grid_lon
# #             ),

# #             iceberg_positions=[

# #                 position.model_dump()

# #                 for position
# #                 in request.iceberg_positions
# #             ],

# #             safety_radius_km=
# #                 request.safety_radius_km,

# #             influence_radius_km=
# #                 request.influence_radius_km,
# #         )


# #         return {

# #             "combined_risk":

# #                 np.asarray(
# #                     result[
# #                         "combined_risk"
# #                     ]
# #                 ).tolist(),


# #             "sea_ice_risk":

# #                 np.asarray(
# #                     result[
# #                         "sea_ice_risk"
# #                     ]
# #                 ).tolist(),


# #             "iceberg_risk":

# #                 np.asarray(
# #                     result[
# #                         "iceberg_risk"
# #                     ]
# #                 ).tolist(),


# #             "uncertainty_risk":

# #                 np.asarray(
# #                     result[
# #                         "uncertainty_risk"
# #                     ]
# #                 ).tolist(),


# #             "routing_cost":

# #                 np.asarray(
# #                     result[
# #                         "routing_cost"
# #                     ]
# #                 ).tolist(),


# #             "mode":
# #                 "prototype risk score",
# #         }


# #     except Exception as exc:

# #         raise HTTPException(
# #             status_code=400,
# #             detail=str(exc),
# #         ) from exc


# # # ============================================================
# # # SAFE NAVIGATION ROUTE
# # # ============================================================

# # @app.post("/route")
# # def route(
# #     request: RouteRequest
# # ):

# #     try:

# #         result = build_navigation_route(

# #             sic=array(
# #                 request.sic
# #             ),

# #             uncertainty=array(
# #                 request.uncertainty
# #             ),

# #             grid_lat=array(
# #                 request.grid_lat
# #             ),

# #             grid_lon=array(
# #                 request.grid_lon
# #             ),

# #             iceberg_positions=[

# #                 position.model_dump()

# #                 for position
# #                 in request.iceberg_positions
# #             ],

# #             start_lat=
# #                 request.start_lat,

# #             start_lon=
# #                 request.start_lon,

# #             destination_lat=
# #                 request.destination_lat,

# #             destination_lon=
# #                 request.destination_lon,

# #             vessel_profile=
# #                 request.vessel_profile,

# #             safety_radius_km=
# #                 request.safety_radius_km,

# #             influence_radius_km=
# #                 request.influence_radius_km,
# #         )


# #         return {

# #             "success":
# #                 bool(
# #                     result[
# #                         "success"
# #                     ]
# #                 ),


# #             "recommendation":
# #                 result.get(
# #                     "recommendation"
# #                 ),


# #             "route":
# #                 result.get(
# #                     "route"
# #                 ),


# #             # IMPORTANT:
# #             # navigation_service uses route_summary.
# #             "route_summary":
# #                 result.get(
# #                     "route_summary"
# #                 ),


# #             "constraint_summary":
# #                 result.get(
# #                     "constraint_summary"
# #                 ),


# #             "disclaimer": (
# #                 "Prototype decision support only; "
# #                 "not certified operational navigation."
# #             ),
# #         }


# #     except Exception as exc:

# #         raise HTTPException(
# #             status_code=400,
# #             detail=str(exc),
# #         ) from exc


# # # ============================================================
# # # RUN SERVER
# # # ============================================================
# # @app.get("/visualization/sea-ice")
# # def visualization_sea_ice(
# #     date: str = "2025-12-28",
# #     sample_step: int = 8,
# # ):

# #     try:

# #         if sample_step < 1:
# #             raise ValueError(
# #                 "sample_step must be at least 1."
# #             )

# #         if sample_step > 30:
# #             raise ValueError(
# #                 "sample_step must be 30 or less."
# #             )

# #         return build_sea_ice_visualization(
# #             initialization_date=date,
# #             sample_step=sample_step,
# #         )

# #     except Exception as exc:

# #         raise HTTPException(
# #             status_code=400,
# #             detail=str(exc),
# #         ) from exc

# # if __name__ == "__main__":

# #     import uvicorn

# #     uvicorn.run(

# #         app,

# #         host="127.0.0.1",

# #         port=8000,

# #         reload=False,
# #     )

# from typing import List, Optional

# import numpy as np

# from fastapi import FastAPI, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel, Field

# from sea_ice_service import (
#     predict_sea_ice,
#     load_uncertainty,
# )

# from polarguard_pipeline import (
#     run_polarguard,
# )

# from risk_engine import (
#     build_risk_grid,
# )

# from navigation_service import (
#     build_navigation_route,
# )

# from cesium_data_service import (
#     build_sea_ice_visualization,
# )


# # ============================================================
# # FASTAPI APP
# # ============================================================

# app = FastAPI(
#     title="PolarGuard Cesium API",
#     version="1.1.0",
#     description=(
#         "PolarGuard Antarctic sea-ice, iceberg, "
#         "risk and navigation decision-support API."
#     ),
# )


# # ============================================================
# # CORS
# # ============================================================

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=[
#         "http://127.0.0.1:5500",
#         "http://localhost:5500",
#     ],
#     allow_credentials=False,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


# # ============================================================
# # REQUEST MODELS
# # ============================================================

# class SeaIceRequest(BaseModel):

#     current: List[List[Optional[float]]]

#     lag1: List[List[Optional[float]]]
#     lag2: List[List[Optional[float]]]
#     lag3: List[List[Optional[float]]]

#     x_coords: List[float]
#     y_coords: List[float]

#     date: str

#     include_grids: bool = False


# class IcebergRequest(BaseModel):

#     lat_tm3: float
#     lon_tm3: float

#     lat_tm2: float
#     lon_tm2: float

#     lat_tm1: float
#     lon_tm1: float

#     current_latitude: float
#     current_longitude: float

#     date: str

#     wind_u10: float
#     wind_v10: float

#     ocean_uo: float
#     ocean_vo: float


# class IcebergPosition(BaseModel):

#     latitude: float
#     longitude: float


# class RiskRequest(BaseModel):

#     sic: List[List[Optional[float]]]

#     uncertainty: List[List[Optional[float]]]

#     grid_lat: List[List[float]]
#     grid_lon: List[List[float]]

#     iceberg_positions: List[IcebergPosition] = (
#         Field(default_factory=list)
#     )

#     safety_radius_km: float = 8.0
#     influence_radius_km: float = 24.0


# class RouteRequest(RiskRequest):

#     start_lat: float
#     start_lon: float

#     destination_lat: float
#     destination_lon: float

#     vessel_profile: str = "MEDIUM"


# # ============================================================
# # HELPERS
# # ============================================================

# def array(values):

#     return np.asarray(
#         values,
#         dtype=float,
#     )


# def finite_stats(values):

#     arr = np.asarray(
#         values,
#         dtype=float,
#     )

#     valid = arr[
#         np.isfinite(arr)
#     ]

#     if valid.size == 0:

#         return {
#             "valid_cells": 0,
#             "mean": None,
#             "min": None,
#             "max": None,
#         }

#     return {
#         "valid_cells":
#             int(valid.size),

#         "mean":
#             float(np.mean(valid)),

#         "min":
#             float(np.min(valid)),

#         "max":
#             float(np.max(valid)),
#     }


# # ============================================================
# # ROOT
# # ============================================================

# @app.get("/")
# def root():

#     return {

#         "system":
#             "PolarGuard",

#         "status":
#             "online",

#         "mode":
#             "prototype decision support",

#         "frontend":
#             "CesiumJS",

#         "endpoints": [
#             "/health",
#             "/models",
#             "/sea-ice",
#             "/iceberg",
#             "/risk",
#             "/route",
#             "/visualization/sea-ice",
#             "/visualization/full",
#         ],

#         "disclaimer": (
#             "Prototype decision-support system. "
#             "Not certified for operational vessel navigation."
#         ),
#     }


# # ============================================================
# # HEALTH
# # ============================================================

# @app.get("/health")
# def health():

#     return {

#         "status":
#             "healthy",

#         "service":
#             "PolarGuard Cesium API",

#         "sea_ice_service":
#             "connected",

#         "iceberg_pipeline":
#             "connected",

#         "risk_engine":
#             "connected",

#         "navigation_engine":
#             "connected",

#         "cesium_visualization":
#             "connected",
#     }


# # ============================================================
# # MODEL INFORMATION
# # ============================================================

# @app.get("/models")
# def models():

#     return {

#         "sea_ice": {

#             "version":
#                 "Hybrid v1 - Frozen",

#             "horizons": [
#                 "24h",
#                 "48h",
#                 "72h",
#             ],

#             "status":
#                 "ready",
#         },

#         "iceberg": {

#             "version":
#                 "Environment v1 - Frozen",

#             "horizons": [
#                 "24h",
#                 "48h",
#                 "72h",
#             ],

#             "status":
#                 "ready",
#         },

#         "navigation": {

#             "algorithm":
#                 "A* + PolarGuard Risk Engine",

#             "status":
#                 "ready",
#         },

#         "risk": {

#             "mode":
#                 "prototype weighted risk",

#             "status":
#                 "ready",
#         },

#         "disclaimer":
#             "Not certified operational navigation.",
#     }


# # ============================================================
# # SEA-ICE FORECAST
# # ============================================================

# @app.post("/sea-ice")
# def sea_ice(
#     request: SeaIceRequest
# ):

#     try:

#         forecasts = predict_sea_ice(

#             current=array(
#                 request.current
#             ),

#             lag1=array(
#                 request.lag1
#             ),

#             lag2=array(
#                 request.lag2
#             ),

#             lag3=array(
#                 request.lag3
#             ),

#             x_coords=np.asarray(
#                 request.x_coords,
#                 dtype=float,
#             ),

#             y_coords=np.asarray(
#                 request.y_coords,
#                 dtype=float,
#             ),

#             # IMPORTANT:
#             # sea_ice_service expects numpy datetime64.
#             date=np.datetime64(
#                 request.date
#             ),
#         )

#         uncertainty = (
#             load_uncertainty()
#         )

#         response = {

#             "initialization_date":
#                 request.date,

#             "model_version":
#                 "hybrid-v1-frozen",

#             "forecast_summary": {

#                 "24h":
#                     finite_stats(
#                         forecasts["24h"]
#                     ),

#                 "48h":
#                     finite_stats(
#                         forecasts["48h"]
#                     ),

#                 "72h":
#                     finite_stats(
#                         forecasts["72h"]
#                     ),
#             },

#             "uncertainty_summary": {

#                 "24h":
#                     finite_stats(
#                         uncertainty["24h"]
#                     ),

#                 "48h":
#                     finite_stats(
#                         uncertainty["48h"]
#                     ),

#                 "72h":
#                     finite_stats(
#                         uncertainty["72h"]
#                     ),
#             },
#         }

#         if request.include_grids:

#             response[
#                 "forecast_grids"
#             ] = {

#                 "24h":
#                     np.asarray(
#                         forecasts["24h"]
#                     ).tolist(),

#                 "48h":
#                     np.asarray(
#                         forecasts["48h"]
#                     ).tolist(),

#                 "72h":
#                     np.asarray(
#                         forecasts["72h"]
#                     ).tolist(),
#             }

#             response[
#                 "uncertainty_grids"
#             ] = {

#                 "24h":
#                     np.asarray(
#                         uncertainty["24h"]
#                     ).tolist(),

#                 "48h":
#                     np.asarray(
#                         uncertainty["48h"]
#                     ).tolist(),

#                 "72h":
#                     np.asarray(
#                         uncertainty["72h"]
#                     ).tolist(),
#             }

#         return response

#     except Exception as exc:

#         raise HTTPException(
#             status_code=400,
#             detail=str(exc),
#         ) from exc


# # ============================================================
# # ICEBERG FORECAST
# # ============================================================

# @app.post("/iceberg")
# def iceberg(
#     request: IcebergRequest
# ):

#     try:

#         result = run_polarguard(

#             lat_tm3=
#                 request.lat_tm3,

#             lon_tm3=
#                 request.lon_tm3,

#             lat_tm2=
#                 request.lat_tm2,

#             lon_tm2=
#                 request.lon_tm2,

#             lat_tm1=
#                 request.lat_tm1,

#             lon_tm1=
#                 request.lon_tm1,

#             current_latitude=
#                 request.current_latitude,

#             current_longitude=
#                 request.current_longitude,

#             date=
#                 request.date,

#             wind_u10=
#                 request.wind_u10,

#             wind_v10=
#                 request.wind_v10,

#             ocean_uo=
#                 request.ocean_uo,

#             ocean_vo=
#                 request.ocean_vo,
#         )

#         return result

#     except Exception as exc:

#         raise HTTPException(
#             status_code=400,
#             detail=str(exc),
#         ) from exc


# # ============================================================
# # RISK GRID
# # ============================================================

# @app.post("/risk")
# def risk(
#     request: RiskRequest
# ):

#     try:

#         result = build_risk_grid(

#             sic=array(
#                 request.sic
#             ),

#             uncertainty=array(
#                 request.uncertainty
#             ),

#             grid_lat=array(
#                 request.grid_lat
#             ),

#             grid_lon=array(
#                 request.grid_lon
#             ),

#             iceberg_positions=[

#                 position.model_dump()

#                 for position
#                 in request.iceberg_positions
#             ],

#             safety_radius_km=
#                 request.safety_radius_km,

#             influence_radius_km=
#                 request.influence_radius_km,
#         )

#         return {

#             "combined_risk":
#                 np.asarray(
#                     result[
#                         "combined_risk"
#                     ]
#                 ).tolist(),

#             "sea_ice_risk":
#                 np.asarray(
#                     result[
#                         "sea_ice_risk"
#                     ]
#                 ).tolist(),

#             "iceberg_risk":
#                 np.asarray(
#                     result[
#                         "iceberg_risk"
#                     ]
#                 ).tolist(),

#             "uncertainty_risk":
#                 np.asarray(
#                     result[
#                         "uncertainty_risk"
#                     ]
#                 ).tolist(),

#             "routing_cost":
#                 np.asarray(
#                     result[
#                         "routing_cost"
#                     ]
#                 ).tolist(),

#             "mode":
#                 "prototype risk score",
#         }

#     except Exception as exc:

#         raise HTTPException(
#             status_code=400,
#             detail=str(exc),
#         ) from exc


# # ============================================================
# # SAFE NAVIGATION ROUTE
# # ============================================================

# @app.post("/route")
# def route(
#     request: RouteRequest
# ):

#     try:

#         result = build_navigation_route(

#             sic=array(
#                 request.sic
#             ),

#             uncertainty=array(
#                 request.uncertainty
#             ),

#             grid_lat=array(
#                 request.grid_lat
#             ),

#             grid_lon=array(
#                 request.grid_lon
#             ),

#             iceberg_positions=[

#                 position.model_dump()

#                 for position
#                 in request.iceberg_positions
#             ],

#             start_lat=
#                 request.start_lat,

#             start_lon=
#                 request.start_lon,

#             destination_lat=
#                 request.destination_lat,

#             destination_lon=
#                 request.destination_lon,

#             vessel_profile=
#                 request.vessel_profile,

#             safety_radius_km=
#                 request.safety_radius_km,

#             influence_radius_km=
#                 request.influence_radius_km,
#         )

#         return {

#             "success":
#                 bool(
#                     result[
#                         "success"
#                     ]
#                 ),

#             "recommendation":
#                 result.get(
#                     "recommendation"
#                 ),

#             "route":
#                 result.get(
#                     "route"
#                 ),

#             # navigation_service uses route_summary.
#             "route_summary":
#                 result.get(
#                     "route_summary"
#                 ),

#             "constraint_summary":
#                 result.get(
#                     "constraint_summary"
#                 ),

#             "disclaimer": (
#                 "Prototype decision support only; "
#                 "not certified operational navigation."
#             ),
#         }

#     except Exception as exc:

#         raise HTTPException(
#             status_code=400,
#             detail=str(exc),
#         ) from exc


# # ============================================================
# # CESIUM SEA-ICE VISUALIZATION
# # ============================================================

# @app.get("/visualization/sea-ice")
# def visualization_sea_ice(
#     date: str = "2025-12-28",
#     sample_step: int = 8,
# ):

#     try:

#         if sample_step < 1:

#             raise ValueError(
#                 "sample_step must be at least 1."
#             )

#         if sample_step > 30:

#             raise ValueError(
#                 "sample_step must be 30 or less."
#             )

#         return build_sea_ice_visualization(
#             initialization_date=date,
#             sample_step=sample_step,
#         )

#     except Exception as exc:

#         raise HTTPException(
#             status_code=400,
#             detail=str(exc),
#         ) from exc


# # ============================================================
# # COMPLETE CESIUM VISUALIZATION
# # MEMBER 1 + MEMBER 2
# # ============================================================

# @app.get("/visualization/full")
# def visualization_full(
#     date: str = "2025-12-28",
#     sample_step: int = 5,
# ):

#     """
#     Complete synchronized PolarGuard visualization.

#     Member 1:
#     Sea-ice concentration + uncertainty.

#     Member 2:
#     Frozen environment-enhanced iceberg trajectory model.
#     """

#     try:

#         # ----------------------------------------------------
#         # VALIDATE DISPLAY SAMPLING
#         # ----------------------------------------------------

#         if sample_step < 1:

#             raise ValueError(
#                 "sample_step must be at least 1."
#             )

#         if sample_step > 20:

#             raise ValueError(
#                 "sample_step must be 20 or less."
#             )


#         # ----------------------------------------------------
#         # MEMBER 1 SEA-ICE
#         # ----------------------------------------------------

#         sea_ice = build_sea_ice_visualization(
#             initialization_date=date,
#             sample_step=sample_step,
#         )


#         # ----------------------------------------------------
#         # MEMBER 2 ICEBERG
#         #
#         # Existing PolarGuard demonstration trajectory.
#         # Environmental inputs are the frozen demo values.
#         # ----------------------------------------------------

#         iceberg_result = run_polarguard(

#             lat_tm3=-75.75435,
#             lon_tm3=-41.10950,

#             lat_tm2=-75.69135,
#             lon_tm2=-41.09485,

#             lat_tm1=-75.63525,
#             lon_tm1=-41.08170,

#             current_latitude=-75.611000,
#             current_longitude=-41.076000,

#             date=date,

#             wind_u10=-3.0,
#             wind_v10=2.0,

#             ocean_uo=-0.05,
#             ocean_vo=0.03,
#         )


#         # ----------------------------------------------------
#         # EXTRACT FROZEN MEMBER 2 FORECAST
#         # ----------------------------------------------------

#         iceberg_forecast = (
#             iceberg_result[
#                 "iceberg"
#             ][
#                 "forecast"
#             ]
#         )


#         # ----------------------------------------------------
#         # CESIUM-FRIENDLY ICEBERG PACKAGE
#         # ----------------------------------------------------

#         trajectory = {

#             "history": [

#                 {
#                     "stage":
#                         "t-3",

#                     "latitude":
#                         -75.75435,

#                     "longitude":
#                         -41.10950,
#                 },

#                 {
#                     "stage":
#                         "t-2",

#                     "latitude":
#                         -75.69135,

#                     "longitude":
#                         -41.09485,
#                 },

#                 {
#                     "stage":
#                         "t-1",

#                     "latitude":
#                         -75.63525,

#                     "longitude":
#                         -41.08170,
#                 },
#             ],


#             "current": {

#                 "stage":
#                     "current",

#                 "latitude":
#                     -75.611000,

#                 "longitude":
#                     -41.076000,
#             },


#             "forecast": {

#                 "24h":
#                     iceberg_forecast[
#                         "24h"
#                     ],

#                 "48h":
#                     iceberg_forecast[
#                         "48h"
#                     ],

#                 "72h":
#                     iceberg_forecast[
#                         "72h"
#                     ],
#             },


#             "environment": {

#                 "wind_u10_mps":
#                     -3.0,

#                 "wind_v10_mps":
#                     2.0,

#                 "ocean_uo_mps":
#                     -0.05,

#                 "ocean_vo_mps":
#                     0.03,
#             },


#             # Presentation / planning radius.
#             # NOT a collision probability.
#             "planning_buffer_km":
#                 10.0,


#             "buffer_disclaimer": (
#                 "Navigation planning buffer only. "
#                 "It is not a calibrated "
#                 "collision-probability region."
#             ),
#         }


#         # ----------------------------------------------------
#         # COMPLETE RESPONSE
#         # ----------------------------------------------------

#         return {

#             "system":
#                 "PolarGuard",

#             "initialization_date":
#                 date,

#             "sea_ice":
#                 sea_ice,

#             "iceberg":
#                 trajectory,

#             "models": {

#                 "sea_ice":
#                     "hybrid-v1-frozen",

#                 "iceberg":
#                     "environment-v1-frozen",
#             },

#             "disclaimer": (
#                 "Research prototype decision support only. "
#                 "Not certified for operational navigation."
#             ),
#         }


#     except Exception as exc:

#         raise HTTPException(
#             status_code=400,
#             detail=str(exc),
#         ) from exc


# # ============================================================
# # RUN SERVER
# # ============================================================

# if __name__ == "__main__":

#     import uvicorn

#     uvicorn.run(
#         app,
#         host="127.0.0.1",
#         port=8000,
#         reload=False,
#     )


import numpy as np

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel
from typing import List, Optional


from sea_ice_service import (
    predict_sea_ice,
    load_uncertainty,
)

from polarguard_pipeline import (
    run_polarguard,
)

from risk_engine import (
    build_risk_grid,
)

from navigation_service import (
    build_navigation_route,
)

from cesium_data_service import (
    build_sea_ice_visualization,
)

from sih_final_service import (
    run_sih_mission,
)


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="PolarGuard API",
    description=(
        "AI-enabled Antarctic sea-ice, iceberg trajectory, "
        "risk assessment and navigation decision-support API."
    ),
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# HELPERS
# ============================================================

def _array(value):
    return np.asarray(
        value,
        dtype=float,
    )


def _finite_stats(array):
    arr = np.asarray(
        array,
        dtype=float,
    )

    valid = arr[
        np.isfinite(arr)
    ]

    if valid.size == 0:
        return {
            "count": 0,
            "minimum": None,
            "maximum": None,
            "mean": None,
        }

    return {
        "count": int(
            valid.size
        ),
        "minimum": float(
            np.min(valid)
        ),
        "maximum": float(
            np.max(valid)
        ),
        "mean": float(
            np.mean(valid)
        ),
    }


# ============================================================
# REQUEST MODELS
# ============================================================

class SeaIceRequest(BaseModel):

    current: List[List[float]]
    lag1: List[List[float]]
    lag2: List[List[float]]
    lag3: List[List[float]]

    x_coords: List[float]
    y_coords: List[float]

    date: str

    include_grids: bool = False


class IcebergRequest(BaseModel):

    lat_tm3: float
    lon_tm3: float

    lat_tm2: float
    lon_tm2: float

    lat_tm1: float
    lon_tm1: float

    current_latitude: float
    current_longitude: float

    date: str

    wind_u10: float
    wind_v10: float

    ocean_uo: float
    ocean_vo: float


class IcebergPosition(BaseModel):

    latitude: float
    longitude: float


class RiskRequest(BaseModel):

    sic: List[List[float]]

    uncertainty: List[List[float]]

    grid_lat: List[List[float]]
    grid_lon: List[List[float]]

    iceberg_positions: List[
        IcebergPosition
    ]

    safety_radius_km: float = 10.0

    influence_radius_km: float = 30.0


class RouteRequest(BaseModel):

    sic: List[List[float]]

    uncertainty: List[List[float]]

    grid_lat: List[List[float]]
    grid_lon: List[List[float]]

    iceberg_positions: List[
        IcebergPosition
    ]

    start_lat: float
    start_lon: float

    destination_lat: float
    destination_lon: float

    vessel_profile: str = (
        "MEDIUM_ICE_CAPABILITY"
    )

    safety_radius_km: float = 10.0

    influence_radius_km: float = 30.0


class MissionRequest(BaseModel):

    initialization_date: str = (
        "2025-12-28"
    )

    lat_tm3: float = -75.75435
    lon_tm3: float = -41.10950

    lat_tm2: float = -75.69135
    lon_tm2: float = -41.09485

    lat_tm1: float = -75.63525
    lon_tm1: float = -41.08170

    current_latitude: float = (
        -75.611000
    )

    current_longitude: float = (
        -41.076000
    )

    wind_u10: float = -3.0
    wind_v10: float = 2.0

    ocean_uo: float = -0.05
    ocean_vo: float = 0.03

    routing_horizon: str = "24h"

    start_lat: float
    start_lon: float

    destination_lat: float
    destination_lon: float

    vessel_profile: str = "MEDIUM"

    safety_radius_km: float = 10.0

    sample_step: int = 6


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "system": "PolarGuard",
        "service": (
            "Antarctic Navigation "
            "Decision Support API"
        ),
        "status": "online",
        "version": "1.0.0",
        "documentation": "/docs",
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "healthy",
        "service": (
            "PolarGuard Cesium API"
        ),
        "sea_ice_service": (
            "connected"
        ),
        "iceberg_pipeline": (
            "connected"
        ),
        "risk_engine": (
            "connected"
        ),
        "navigation_engine": (
            "connected"
        ),
        "sih_final_service": (
            "connected"
        ),
    }


# ============================================================
# MODEL INFORMATION
# ============================================================

@app.get("/models")
def models():

    return {
        "sea_ice": {
            "version": (
                "hybrid-v1-frozen"
            ),
            "horizons": [
                "24h",
                "48h",
                "72h",
            ],
            "uncertainty": (
                "Historical per-grid-cell "
                "RMSE from 2024 validation "
                "residuals."
            ),
        },

        "iceberg": {
            "version": (
                "environment-v1-frozen"
            ),
            "horizons": [
                "24h",
                "48h",
                "72h",
            ],
        },

        "navigation": {
            "algorithm": (
                "A* + PolarGuard "
                "Risk Engine"
            ),
            "alternative_routes": True,
            "vessel_constraints": True,
            "hazard_intelligence": True,
        },

        "system": {
            "name": "PolarGuard",
            "mode": (
                "SIH prototype "
                "decision support"
            ),
        },
    }


# ============================================================
# SEA ICE
# ============================================================

@app.post("/sea-ice")
def sea_ice(
    request: SeaIceRequest,
):

    try:

        forecasts = (
            predict_sea_ice(

                current=_array(
                    request.current
                ),

                lag1=_array(
                    request.lag1
                ),

                lag2=_array(
                    request.lag2
                ),

                lag3=_array(
                    request.lag3
                ),

                x_coords=np.asarray(
                    request.x_coords,
                    dtype=float,
                ),

                y_coords=np.asarray(
                    request.y_coords,
                    dtype=float,
                ),

                date=np.datetime64(
                    request.date
                ),
            )
        )

        uncertainty = (
            load_uncertainty()
        )

        response = {

            "initialization_date":
                request.date,

            "model_version":
                "hybrid-v1-frozen",

            "forecast_summary": {

                "24h":
                    _finite_stats(
                        forecasts[
                            "24h"
                        ]
                    ),

                "48h":
                    _finite_stats(
                        forecasts[
                            "48h"
                        ]
                    ),

                "72h":
                    _finite_stats(
                        forecasts[
                            "72h"
                        ]
                    ),
            },

            "uncertainty_summary": {

                "24h":
                    _finite_stats(
                        uncertainty[
                            "24h"
                        ]
                    ),

                "48h":
                    _finite_stats(
                        uncertainty[
                            "48h"
                        ]
                    ),

                "72h":
                    _finite_stats(
                        uncertainty[
                            "72h"
                        ]
                    ),
            },
        }

        if request.include_grids:

            response[
                "forecast_grids"
            ] = {

                "24h":
                    np.asarray(
                        forecasts[
                            "24h"
                        ]
                    ).tolist(),

                "48h":
                    np.asarray(
                        forecasts[
                            "48h"
                        ]
                    ).tolist(),

                "72h":
                    np.asarray(
                        forecasts[
                            "72h"
                        ]
                    ).tolist(),
            }

        return response

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# ICEBERG
# ============================================================

@app.post("/iceberg")
def iceberg(
    request: IcebergRequest,
):

    try:

        return run_polarguard(

            lat_tm3=
                request.lat_tm3,

            lon_tm3=
                request.lon_tm3,

            lat_tm2=
                request.lat_tm2,

            lon_tm2=
                request.lon_tm2,

            lat_tm1=
                request.lat_tm1,

            lon_tm1=
                request.lon_tm1,

            current_latitude=
                request.current_latitude,

            current_longitude=
                request.current_longitude,

            date=
                request.date,

            wind_u10=
                request.wind_u10,

            wind_v10=
                request.wind_v10,

            ocean_uo=
                request.ocean_uo,

            ocean_vo=
                request.ocean_vo,
        )

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# RISK
# ============================================================

@app.post("/risk")
def risk(
    request: RiskRequest,
):

    try:

        result = build_risk_grid(

            sic=_array(
                request.sic
            ),

            uncertainty=_array(
                request.uncertainty
            ),

            grid_lat=_array(
                request.grid_lat
            ),

            grid_lon=_array(
                request.grid_lon
            ),

            iceberg_positions=[

                position.model_dump()

                for position
                in request.iceberg_positions
            ],

            safety_radius_km=
                request.safety_radius_km,

            influence_radius_km=
                request.influence_radius_km,
        )

        return {

            "combined_risk":
                np.asarray(
                    result[
                        "combined_risk"
                    ]
                ).tolist(),

            "routing_cost":
                np.asarray(
                    result[
                        "routing_cost"
                    ]
                ).tolist(),

            "sea_ice_risk":
                np.asarray(
                    result[
                        "sea_ice_risk"
                    ]
                ).tolist(),

            "iceberg_risk":
                np.asarray(
                    result[
                        "iceberg_risk"
                    ]
                ).tolist(),

            "uncertainty_risk":
                np.asarray(
                    result[
                        "uncertainty_risk"
                    ]
                ).tolist(),

            "mode":
                "prototype risk score",
        }

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# ROUTE
# ============================================================

@app.post("/route")
def route(
    request: RouteRequest,
):

    try:

        result = (
            build_navigation_route(

                sic=_array(
                    request.sic
                ),

                uncertainty=_array(
                    request.uncertainty
                ),

                grid_lat=_array(
                    request.grid_lat
                ),

                grid_lon=_array(
                    request.grid_lon
                ),

                iceberg_positions=[

                    position.model_dump()

                    for position
                    in request.iceberg_positions
                ],

                start_lat=
                    request.start_lat,

                start_lon=
                    request.start_lon,

                destination_lat=
                    request.destination_lat,

                destination_lon=
                    request.destination_lon,

                vessel_profile=
                    request.vessel_profile,

                safety_radius_km=
                    request.safety_radius_km,

                influence_radius_km=
                    request.influence_radius_km,
            )
        )

        return {

            "success":
                result[
                    "success"
                ],

            "route":
                result[
                    "route"
                ],

            "route_summary":
                result[
                    "route_summary"
                ],

            "constraint_summary":
                result[
                    "constraint_summary"
                ],

            "recommendation":
                result[
                    "recommendation"
                ],
        }

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# EXISTING CESIUM SEA-ICE VISUALIZATION
# ============================================================

@app.get(
    "/visualization/sea-ice"
)
def visualization_sea_ice(

    date: str = "2025-12-28",

    sample_step: int = 8,
):

    try:

        if sample_step < 1:

            raise ValueError(
                "sample_step must be "
                "at least 1."
            )

        if sample_step > 30:

            raise ValueError(
                "sample_step must be "
                "30 or less."
            )

        return (
            build_sea_ice_visualization(

                initialization_date=
                    date,

                sample_step=
                    sample_step,
            )
        )

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# SYNCHRONIZED SEA ICE + ICEBERG VISUALIZATION
# ============================================================

@app.get(
    "/visualization/full"
)
def visualization_full(

    date: str = "2025-12-28",

    sample_step: int = 5,
):

    try:

        if sample_step < 1:

            raise ValueError(
                "sample_step must be "
                "at least 1."
            )

        if sample_step > 20:

            raise ValueError(
                "sample_step must be "
                "20 or less."
            )


        sea_ice_data = (
            build_sea_ice_visualization(

                initialization_date=
                    date,

                sample_step=
                    sample_step,
            )
        )


        iceberg_data = (
            run_polarguard(

                lat_tm3=
                    -75.75435,

                lon_tm3=
                    -41.10950,

                lat_tm2=
                    -75.69135,

                lon_tm2=
                    -41.09485,

                lat_tm1=
                    -75.63525,

                lon_tm1=
                    -41.08170,

                current_latitude=
                    -75.611000,

                current_longitude=
                    -41.076000,

                date=
                    date,

                wind_u10=
                    -3.0,

                wind_v10=
                    2.0,

                ocean_uo=
                    -0.05,

                ocean_vo=
                    0.03,
            )
        )


        forecasts = (
            iceberg_data[
                "iceberg"
            ][
                "forecast"
            ]
        )


        trajectory = {

            "history": [

                {
                    "stage": "t-3",
                    "latitude": -75.75435,
                    "longitude": -41.10950,
                },

                {
                    "stage": "t-2",
                    "latitude": -75.69135,
                    "longitude": -41.09485,
                },

                {
                    "stage": "t-1",
                    "latitude": -75.63525,
                    "longitude": -41.08170,
                },
            ],

            "current": {

                "stage": "current",

                "latitude":
                    -75.611000,

                "longitude":
                    -41.076000,
            },

            "forecast": {

                "24h":
                    forecasts[
                        "24h"
                    ],

                "48h":
                    forecasts[
                        "48h"
                    ],

                "72h":
                    forecasts[
                        "72h"
                    ],
            },

            "environment": {

                "wind_u10_mps":
                    -3.0,

                "wind_v10_mps":
                    2.0,

                "ocean_uo_mps":
                    -0.05,

                "ocean_vo_mps":
                    0.03,
            },

            "planning_buffer_km":
                10.0,

            "buffer_disclaimer": (
                "Navigation planning buffer only. "
                "It is not a calibrated "
                "collision-probability region."
            ),
        }


        return {

            "system":
                "PolarGuard",

            "initialization_date":
                date,

            "sea_ice":
                sea_ice_data,

            "iceberg":
                trajectory,

            "models": {

                "sea_ice":
                    "hybrid-v1-frozen",

                "iceberg":
                    "environment-v1-frozen",
            },

            "disclaimer": (
                "Research prototype "
                "decision support only. "
                "Not certified for "
                "operational navigation."
            ),
        }

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# COMPLETE SIH MISSION ENDPOINT
# ============================================================

@app.post(
    "/mission"
)
def mission(
    request: MissionRequest,
):

    try:

        return run_sih_mission(

            initialization_date=
                request.initialization_date,

            lat_tm3=
                request.lat_tm3,

            lon_tm3=
                request.lon_tm3,

            lat_tm2=
                request.lat_tm2,

            lon_tm2=
                request.lon_tm2,

            lat_tm1=
                request.lat_tm1,

            lon_tm1=
                request.lon_tm1,

            current_latitude=
                request.current_latitude,

            current_longitude=
                request.current_longitude,

            wind_u10=
                request.wind_u10,

            wind_v10=
                request.wind_v10,

            ocean_uo=
                request.ocean_uo,

            ocean_vo=
                request.ocean_vo,

            routing_horizon=
                request.routing_horizon,

            start_lat=
                request.start_lat,

            start_lon=
                request.start_lon,

            destination_lat=
                request.destination_lat,

            destination_lon=
                request.destination_lon,

            vessel_profile=
                request.vessel_profile,

            safety_radius_km=
                request.safety_radius_km,

            sample_step=
                request.sample_step,
        )

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
    )