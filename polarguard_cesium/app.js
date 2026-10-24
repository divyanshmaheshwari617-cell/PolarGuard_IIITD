// // // const API_BASE = "http://127.0.0.1:8000";
// // // // ============================================================
// // // // POLARGUARD REAL SEA-ICE VISUALIZATION
// // // // ============================================================

// // // let seaIceEntities = [];
// // // let seaIceData = null;
// // // let activeSeaIceHorizon = "current";


// // // // ============================================================
// // // // POLARGUARD STATE
// // // // ============================================================

// // // const state = {
// // //     horizon: "current",

// // //     recommendedEntity: null,
// // //     alternativeEntity: null,

// // //     recommendedData: null,
// // //     alternativeData: null
// // // };


// // // // ============================================================
// // // // CREATE CESIUM VIEWER
// // // // ============================================================

// // // const viewer = new Cesium.Viewer("cesiumContainer", {

// // //     animation: false,
// // //     timeline: false,

// // //     baseLayerPicker: false,
// // //     geocoder: false,
// // //     homeButton: false,

// // //     sceneModePicker: true,
// // //     navigationHelpButton: false,

// // //     fullscreenButton: true,
// // //     infoBox: true,
// // //     selectionIndicator: true,

// // //     terrainProvider: new Cesium.EllipsoidTerrainProvider(),

// // //     imageryProvider: new Cesium.OpenStreetMapImageryProvider({
// // //         url: "https://tile.openstreetmap.org/"
// // //     })
// // // });


// // // // ============================================================
// // // // BASIC CESIUM APPEARANCE
// // // // ============================================================

// // // viewer.scene.globe.enableLighting = true;

// // // viewer.scene.globe.showGroundAtmosphere = true;

// // // viewer.scene.backgroundColor =
// // //     Cesium.Color.fromCssColorString("#07111f");


// // // // ============================================================
// // // // ANTARCTIC CAMERA
// // // // ============================================================

// // // function resetAntarcticView() {

// // //     viewer.camera.flyTo({

// // //         destination:
// // //             Cesium.Cartesian3.fromDegrees(
// // //                 0.0,
// // //                 -89.0,
// // //                 8500000.0
// // //             ),

// // //         orientation: {

// // //             heading: 0.0,

// // //             pitch:
// // //                 Cesium.Math.toRadians(-90.0),

// // //             roll: 0.0
// // //         },

// // //         duration: 1.2
// // //     });
// // // }


// // // resetAntarcticView();


// // // // ============================================================
// // // // API STATUS
// // // // ============================================================

// // // function setApiStatus(
// // //     online,
// // //     message
// // // ) {

// // //     const status =
// // //         document.getElementById("apiStatus");

// // //     status.textContent =
// // //         online
// // //             ? "API Online"
// // //             : "API Offline";


// // //     status.classList.remove(
// // //         "status-online",
// // //         "status-offline"
// // //     );


// // //     status.classList.add(
// // //         online
// // //             ? "status-online"
// // //             : "status-offline"
// // //     );


// // //     if (message) {

// // //         document.getElementById(
// // //             "modelStatus"
// // //         ).textContent = message;
// // //     }
// // // }


// // // // ============================================================
// // // // CHECK FASTAPI BACKEND
// // // // ============================================================

// // // async function checkApi() {

// // //     try {

// // //         const health =
// // //             await fetch(
// // //                 `${API_BASE}/health`
// // //             );


// // //         if (!health.ok) {

// // //             throw new Error(
// // //                 "Health endpoint returned an error."
// // //             );
// // //         }


// // //         const modelsResponse =
// // //             await fetch(
// // //                 `${API_BASE}/models`
// // //             );


// // //         if (!modelsResponse.ok) {

// // //             throw new Error(
// // //                 "Models endpoint returned an error."
// // //             );
// // //         }


// // //         const models =
// // //             await modelsResponse.json();


// // //         setApiStatus(
// // //             true,

// // //             `Sea ice: ${models.sea_ice.version} | ` +
// // //             `Iceberg: ${models.iceberg.version} | ` +
// // //             `Navigation: ${models.navigation.algorithm}`
// // //         );


// // //         addAlert(
// // //             "safe",
// // //             "PolarGuard backend connected successfully."
// // //         );

// // //     }

// // //     catch (error) {

// // //         setApiStatus(
// // //             false,

// // //             `Cannot reach ${API_BASE}. ` +
// // //             `Start polarguard_api_cesium.py first.`
// // //         );


// // //         addAlert(
// // //             "warning",
// // //             "FastAPI backend is currently offline."
// // //         );
// // //     }
// // // }


// // // // ============================================================
// // // // READ ROUTE FROM GEOJSON
// // // // ============================================================

// // // function geometryCoordinatesFromGeoJson(
// // //     geojson
// // // ) {

// // //     if (
// // //         !geojson ||
// // //         geojson.type !== "FeatureCollection" ||
// // //         !Array.isArray(
// // //             geojson.features
// // //         ) ||
// // //         geojson.features.length === 0
// // //     ) {

// // //         throw new Error(
// // //             "Expected a GeoJSON FeatureCollection."
// // //         );
// // //     }


// // //     const feature =
// // //         geojson.features[0];


// // //     if (
// // //         !feature.geometry ||
// // //         feature.geometry.type !==
// // //             "LineString"
// // //     ) {

// // //         throw new Error(
// // //             "Expected a GeoJSON LineString."
// // //         );
// // //     }


// // //     return {

// // //         coordinates:
// // //             feature.geometry.coordinates,

// // //         properties:
// // //             feature.properties || {}
// // //     };
// // // }


// // // // ============================================================
// // // // FORMAT DISTANCE
// // // // ============================================================

// // // function formatDistance(value) {

// // //     const number =
// // //         Number(value);


// // //     if (
// // //         !Number.isFinite(number)
// // //     ) {

// // //         return "—";
// // //     }


// // //     return `${number.toFixed(1)} km`;
// // // }


// // // // ============================================================
// // // // ADD ROUTE TO 3D MAP
// // // // ============================================================

// // // function addRouteToViewer(
// // //     routeType,
// // //     geojson
// // // ) {

// // //     const parsed =
// // //         geometryCoordinatesFromGeoJson(
// // //             geojson
// // //         );


// // //     const positions =
// // //         parsed.coordinates.map(
// // //             ([lon, lat]) =>

// // //                 Cesium.Cartesian3.fromDegrees(
// // //                     Number(lon),
// // //                     Number(lat),
// // //                     2500
// // //                 )
// // //         );


// // //     const isRecommended =
// // //         routeType === "recommended";


// // //     const routeName =
// // //         isRecommended
// // //             ? "Recommended Route"
// // //             : "Alternative Route";


// // //     const entity =
// // //         viewer.entities.add({

// // //             name: routeName,


// // //             polyline: {

// // //                 positions: positions,

// // //                 width:
// // //                     isRecommended
// // //                         ? 7
// // //                         : 6,

// // //                 clampToGround: false,


// // //                 material:

// // //                     isRecommended

// // //                         ?

// // //                         Cesium.Color.LIME
// // //                             .withAlpha(0.95)

// // //                         :

// // //                         new Cesium
// // //                             .PolylineDashMaterialProperty({

// // //                                 color:
// // //                                     Cesium.Color
// // //                                         .DODGERBLUE,

// // //                                 dashLength: 18
// // //                             })
// // //             },


// // //             description:

// // //                 `<h3>${routeName}</h3>` +

// // //                 `<b>Distance:</b> ` +
// // //                 `${parsed.properties.distance_km ?? "N/A"} km<br>` +

// // //                 `<b>Forecast Horizon:</b> ` +
// // //                 `${parsed.properties.routing_horizon ?? "N/A"}<br>` +

// // //                 `<b>Vessel Profile:</b> ` +
// // //                 `${parsed.properties.vessel_profile ?? "N/A"}`
// // //         });


// // // // ============================================================
// // // // SAVE RECOMMENDED ROUTE
// // // // ============================================================

// // //     if (isRecommended) {

// // //         if (
// // //             state.recommendedEntity
// // //         ) {

// // //             viewer.entities.remove(
// // //                 state.recommendedEntity
// // //             );
// // //         }


// // //         state.recommendedEntity =
// // //             entity;


// // //         state.recommendedData =
// // //             geojson;


// // //         document.getElementById(
// // //             "recommendedDistance"
// // //         ).textContent =
// // //             formatDistance(
// // //                 parsed.properties.distance_km
// // //             );


// // //         document.getElementById(
// // //             "cmpRecDistance"
// // //         ).textContent =
// // //             formatDistance(
// // //                 parsed.properties.distance_km
// // //             );
// // //     }


// // // // ============================================================
// // // // SAVE ALTERNATIVE ROUTE
// // // // ============================================================

// // //     else {

// // //         if (
// // //             state.alternativeEntity
// // //         ) {

// // //             viewer.entities.remove(
// // //                 state.alternativeEntity
// // //             );
// // //         }


// // //         state.alternativeEntity =
// // //             entity;


// // //         state.alternativeData =
// // //             geojson;


// // //         document.getElementById(
// // //             "alternativeDistance"
// // //         ).textContent =
// // //             formatDistance(
// // //                 parsed.properties.distance_km
// // //             );


// // //         document.getElementById(
// // //             "cmpAltDistance"
// // //         ).textContent =
// // //             formatDistance(
// // //                 parsed.properties.distance_km
// // //             );


// // //         if (
// // //             parsed.properties
// // //                 .route_overlap_percent !==
// // //             undefined
// // //         ) {

// // //             document.getElementById(
// // //                 "routeOverlap"
// // //             ).textContent =

// // //                 `${Number(
// // //                     parsed.properties
// // //                         .route_overlap_percent
// // //                 ).toFixed(1)}%`;
// // //         }
// // //     }


// // //     refreshVisibility();


// // //     fitRoutes();
// // // }


// // // // ============================================================
// // // // LOAD GEOJSON FILE
// // // // ============================================================

// // // async function loadGeoJsonFile(
// // //     file,
// // //     routeType
// // // ) {

// // //     const text =
// // //         await file.text();


// // //     const geojson =
// // //         JSON.parse(text);


// // //     addRouteToViewer(
// // //         routeType,
// // //         geojson
// // //     );


// // //     addAlert(

// // //         "info",

// // //         `${
// // //             routeType === "recommended"
// // //                 ? "Recommended"
// // //                 : "Alternative"
// // //         } route loaded successfully.`
// // //     );
// // // }


// // // // ============================================================
// // // // ALERT SYSTEM
// // // // ============================================================

// // // function addAlert(
// // //     level,
// // //     message
// // // ) {

// // //     const alerts =
// // //         document.getElementById(
// // //             "alerts"
// // //         );


// // //     if (
// // //         alerts.children.length === 1 &&
// // //         alerts.textContent.includes(
// // //             "Load route exports"
// // //         )
// // //     ) {

// // //         alerts.innerHTML = "";
// // //     }


// // //     const item =
// // //         document.createElement(
// // //             "div"
// // //         );


// // //     item.className =
// // //         `alert ${level}`;


// // //     item.textContent =
// // //         message;


// // //     alerts.prepend(
// // //         item
// // //     );
// // // }


// // // // ============================================================
// // // // CLEAR ROUTES
// // // // ============================================================

// // // function clearRoutes() {

// // //     if (
// // //         state.recommendedEntity
// // //     ) {

// // //         viewer.entities.remove(
// // //             state.recommendedEntity
// // //         );
// // //     }


// // //     if (
// // //         state.alternativeEntity
// // //     ) {

// // //         viewer.entities.remove(
// // //             state.alternativeEntity
// // //         );
// // //     }


// // //     state.recommendedEntity =
// // //         null;


// // //     state.alternativeEntity =
// // //         null;


// // //     state.recommendedData =
// // //         null;


// // //     state.alternativeData =
// // //         null;


// // //     document.getElementById(
// // //         "recommendedDistance"
// // //     ).textContent = "—";


// // //     document.getElementById(
// // //         "alternativeDistance"
// // //     ).textContent = "—";


// // //     document.getElementById(
// // //         "routeOverlap"
// // //     ).textContent = "—";


// // //     document.getElementById(
// // //         "cmpRecDistance"
// // //     ).textContent = "—";


// // //     document.getElementById(
// // //         "cmpAltDistance"
// // //     ).textContent = "—";


// // //     addAlert(
// // //         "info",
// // //         "Routes cleared."
// // //     );
// // // }


// // // // ============================================================
// // // // FIT CAMERA TO ROUTES
// // // // ============================================================

// // // function fitRoutes() {

// // //     const entities = [];


// // //     if (
// // //         state.recommendedEntity
// // //     ) {

// // //         entities.push(
// // //             state.recommendedEntity
// // //         );
// // //     }


// // //     if (
// // //         state.alternativeEntity
// // //     ) {

// // //         entities.push(
// // //             state.alternativeEntity
// // //         );
// // //     }


// // //     if (
// // //         entities.length === 0
// // //     ) {

// // //         resetAntarcticView();

// // //         return;
// // //     }


// // //     viewer.flyTo(

// // //         entities,

// // //         {

// // //             duration: 1.2,

// // //             offset:

// // //                 new Cesium
// // //                     .HeadingPitchRange(

// // //                         0,

// // //                         Cesium.Math
// // //                             .toRadians(-75),

// // //                         250000
// // //                     )
// // //         }
// // //     );
// // // }


// // // // ============================================================
// // // // ROUTE VISIBILITY
// // // // ============================================================

// // // function refreshVisibility() {

// // //     const showRecommended =
// // //         document.getElementById(
// // //             "showRecommended"
// // //         ).checked;


// // //     const showAlternative =
// // //         document.getElementById(
// // //             "showAlternative"
// // //         ).checked;


// // //     if (
// // //         state.recommendedEntity
// // //     ) {

// // //         state.recommendedEntity.show =
// // //             showRecommended;
// // //     }


// // //     if (
// // //         state.alternativeEntity
// // //     ) {

// // //         state.alternativeEntity.show =
// // //             showAlternative;
// // //     }
// // // }


// // // // ============================================================
// // // // FORECAST HORIZON
// // // // ============================================================

// // // function changeHorizon(
// // //     horizon
// // // ) {

// // //     state.horizon =
// // //         horizon;


// // //     document
// // //         .querySelectorAll(
// // //             ".horizon-btn"
// // //         )
// // //         .forEach(
// // //             (button) => {

// // //                 button.classList.toggle(

// // //                     "active",

// // //                     button.dataset.horizon ===
// // //                         horizon
// // //                 );
// // //             }
// // //         );


// // //     const label =

// // //         horizon === "current"

// // //             ? "Current"

// // //             : `+${horizon}`;


// // //     document.getElementById(
// // //         "currentHorizon"
// // //     ).textContent =
// // //         label;


// // //     document.getElementById(
// // //         "summaryHorizon"
// // //     ).textContent =
// // //         label;


// // //     addAlert(

// // //         "info",

// // //         `Visualization horizon changed to ${label}.`
// // //     );
// // // }


// // // // ============================================================
// // // // HORIZON BUTTON EVENTS
// // // // ============================================================

// // // document
// // //     .querySelectorAll(
// // //         ".horizon-btn"
// // //     )
// // //     .forEach(
// // //         (button) => {

// // //             button.addEventListener(

// // //                 "click",

// // //                 () =>
// // //                     changeHorizon(
// // //                         button.dataset.horizon
// // //                     )
// // //             );
// // //         }
// // //     );


// // // // ============================================================
// // // // API BUTTON
// // // // ============================================================

// // // document
// // //     .getElementById(
// // //         "connectApiBtn"
// // //     )
// // //     .addEventListener(

// // //         "click",

// // //         checkApi
// // //     );


// // // // ============================================================
// // // // RECOMMENDED ROUTE UPLOAD
// // // // ============================================================

// // // document
// // //     .getElementById(
// // //         "recommendedFile"
// // //     )
// // //     .addEventListener(

// // //         "change",

// // //         async (event) => {

// // //             const file =
// // //                 event.target.files[0];


// // //             if (!file) {

// // //                 return;
// // //             }


// // //             try {

// // //                 await loadGeoJsonFile(

// // //                     file,

// // //                     "recommended"
// // //                 );

// // //             }

// // //             catch (error) {

// // //                 addAlert(

// // //                     "critical",

// // //                     `Recommended route load failed: ${error.message}`
// // //                 );
// // //             }
// // //         }
// // //     );


// // // // ============================================================
// // // // ALTERNATIVE ROUTE UPLOAD
// // // // ============================================================

// // // document
// // //     .getElementById(
// // //         "alternativeFile"
// // //     )
// // //     .addEventListener(

// // //         "change",

// // //         async (event) => {

// // //             const file =
// // //                 event.target.files[0];


// // //             if (!file) {

// // //                 return;
// // //             }


// // //             try {

// // //                 await loadGeoJsonFile(

// // //                     file,

// // //                     "alternative"
// // //                 );

// // //             }

// // //             catch (error) {

// // //                 addAlert(

// // //                     "critical",

// // //                     `Alternative route load failed: ${error.message}`
// // //                 );
// // //             }
// // //         }
// // //     );


// // // // ============================================================
// // // // CLEAR ROUTES BUTTON
// // // // ============================================================

// // // document
// // //     .getElementById(
// // //         "clearRoutesBtn"
// // //     )
// // //     .addEventListener(

// // //         "click",

// // //         clearRoutes
// // //     );


// // // // ============================================================
// // // // RESET VIEW BUTTON
// // // // ============================================================

// // // document
// // //     .getElementById(
// // //         "resetViewBtn"
// // //     )
// // //     .addEventListener(

// // //         "click",

// // //         resetAntarcticView
// // //     );


// // // // ============================================================
// // // // FIT ROUTES BUTTON
// // // // ============================================================

// // // document
// // //     .getElementById(
// // //         "fitRoutesBtn"
// // //     )
// // //     .addEventListener(

// // //         "click",

// // //         fitRoutes
// // //     );


// // // // ============================================================
// // // // LAYER CHECKBOX EVENTS
// // // // ============================================================

// // // document
// // //     .getElementById(
// // //         "showRecommended"
// // //     )
// // //     .addEventListener(

// // //         "change",

// // //         refreshVisibility
// // //     );


// // // document
// // //     .getElementById(
// // //         "showAlternative"
// // //     )
// // //     .addEventListener(

// // //         "change",

// // //         refreshVisibility
// // //     );


// // // // ============================================================
// // // // INITIAL BACKEND CHECK
// // // // ============================================================
// // // // ============================================================
// // // // REAL MEMBER 1 SEA-ICE DATA
// // // // ============================================================

// // // async function loadRealSeaIce() {

// // //     try {

// // //         addAlert(
// // //             "INFO",
// // //             "Loading PolarGuard sea-ice forecast..."
// // //         );

// // //         const response = await fetch(
// // //             `${API_BASE}/visualization/sea-ice?date=2025-12-28&sample_step=8`
// // //         );

// // //         if (!response.ok) {
// // //             throw new Error(
// // //                 `Sea-ice API returned ${response.status}`
// // //             );
// // //         }

// // //         seaIceData = await response.json();

// // //         console.log(
// // //             "PolarGuard sea-ice data:",
// // //             seaIceData
// // //         );

// // //         renderSeaIce(
// // //             activeSeaIceHorizon
// // //         );

// // //         addAlert(
// // //             "INFO",
// // //             "Real Member 1 sea-ice layer loaded."
// // //         );

// // //     } catch (error) {

// // //         console.error(
// // //             "Sea-ice loading failed:",
// // //             error
// // //         );

// // //         addAlert(
// // //             "WARNING",
// // //             `Sea-ice layer failed: ${error.message}`
// // //         );
// // //     }
// // // }


// // // // ============================================================
// // // // REMOVE OLD SEA-ICE ENTITIES
// // // // ============================================================

// // // function clearSeaIce() {

// // //     seaIceEntities.forEach(
// // //         (entity) => {

// // //             viewer.entities.remove(
// // //                 entity
// // //             );
// // //         }
// // //     );

// // //     seaIceEntities = [];
// // // }


// // // // ============================================================
// // // // CONVERT BACKEND RGBA -> CESIUM COLOR
// // // // ============================================================

// // // function rgbaToCesiumColor(rgba) {

// // //     if (
// // //         !rgba ||
// // //         rgba.length < 4
// // //     ) {

// // //         return Cesium.Color.WHITE
// // //             .withAlpha(0.5);
// // //     }

// // //     return Cesium.Color.fromBytes(
// // //         rgba[0],
// // //         rgba[1],
// // //         rgba[2],
// // //         rgba[3]
// // //     );
// // // }


// // // // ============================================================
// // // // RENDER ONE SEA-ICE HORIZON
// // // // ============================================================

// // // function renderSeaIce(horizon) {

// // //     if (!seaIceData) {
// // //         return;
// // //     }

// // //     const horizonData =
// // //         seaIceData.horizons[horizon];

// // //     if (!horizonData) {

// // //         console.warn(
// // //             `Unknown sea-ice horizon: ${horizon}`
// // //         );

// // //         return;
// // //     }

// // //     clearSeaIce();

// // //     const cells =
// // //         horizonData.sic_cells || [];

// // //     cells.forEach(
// // //         (cell, index) => {

// // //             const sic =
// // //                 Number(cell.value);

// // //             if (!Number.isFinite(sic)) {
// // //                 return;
// // //             }

// // //             const entity =
// // //                 viewer.entities.add({

// // //                     id:
// // //                         `sea-ice-${horizon}-${index}`,

// // //                     name:
// // //                         `Sea Ice ${
// // //                             (
// // //                                 sic * 100
// // //                             ).toFixed(1)
// // //                         }%`,

// // //                     position:
// // //                         Cesium.Cartesian3.fromDegrees(
// // //                             Number(
// // //                                 cell.longitude
// // //                             ),
// // //                             Number(
// // //                                 cell.latitude
// // //                             ),
// // //                             2500
// // //                         ),

// // //                     point: {

// // //                         pixelSize:
// // //                             13,

// // //                         color:
// // //                             rgbaToCesiumColor(
// // //                                 cell.color
// // //                             ),

// // //                         outlineColor:
// // //                             Cesium.Color.WHITE
// // //                                 .withAlpha(0.35),

// // //                         outlineWidth:
// // //                             1,

// // //                         heightReference:
// // //                             Cesium.HeightReference.NONE,
// // //                     },

// // //                     description: `
// // //                         <div style="
// // //                             font-family:Arial;
// // //                             min-width:190px;
// // //                         ">
// // //                             <h3>
// // //                                 PolarGuard Sea Ice
// // //                             </h3>

// // //                             <b>Horizon:</b>
// // //                             ${horizon}
// // //                             <br>

// // //                             <b>SIC:</b>
// // //                             ${(
// // //                                 sic * 100
// // //                             ).toFixed(1)}%
// // //                             <br>

// // //                             <b>Latitude:</b>
// // //                             ${Number(
// // //                                 cell.latitude
// // //                             ).toFixed(4)}
// // //                             <br>

// // //                             <b>Longitude:</b>
// // //                             ${Number(
// // //                                 cell.longitude
// // //                             ).toFixed(4)}
// // //                             <br><br>

// // //                             <small>
// // //                                 Frozen Member 1
// // //                                 hybrid forecast
// // //                             </small>
// // //                         </div>
// // //                     `,
// // //                 });

// // //             seaIceEntities.push(
// // //                 entity
// // //             );
// // //         }
// // //     );

// // //     activeSeaIceHorizon =
// // //         horizon;

// // //     console.log(
// // //         `Rendered ${seaIceEntities.length} sea-ice cells for ${horizon}`
// // //     );
// // // }


// // // // ============================================================
// // // // CHANGE FORECAST HORIZON
// // // // ============================================================

// // // function setSeaIceHorizon(horizon) {

// // //     activeSeaIceHorizon =
// // //         horizon;

// // //     renderSeaIce(
// // //         horizon
// // //     );
// // // }
// // // checkApi();


// // const API_BASE = "http://127.0.0.1:8000";

// // // ============================================================
// // // POLARGUARD REAL SEA-ICE VISUALIZATION
// // // ============================================================

// // let seaIceEntities = [];
// // let seaIceData = null;
// // let activeSeaIceHorizon = "current";


// // // ============================================================
// // // POLARGUARD STATE
// // // ============================================================

// // const state = {
// //     horizon: "current",

// //     recommendedEntity: null,
// //     alternativeEntity: null,

// //     recommendedData: null,
// //     alternativeData: null
// // };


// // // ============================================================
// // // CREATE CESIUM VIEWER
// // // ============================================================

// // const viewer = new Cesium.Viewer("cesiumContainer", {

// //     animation: false,
// //     timeline: false,

// //     baseLayerPicker: false,
// //     geocoder: false,
// //     homeButton: false,

// //     sceneModePicker: true,
// //     navigationHelpButton: false,

// //     fullscreenButton: true,
// //     infoBox: true,
// //     selectionIndicator: true,

// //     terrainProvider: new Cesium.EllipsoidTerrainProvider(),

// //     imageryProvider: new Cesium.OpenStreetMapImageryProvider({
// //         url: "https://tile.openstreetmap.org/"
// //     })
// // });


// // // ============================================================
// // // BASIC CESIUM APPEARANCE
// // // ============================================================

// // viewer.scene.globe.enableLighting = true;

// // viewer.scene.globe.showGroundAtmosphere = true;

// // viewer.scene.backgroundColor =
// //     Cesium.Color.fromCssColorString("#07111f");


// // // ============================================================
// // // ANTARCTIC CAMERA
// // // ============================================================

// // function resetAntarcticView() {

// //     viewer.camera.flyTo({

// //         destination:
// //             Cesium.Cartesian3.fromDegrees(
// //                 0.0,
// //                 -89.0,
// //                 8500000.0
// //             ),

// //         orientation: {

// //             heading: 0.0,

// //             pitch:
// //                 Cesium.Math.toRadians(-90.0),

// //             roll: 0.0
// //         },

// //         duration: 1.2
// //     });
// // }


// // resetAntarcticView();


// // // ============================================================
// // // API STATUS
// // // ============================================================

// // function setApiStatus(
// //     online,
// //     message
// // ) {

// //     const status =
// //         document.getElementById("apiStatus");

// //     status.textContent =
// //         online
// //             ? "API Online"
// //             : "API Offline";


// //     status.classList.remove(
// //         "status-online",
// //         "status-offline"
// //     );


// //     status.classList.add(
// //         online
// //             ? "status-online"
// //             : "status-offline"
// //     );


// //     if (message) {

// //         document.getElementById(
// //             "modelStatus"
// //         ).textContent = message;
// //     }
// // }


// // // ============================================================
// // // CHECK FASTAPI BACKEND
// // // ============================================================

// // async function checkApi() {

// //     try {

// //         const health =
// //             await fetch(
// //                 `${API_BASE}/health`
// //             );


// //         if (!health.ok) {

// //             throw new Error(
// //                 "Health endpoint returned an error."
// //             );
// //         }


// //         const modelsResponse =
// //             await fetch(
// //                 `${API_BASE}/models`
// //             );


// //         if (!modelsResponse.ok) {

// //             throw new Error(
// //                 "Models endpoint returned an error."
// //             );
// //         }


// //         const models =
// //             await modelsResponse.json();


// //         setApiStatus(
// //             true,

// //             `Sea ice: ${models.sea_ice.version} | ` +
// //             `Iceberg: ${models.iceberg.version} | ` +
// //             `Navigation: ${models.navigation.algorithm}`
// //         );


// //         addAlert(
// //             "safe",
// //             "PolarGuard backend connected successfully."
// //         );

// //     }

// //     catch (error) {

// //         setApiStatus(
// //             false,

// //             `Cannot reach ${API_BASE}. ` +
// //             `Start polarguard_api_cesium.py first.`
// //         );


// //         addAlert(
// //             "warning",
// //             "FastAPI backend is currently offline."
// //         );
// //     }
// // }


// // // ============================================================
// // // READ ROUTE FROM GEOJSON
// // // ============================================================

// // function geometryCoordinatesFromGeoJson(
// //     geojson
// // ) {

// //     if (
// //         !geojson ||
// //         geojson.type !== "FeatureCollection" ||
// //         !Array.isArray(
// //             geojson.features
// //         ) ||
// //         geojson.features.length === 0
// //     ) {

// //         throw new Error(
// //             "Expected a GeoJSON FeatureCollection."
// //         );
// //     }


// //     const feature =
// //         geojson.features[0];


// //     if (
// //         !feature.geometry ||
// //         feature.geometry.type !==
// //             "LineString"
// //     ) {

// //         throw new Error(
// //             "Expected a GeoJSON LineString."
// //         );
// //     }


// //     return {

// //         coordinates:
// //             feature.geometry.coordinates,

// //         properties:
// //             feature.properties || {}
// //     };
// // }


// // // ============================================================
// // // FORMAT DISTANCE
// // // ============================================================

// // function formatDistance(value) {

// //     const number =
// //         Number(value);


// //     if (
// //         !Number.isFinite(number)
// //     ) {

// //         return "—";
// //     }


// //     return `${number.toFixed(1)} km`;
// // }


// // // ============================================================
// // // ADD ROUTE TO 3D MAP
// // // ============================================================

// // function addRouteToViewer(
// //     routeType,
// //     geojson
// // ) {

// //     const parsed =
// //         geometryCoordinatesFromGeoJson(
// //             geojson
// //         );


// //     const positions =
// //         parsed.coordinates.map(
// //             ([lon, lat]) =>

// //                 Cesium.Cartesian3.fromDegrees(
// //                     Number(lon),
// //                     Number(lat),
// //                     2500
// //                 )
// //         );


// //     const isRecommended =
// //         routeType === "recommended";


// //     const routeName =
// //         isRecommended
// //             ? "Recommended Route"
// //             : "Alternative Route";


// //     const entity =
// //         viewer.entities.add({

// //             name: routeName,


// //             polyline: {

// //                 positions: positions,

// //                 width:
// //                     isRecommended
// //                         ? 7
// //                         : 6,

// //                 clampToGround: false,


// //                 material:

// //                     isRecommended

// //                         ?

// //                         Cesium.Color.LIME
// //                             .withAlpha(0.95)

// //                         :

// //                         new Cesium
// //                             .PolylineDashMaterialProperty({

// //                                 color:
// //                                     Cesium.Color
// //                                         .DODGERBLUE,

// //                                 dashLength: 18
// //                             })
// //             },


// //             description:

// //                 `<h3>${routeName}</h3>` +

// //                 `<b>Distance:</b> ` +
// //                 `${parsed.properties.distance_km ?? "N/A"} km<br>` +

// //                 `<b>Forecast Horizon:</b> ` +
// //                 `${parsed.properties.routing_horizon ?? "N/A"}<br>` +

// //                 `<b>Vessel Profile:</b> ` +
// //                 `${parsed.properties.vessel_profile ?? "N/A"}`
// //         });


// //     // ============================================================
// //     // SAVE RECOMMENDED ROUTE
// //     // ============================================================

// //     if (isRecommended) {

// //         if (
// //             state.recommendedEntity
// //         ) {

// //             viewer.entities.remove(
// //                 state.recommendedEntity
// //             );
// //         }


// //         state.recommendedEntity =
// //             entity;


// //         state.recommendedData =
// //             geojson;


// //         document.getElementById(
// //             "recommendedDistance"
// //         ).textContent =
// //             formatDistance(
// //                 parsed.properties.distance_km
// //             );


// //         document.getElementById(
// //             "cmpRecDistance"
// //         ).textContent =
// //             formatDistance(
// //                 parsed.properties.distance_km
// //             );
// //     }


// //     // ============================================================
// //     // SAVE ALTERNATIVE ROUTE
// //     // ============================================================

// //     else {

// //         if (
// //             state.alternativeEntity
// //         ) {

// //             viewer.entities.remove(
// //                 state.alternativeEntity
// //             );
// //         }


// //         state.alternativeEntity =
// //             entity;


// //         state.alternativeData =
// //             geojson;


// //         document.getElementById(
// //             "alternativeDistance"
// //         ).textContent =
// //             formatDistance(
// //                 parsed.properties.distance_km
// //             );


// //         document.getElementById(
// //             "cmpAltDistance"
// //         ).textContent =
// //             formatDistance(
// //                 parsed.properties.distance_km
// //             );


// //         if (
// //             parsed.properties
// //                 .route_overlap_percent !==
// //             undefined
// //         ) {

// //             document.getElementById(
// //                 "routeOverlap"
// //             ).textContent =

// //                 `${Number(
// //                     parsed.properties
// //                         .route_overlap_percent
// //                 ).toFixed(1)}%`;
// //         }
// //     }


// //     refreshVisibility();


// //     fitRoutes();
// // }


// // // ============================================================
// // // LOAD GEOJSON FILE
// // // ============================================================

// // async function loadGeoJsonFile(
// //     file,
// //     routeType
// // ) {

// //     const text =
// //         await file.text();


// //     const geojson =
// //         JSON.parse(text);


// //     addRouteToViewer(
// //         routeType,
// //         geojson
// //     );


// //     addAlert(

// //         "info",

// //         `${
// //             routeType === "recommended"
// //                 ? "Recommended"
// //                 : "Alternative"
// //         } route loaded successfully.`
// //     );
// // }


// // // ============================================================
// // // ALERT SYSTEM
// // // ============================================================

// // function addAlert(
// //     level,
// //     message
// // ) {

// //     const alerts =
// //         document.getElementById(
// //             "alerts"
// //         );


// //     if (
// //         alerts.children.length === 1 &&
// //         alerts.textContent.includes(
// //             "Load route exports"
// //         )
// //     ) {

// //         alerts.innerHTML = "";
// //     }


// //     const item =
// //         document.createElement(
// //             "div"
// //         );


// //     item.className =
// //         `alert ${level}`;


// //     item.textContent =
// //         message;


// //     alerts.prepend(
// //         item
// //     );
// // }


// // // ============================================================
// // // CLEAR ROUTES
// // // ============================================================

// // function clearRoutes() {

// //     if (
// //         state.recommendedEntity
// //     ) {

// //         viewer.entities.remove(
// //             state.recommendedEntity
// //         );
// //     }


// //     if (
// //         state.alternativeEntity
// //     ) {

// //         viewer.entities.remove(
// //             state.alternativeEntity
// //         );
// //     }


// //     state.recommendedEntity =
// //         null;


// //     state.alternativeEntity =
// //         null;


// //     state.recommendedData =
// //         null;


// //     state.alternativeData =
// //         null;


// //     document.getElementById(
// //         "recommendedDistance"
// //     ).textContent = "—";


// //     document.getElementById(
// //         "alternativeDistance"
// //     ).textContent = "—";


// //     document.getElementById(
// //         "routeOverlap"
// //     ).textContent = "—";


// //     document.getElementById(
// //         "cmpRecDistance"
// //     ).textContent = "—";


// //     document.getElementById(
// //         "cmpAltDistance"
// //     ).textContent = "—";


// //     addAlert(
// //         "info",
// //         "Routes cleared."
// //     );
// // }


// // // ============================================================
// // // FIT CAMERA TO ROUTES
// // // ============================================================

// // function fitRoutes() {

// //     const entities = [];


// //     if (
// //         state.recommendedEntity
// //     ) {

// //         entities.push(
// //             state.recommendedEntity
// //         );
// //     }


// //     if (
// //         state.alternativeEntity
// //     ) {

// //         entities.push(
// //             state.alternativeEntity
// //         );
// //     }


// //     if (
// //         entities.length === 0
// //     ) {

// //         resetAntarcticView();

// //         return;
// //     }


// //     viewer.flyTo(

// //         entities,

// //         {

// //             duration: 1.2,

// //             offset:

// //                 new Cesium
// //                     .HeadingPitchRange(

// //                         0,

// //                         Cesium.Math
// //                             .toRadians(-75),

// //                         250000
// //                     )
// //         }
// //     );
// // }


// // // ============================================================
// // // ROUTE VISIBILITY
// // // ============================================================

// // function refreshVisibility() {

// //     const showRecommended =
// //         document.getElementById(
// //             "showRecommended"
// //         ).checked;


// //     const showAlternative =
// //         document.getElementById(
// //             "showAlternative"
// //         ).checked;


// //     if (
// //         state.recommendedEntity
// //     ) {

// //         state.recommendedEntity.show =
// //             showRecommended;
// //     }


// //     if (
// //         state.alternativeEntity
// //     ) {

// //         state.alternativeEntity.show =
// //             showAlternative;
// //     }
// // }


// // // ============================================================
// // // REAL MEMBER 1 SEA-ICE DATA
// // // ============================================================

// // async function loadRealSeaIce() {

// //     try {

// //         addAlert(
// //             "info",
// //             "Loading PolarGuard synchronized forecast..."
// //         );

// //         const response = await fetch(
// //             `${API_BASE}/visualization/full?date=2025-12-28&sample_step=5`
// //         );

// //         if (!response.ok) {
// //             throw new Error(
// //                 `Visualization API returned ${response.status}`
// //             );
// //         }

// //         fullPolarGuardData = await response.json();

// //         seaIceData = fullPolarGuardData.sea_ice;

// //         console.log(
// //             "Complete PolarGuard data:",
// //             fullPolarGuardData
// //         );

// //         renderSeaIce(activeSeaIceHorizon);
// //         renderIcebergTrajectory(activeSeaIceHorizon);
// //         renderUncertainty(activeSeaIceHorizon);

// //         addAlert(
// //             "safe",
// //             "Sea ice + iceberg forecast loaded."
// //         );

// //     } catch (error) {

// //         console.error(
// //             "PolarGuard visualization failed:",
// //             error
// //         );

// //         addAlert(
// //             "warning",
// //             `Visualization failed: ${error.message}`
// //         );
// //     }
// // }

// // // ============================================================
// // // REMOVE OLD SEA-ICE ENTITIES
// // // ============================================================

// // function clearSeaIce() {

// //     seaIceEntities.forEach(
// //         (entity) => {

// //             viewer.entities.remove(
// //                 entity
// //             );
// //         }
// //     );


// //     seaIceEntities = [];
// // }


// // // ============================================================
// // // CONVERT BACKEND RGBA -> CESIUM COLOR
// // // ============================================================

// // function rgbaToCesiumColor(rgba) {

// //     if (
// //         !rgba ||
// //         rgba.length < 4
// //     ) {

// //         return Cesium.Color.WHITE
// //             .withAlpha(0.5);
// //     }


// //     return Cesium.Color.fromBytes(
// //         rgba[0],
// //         rgba[1],
// //         rgba[2],
// //         rgba[3]
// //     );
// // }


// // // ============================================================
// // // RENDER ONE SEA-ICE HORIZON
// // // ============================================================

// // function renderSeaIce(horizon) {

// //     if (!seaIceData) {

// //         return;
// //     }


// //     const horizonData =
// //         seaIceData.horizons[horizon];


// //     if (!horizonData) {

// //         console.warn(
// //             `Unknown sea-ice horizon: ${horizon}`
// //         );

// //         return;
// //     }


// //     clearSeaIce();


// //     const cells =
// //         horizonData.sic_cells || [];


// //     cells.forEach(
// //         (cell, index) => {

// //             const sic =
// //                 Number(cell.value);


// //             if (!Number.isFinite(sic)) {

// //                 return;
// //             }


// //             const entity =
// //                 viewer.entities.add({

// //                     id:
// //                         `sea-ice-${horizon}-${index}`,

// //                     name:
// //                         `Sea Ice ${
// //                             (
// //                                 sic * 100
// //                             ).toFixed(1)
// //                         }%`,


// //                     position:
// //                         Cesium.Cartesian3.fromDegrees(
// //                             Number(
// //                                 cell.longitude
// //                             ),
// //                             Number(
// //                                 cell.latitude
// //                             ),
// //                             2500
// //                         ),


// //                     point: {

// //                         pixelSize: 13,


// //                         color:
// //                             rgbaToCesiumColor(
// //                                 cell.color
// //                             ),


// //                         outlineColor:
// //                             Cesium.Color.WHITE
// //                                 .withAlpha(0.35),


// //                         outlineWidth: 1,


// //                         heightReference:
// //                             Cesium.HeightReference.NONE
// //                     },


// //                     description: `

// //                         <div style="
// //                             font-family:Arial;
// //                             min-width:190px;
// //                         ">

// //                             <h3>
// //                                 PolarGuard Sea Ice
// //                             </h3>

// //                             <b>Horizon:</b>
// //                             ${horizon}

// //                             <br>

// //                             <b>SIC:</b>
// //                             ${(
// //                                 sic * 100
// //                             ).toFixed(1)}%

// //                             <br>

// //                             <b>Latitude:</b>
// //                             ${Number(
// //                                 cell.latitude
// //                             ).toFixed(4)}

// //                             <br>

// //                             <b>Longitude:</b>
// //                             ${Number(
// //                                 cell.longitude
// //                             ).toFixed(4)}

// //                             <br><br>

// //                             <small>
// //                                 Frozen Member 1
// //                                 hybrid forecast
// //                             </small>

// //                         </div>
// //                     `
// //                 });


// //             seaIceEntities.push(
// //                 entity
// //             );
// //         }
// //     );


// //     activeSeaIceHorizon =
// //         horizon;


// //     console.log(

// //         `Rendered ${seaIceEntities.length} ` +
// //         `sea-ice cells for ${horizon}`
// //     );
// // }


// // // ============================================================
// // // SET SEA-ICE FORECAST HORIZON
// // // ============================================================

// // function setSeaIceHorizon(
// //     horizon
// // ) {

// //     activeSeaIceHorizon =
// //         horizon;


// //     renderSeaIce(
// //         horizon
// //     );
// // }


// // // ============================================================
// // // FORECAST HORIZON
// // // ============================================================

// // function changeHorizon(
// //     horizon
// // ) {

// //     state.horizon =
// //         horizon;


// //     document
// //         .querySelectorAll(
// //             ".horizon-btn"
// //         )
// //         .forEach(
// //             (button) => {

// //                 button.classList.toggle(

// //                     "active",

// //                     button.dataset.horizon ===
// //                         horizon
// //                 );
// //             }
// //         );


// //     const label =

// //         horizon === "current"

// //             ? "Current"

// //             : `+${horizon}`;


// //     document.getElementById(
// //         "currentHorizon"
// //     ).textContent =
// //         label;


// //     document.getElementById(
// //         "summaryHorizon"
// //     ).textContent =
// //         label;


// //     // Update the REAL Member 1 sea-ice map.
// //     setSeaIceHorizon(
// //         horizon
// //     );


// //     addAlert(

// //         "info",

// //         `Visualization horizon changed to ${label}.`
// //     );
// // }


// // // ============================================================
// // // HORIZON BUTTON EVENTS
// // // ============================================================

// // document
// //     .querySelectorAll(
// //         ".horizon-btn"
// //     )
// //     .forEach(
// //         (button) => {

// //             button.addEventListener(

// //                 "click",

// //                 () =>
// //                     changeHorizon(
// //                         button.dataset.horizon
// //                     )
// //             );
// //         }
// //     );


// // // ============================================================
// // // API BUTTON
// // // ============================================================

// // document
// //     .getElementById(
// //         "connectApiBtn"
// //     )
// //     .addEventListener(

// //         "click",

// //         checkApi
// //     );


// // // ============================================================
// // // RECOMMENDED ROUTE UPLOAD
// // // ============================================================

// // document
// //     .getElementById(
// //         "recommendedFile"
// //     )
// //     .addEventListener(

// //         "change",

// //         async (event) => {

// //             const file =
// //                 event.target.files[0];


// //             if (!file) {

// //                 return;
// //             }


// //             try {

// //                 await loadGeoJsonFile(

// //                     file,

// //                     "recommended"
// //                 );

// //             }

// //             catch (error) {

// //                 addAlert(

// //                     "critical",

// //                     `Recommended route load failed: ${error.message}`
// //                 );
// //             }
// //         }
// //     );


// // // ============================================================
// // // ALTERNATIVE ROUTE UPLOAD
// // // ============================================================

// // document
// //     .getElementById(
// //         "alternativeFile"
// //     )
// //     .addEventListener(

// //         "change",

// //         async (event) => {

// //             const file =
// //                 event.target.files[0];


// //             if (!file) {

// //                 return;
// //             }


// //             try {

// //                 await loadGeoJsonFile(

// //                     file,

// //                     "alternative"
// //                 );

// //             }

// //             catch (error) {

// //                 addAlert(

// //                     "critical",

// //                     `Alternative route load failed: ${error.message}`
// //                 );
// //             }
// //         }
// //     );


// // // ============================================================
// // // CLEAR ROUTES BUTTON
// // // ============================================================

// // document
// //     .getElementById(
// //         "clearRoutesBtn"
// //     )
// //     .addEventListener(

// //         "click",

// //         clearRoutes
// //     );


// // // ============================================================
// // // RESET VIEW BUTTON
// // // ============================================================

// // document
// //     .getElementById(
// //         "resetViewBtn"
// //     )
// //     .addEventListener(

// //         "click",

// //         resetAntarcticView
// //     );


// // // ============================================================
// // // FIT ROUTES BUTTON
// // // ============================================================

// // document
// //     .getElementById(
// //         "fitRoutesBtn"
// //     )
// //     .addEventListener(

// //         "click",

// //         fitRoutes
// //     );


// // // ============================================================
// // // LAYER CHECKBOX EVENTS
// // // ============================================================

// // document
// //     .getElementById(
// //         "showRecommended"
// //     )
// //     .addEventListener(

// //         "change",

// //         refreshVisibility
// //     );


// // document
// //     .getElementById(
// //         "showAlternative"
// //     )
// //     .addEventListener(

// //         "change",

// //         refreshVisibility
// //     );

// // // ============================================================
// // // SIC LEGEND
// // // ============================================================

// // function addPolarGuardLegend() {

// //     if (
// //         document.getElementById(
// //             "polarguardLegend"
// //         )
// //     ) {
// //         return;
// //     }

// //     const legend =
// //         document.createElement(
// //             "div"
// //         );

// //     legend.id =
// //         "polarguardLegend";

// //     legend.style.cssText = `
// //         position:absolute;
// //         left:355px;
// //         bottom:25px;
// //         z-index:50;
// //         background:rgba(7,17,31,0.92);
// //         color:#ffffff;
// //         padding:12px 14px;
// //         border:1px solid rgba(148,163,184,0.35);
// //         border-radius:10px;
// //         font-family:Arial,sans-serif;
// //         font-size:12px;
// //         line-height:1.5;
// //         pointer-events:none;
// //         backdrop-filter:blur(8px);
// //     `;

// //     legend.innerHTML = `
// //         <div style="
// //             font-weight:700;
// //             margin-bottom:7px;
// //         ">
// //             Sea-Ice Concentration
// //         </div>

// //         <div>
// //             <span style="color:#dbeafe">●</span>
// //             5–30% Low
// //         </div>

// //         <div>
// //             <span style="color:#93c5fd">●</span>
// //             30–60% Moderate
// //         </div>

// //         <div>
// //             <span style="color:#60a5fa">●</span>
// //             60–80% High
// //         </div>

// //         <div>
// //             <span style="color:#2563eb">●</span>
// //             80–100% Very High
// //         </div>

// //         <div style="
// //             margin-top:7px;
// //             color:#fbbf24;
// //         ">
// //             Orange/Red =
// //             forecast uncertainty
// //         </div>
// //     `;

// //     document.body.appendChild(
// //         legend
// //     );
// // }
// // // ============================================================
// // // INITIAL STARTUP
// // // ============================================================

// // // Check FastAPI backend.
// // checkApi();

// // // Load real Member 1 SIC data.
// // addPolarGuardLegend();

// // loadRealSeaIce();

// const API_BASE = "http://127.0.0.1:8000";

// // ============================================================
// // POLARGUARD VISUALIZATION STATE
// // ============================================================

// let seaIceEntities = [];
// let uncertaintyEntities = [];
// let icebergEntities = [];

// let seaIceData = null;
// let fullPolarGuardData = null;

// let activeSeaIceHorizon = "current";

// let icebergObservedEntity = null;
// let icebergForecastEntity = null;
// let icebergBufferEntity = null;


// // ============================================================
// // POLARGUARD STATE
// // ============================================================

// const state = {
//     horizon: "current",

//     recommendedEntity: null,
//     alternativeEntity: null,

//     recommendedData: null,
//     alternativeData: null
// };


// // ============================================================
// // CREATE CESIUM VIEWER
// // ============================================================

// const viewer = new Cesium.Viewer("cesiumContainer", {

//     animation: false,
//     timeline: false,

//     baseLayerPicker: false,
//     geocoder: false,
//     homeButton: false,

//     sceneModePicker: true,
//     navigationHelpButton: false,

//     fullscreenButton: true,
//     infoBox: true,
//     selectionIndicator: true,

//     terrainProvider:
//         new Cesium.EllipsoidTerrainProvider(),

//     imageryProvider:
//         new Cesium.OpenStreetMapImageryProvider({
//             url: "https://tile.openstreetmap.org/"
//         })
// });


// // ============================================================
// // CESIUM APPEARANCE
// // ============================================================

// viewer.scene.globe.enableLighting = true;

// viewer.scene.globe.showGroundAtmosphere = true;

// viewer.scene.backgroundColor =
//     Cesium.Color.fromCssColorString("#07111f");


// // ============================================================
// // ANTARCTIC CAMERA
// // ============================================================

// function resetAntarcticView() {

//     viewer.camera.flyTo({

//         destination:
//             Cesium.Cartesian3.fromDegrees(
//                 0.0,
//                 -89.0,
//                 8500000.0
//             ),

//         orientation: {

//             heading: 0.0,

//             pitch:
//                 Cesium.Math.toRadians(-90.0),

//             roll: 0.0
//         },

//         duration: 1.2
//     });
// }

// resetAntarcticView();


// // ============================================================
// // ALERT SYSTEM
// // ============================================================

// function addAlert(level, message) {

//     const alerts =
//         document.getElementById("alerts");

//     if (!alerts) {
//         console.log(`[${level}] ${message}`);
//         return;
//     }

//     if (
//         alerts.children.length === 1 &&
//         alerts.textContent.includes(
//             "Load route exports"
//         )
//     ) {
//         alerts.innerHTML = "";
//     }

//     const item =
//         document.createElement("div");

//     item.className =
//         `alert ${level}`;

//     item.textContent =
//         message;

//     alerts.prepend(item);
// }


// // ============================================================
// // API STATUS
// // ============================================================

// function setApiStatus(
//     online,
//     message
// ) {

//     const status =
//         document.getElementById(
//             "apiStatus"
//         );

//     if (status) {

//         status.textContent =
//             online
//                 ? "API Online"
//                 : "API Offline";

//         status.classList.remove(
//             "status-online",
//             "status-offline"
//         );

//         status.classList.add(
//             online
//                 ? "status-online"
//                 : "status-offline"
//         );
//     }

//     const modelStatus =
//         document.getElementById(
//             "modelStatus"
//         );

//     if (
//         modelStatus &&
//         message
//     ) {
//         modelStatus.textContent =
//             message;
//     }
// }


// // ============================================================
// // CHECK FASTAPI BACKEND
// // ============================================================

// async function checkApi() {

//     try {

//         const health =
//             await fetch(
//                 `${API_BASE}/health`
//             );

//         if (!health.ok) {

//             throw new Error(
//                 "Health endpoint returned an error."
//             );
//         }

//         const modelsResponse =
//             await fetch(
//                 `${API_BASE}/models`
//             );

//         if (!modelsResponse.ok) {

//             throw new Error(
//                 "Models endpoint returned an error."
//             );
//         }

//         const models =
//             await modelsResponse.json();

//         setApiStatus(
//             true,

//             `Sea ice: ${models.sea_ice.version} | ` +
//             `Iceberg: ${models.iceberg.version} | ` +
//             `Navigation: ${models.navigation.algorithm}`
//         );

//         addAlert(
//             "safe",
//             "PolarGuard backend connected successfully."
//         );
//     }

//     catch (error) {

//         console.error(
//             "Backend check failed:",
//             error
//         );

//         setApiStatus(
//             false,

//             `Cannot reach ${API_BASE}. ` +
//             `Start polarguard_api_cesium.py first.`
//         );

//         addAlert(
//             "warning",
//             "FastAPI backend is currently offline."
//         );
//     }
// }


// // ============================================================
// // GEOJSON ROUTE READER
// // ============================================================

// function geometryCoordinatesFromGeoJson(
//     geojson
// ) {

//     if (
//         !geojson ||
//         geojson.type !==
//             "FeatureCollection" ||
//         !Array.isArray(
//             geojson.features
//         ) ||
//         geojson.features.length === 0
//     ) {

//         throw new Error(
//             "Expected a GeoJSON FeatureCollection."
//         );
//     }

//     const feature =
//         geojson.features[0];

//     if (
//         !feature.geometry ||
//         feature.geometry.type !==
//             "LineString"
//     ) {

//         throw new Error(
//             "Expected a GeoJSON LineString."
//         );
//     }

//     return {

//         coordinates:
//             feature.geometry.coordinates,

//         properties:
//             feature.properties || {}
//     };
// }


// // ============================================================
// // FORMAT DISTANCE
// // ============================================================

// function formatDistance(value) {

//     const number =
//         Number(value);

//     if (
//         !Number.isFinite(number)
//     ) {
//         return "—";
//     }

//     return `${number.toFixed(1)} km`;
// }


// // ============================================================
// // ADD ROUTE
// // ============================================================

// function addRouteToViewer(
//     routeType,
//     geojson
// ) {

//     const parsed =
//         geometryCoordinatesFromGeoJson(
//             geojson
//         );

//     const positions =
//         parsed.coordinates.map(
//             ([lon, lat]) =>

//                 Cesium.Cartesian3
//                     .fromDegrees(
//                         Number(lon),
//                         Number(lat),
//                         2500
//                     )
//         );

//     const isRecommended =
//         routeType ===
//         "recommended";

//     const routeName =
//         isRecommended
//             ? "Recommended Route"
//             : "Alternative Route";

//     const entity =
//         viewer.entities.add({

//             name:
//                 routeName,

//             polyline: {

//                 positions:
//                     positions,

//                 width:
//                     isRecommended
//                         ? 7
//                         : 6,

//                 clampToGround:
//                     false,

//                 material:
//                     isRecommended

//                         ? Cesium.Color.LIME
//                             .withAlpha(0.95)

//                         : new Cesium
//                             .PolylineDashMaterialProperty({

//                                 color:
//                                     Cesium.Color
//                                         .DODGERBLUE,

//                                 dashLength:
//                                     18
//                             })
//             },

//             description:

//                 `<h3>${routeName}</h3>` +

//                 `<b>Distance:</b> ` +
//                 `${parsed.properties.distance_km ?? "N/A"} km<br>` +

//                 `<b>Forecast Horizon:</b> ` +
//                 `${parsed.properties.routing_horizon ?? "N/A"}<br>` +

//                 `<b>Vessel Profile:</b> ` +
//                 `${parsed.properties.vessel_profile ?? "N/A"}`
//         });


//     if (isRecommended) {

//         if (
//             state.recommendedEntity
//         ) {

//             viewer.entities.remove(
//                 state.recommendedEntity
//             );
//         }

//         state.recommendedEntity =
//             entity;

//         state.recommendedData =
//             geojson;

//         const distance =
//             formatDistance(
//                 parsed.properties
//                     .distance_km
//             );

//         const recommendedDistance =
//             document.getElementById(
//                 "recommendedDistance"
//             );

//         if (recommendedDistance) {
//             recommendedDistance
//                 .textContent =
//                 distance;
//         }

//         const cmpRecDistance =
//             document.getElementById(
//                 "cmpRecDistance"
//             );

//         if (cmpRecDistance) {
//             cmpRecDistance
//                 .textContent =
//                 distance;
//         }
//     }

//     else {

//         if (
//             state.alternativeEntity
//         ) {

//             viewer.entities.remove(
//                 state.alternativeEntity
//             );
//         }

//         state.alternativeEntity =
//             entity;

//         state.alternativeData =
//             geojson;

//         const distance =
//             formatDistance(
//                 parsed.properties
//                     .distance_km
//             );

//         const alternativeDistance =
//             document.getElementById(
//                 "alternativeDistance"
//             );

//         if (alternativeDistance) {
//             alternativeDistance
//                 .textContent =
//                 distance;
//         }

//         const cmpAltDistance =
//             document.getElementById(
//                 "cmpAltDistance"
//             );

//         if (cmpAltDistance) {
//             cmpAltDistance
//                 .textContent =
//                 distance;
//         }

//         if (
//             parsed.properties
//                 .route_overlap_percent !==
//             undefined
//         ) {

//             const routeOverlap =
//                 document.getElementById(
//                     "routeOverlap"
//                 );

//             if (routeOverlap) {

//                 routeOverlap.textContent =
//                     `${Number(
//                         parsed.properties
//                             .route_overlap_percent
//                     ).toFixed(1)}%`;
//             }
//         }
//     }

//     refreshVisibility();

//     fitRoutes();
// }


// // ============================================================
// // LOAD GEOJSON FILE
// // ============================================================

// async function loadGeoJsonFile(
//     file,
//     routeType
// ) {

//     const text =
//         await file.text();

//     const geojson =
//         JSON.parse(text);

//     addRouteToViewer(
//         routeType,
//         geojson
//     );

//     addAlert(
//         "info",

//         `${
//             routeType ===
//             "recommended"
//                 ? "Recommended"
//                 : "Alternative"
//         } route loaded successfully.`
//     );
// }


// // ============================================================
// // CLEAR ROUTES
// // ============================================================

// function clearRoutes() {

//     if (
//         state.recommendedEntity
//     ) {

//         viewer.entities.remove(
//             state.recommendedEntity
//         );
//     }

//     if (
//         state.alternativeEntity
//     ) {

//         viewer.entities.remove(
//             state.alternativeEntity
//         );
//     }

//     state.recommendedEntity =
//         null;

//     state.alternativeEntity =
//         null;

//     state.recommendedData =
//         null;

//     state.alternativeData =
//         null;

//     const ids = [
//         "recommendedDistance",
//         "alternativeDistance",
//         "routeOverlap",
//         "cmpRecDistance",
//         "cmpAltDistance"
//     ];

//     ids.forEach(
//         id => {

//             const element =
//                 document.getElementById(
//                     id
//                 );

//             if (element) {
//                 element.textContent =
//                     "—";
//             }
//         }
//     );

//     addAlert(
//         "info",
//         "Routes cleared."
//     );
// }


// // ============================================================
// // FIT CAMERA TO ROUTES
// // ============================================================

// function fitRoutes() {

//     const entities = [];

//     if (
//         state.recommendedEntity
//     ) {

//         entities.push(
//             state.recommendedEntity
//         );
//     }

//     if (
//         state.alternativeEntity
//     ) {

//         entities.push(
//             state.alternativeEntity
//         );
//     }

//     if (
//         entities.length === 0
//     ) {

//         resetAntarcticView();

//         return;
//     }

//     viewer.flyTo(
//         entities,
//         {

//             duration:
//                 1.2,

//             offset:
//                 new Cesium
//                     .HeadingPitchRange(

//                         0,

//                         Cesium.Math
//                             .toRadians(-75),

//                         250000
//                     )
//         }
//     );
// }


// // ============================================================
// // ROUTE + ICEBERG VISIBILITY
// // ============================================================

// function refreshVisibility() {

//     const recommendedCheckbox =
//         document.getElementById(
//             "showRecommended"
//         );

//     const alternativeCheckbox =
//         document.getElementById(
//             "showAlternative"
//         );

//     const icebergCheckbox =
//         document.getElementById(
//             "showIceberg"
//         );

//     const showRecommended =
//         recommendedCheckbox
//             ? recommendedCheckbox.checked
//             : true;

//     const showAlternative =
//         alternativeCheckbox
//             ? alternativeCheckbox.checked
//             : true;

//     const showIceberg =
//         icebergCheckbox
//             ? icebergCheckbox.checked
//             : true;


//     if (
//         state.recommendedEntity
//     ) {

//         state.recommendedEntity.show =
//             showRecommended;
//     }

//     if (
//         state.alternativeEntity
//     ) {

//         state.alternativeEntity.show =
//             showAlternative;
//     }


//     icebergEntities.forEach(
//         entity => {

//             entity.show =
//                 showIceberg;
//         }
//     );

//     if (
//         icebergObservedEntity
//     ) {

//         icebergObservedEntity.show =
//             showIceberg;
//     }

//     if (
//         icebergForecastEntity
//     ) {

//         icebergForecastEntity.show =
//             showIceberg;
//     }

//     if (
//         icebergBufferEntity
//     ) {

//         icebergBufferEntity.show =
//             showIceberg;
//     }
// }


// // ============================================================
// // LOAD COMPLETE REAL POLARGUARD VISUALIZATION
// // ============================================================

// async function loadRealSeaIce() {

//     try {

//         addAlert(
//             "info",
//             "Loading PolarGuard synchronized forecast..."
//         );

//         const response =
//             await fetch(

//                 `${API_BASE}/visualization/full` +
//                 `?date=2025-12-28` +
//                 `&sample_step=5`
//             );

//         if (!response.ok) {

//             const errorText =
//                 await response.text();

//             throw new Error(
//                 `Visualization API returned ` +
//                 `${response.status}: ` +
//                 `${errorText}`
//             );
//         }

//         fullPolarGuardData =
//             await response.json();

//         seaIceData =
//             fullPolarGuardData
//                 .sea_ice;

//         console.log(
//             "Complete PolarGuard data:",
//             fullPolarGuardData
//         );

//         renderSeaIce(
//             activeSeaIceHorizon
//         );

//         renderUncertainty(
//             activeSeaIceHorizon
//         );

//         renderIcebergTrajectory(
//             activeSeaIceHorizon
//         );

//         refreshVisibility();

//         addAlert(
//             "safe",
//             "Sea ice + iceberg forecast loaded."
//         );
//     }

//     catch (error) {

//         console.error(
//             "PolarGuard visualization failed:",
//             error
//         );

//         addAlert(
//             "warning",
//             `Visualization failed: ${error.message}`
//         );
//     }
// }


// // ============================================================
// // CLEAR SEA ICE
// // ============================================================

// function clearSeaIce() {

//     seaIceEntities.forEach(
//         entity => {

//             viewer.entities.remove(
//                 entity
//             );
//         }
//     );

//     seaIceEntities = [];
// }


// // ============================================================
// // RGBA -> CESIUM COLOR
// // ============================================================

// function rgbaToCesiumColor(
//     rgba
// ) {

//     if (
//         !rgba ||
//         rgba.length < 4
//     ) {

//         return Cesium.Color.WHITE
//             .withAlpha(0.5);
//     }

//     return Cesium.Color.fromBytes(
//         rgba[0],
//         rgba[1],
//         rgba[2],
//         rgba[3]
//     );
// }


// // ============================================================
// // RENDER SEA ICE
// // ============================================================

// function renderSeaIce(
//     horizon
// ) {

//     if (!seaIceData) {
//         return;
//     }

//     const horizonData =
//         seaIceData
//             .horizons[horizon];

//     if (!horizonData) {

//         console.warn(
//             `Unknown sea-ice horizon: ${horizon}`
//         );

//         return;
//     }

//     clearSeaIce();

//     const cells =
//         horizonData
//             .sic_cells || [];

//     cells.forEach(
//         (cell, index) => {

//             const sic =
//                 Number(
//                     cell.value
//                 );

//             const latitude =
//                 Number(
//                     cell.latitude
//                 );

//             const longitude =
//                 Number(
//                     cell.longitude
//                 );

//             if (
//                 !Number.isFinite(sic) ||
//                 !Number.isFinite(latitude) ||
//                 !Number.isFinite(longitude)
//             ) {
//                 return;
//             }

//             const radius =
//                 62000;

//             const entity =
//                 viewer.entities.add({

//                     id:
//                         `sea-ice-${horizon}-${index}`,

//                     name:
//                         `Sea Ice ${(sic * 100).toFixed(1)}%`,

//                     position:
//                         Cesium.Cartesian3
//                             .fromDegrees(
//                                 longitude,
//                                 latitude,
//                                 1000
//                             ),

//                     ellipse: {

//                         semiMajorAxis:
//                             radius,

//                         semiMinorAxis:
//                             radius,

//                         material:
//                             rgbaToCesiumColor(
//                                 cell.color
//                             ),

//                         outline:
//                             false,

//                         height:
//                             900
//                     },

//                     description: `
//                         <div style="
//                             font-family:Arial;
//                             min-width:210px;
//                         ">

//                             <h3>
//                                 PolarGuard Sea Ice
//                             </h3>

//                             <b>Forecast:</b>
//                             ${
//                                 horizon ===
//                                 "current"
//                                     ? "Current"
//                                     : "+" + horizon
//                             }

//                             <br>

//                             <b>SIC:</b>
//                             ${(sic * 100).toFixed(1)}%

//                             <br>

//                             <b>Latitude:</b>
//                             ${latitude.toFixed(4)}

//                             <br>

//                             <b>Longitude:</b>
//                             ${longitude.toFixed(4)}

//                             <br><br>

//                             <small>
//                                 Member 1 •
//                                 Hybrid v1 •
//                                 Frozen
//                             </small>

//                         </div>
//                     `
//                 });

//             seaIceEntities.push(
//                 entity
//             );
//         }
//     );

//     activeSeaIceHorizon =
//         horizon;

//     console.log(
//         `Rendered ` +
//         `${seaIceEntities.length} ` +
//         `SIC cells for ${horizon}`
//     );
// }


// // ============================================================
// // UNCERTAINTY
// // ============================================================

// function clearUncertainty() {

//     uncertaintyEntities
//         .forEach(
//             entity => {

//                 viewer.entities.remove(
//                     entity
//                 );
//             }
//         );

//     uncertaintyEntities = [];
// }


// function uncertaintyCesiumColor(
//     value
// ) {

//     if (value < 0.01) {

//         return Cesium.Color.YELLOW
//             .withAlpha(0.10);
//     }

//     if (value < 0.02) {

//         return Cesium.Color.GOLD
//             .withAlpha(0.12);
//     }

//     if (value < 0.03) {

//         return Cesium.Color.ORANGE
//             .withAlpha(0.14);
//     }

//     if (value < 0.05) {

//         return Cesium.Color.ORANGERED
//             .withAlpha(0.17);
//     }

//     return Cesium.Color.RED
//         .withAlpha(0.20);
// }


// function renderUncertainty(
//     horizon
// ) {

//     clearUncertainty();

//     if (!seaIceData) {
//         return;
//     }

//     // Current SIC is an observation,
//     // not a forecast.
//     if (
//         horizon === "current"
//     ) {
//         return;
//     }

//     const horizonData =
//         seaIceData
//             .horizons[horizon];

//     if (!horizonData) {
//         return;
//     }

//     const cells =
//         horizonData
//             .uncertainty_cells || [];

//     cells.forEach(
//         (cell, index) => {

//             const value =
//                 Number(
//                     cell.value
//                 );

//             const latitude =
//                 Number(
//                     cell.latitude
//                 );

//             const longitude =
//                 Number(
//                     cell.longitude
//                 );

//             if (
//                 !Number.isFinite(value) ||
//                 !Number.isFinite(latitude) ||
//                 !Number.isFinite(longitude)
//             ) {
//                 return;
//             }

//             const entity =
//                 viewer.entities.add({

//                     id:
//                         `uncertainty-${horizon}-${index}`,

//                     name:
//                         "Forecast Uncertainty",

//                     position:
//                         Cesium.Cartesian3
//                             .fromDegrees(
//                                 longitude,
//                                 latitude,
//                                 1600
//                             ),

//                     ellipse: {

//                         semiMajorAxis:
//                             36000,

//                         semiMinorAxis:
//                             36000,

//                         material:
//                             uncertaintyCesiumColor(
//                                 value
//                             ),

//                         outline:
//                             false,

//                         height:
//                             1500
//                     },

//                     description: `
//                         <div style="
//                             font-family:Arial;
//                             min-width:220px;
//                         ">

//                             <h3>
//                                 Sea-Ice Forecast Uncertainty
//                             </h3>

//                             <b>Horizon:</b>
//                             +${horizon}

//                             <br>

//                             <b>Historical RMSE:</b>
//                             ${(value * 100).toFixed(2)}
//                             SIC percentage points

//                             <br><br>

//                             <small>
//                                 Historical per-grid-cell
//                                 RMSE from 2024 validation
//                                 residuals.

//                                 <br>

//                                 Not a calibrated
//                                 confidence interval.
//                             </small>

//                         </div>
//                     `
//                 });

//             uncertaintyEntities.push(
//                 entity
//             );
//         }
//     );

//     console.log(
//         `Rendered ` +
//         `${uncertaintyEntities.length} ` +
//         `uncertainty cells for ${horizon}`
//     );
// }


// // ============================================================
// // CLEAR ICEBERG TRAJECTORY
// // ============================================================

// function clearIcebergTrajectory() {

//     icebergEntities
//         .forEach(
//             entity => {

//                 viewer.entities.remove(
//                     entity
//                 );
//             }
//         );

//     icebergEntities = [];


//     if (
//         icebergObservedEntity
//     ) {

//         viewer.entities.remove(
//             icebergObservedEntity
//         );

//         icebergObservedEntity =
//             null;
//     }


//     if (
//         icebergForecastEntity
//     ) {

//         viewer.entities.remove(
//             icebergForecastEntity
//         );

//         icebergForecastEntity =
//             null;
//     }


//     if (
//         icebergBufferEntity
//     ) {

//         viewer.entities.remove(
//             icebergBufferEntity
//         );

//         icebergBufferEntity =
//             null;
//     }
// }


// // ============================================================
// // ICEBERG FORECAST COLORS
// // ============================================================

// function icebergColorForHorizon(
//     horizon
// ) {

//     if (
//         horizon === "24h"
//     ) {

//         return Cesium.Color.LIME;
//     }

//     if (
//         horizon === "48h"
//     ) {

//         return Cesium.Color
//             .DODGERBLUE;
//     }

//     if (
//         horizon === "72h"
//     ) {

//         return Cesium.Color
//             .MEDIUMPURPLE;
//     }

//     return Cesium.Color.GOLD;
// }


// // ============================================================
// // ADD ICEBERG MARKER
// // ============================================================

// function addIcebergMarker(
//     stage,
//     latitude,
//     longitude,
//     color,
//     size = 14
// ) {

//     const lat =
//         Number(latitude);

//     const lon =
//         Number(longitude);

//     if (
//         !Number.isFinite(lat) ||
//         !Number.isFinite(lon)
//     ) {
//         return null;
//     }

//     const entity =
//         viewer.entities.add({

//             name:
//                 `Iceberg ${stage}`,

//             position:
//                 Cesium.Cartesian3
//                     .fromDegrees(
//                         lon,
//                         lat,
//                         9000
//                     ),

//             point: {

//                 pixelSize:
//                     size,

//                 color:
//                     color,

//                 outlineColor:
//                     Cesium.Color.WHITE,

//                 outlineWidth:
//                     2
//             },

//             label: {

//                 text:
//                     stage,

//                 font:
//                     "13px sans-serif",

//                 fillColor:
//                     Cesium.Color.WHITE,

//                 outlineColor:
//                     Cesium.Color.BLACK,

//                 outlineWidth:
//                     3,

//                 style:
//                     Cesium.LabelStyle
//                         .FILL_AND_OUTLINE,

//                 pixelOffset:
//                     new Cesium
//                         .Cartesian2(
//                             0,
//                             -24
//                         ),

//                 distanceDisplayCondition:
//                     new Cesium
//                         .DistanceDisplayCondition(
//                             0,
//                             4000000
//                         )
//             },

//             description: `
//                 <div style="
//                     font-family:Arial;
//                     min-width:210px;
//                 ">

//                     <h3>
//                         PolarGuard Iceberg Forecast
//                     </h3>

//                     <b>Stage:</b>
//                     ${stage}

//                     <br>

//                     <b>Latitude:</b>
//                     ${lat.toFixed(6)}

//                     <br>

//                     <b>Longitude:</b>
//                     ${lon.toFixed(6)}

//                     <br><br>

//                     <small>
//                         Member 2 •
//                         Environment v1 •
//                         Frozen
//                     </small>

//                 </div>
//             `
//         });

//     icebergEntities.push(
//         entity
//     );

//     return entity;
// }


// // ============================================================
// // RENDER ICEBERG TRAJECTORY
// // ============================================================

// function renderIcebergTrajectory(
//     horizon
// ) {

//     clearIcebergTrajectory();

//     if (
//         !fullPolarGuardData ||
//         !fullPolarGuardData.iceberg
//     ) {
//         return;
//     }

//     const data =
//         fullPolarGuardData
//             .iceberg;

//     const history =
//         data.history || [];

//     const current =
//         data.current;

//     const forecast =
//         data.forecast || {};


//     if (!current) {
//         return;
//     }


//     // --------------------------------------------------------
//     // OBSERVED TRACK
//     // --------------------------------------------------------

//     const observedPoints =
//         history.map(
//             item =>

//                 Cesium.Cartesian3
//                     .fromDegrees(
//                         Number(
//                             item.longitude
//                         ),
//                         Number(
//                             item.latitude
//                         ),
//                         6000
//                     )
//         );


//     observedPoints.push(

//         Cesium.Cartesian3
//             .fromDegrees(
//                 Number(
//                     current.longitude
//                 ),
//                 Number(
//                     current.latitude
//                 ),
//                 6000
//             )
//     );


//     if (
//         observedPoints.length > 1
//     ) {

//         icebergObservedEntity =
//             viewer.entities.add({

//                 name:
//                     "Observed Iceberg Track",

//                 polyline: {

//                     positions:
//                         observedPoints,

//                     width:
//                         3,

//                     material:
//                         Cesium.Color
//                             .LIGHTGRAY
//                             .withAlpha(0.85)
//                 }
//             });
//     }


//     // --------------------------------------------------------
//     // HISTORICAL MARKERS
//     // --------------------------------------------------------

//     history.forEach(
//         item => {

//             addIcebergMarker(
//                 item.stage,
//                 item.latitude,
//                 item.longitude,
//                 Cesium.Color.LIGHTGRAY,
//                 9
//             );
//         }
//     );


//     // --------------------------------------------------------
//     // CURRENT MARKER
//     // --------------------------------------------------------

//     addIcebergMarker(
//         "Current",
//         current.latitude,
//         current.longitude,
//         Cesium.Color.GOLD,
//         16
//     );


//     // --------------------------------------------------------
//     // FORECASTS TO DISPLAY
//     // --------------------------------------------------------

//     const forecastOrder = [
//         "24h",
//         "48h",
//         "72h"
//     ];

//     let visibleForecasts = [];


//     if (
//         horizon !== "current"
//     ) {

//         const stopIndex =
//             forecastOrder
//                 .indexOf(
//                     horizon
//                 );

//         if (
//             stopIndex >= 0
//         ) {

//             visibleForecasts =
//                 forecastOrder.slice(
//                     0,
//                     stopIndex + 1
//                 );
//         }
//     }


//     const forecastPositions = [

//         Cesium.Cartesian3
//             .fromDegrees(
//                 Number(
//                     current.longitude
//                 ),
//                 Number(
//                     current.latitude
//                 ),
//                 7000
//             )
//     ];


//     visibleForecasts
//         .forEach(
//             key => {

//                 const item =
//                     forecast[key];

//                 if (!item) {
//                     return;
//                 }


//                 addIcebergMarker(
//                     `+${key}`,
//                     item.latitude,
//                     item.longitude,
//                     icebergColorForHorizon(
//                         key
//                     ),
//                     17
//                 );


//                 forecastPositions.push(

//                     Cesium.Cartesian3
//                         .fromDegrees(
//                             Number(
//                                 item.longitude
//                             ),
//                             Number(
//                                 item.latitude
//                             ),
//                             7000
//                         )
//                 );
//             }
//         );


//     // --------------------------------------------------------
//     // FORECAST TRAJECTORY LINE
//     // --------------------------------------------------------

//     if (
//         forecastPositions.length > 1
//     ) {

//         icebergForecastEntity =
//             viewer.entities.add({

//                 name:
//                     "Predicted Iceberg Trajectory",

//                 polyline: {

//                     positions:
//                         forecastPositions,

//                     width:
//                         5,

//                     material:
//                         Cesium.Color.CYAN
//                             .withAlpha(0.95)
//                 }
//             });
//     }


//     // --------------------------------------------------------
//     // 10 KM PLANNING BUFFER
//     // --------------------------------------------------------

//     if (
//         horizon !== "current" &&
//         forecast[horizon]
//     ) {

//         const selected =
//             forecast[horizon];

//         const bufferKm =
//             Number(
//                 data.planning_buffer_km ||
//                 10
//             );


//         icebergBufferEntity =
//             viewer.entities.add({

//                 name:
//                     "Iceberg Navigation Planning Buffer",

//                 position:
//                     Cesium.Cartesian3
//                         .fromDegrees(
//                             Number(
//                                 selected.longitude
//                             ),
//                             Number(
//                                 selected.latitude
//                             ),
//                             5000
//                         ),

//                 ellipse: {

//                     semiMajorAxis:
//                         bufferKm * 1000,

//                     semiMinorAxis:
//                         bufferKm * 1000,

//                     material:
//                         Cesium.Color.RED
//                             .withAlpha(0.08),

//                     outline:
//                         true,

//                     outlineColor:
//                         Cesium.Color.RED
//                             .withAlpha(0.9),

//                     height:
//                         5000
//                 },

//                 description: `
//                     <div style="
//                         font-family:Arial;
//                         min-width:220px;
//                     ">

//                         <h3>
//                             Navigation Planning Buffer
//                         </h3>

//                         <b>Forecast:</b>
//                         +${horizon}

//                         <br>

//                         <b>Radius:</b>
//                         ${bufferKm.toFixed(0)} km

//                         <br><br>

//                         <small>
//                             Prototype navigation
//                             planning buffer only.

//                             <br>

//                             Not a calibrated
//                             collision-probability
//                             region.
//                         </small>

//                     </div>
//                 `
//             });
//     }


//     refreshVisibility();
// }


// // ============================================================
// // SET SYNCHRONIZED FORECAST HORIZON
// // ============================================================

// function setSeaIceHorizon(
//     horizon
// ) {

//     activeSeaIceHorizon =
//         horizon;

//     renderSeaIce(
//         horizon
//     );

//     renderUncertainty(
//         horizon
//     );

//     renderIcebergTrajectory(
//         horizon
//     );
// }


// // ============================================================
// // CHANGE FORECAST HORIZON
// // ============================================================

// function changeHorizon(
//     horizon
// ) {

//     state.horizon =
//         horizon;

//     document
//         .querySelectorAll(
//             ".horizon-btn"
//         )
//         .forEach(
//             button => {

//                 button.classList.toggle(
//                     "active",

//                     button.dataset.horizon ===
//                         horizon
//                 );
//             }
//         );


//     const label =
//         horizon === "current"
//             ? "Current"
//             : `+${horizon}`;


//     const currentHorizon =
//         document.getElementById(
//             "currentHorizon"
//         );

//     if (currentHorizon) {

//         currentHorizon.textContent =
//             label;
//     }


//     const summaryHorizon =
//         document.getElementById(
//             "summaryHorizon"
//         );

//     if (summaryHorizon) {

//         summaryHorizon.textContent =
//             label;
//     }


//     setSeaIceHorizon(
//         horizon
//     );


//     addAlert(
//         "info",
//         `Visualization horizon changed to ${label}.`
//     );
// }


// // ============================================================
// // SIC LEGEND
// // ============================================================

// function addPolarGuardLegend() {

//     if (
//         document.getElementById(
//             "polarguardLegend"
//         )
//     ) {
//         return;
//     }


//     const legend =
//         document.createElement(
//             "div"
//         );


//     legend.id =
//         "polarguardLegend";


//     legend.style.cssText = `
//         position:absolute;
//         left:355px;
//         bottom:25px;
//         z-index:50;

//         background:
//             rgba(7,17,31,0.92);

//         color:#ffffff;

//         padding:
//             12px 14px;

//         border:
//             1px solid
//             rgba(148,163,184,0.35);

//         border-radius:
//             10px;

//         font-family:
//             Arial,sans-serif;

//         font-size:
//             12px;

//         line-height:
//             1.5;

//         pointer-events:
//             none;

//         backdrop-filter:
//             blur(8px);
//     `;


//     legend.innerHTML = `

//         <div style="
//             font-weight:700;
//             margin-bottom:7px;
//         ">
//             PolarGuard Layers
//         </div>


//         <div style="
//             margin-bottom:4px;
//             font-weight:600;
//         ">
//             Sea-Ice Concentration
//         </div>


//         <div>
//             <span style="
//                 color:#dbeafe
//             ">●</span>

//             5–30% Low
//         </div>


//         <div>
//             <span style="
//                 color:#93c5fd
//             ">●</span>

//             30–60% Moderate
//         </div>


//         <div>
//             <span style="
//                 color:#60a5fa
//             ">●</span>

//             60–80% High
//         </div>


//         <div>
//             <span style="
//                 color:#2563eb
//             ">●</span>

//             80–100% Very High
//         </div>


//         <div style="
//             margin-top:7px;
//             color:#fbbf24;
//         ">
//             ● Orange/Red =
//             forecast uncertainty
//         </div>


//         <div style="
//             margin-top:4px;
//             color:#ffd700;
//         ">
//             ● Gold =
//             current iceberg
//         </div>


//         <div style="
//             color:#00ffff;
//         ">
//             ━ Cyan =
//             predicted iceberg track
//         </div>


//         <div style="
//             color:#ff6b6b;
//         ">
//             ○ Red =
//             iceberg planning buffer
//         </div>
//     `;


//     document.body.appendChild(
//         legend
//     );
// }


// // ============================================================
// // HORIZON BUTTON EVENTS
// // ============================================================

// document
//     .querySelectorAll(
//         ".horizon-btn"
//     )
//     .forEach(
//         button => {

//             button.addEventListener(
//                 "click",

//                 () =>
//                     changeHorizon(
//                         button.dataset.horizon
//                     )
//             );
//         }
//     );


// // ============================================================
// // API BUTTON
// // ============================================================

// const connectApiBtn =
//     document.getElementById(
//         "connectApiBtn"
//     );

// if (connectApiBtn) {

//     connectApiBtn.addEventListener(
//         "click",
//         checkApi
//     );
// }


// // ============================================================
// // RECOMMENDED ROUTE UPLOAD
// // ============================================================

// const recommendedFile =
//     document.getElementById(
//         "recommendedFile"
//     );

// if (recommendedFile) {

//     recommendedFile
//         .addEventListener(

//             "change",

//             async event => {

//                 const file =
//                     event.target.files[0];

//                 if (!file) {
//                     return;
//                 }

//                 try {

//                     await loadGeoJsonFile(
//                         file,
//                         "recommended"
//                     );
//                 }

//                 catch (error) {

//                     addAlert(
//                         "critical",

//                         `Recommended route load failed: ` +
//                         `${error.message}`
//                     );
//                 }
//             }
//         );
// }


// // ============================================================
// // ALTERNATIVE ROUTE UPLOAD
// // ============================================================

// const alternativeFile =
//     document.getElementById(
//         "alternativeFile"
//     );

// if (alternativeFile) {

//     alternativeFile
//         .addEventListener(

//             "change",

//             async event => {

//                 const file =
//                     event.target.files[0];

//                 if (!file) {
//                     return;
//                 }

//                 try {

//                     await loadGeoJsonFile(
//                         file,
//                         "alternative"
//                     );
//                 }

//                 catch (error) {

//                     addAlert(
//                         "critical",

//                         `Alternative route load failed: ` +
//                         `${error.message}`
//                     );
//                 }
//             }
//         );
// }


// // ============================================================
// // CLEAR ROUTES BUTTON
// // ============================================================

// const clearRoutesBtn =
//     document.getElementById(
//         "clearRoutesBtn"
//     );

// if (clearRoutesBtn) {

//     clearRoutesBtn.addEventListener(
//         "click",
//         clearRoutes
//     );
// }


// // ============================================================
// // RESET VIEW BUTTON
// // ============================================================

// const resetViewBtn =
//     document.getElementById(
//         "resetViewBtn"
//     );

// if (resetViewBtn) {

//     resetViewBtn.addEventListener(
//         "click",
//         resetAntarcticView
//     );
// }


// // ============================================================
// // FIT ROUTES BUTTON
// // ============================================================

// const fitRoutesBtn =
//     document.getElementById(
//         "fitRoutesBtn"
//     );

// if (fitRoutesBtn) {

//     fitRoutesBtn.addEventListener(
//         "click",
//         fitRoutes
//     );
// }


// // ============================================================
// // LAYER CHECKBOX EVENTS
// // ============================================================

// const showRecommended =
//     document.getElementById(
//         "showRecommended"
//     );

// if (showRecommended) {

//     showRecommended.addEventListener(
//         "change",
//         refreshVisibility
//     );
// }


// const showAlternative =
//     document.getElementById(
//         "showAlternative"
//     );

// if (showAlternative) {

//     showAlternative.addEventListener(
//         "change",
//         refreshVisibility
//     );
// }


// const showIceberg =
//     document.getElementById(
//         "showIceberg"
//     );

// if (showIceberg) {

//     showIceberg.addEventListener(
//         "change",
//         refreshVisibility
//     );
// }


// // ============================================================
// // INITIAL STARTUP
// // ============================================================

// checkApi();

// addPolarGuardLegend();

// loadRealSeaIce();







const API_BASE = "http://127.0.0.1:8000";


// ============================================================
// GLOBAL STATE
// ============================================================

let seaIceEntities = [];
let uncertaintyEntities = [];
let icebergEntities = [];

let icebergObservedEntity = null;
let icebergForecastEntity = null;
let icebergBufferEntity = null;

let vesselStartEntity = null;
let vesselDestinationEntity = null;

let seaIceData = null;
let fullPolarGuardData = null;

let activeSeaIceHorizon = "current";

const state = {

    horizon: "current",

    recommendedEntity: null,
    alternativeEntity: null,

    recommendedData: null,
    alternativeData: null,

    missionResult: null,

    missionRunning: false
};


// ============================================================
// CESIUM VIEWER
// ============================================================

const viewer = new Cesium.Viewer(
    "cesiumContainer",
    {

        animation: false,
        timeline: false,

        baseLayerPicker: false,
        geocoder: false,
        homeButton: false,

        sceneModePicker: true,
        navigationHelpButton: false,

        fullscreenButton: true,
        infoBox: true,
        selectionIndicator: true,

        terrainProvider:
            new Cesium.EllipsoidTerrainProvider(),

        imageryProvider:
            new Cesium.OpenStreetMapImageryProvider({
                url:
                    "https://tile.openstreetmap.org/"
            })
    }
);


// ============================================================
// CESIUM APPEARANCE
// ============================================================

viewer.scene.globe.enableLighting = true;

viewer.scene.globe.showGroundAtmosphere =
    true;

viewer.scene.backgroundColor =
    Cesium.Color.fromCssColorString(
        "#07111f"
    );

viewer.scene.globe.depthTestAgainstTerrain =
    false;


// ============================================================
// CAMERA
// ============================================================

function resetAntarcticView() {

    viewer.camera.flyTo({

        destination:
            Cesium.Cartesian3.fromDegrees(
                0.0,
                -89.0,
                5900000.0
            ),

        orientation: {

            heading: 0.0,

            pitch:
                Cesium.Math.toRadians(
                    -90.0
                ),

            roll: 0.0
        },

        duration: 1.2
    });
}


resetAntarcticView();


// ============================================================
// GENERAL DOM HELPERS
// ============================================================

function getElement(id) {

    return document.getElementById(
        id
    );
}


function setText(
    id,
    value
) {

    const element =
        getElement(id);

    if (element) {

        element.textContent =
            value ?? "—";
    }
}


function escapeHtml(value) {

    return String(
        value ?? ""
    )
        .replaceAll(
            "&",
            "&amp;"
        )
        .replaceAll(
            "<",
            "&lt;"
        )
        .replaceAll(
            ">",
            "&gt;"
        )
        .replaceAll(
            '"',
            "&quot;"
        )
        .replaceAll(
            "'",
            "&#039;"
        );
}


function numericValue(
    id,
    fallback = null
) {

    const element =
        getElement(id);

    if (!element) {

        return fallback;
    }

    const value =
        Number(
            element.value
        );

    if (
        !Number.isFinite(
            value
        )
    ) {

        return fallback;
    }

    return value;
}


function inputValue(
    id,
    fallback = ""
) {

    const element =
        getElement(id);

    if (!element) {

        return fallback;
    }

    return element.value;
}


// ============================================================
// ALERT SYSTEM
// ============================================================

function addAlert(
    level,
    message
) {

    const alerts =
        getElement(
            "alerts"
        );

    if (!alerts) {

        console.log(
            `[${level}] ${message}`
        );

        return;
    }


    if (
        alerts.children.length === 1 &&
        alerts.textContent.includes(
            "Load route exports"
        )
    ) {

        alerts.innerHTML = "";
    }


    const item =
        document.createElement(
            "div"
        );

    item.className =
        `alert ${level}`;

    item.textContent =
        message;

    alerts.prepend(
        item
    );


    while (
        alerts.children.length > 12
    ) {

        alerts.removeChild(
            alerts.lastChild
        );
    }
}


// ============================================================
// API STATUS
// ============================================================

function setApiStatus(
    online,
    message
) {

    const status =
        getElement(
            "apiStatus"
        );

    if (status) {

        status.textContent =
            online
                ? "API Online"
                : "API Offline";

        status.classList.remove(
            "status-online",
            "status-offline"
        );

        status.classList.add(
            online
                ? "status-online"
                : "status-offline"
        );
    }


    const modelStatus =
        getElement(
            "modelStatus"
        );

    if (
        modelStatus &&
        message
    ) {

        modelStatus.textContent =
            message;
    }
}


// ============================================================
// CHECK BACKEND
// ============================================================

async function checkApi() {

    try {

        const health =
            await fetch(
                `${API_BASE}/health`
            );

        if (!health.ok) {

            throw new Error(
                "Health endpoint failed."
            );
        }


        const modelsResponse =
            await fetch(
                `${API_BASE}/models`
            );

        if (
            !modelsResponse.ok
        ) {

            throw new Error(
                "Models endpoint failed."
            );
        }


        const models =
            await modelsResponse.json();


        setApiStatus(

            true,

            `Sea ice: ${models.sea_ice.version} | ` +
            `Iceberg: ${models.iceberg.version} | ` +
            `Navigation: ${models.navigation.algorithm}`
        );


        addAlert(
            "safe",
            "PolarGuard backend connected successfully."
        );


        return true;
    }

    catch (error) {

        console.error(
            "Backend check failed:",
            error
        );


        setApiStatus(

            false,

            `Cannot reach ${API_BASE}. ` +
            `Start polarguard_api_cesium.py first.`
        );


        addAlert(
            "warning",
            "FastAPI backend is currently offline."
        );


        return false;
    }
}


// ============================================================
// GEOJSON HELPERS
// ============================================================

function geometryCoordinatesFromGeoJson(
    geojson
) {

    if (
        !geojson ||
        geojson.type !==
            "FeatureCollection" ||
        !Array.isArray(
            geojson.features
        ) ||
        geojson.features.length === 0
    ) {

        throw new Error(
            "Expected a GeoJSON FeatureCollection."
        );
    }


    const feature =
        geojson.features[0];


    if (
        !feature.geometry ||
        feature.geometry.type !==
            "LineString"
    ) {

        throw new Error(
            "Expected a GeoJSON LineString."
        );
    }


    return {

        coordinates:
            feature.geometry.coordinates,

        properties:
            feature.properties || {}
    };
}


// ============================================================
// FORMATTERS
// ============================================================

function formatDistance(
    value
) {

    const number =
        Number(
            value
        );

    if (
        !Number.isFinite(
            number
        )
    ) {

        return "—";
    }

    return `${number.toFixed(1)} km`;
}


function formatPercent(
    value
) {

    const number =
        Number(
            value
        );

    if (
        !Number.isFinite(
            number
        )
    ) {

        return "—";
    }

    return `${number.toFixed(1)}%`;
}


function formatCoordinate(
    value
) {

    const number =
        Number(
            value
        );

    if (
        !Number.isFinite(
            number
        )
    ) {

        return "—";
    }

    return number.toFixed(
        5
    );
}


// ============================================================
// REMOVE ROUTE ENTITY
// ============================================================

function removeRouteEntity(
    routeType
) {

    if (
        routeType ===
        "recommended"
    ) {

        if (
            state.recommendedEntity
        ) {

            viewer.entities.remove(
                state.recommendedEntity
            );
        }

        state.recommendedEntity =
            null;

        state.recommendedData =
            null;
    }

    else {

        if (
            state.alternativeEntity
        ) {

            viewer.entities.remove(
                state.alternativeEntity
            );
        }

        state.alternativeEntity =
            null;

        state.alternativeData =
            null;
    }
}


// ============================================================
// ADD ROUTE TO CESIUM
// ============================================================

function addRouteToViewer(
    routeType,
    geojson,
    autoFit = false
) {

    if (!geojson) {

        return null;
    }


    const parsed =
        geometryCoordinatesFromGeoJson(
            geojson
        );


    const positions =
        parsed.coordinates.map(

            ([lon, lat]) =>

                Cesium.Cartesian3
                    .fromDegrees(

                        Number(
                            lon
                        ),

                        Number(
                            lat
                        ),

                        8000
                    )
        );


    if (
        positions.length < 2
    ) {

        return null;
    }


    const isRecommended =
        routeType ===
        "recommended";


    removeRouteEntity(
        routeType
    );


    const routeName =
        isRecommended
            ? "Recommended Safe Route"
            : "Alternative Safe Route";


    const entity =
        viewer.entities.add({

            name:
                routeName,

            polyline: {

                positions:
                    positions,

                width:
                    isRecommended
                        ? 7
                        : 6,

                clampToGround:
                    false,

                material:
                    isRecommended

                        ? Cesium.Color.LIME
                            .withAlpha(
                                0.95
                            )

                        : new Cesium
                            .PolylineDashMaterialProperty({

                                color:
                                    Cesium.Color
                                        .DODGERBLUE,

                                dashLength:
                                    18
                            })
            },

            description: `

                <div style="
                    font-family:Arial;
                    min-width:230px;
                ">

                    <h3>
                        ${routeName}
                    </h3>

                    <b>Distance:</b>
                    ${
                        formatDistance(
                            parsed.properties
                                .distance_km
                        )
                    }

                    <br>

                    <b>Forecast Horizon:</b>
                    ${
                        escapeHtml(
                            parsed.properties
                                .routing_horizon ??
                            "N/A"
                        )
                    }

                    <br>

                    <b>Vessel Profile:</b>
                    ${
                        escapeHtml(
                            parsed.properties
                                .vessel_profile ??
                            "N/A"
                        )
                    }

                </div>
            `
        });


    if (isRecommended) {

        state.recommendedEntity =
            entity;

        state.recommendedData =
            geojson;


        const distance =
            formatDistance(
                parsed.properties
                    .distance_km
            );


        setText(
            "recommendedDistance",
            distance
        );

        setText(
            "cmpRecDistance",
            distance
        );
    }

    else {

        state.alternativeEntity =
            entity;

        state.alternativeData =
            geojson;


        const distance =
            formatDistance(
                parsed.properties
                    .distance_km
            );


        setText(
            "alternativeDistance",
            distance
        );

        setText(
            "cmpAltDistance",
            distance
        );


        if (
            parsed.properties
                .route_overlap_percent !==
            undefined
        ) {

            setText(

                "routeOverlap",

                formatPercent(
                    parsed.properties
                        .route_overlap_percent
                )
            );
        }
    }


    refreshVisibility();


    if (autoFit) {

        fitRoutes();
    }


    return entity;
}


// ============================================================
// LOAD GEOJSON FILE
// ============================================================

async function loadGeoJsonFile(
    file,
    routeType
) {

    const text =
        await file.text();

    const geojson =
        JSON.parse(
            text
        );

    addRouteToViewer(
        routeType,
        geojson,
        true
    );


    addAlert(

        "info",

        `${
            routeType ===
            "recommended"
                ? "Recommended"
                : "Alternative"
        } route loaded successfully.`
    );
}


// ============================================================
// CLEAR ROUTES
// ============================================================

function clearRoutes(
    showAlert = true
) {

    removeRouteEntity(
        "recommended"
    );

    removeRouteEntity(
        "alternative"
    );


    const ids = [

        "recommendedDistance",
        "alternativeDistance",
        "routeOverlap",
        "cmpRecDistance",
        "cmpAltDistance"
    ];


    ids.forEach(

        id =>
            setText(
                id,
                "—"
            )
    );


    if (showAlert) {

        addAlert(
            "info",
            "Routes cleared."
        );
    }
}


// ============================================================
// FIT CAMERA TO ROUTES
// ============================================================

function fitRoutes() {

    const entities = [];


    if (
        state.recommendedEntity
    ) {

        entities.push(
            state.recommendedEntity
        );
    }


    if (
        state.alternativeEntity
    ) {

        entities.push(
            state.alternativeEntity
        );
    }


    if (
        entities.length === 0
    ) {

        resetAntarcticView();

        return;
    }


    viewer.flyTo(
        entities,
        {

            duration:
                1.2,

            offset:
                new Cesium
                    .HeadingPitchRange(

                        0,

                        Cesium.Math
                            .toRadians(
                                -70
                            ),

                        180000
                    )
        }
    );
}


// ============================================================
// FOCUS ICEBERG
// ============================================================

function focusIceberg() {

    if (
        !fullPolarGuardData ||
        !fullPolarGuardData.iceberg
    ) {

        addAlert(
            "warning",
            "No iceberg prediction is currently loaded."
        );

        return;
    }


    const data =
        fullPolarGuardData.iceberg;


    let position =
        data.current;


    if (
        activeSeaIceHorizon !==
            "current" &&
        data.forecast &&
        data.forecast[
            activeSeaIceHorizon
        ]
    ) {

        position =
            data.forecast[
                activeSeaIceHorizon
            ];
    }


    if (!position) {

        return;
    }


    viewer.camera.flyTo({

        destination:
            Cesium.Cartesian3.fromDegrees(

                Number(
                    position.longitude
                ),

                Number(
                    position.latitude
                ),

                220000
            ),

        orientation: {

            heading: 0.0,

            pitch:
                Cesium.Math.toRadians(
                    -80
                ),

            roll: 0.0
        },

        duration: 1.1
    });
}


// ============================================================
// REFRESH LAYER VISIBILITY
// ============================================================

function refreshVisibility() {

    const recommendedCheckbox =
        getElement(
            "showRecommended"
        );

    const alternativeCheckbox =
        getElement(
            "showAlternative"
        );

    const icebergCheckbox =
        getElement(
            "showIceberg"
        );


    const showRecommended =
        recommendedCheckbox
            ? recommendedCheckbox.checked
            : true;


    const showAlternative =
        alternativeCheckbox
            ? alternativeCheckbox.checked
            : true;


    const showIceberg =
        icebergCheckbox
            ? icebergCheckbox.checked
            : true;


    if (
        state.recommendedEntity
    ) {

        state.recommendedEntity.show =
            showRecommended;
    }


    if (
        state.alternativeEntity
    ) {

        state.alternativeEntity.show =
            showAlternative;
    }


    icebergEntities.forEach(

        entity => {

            entity.show =
                showIceberg;
        }
    );


    if (
        icebergObservedEntity
    ) {

        icebergObservedEntity.show =
            showIceberg;
    }


    if (
        icebergForecastEntity
    ) {

        icebergForecastEntity.show =
            showIceberg;
    }


    if (
        icebergBufferEntity
    ) {

        icebergBufferEntity.show =
            showIceberg;
    }
}


// ============================================================
// CLEAR SEA ICE
// ============================================================

function clearSeaIce() {

    seaIceEntities.forEach(

        entity => {

            viewer.entities.remove(
                entity
            );
        }
    );


    seaIceEntities = [];
}


// ============================================================
// RGBA -> CESIUM COLOR
// ============================================================

function rgbaToCesiumColor(
    rgba
) {

    if (
        !rgba ||
        rgba.length < 4
    ) {

        return Cesium.Color.WHITE
            .withAlpha(
                0.5
            );
    }


    return Cesium.Color.fromBytes(

        Number(
            rgba[0]
        ),

        Number(
            rgba[1]
        ),

        Number(
            rgba[2]
        ),

        Number(
            rgba[3]
        )
    );
}


// ============================================================
// SEA ICE
// ============================================================

function renderSeaIce(
    horizon
) {

    clearSeaIce();


    if (!seaIceData) {

        return;
    }


    const horizonData =
        seaIceData.horizons?.[
            horizon
        ];


    if (!horizonData) {

        console.warn(
            `Unknown sea-ice horizon: ${horizon}`
        );

        return;
    }


    const cells =
        horizonData.sic_cells ||
        [];


    cells.forEach(

        (
            cell,
            index
        ) => {

            const sic =
                Number(
                    cell.value
                );

            const latitude =
                Number(
                    cell.latitude
                );

            const longitude =
                Number(
                    cell.longitude
                );


            if (
                !Number.isFinite(
                    sic
                ) ||
                !Number.isFinite(
                    latitude
                ) ||
                !Number.isFinite(
                    longitude
                )
            ) {

                return;
            }


            // 25 km source grid.
            // Display radius is enlarged slightly
            // because cells are sampled for Cesium.
            const radius =
                50000;


            const entity =
                viewer.entities.add({

                    id:
                        `sea-ice-${horizon}-${index}`,

                    name:
                        `SIC ${(sic * 100).toFixed(1)}%`,

                    position:
                        Cesium.Cartesian3
                            .fromDegrees(

                                longitude,
                                latitude,
                                900
                            ),

                    ellipse: {

                        semiMajorAxis:
                            radius,

                        semiMinorAxis:
                            radius,

                        material:
                            rgbaToCesiumColor(
                                cell.color
                            ),

                        outline:
                            false,

                        height:
                            800
                    },

                    description: `

                        <div style="
                            font-family:Arial;
                            min-width:220px;
                        ">

                            <h3>
                                PolarGuard Sea Ice
                            </h3>

                            <b>Forecast:</b>
                            ${
                                horizon ===
                                    "current"
                                    ? "Current observation"
                                    : "+" + horizon
                            }

                            <br>

                            <b>SIC:</b>
                            ${(sic * 100).toFixed(1)}%

                            <br>

                            <b>Latitude:</b>
                            ${latitude.toFixed(4)}

                            <br>

                            <b>Longitude:</b>
                            ${longitude.toFixed(4)}

                            <br><br>

                            <small>
                                Member 1 •
                                Hybrid v1 Frozen
                            </small>

                        </div>
                    `
                });


            seaIceEntities.push(
                entity
            );
        }
    );


    activeSeaIceHorizon =
        horizon;
}


// ============================================================
// UNCERTAINTY
// ============================================================

function clearUncertainty() {

    uncertaintyEntities
        .forEach(

            entity => {

                viewer.entities.remove(
                    entity
                );
            }
        );


    uncertaintyEntities = [];
}


function uncertaintyCesiumColor(
    value
) {

    if (
        value < 0.01
    ) {

        return Cesium.Color.YELLOW
            .withAlpha(
                0.045
            );
    }


    if (
        value < 0.02
    ) {

        return Cesium.Color.GOLD
            .withAlpha(
                0.055
            );
    }


    if (
        value < 0.03
    ) {

        return Cesium.Color.ORANGE
            .withAlpha(
                0.065
            );
    }


    if (
        value < 0.05
    ) {

        return Cesium.Color.ORANGERED
            .withAlpha(
                0.075
            );
    }


    return Cesium.Color.RED
        .withAlpha(
            0.09
        );
}


function renderUncertainty(
    horizon
) {

    clearUncertainty();


    if (!seaIceData) {

        return;
    }


    if (
        horizon ===
        "current"
    ) {

        return;
    }


    const horizonData =
        seaIceData.horizons?.[
            horizon
        ];


    if (!horizonData) {

        return;
    }


    const cells =
        horizonData
            .uncertainty_cells ||
        [];


    // Limit rendered entities for browser responsiveness.
    const maxCells =
        1100;


    const stride =
        Math.max(
            1,
            Math.ceil(
                cells.length /
                maxCells
            )
        );


    for (
        let index = 0;
        index < cells.length;
        index += stride
    ) {

        const cell =
            cells[index];


        const value =
            Number(
                cell.value
            );

        const latitude =
            Number(
                cell.latitude
            );

        const longitude =
            Number(
                cell.longitude
            );


        if (
            !Number.isFinite(
                value
            ) ||
            !Number.isFinite(
                latitude
            ) ||
            !Number.isFinite(
                longitude
            )
        ) {

            continue;
        }


        const entity =
            viewer.entities.add({

                id:
                    `uncertainty-${horizon}-${index}`,

                name:
                    "Forecast Uncertainty",

                position:
                    Cesium.Cartesian3
                        .fromDegrees(

                            longitude,
                            latitude,
                            1400
                        ),

                ellipse: {

                    semiMajorAxis:
                        28000,

                    semiMinorAxis:
                        28000,

                    material:
                        uncertaintyCesiumColor(
                            value
                        ),

                    outline:
                        false,

                    height:
                        1300
                },

                description: `

                    <div style="
                        font-family:Arial;
                        min-width:230px;
                    ">

                        <h3>
                            Sea-Ice Forecast Uncertainty
                        </h3>

                        <b>Horizon:</b>
                        +${horizon}

                        <br>

                        <b>Historical RMSE:</b>
                        ${(value * 100).toFixed(2)}
                        SIC percentage points

                        <br><br>

                        <small>

                            Historical per-grid-cell
                            RMSE calculated from
                            2024 validation residuals.

                            <br>

                            This is not a calibrated
                            confidence interval.

                        </small>

                    </div>
                `
            });


        uncertaintyEntities.push(
            entity
        );
    }
}


// ============================================================
// ICEBERG
// ============================================================

function clearIcebergTrajectory() {

    icebergEntities
        .forEach(

            entity => {

                viewer.entities.remove(
                    entity
                );
            }
        );


    icebergEntities = [];


    if (
        icebergObservedEntity
    ) {

        viewer.entities.remove(
            icebergObservedEntity
        );

        icebergObservedEntity =
            null;
    }


    if (
        icebergForecastEntity
    ) {

        viewer.entities.remove(
            icebergForecastEntity
        );

        icebergForecastEntity =
            null;
    }


    if (
        icebergBufferEntity
    ) {

        viewer.entities.remove(
            icebergBufferEntity
        );

        icebergBufferEntity =
            null;
    }
}


function icebergColorForHorizon(
    horizon
) {

    if (
        horizon === "24h"
    ) {

        return Cesium.Color.LIME;
    }


    if (
        horizon === "48h"
    ) {

        return Cesium.Color
            .DODGERBLUE;
    }


    if (
        horizon === "72h"
    ) {

        return Cesium.Color
            .MEDIUMPURPLE;
    }


    return Cesium.Color.GOLD;
}


function addIcebergMarker(
    stage,
    latitude,
    longitude,
    color,
    size = 14
) {

    const lat =
        Number(
            latitude
        );

    const lon =
        Number(
            longitude
        );


    if (
        !Number.isFinite(
            lat
        ) ||
        !Number.isFinite(
            lon
        )
    ) {

        return null;
    }


    const entity =
        viewer.entities.add({

            name:
                `Iceberg ${stage}`,

            position:
                Cesium.Cartesian3
                    .fromDegrees(

                        lon,
                        lat,
                        9000
                    ),

            point: {

                pixelSize:
                    size,

                color:
                    color,

                outlineColor:
                    Cesium.Color.WHITE,

                outlineWidth:
                    2
            },

            label: {

                text:
                    stage,

                font:
                    "13px sans-serif",

                fillColor:
                    Cesium.Color.WHITE,

                outlineColor:
                    Cesium.Color.BLACK,

                outlineWidth:
                    3,

                style:
                    Cesium.LabelStyle
                        .FILL_AND_OUTLINE,

                pixelOffset:
                    new Cesium
                        .Cartesian2(
                            0,
                            -24
                        ),

                distanceDisplayCondition:
                    new Cesium
                        .DistanceDisplayCondition(

                            0,
                            3000000
                        )
            },

            description: `

                <div style="
                    font-family:Arial;
                    min-width:220px;
                ">

                    <h3>
                        PolarGuard Iceberg
                    </h3>

                    <b>Stage:</b>
                    ${escapeHtml(stage)}

                    <br>

                    <b>Latitude:</b>
                    ${lat.toFixed(6)}

                    <br>

                    <b>Longitude:</b>
                    ${lon.toFixed(6)}

                    <br><br>

                    <small>
                        Member 2 •
                        Environment v1 Frozen
                    </small>

                </div>
            `
        });


    icebergEntities.push(
        entity
    );


    return entity;
}


function renderIcebergTrajectory(
    horizon
) {

    clearIcebergTrajectory();


    if (
        !fullPolarGuardData ||
        !fullPolarGuardData.iceberg
    ) {

        return;
    }


    const data =
        fullPolarGuardData
            .iceberg;


    const history =
        data.history || [];


    const current =
        data.current;


    const forecast =
        data.forecast || {};


    if (!current) {

        return;
    }


    // OBSERVED TRACK

    const observedPoints =
        history
            .filter(

                item =>
                    Number.isFinite(
                        Number(
                            item.latitude
                        )
                    ) &&
                    Number.isFinite(
                        Number(
                            item.longitude
                        )
                    )
            )
            .map(

                item =>

                    Cesium.Cartesian3
                        .fromDegrees(

                            Number(
                                item.longitude
                            ),

                            Number(
                                item.latitude
                            ),

                            6000
                        )
            );


    observedPoints.push(

        Cesium.Cartesian3
            .fromDegrees(

                Number(
                    current.longitude
                ),

                Number(
                    current.latitude
                ),

                6000
            )
    );


    if (
        observedPoints.length > 1
    ) {

        icebergObservedEntity =
            viewer.entities.add({

                name:
                    "Observed Iceberg Track",

                polyline: {

                    positions:
                        observedPoints,

                    width:
                        3,

                    material:
                        Cesium.Color
                            .LIGHTGRAY
                            .withAlpha(
                                0.9
                            )
                }
            });
    }


    // HISTORY MARKERS

    history.forEach(

        item => {

            addIcebergMarker(

                item.stage,

                item.latitude,

                item.longitude,

                Cesium.Color
                    .LIGHTGRAY,

                9
            );
        }
    );


    // CURRENT

    addIcebergMarker(

        "Current",

        current.latitude,

        current.longitude,

        Cesium.Color.GOLD,

        16
    );


    const forecastOrder = [
        "24h",
        "48h",
        "72h"
    ];


    let visibleForecasts =
        [];


    if (
        horizon !==
        "current"
    ) {

        const stopIndex =
            forecastOrder
                .indexOf(
                    horizon
                );


        if (
            stopIndex >= 0
        ) {

            visibleForecasts =
                forecastOrder.slice(
                    0,
                    stopIndex + 1
                );
        }
    }


    const forecastPositions = [

        Cesium.Cartesian3
            .fromDegrees(

                Number(
                    current.longitude
                ),

                Number(
                    current.latitude
                ),

                7000
            )
    ];


    visibleForecasts.forEach(

        key => {

            const item =
                forecast[key];


            if (!item) {

                return;
            }


            addIcebergMarker(

                `+${key}`,

                item.latitude,

                item.longitude,

                icebergColorForHorizon(
                    key
                ),

                17
            );


            forecastPositions.push(

                Cesium.Cartesian3
                    .fromDegrees(

                        Number(
                            item.longitude
                        ),

                        Number(
                            item.latitude
                        ),

                        7000
                    )
            );
        }
    );


    if (
        forecastPositions.length > 1
    ) {

        icebergForecastEntity =
            viewer.entities.add({

                name:
                    "Predicted Iceberg Trajectory",

                polyline: {

                    positions:
                        forecastPositions,

                    width:
                        5,

                    material:
                        Cesium.Color.CYAN
                            .withAlpha(
                                0.95
                            )
                }
            });
    }


    // PLANNING BUFFER

    if (
        horizon !==
            "current" &&
        forecast[horizon]
    ) {

        const selected =
            forecast[horizon];


        const bufferKm =
            Number(

                data
                    .planning_buffer_km ||
                10
            );


        icebergBufferEntity =
            viewer.entities.add({

                name:
                    "Iceberg Planning Buffer",

                position:
                    Cesium.Cartesian3
                        .fromDegrees(

                            Number(
                                selected.longitude
                            ),

                            Number(
                                selected.latitude
                            ),

                            5000
                        ),

                ellipse: {

                    semiMajorAxis:
                        bufferKm *
                        1000,

                    semiMinorAxis:
                        bufferKm *
                        1000,

                    material:
                        Cesium.Color.RED
                            .withAlpha(
                                0.08
                            ),

                    outline:
                        true,

                    outlineColor:
                        Cesium.Color.RED
                            .withAlpha(
                                0.9
                            ),

                    height:
                        5000
                },

                description: `

                    <div style="
                        font-family:Arial;
                        min-width:230px;
                    ">

                        <h3>
                            Navigation Planning Buffer
                        </h3>

                        <b>Forecast:</b>
                        +${horizon}

                        <br>

                        <b>Radius:</b>
                        ${bufferKm.toFixed(1)} km

                        <br><br>

                        <small>
                            Prototype planning buffer.
                            It is not a calibrated
                            collision-probability region.
                        </small>

                    </div>
                `
            });
    }


    refreshVisibility();
}


// ============================================================
// VESSEL MARKERS
// ============================================================

function clearVesselMarkers() {

    if (
        vesselStartEntity
    ) {

        viewer.entities.remove(
            vesselStartEntity
        );

        vesselStartEntity =
            null;
    }


    if (
        vesselDestinationEntity
    ) {

        viewer.entities.remove(
            vesselDestinationEntity
        );

        vesselDestinationEntity =
            null;
    }
}


function renderVesselMarkers(
    mission
) {

    clearVesselMarkers();


    if (
        !mission ||
        !mission.mission_input
    ) {

        return;
    }


    const start =
        mission
            .mission_input
            .start;


    const destination =
        mission
            .mission_input
            .destination;


    if (start) {

        vesselStartEntity =
            viewer.entities.add({

                name:
                    "Vessel Start",

                position:
                    Cesium.Cartesian3
                        .fromDegrees(

                            Number(
                                start.longitude
                            ),

                            Number(
                                start.latitude
                            ),

                            10000
                        ),

                point: {

                    pixelSize:
                        15,

                    color:
                        Cesium.Color
                            .SPRINGGREEN,

                    outlineColor:
                        Cesium.Color.WHITE,

                    outlineWidth:
                        3
                },

                label: {

                    text:
                        "VESSEL START",

                    font:
                        "bold 12px sans-serif",

                    fillColor:
                        Cesium.Color.WHITE,

                    outlineColor:
                        Cesium.Color.BLACK,

                    outlineWidth:
                        3,

                    style:
                        Cesium.LabelStyle
                            .FILL_AND_OUTLINE,

                    pixelOffset:
                        new Cesium.Cartesian2(
                            0,
                            -25
                        )
                }
            });
    }


    if (destination) {

        vesselDestinationEntity =
            viewer.entities.add({

                name:
                    "Destination",

                position:
                    Cesium.Cartesian3
                        .fromDegrees(

                            Number(
                                destination.longitude
                            ),

                            Number(
                                destination.latitude
                            ),

                            10000
                        ),

                point: {

                    pixelSize:
                        15,

                    color:
                        Cesium.Color
                            .MAGENTA,

                    outlineColor:
                        Cesium.Color.WHITE,

                    outlineWidth:
                        3
                },

                label: {

                    text:
                        "DESTINATION",

                    font:
                        "bold 12px sans-serif",

                    fillColor:
                        Cesium.Color.WHITE,

                    outlineColor:
                        Cesium.Color.BLACK,

                    outlineWidth:
                        3,

                    style:
                        Cesium.LabelStyle
                            .FILL_AND_OUTLINE,

                    pixelOffset:
                        new Cesium.Cartesian2(
                            0,
                            -25
                        )
                }
            });
    }
}


// ============================================================
// SYNCHRONIZED HORIZON
// ============================================================

function setSeaIceHorizon(
    horizon
) {

    activeSeaIceHorizon =
        horizon;


    renderSeaIce(
        horizon
    );


    renderUncertainty(
        horizon
    );


    renderIcebergTrajectory(
        horizon
    );
}


function changeHorizon(
    horizon
) {

    state.horizon =
        horizon;


    document
        .querySelectorAll(
            ".horizon-btn"
        )
        .forEach(

            button => {

                button.classList.toggle(

                    "active",

                    button.dataset.horizon ===
                        horizon
                );
            }
        );


    const label =
        horizon ===
        "current"
            ? "Current"
            : `+${horizon}`;


    setText(
        "currentHorizon",
        label
    );

    setText(
        "summaryHorizon",
        label
    );


    setSeaIceHorizon(
        horizon
    );


    addAlert(

        "info",

        `Visualization horizon changed to ${label}.`
    );
}


// ============================================================
// LEGEND
// ============================================================

function addPolarGuardLegend() {

    if (
        getElement(
            "polarguardLegend"
        )
    ) {

        return;
    }


    const legend =
        document.createElement(
            "div"
        );


    legend.id =
        "polarguardLegend";


    legend.style.cssText = `

        position:absolute;

        left:355px;
        bottom:25px;

        z-index:50;

        background:
            rgba(7,17,31,0.92);

        color:#ffffff;

        padding:
            12px 14px;

        border:
            1px solid
            rgba(148,163,184,0.35);

        border-radius:
            10px;

        font-family:
            Arial,sans-serif;

        font-size:
            12px;

        line-height:
            1.55;

        pointer-events:
            none;

        backdrop-filter:
            blur(8px);

        box-shadow:
            0 10px 28px
            rgba(0,0,0,0.25);
    `;


    legend.innerHTML = `

        <div style="
            font-weight:700;
            margin-bottom:7px;
        ">
            PolarGuard Layers
        </div>

        <div>
            <span style="color:#dbeafe">
                ●
            </span>
            5–30% SIC
        </div>

        <div>
            <span style="color:#93c5fd">
                ●
            </span>
            30–60% SIC
        </div>

        <div>
            <span style="color:#60a5fa">
                ●
            </span>
            60–80% SIC
        </div>

        <div>
            <span style="color:#2563eb">
                ●
            </span>
            80–100% SIC
        </div>

        <div style="
            margin-top:6px;
            color:#fbbf24;
        ">
            ● Forecast uncertainty
        </div>

        <div style="
            color:#ffd700;
        ">
            ● Current iceberg
        </div>

        <div style="
            color:#00ffff;
        ">
            ━ Predicted trajectory
        </div>

        <div style="
            color:#ff6b6b;
        ">
            ○ Iceberg planning buffer
        </div>

        <div style="
            color:#7CFC00;
        ">
            ━ Recommended route
        </div>

        <div style="
            color:#1e90ff;
        ">
            ┅ Alternative route
        </div>

        <div style="
            color:#00ff7f;
        ">
            ● Vessel start
        </div>

        <div style="
            color:#ff00ff;
        ">
            ● Destination
        </div>
    `;


    document.body.appendChild(
        legend
    );
}


// ============================================================
// LOAD DEFAULT DEMO VISUALIZATION
// ============================================================

async function loadRealSeaIce() {

    try {

        addAlert(

            "info",

            "Loading synchronized PolarGuard demo forecast..."
        );


        const response =
            await fetch(

                `${API_BASE}/visualization/full` +
                `?date=2025-12-28` +
                `&sample_step=6`
            );


        if (
            !response.ok
        ) {

            const errorText =
                await response.text();


            throw new Error(

                `Visualization API returned ` +
                `${response.status}: ` +
                `${errorText}`
            );
        }


        fullPolarGuardData =
            await response.json();


        seaIceData =
            fullPolarGuardData
                .sea_ice;


        renderSeaIce(
            activeSeaIceHorizon
        );


        renderUncertainty(
            activeSeaIceHorizon
        );


        renderIcebergTrajectory(
            activeSeaIceHorizon
        );


        refreshVisibility();


        addAlert(

            "safe",

            "Default sea-ice and iceberg forecast loaded."
        );
    }

    catch (error) {

        console.error(
            "Visualization failed:",
            error
        );


        addAlert(

            "warning",

            `Default visualization failed: ${error.message}`
        );
    }
}


// ============================================================
// MISSION CONTROL PANEL
// ============================================================

function createMissionControlPanel() {

    if (
        getElement(
            "polarMissionPanel"
        )
    ) {

        return;
    }


    const panel =
        document.createElement(
            "div"
        );


    panel.id =
        "polarMissionPanel";


    panel.innerHTML = `

        <div class="pg-mission-header">

            <div>

                <div class="pg-mission-title">
                    POLARGUARD MISSION CONTROL
                </div>

                <div class="pg-mission-subtitle">
                    Complete AI forecast + navigation workflow
                </div>

            </div>

            <button
                id="missionCollapseBtn"
                class="pg-icon-btn"
                title="Collapse mission panel"
            >
                −
            </button>

        </div>


        <div id="missionPanelBody">


            <div class="pg-mission-section">

                <div class="pg-section-title">
                    1 · Mission
                </div>


                <div class="pg-grid-2">

                    <label>
                        Initialization Date
                        <input
                            id="missionDate"
                            type="date"
                            value="2025-12-28"
                        >
                    </label>


                    <label>
                        Routing Horizon
                        <select
                            id="missionHorizon"
                        >
                            <option value="24h">
                                +24h
                            </option>

                            <option value="48h">
                                +48h
                            </option>

                            <option value="72h">
                                +72h
                            </option>
                        </select>
                    </label>

                </div>

            </div>


            <div class="pg-mission-section">

                <div class="pg-section-title">
                    2 · Iceberg Position History
                </div>


                <div class="pg-coordinate-grid">

                    <div>
                        <span>
                            t-3
                        </span>

                        <input
                            id="missionLatTm3"
                            type="number"
                            step="0.00001"
                            value="-75.75435"
                            title="t-3 latitude"
                        >

                        <input
                            id="missionLonTm3"
                            type="number"
                            step="0.00001"
                            value="-41.10950"
                            title="t-3 longitude"
                        >
                    </div>


                    <div>
                        <span>
                            t-2
                        </span>

                        <input
                            id="missionLatTm2"
                            type="number"
                            step="0.00001"
                            value="-75.69135"
                            title="t-2 latitude"
                        >

                        <input
                            id="missionLonTm2"
                            type="number"
                            step="0.00001"
                            value="-41.09485"
                            title="t-2 longitude"
                        >
                    </div>


                    <div>
                        <span>
                            t-1
                        </span>

                        <input
                            id="missionLatTm1"
                            type="number"
                            step="0.00001"
                            value="-75.63525"
                            title="t-1 latitude"
                        >

                        <input
                            id="missionLonTm1"
                            type="number"
                            step="0.00001"
                            value="-41.08170"
                            title="t-1 longitude"
                        >
                    </div>


                    <div>
                        <span>
                            Now
                        </span>

                        <input
                            id="missionCurrentLat"
                            type="number"
                            step="0.00001"
                            value="-75.611000"
                            title="Current latitude"
                        >

                        <input
                            id="missionCurrentLon"
                            type="number"
                            step="0.00001"
                            value="-41.076000"
                            title="Current longitude"
                        >
                    </div>

                </div>


                <div class="pg-small-note">
                    Columns are latitude and longitude.
                </div>

            </div>


            <div class="pg-mission-section">

                <div class="pg-section-title">
                    3 · Environmental Forcing
                </div>


                <div class="pg-grid-2">

                    <label>
                        ERA5 Wind U (m/s)
                        <input
                            id="missionWindU"
                            type="number"
                            step="0.1"
                            value="-3.0"
                        >
                    </label>


                    <label>
                        ERA5 Wind V (m/s)
                        <input
                            id="missionWindV"
                            type="number"
                            step="0.1"
                            value="2.0"
                        >
                    </label>


                    <label>
                        GLORYS Ocean U (m/s)
                        <input
                            id="missionOceanU"
                            type="number"
                            step="0.01"
                            value="-0.05"
                        >
                    </label>


                    <label>
                        GLORYS Ocean V (m/s)
                        <input
                            id="missionOceanV"
                            type="number"
                            step="0.01"
                            value="0.03"
                        >
                    </label>

                </div>

            </div>


            <div class="pg-mission-section">

                <div class="pg-section-title">
                    4 · Navigation
                </div>


                <div class="pg-grid-2">

                    <label>
                        Start Latitude
                        <input
                            id="missionStartLat"
                            type="number"
                            step="0.01"
                            value="-72.50"
                        >
                    </label>


                    <label>
                        Start Longitude
                        <input
                            id="missionStartLon"
                            type="number"
                            step="0.01"
                            value="-50.00"
                        >
                    </label>


                    <label>
                        Destination Latitude
                        <input
                            id="missionDestLat"
                            type="number"
                            step="0.01"
                            value="-70.50"
                        >
                    </label>


                    <label>
                        Destination Longitude
                        <input
                            id="missionDestLon"
                            type="number"
                            step="0.01"
                            value="-35.00"
                        >
                    </label>


                    <label>
                        Vessel Capability
                        <select
                            id="missionVessel"
                        >
                            <option value="LOW">
                                Low Ice Capability
                            </option>

                            <option
                                value="MEDIUM"
                                selected
                            >
                                Medium Ice Capability
                            </option>

                            <option value="HIGH">
                                High Ice Capability
                            </option>
                        </select>
                    </label>


                    <label>
                        Iceberg Safety Radius (km)
                        <input
                            id="missionSafetyRadius"
                            type="number"
                            min="1"
                            max="100"
                            step="1"
                            value="10"
                        >
                    </label>

                </div>

            </div>


            <button
                id="runMissionBtn"
                class="pg-run-btn"
            >
                RUN POLARGUARD MISSION
            </button>


            <div
                id="missionProgress"
                class="pg-mission-progress"
            >
                Ready
            </div>


            <div class="pg-mission-actions">

                <button
                    id="focusIcebergBtn"
                >
                    Focus Iceberg
                </button>

                <button
                    id="fitMissionRouteBtn"
                >
                    Focus Route
                </button>

                <button
                    id="downloadMissionBtn"
                    disabled
                >
                    Export Mission JSON
                </button>

            </div>


            <div class="pg-disclaimer">

                Research prototype decision support.
                Not certified operational navigation advice.

            </div>

        </div>
    `;


    document.body.appendChild(
        panel
    );


    addMissionPanelStyles();


    getElement(
        "runMissionBtn"
    )?.addEventListener(

        "click",

        runMission
    );


    getElement(
        "focusIcebergBtn"
    )?.addEventListener(

        "click",

        focusIceberg
    );


    getElement(
        "fitMissionRouteBtn"
    )?.addEventListener(

        "click",

        fitRoutes
    );


    getElement(
        "downloadMissionBtn"
    )?.addEventListener(

        "click",

        exportMissionJson
    );


    getElement(
        "missionHorizon"
    )?.addEventListener(

        "change",

        event => {

            const horizon =
                event.target.value;

            changeHorizon(
                horizon
            );
        }
    );


    getElement(
        "missionCollapseBtn"
    )?.addEventListener(

        "click",

        () => {

            const body =
                getElement(
                    "missionPanelBody"
                );

            const button =
                getElement(
                    "missionCollapseBtn"
                );


            if (!body) {

                return;
            }


            const hidden =
                body.style.display ===
                "none";


            body.style.display =
                hidden
                    ? "block"
                    : "none";


            if (button) {

                button.textContent =
                    hidden
                        ? "−"
                        : "+";
            }
        }
    );
}


// ============================================================
// MISSION PANEL STYLES
// ============================================================

function addMissionPanelStyles() {

    if (
        getElement(
            "polarMissionStyles"
        )
    ) {

        return;
    }


    const style =
        document.createElement(
            "style"
        );


    style.id =
        "polarMissionStyles";


    style.textContent = `

        #polarMissionPanel {

            position:
                fixed;

            top:
                92px;

            right:
                18px;

            width:
                360px;

            max-height:
                calc(100vh - 120px);

            overflow-y:
                auto;

            z-index:
                1000;

            background:
                rgba(7,17,31,0.96);

            color:
                #e5eef8;

            border:
                1px solid
                rgba(96,165,250,0.30);

            border-radius:
                14px;

            box-shadow:
                0 22px 60px
                rgba(0,0,0,0.42);

            backdrop-filter:
                blur(12px);

            font-family:
                Inter,
                Arial,
                sans-serif;
        }


        #polarMissionPanel::-webkit-scrollbar {

            width:
                7px;
        }


        #polarMissionPanel::-webkit-scrollbar-thumb {

            background:
                rgba(148,163,184,0.35);

            border-radius:
                10px;
        }


        .pg-mission-header {

            display:
                flex;

            justify-content:
                space-between;

            align-items:
                center;

            padding:
                15px 16px;

            border-bottom:
                1px solid
                rgba(148,163,184,0.18);

            position:
                sticky;

            top:
                0;

            z-index:
                2;

            background:
                rgba(7,17,31,0.98);
        }


        .pg-mission-title {

            color:
                #ffffff;

            font-weight:
                800;

            letter-spacing:
                0.045em;

            font-size:
                14px;
        }


        .pg-mission-subtitle {

            color:
                #94a3b8;

            font-size:
                11px;

            margin-top:
                3px;
        }


        .pg-icon-btn {

            width:
                32px;

            height:
                32px;

            border-radius:
                8px;

            border:
                1px solid
                rgba(148,163,184,.25);

            background:
                rgba(15,23,42,.9);

            color:
                white;

            cursor:
                pointer;
        }


        #missionPanelBody {

            padding:
                12px;
        }


        .pg-mission-section {

            background:
                rgba(15,23,42,.70);

            border:
                1px solid
                rgba(148,163,184,.14);

            border-radius:
                10px;

            padding:
                11px;

            margin-bottom:
                10px;
        }


        .pg-section-title {

            font-size:
                11px;

            text-transform:
                uppercase;

            letter-spacing:
                .08em;

            font-weight:
                800;

            color:
                #60a5fa;

            margin-bottom:
                9px;
        }


        .pg-grid-2 {

            display:
                grid;

            grid-template-columns:
                1fr 1fr;

            gap:
                8px;
        }


        .pg-coordinate-grid {

            display:
                grid;

            gap:
                7px;
        }


        .pg-coordinate-grid > div {

            display:
                grid;

            grid-template-columns:
                38px 1fr 1fr;

            gap:
                6px;

            align-items:
                center;
        }


        .pg-coordinate-grid span {

            color:
                #cbd5e1;

            font-size:
                11px;

            font-weight:
                700;
        }


        #polarMissionPanel label {

            display:
                flex;

            flex-direction:
                column;

            gap:
                4px;

            font-size:
                10px;

            color:
                #cbd5e1;

            font-weight:
                600;
        }


        #polarMissionPanel input,
        #polarMissionPanel select {

            width:
                100%;

            box-sizing:
                border-box;

            padding:
                7px 8px;

            color:
                white;

            background:
                rgba(2,6,23,.90);

            border:
                1px solid
                rgba(148,163,184,.28);

            border-radius:
                7px;

            outline:
                none;

            font-size:
                11px;
        }


        #polarMissionPanel input:focus,
        #polarMissionPanel select:focus {

            border-color:
                #60a5fa;

            box-shadow:
                0 0 0 2px
                rgba(96,165,250,.12);
        }


        .pg-small-note {

            margin-top:
                7px;

            color:
                #64748b;

            font-size:
                10px;
        }


        .pg-run-btn {

            width:
                100%;

            padding:
                12px;

            border:
                none;

            border-radius:
                9px;

            cursor:
                pointer;

            color:
                #00111d;

            font-weight:
                900;

            letter-spacing:
                .045em;

            background:
                linear-gradient(
                    135deg,
                    #22d3ee,
                    #22c55e
                );

            box-shadow:
                0 10px 30px
                rgba(34,211,238,.15);
        }


        .pg-run-btn:disabled {

            opacity:
                .55;

            cursor:
                wait;
        }


        .pg-mission-progress {

            margin-top:
                9px;

            padding:
                8px 10px;

            border-radius:
                8px;

            background:
                rgba(15,23,42,.85);

            color:
                #94a3b8;

            font-size:
                10px;

            border:
                1px solid
                rgba(148,163,184,.12);
        }


        .pg-mission-actions {

            display:
                grid;

            grid-template-columns:
                repeat(3,1fr);

            gap:
                6px;

            margin-top:
                8px;
        }


        .pg-mission-actions button {

            padding:
                7px 5px;

            border-radius:
                7px;

            border:
                1px solid
                rgba(148,163,184,.25);

            background:
                rgba(15,23,42,.90);

            color:
                #e2e8f0;

            cursor:
                pointer;

            font-size:
                9px;

            font-weight:
                700;
        }


        .pg-mission-actions button:hover {

            border-color:
                #60a5fa;
        }


        .pg-mission-actions button:disabled {

            opacity:
                .45;

            cursor:
                default;
        }


        .pg-disclaimer {

            margin-top:
                9px;

            font-size:
                9px;

            color:
                #64748b;

            line-height:
                1.4;
        }


        #polarMissionDecision {

            position:
                fixed;

            left:
                355px;

            top:
                95px;

            width:
                300px;

            max-height:
                330px;

            overflow-y:
                auto;

            z-index:
                900;

            background:
                rgba(7,17,31,.94);

            border:
                1px solid
                rgba(148,163,184,.20);

            border-radius:
                12px;

            padding:
                12px;

            color:
                #e2e8f0;

            font-family:
                Inter,
                Arial,
                sans-serif;

            box-shadow:
                0 16px 45px
                rgba(0,0,0,.32);

            backdrop-filter:
                blur(10px);
        }


        .pg-decision-title {

            font-weight:
                800;

            color:
                white;

            margin-bottom:
                9px;
        }


        .pg-decision-row {

            display:
                flex;

            justify-content:
                space-between;

            gap:
                10px;

            padding:
                5px 0;

            border-bottom:
                1px solid
                rgba(148,163,184,.08);

            font-size:
                11px;
        }


        .pg-decision-row span:first-child {

            color:
                #94a3b8;
        }


        .pg-decision-row span:last-child {

            text-align:
                right;

            font-weight:
                700;
        }


        .pg-hazard-box {

            margin-top:
                8px;

            padding:
                8px;

            border-radius:
                8px;

            background:
                rgba(127,29,29,.18);

            border:
                1px solid
                rgba(248,113,113,.20);

            font-size:
                10px;

            line-height:
                1.45;
        }


        @media (
            max-width: 1050px
        ) {

            #polarMissionPanel {

                width:
                    320px;
            }


            #polarMissionDecision {

                display:
                    none;
            }
        }
    `;


    document.head.appendChild(
        style
    );
}


// ============================================================
// MISSION REQUEST
// ============================================================

function buildMissionRequest() {

    const payload = {

        initialization_date:
            inputValue(
                "missionDate",
                "2025-12-28"
            ),

        lat_tm3:
            numericValue(
                "missionLatTm3"
            ),

        lon_tm3:
            numericValue(
                "missionLonTm3"
            ),

        lat_tm2:
            numericValue(
                "missionLatTm2"
            ),

        lon_tm2:
            numericValue(
                "missionLonTm2"
            ),

        lat_tm1:
            numericValue(
                "missionLatTm1"
            ),

        lon_tm1:
            numericValue(
                "missionLonTm1"
            ),

        current_latitude:
            numericValue(
                "missionCurrentLat"
            ),

        current_longitude:
            numericValue(
                "missionCurrentLon"
            ),

        wind_u10:
            numericValue(
                "missionWindU"
            ),

        wind_v10:
            numericValue(
                "missionWindV"
            ),

        ocean_uo:
            numericValue(
                "missionOceanU"
            ),

        ocean_vo:
            numericValue(
                "missionOceanV"
            ),

        routing_horizon:
            inputValue(
                "missionHorizon",
                "24h"
            ),

        start_lat:
            numericValue(
                "missionStartLat"
            ),

        start_lon:
            numericValue(
                "missionStartLon"
            ),

        destination_lat:
            numericValue(
                "missionDestLat"
            ),

        destination_lon:
            numericValue(
                "missionDestLon"
            ),

        vessel_profile:
            inputValue(
                "missionVessel",
                "MEDIUM"
            ),

        safety_radius_km:
            numericValue(
                "missionSafetyRadius",
                10
            ),

        sample_step:
            6
    };


    const requiredNumeric = [

        "lat_tm3",
        "lon_tm3",

        "lat_tm2",
        "lon_tm2",

        "lat_tm1",
        "lon_tm1",

        "current_latitude",
        "current_longitude",

        "wind_u10",
        "wind_v10",

        "ocean_uo",
        "ocean_vo",

        "start_lat",
        "start_lon",

        "destination_lat",
        "destination_lon",

        "safety_radius_km"
    ];


    requiredNumeric.forEach(

        key => {

            if (
                !Number.isFinite(
                    payload[key]
                )
            ) {

                throw new Error(
                    `Invalid value for ${key}.`
                );
            }
        }
    );


    return payload;
}


// ============================================================
// RUN COMPLETE MISSION
// ============================================================

async function runMission() {

    if (
        state.missionRunning
    ) {

        return;
    }


    let payload;


    try {

        payload =
            buildMissionRequest();
    }

    catch (error) {

        addAlert(
            "critical",
            error.message
        );

        return;
    }


    const button =
        getElement(
            "runMissionBtn"
        );


    const progress =
        getElement(
            "missionProgress"
        );


    state.missionRunning =
        true;


    if (button) {

        button.disabled =
            true;

        button.textContent =
            "RUNNING POLARGUARD...";
    }


    if (progress) {

        progress.textContent =
            "Running Member 1 → Member 2 → Risk → A* Routing → Hazard analysis...";
    }


    addAlert(
        "info",
        "PolarGuard mission started."
    );


    try {

        const response =
            await fetch(
                `${API_BASE}/mission`,
                {

                    method:
                        "POST",

                    headers: {

                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify(
                            payload
                        )
                }
            );


        let result;


        try {

            result =
                await response.json();
        }

        catch {

            throw new Error(
                `Backend returned HTTP ${response.status}.`
            );
        }


        if (
            !response.ok
        ) {

            const detail =
                result?.detail ||
                `HTTP ${response.status}`;


            throw new Error(
                detail
            );
        }


        state.missionResult =
            result;


        fullPolarGuardData =
            result;


        seaIceData =
            result.sea_ice;


        // Route data from backend.

        clearRoutes(
            false
        );


        const navigation =
            result.navigation || {};


        const recommended =
            navigation
                .recommended_route;


        const alternative =
            navigation
                .alternative_route;


        if (
            recommended?.available &&
            recommended.geojson
        ) {

            addRouteToViewer(

                "recommended",

                recommended.geojson,

                false
            );
        }


        if (
            alternative?.available &&
            alternative.geojson
        ) {

            addRouteToViewer(

                "alternative",

                alternative.geojson,

                false
            );
        }


        renderVesselMarkers(
            result
        );


        const missionHorizon =
            result.routing_horizon ||
            payload.routing_horizon;


        if (
            getElement(
                "missionHorizon"
            )
        ) {

            getElement(
                "missionHorizon"
            ).value =
                missionHorizon;
        }


        changeHorizon(
            missionHorizon
        );


        renderMissionDecision(
            result
        );


        renderMissionAlerts(
            result
        );


        const exportButton =
            getElement(
                "downloadMissionBtn"
            );


        if (exportButton) {

            exportButton.disabled =
                false;
        }


        if (progress) {

            progress.textContent =
                navigation.success
                    ? "Mission completed successfully."
                    : "Forecast completed. No valid route was found under the selected constraints.";
        }


        if (
            navigation.success
        ) {

            addAlert(

                "safe",

                `Mission complete. Recommended route: ${
                    formatDistance(
                        recommended?.distance_km
                    )
                }.`
            );


            setTimeout(
                fitRoutes,
                400
            );
        }

        else {

            addAlert(

                "warning",

                navigation.recommendation ||
                "No navigable route found under the selected constraints."
            );


            setTimeout(
                focusIceberg,
                400
            );
        }
    }

    catch (error) {

        console.error(
            "Mission failed:",
            error
        );


        if (progress) {

            progress.textContent =
                `Mission failed: ${error.message}`;
        }


        addAlert(

            "critical",

            `PolarGuard mission failed: ${error.message}`
        );
    }

    finally {

        state.missionRunning =
            false;


        if (button) {

            button.disabled =
                false;

            button.textContent =
                "RUN POLARGUARD MISSION";
        }
    }
}


// ============================================================
// DECISION PANEL
// ============================================================

function renderMissionDecision(
    result
) {

    let panel =
        getElement(
            "polarMissionDecision"
        );


    if (!panel) {

        panel =
            document.createElement(
                "div"
            );

        panel.id =
            "polarMissionDecision";

        document.body.appendChild(
            panel
        );
    }


    const summary =
        result.decision_summary ||
        {};


    const navigation =
        result.navigation ||
        {};


    const hazards =
        result.hazards ||
        {};


    const recommendedHazard =
        hazards
            .recommended_route ||
        {};


    const recommendedAvailable =
        Boolean(
            summary
                .recommended_route_available
        );


    const alternativeAvailable =
        Boolean(
            summary
                .alternative_route_available
        );


    let alertHtml = "";


    const routeAlerts =
        Array.isArray(
            recommendedHazard.alerts
        )
            ? recommendedHazard.alerts
            : [];


    if (
        routeAlerts.length > 0
    ) {

        alertHtml = `

            <div class="pg-hazard-box">

                <b>
                    Route Alerts
                </b>

                <br>

                ${routeAlerts
                    .map(
                        item =>
                            `• ${escapeHtml(
                                typeof item === "string"
                                    ? item
                                    : item.message ??
                                      JSON.stringify(
                                          item
                                      )
                            )}`
                    )
                    .join(
                        "<br>"
                    )}

            </div>
        `;
    }


    panel.innerHTML = `

        <div class="pg-decision-title">
            Mission Decision
        </div>


        <div class="pg-decision-row">

            <span>
                Horizon
            </span>

            <span>
                +${
                    escapeHtml(
                        summary.routing_horizon ||
                        result.routing_horizon ||
                        "—"
                    )
                }
            </span>

        </div>


        <div class="pg-decision-row">

            <span>
                Vessel
            </span>

            <span>
                ${
                    escapeHtml(
                        summary.vessel_profile ||
                        "—"
                    )
                }
            </span>

        </div>


        <div class="pg-decision-row">

            <span>
                Recommended Route
            </span>

            <span style="
                color:${
                    recommendedAvailable
                        ? "#4ade80"
                        : "#f87171"
                };
            ">

                ${
                    recommendedAvailable
                        ? "AVAILABLE"
                        : "UNAVAILABLE"
                }

            </span>

        </div>


        <div class="pg-decision-row">

            <span>
                Recommended Distance
            </span>

            <span>
                ${
                    formatDistance(
                        summary
                            .recommended_distance_km
                    )
                }
            </span>

        </div>


        <div class="pg-decision-row">

            <span>
                Alternative Route
            </span>

            <span>
                ${
                    alternativeAvailable
                        ? "AVAILABLE"
                        : "NOT AVAILABLE"
                }
            </span>

        </div>


        <div class="pg-decision-row">

            <span>
                Alternative Distance
            </span>

            <span>
                ${
                    formatDistance(
                        summary
                            .alternative_distance_km
                    )
                }
            </span>

        </div>


        <div class="pg-decision-row">

            <span>
                Route Overlap
            </span>

            <span>
                ${
                    formatPercent(
                        summary
                            .route_overlap_percent
                    )
                }
            </span>

        </div>


        <div class="pg-decision-row">

            <span>
                Recommendation
            </span>

            <span>
                ${
                    escapeHtml(
                        navigation
                            .recommendation ||
                        "—"
                    )
                }
            </span>

        </div>


        ${alertHtml}
    `;


    updateExistingSummary(
        result
    );
}


// ============================================================
// UPDATE EXISTING HTML SUMMARY
// ============================================================

function updateExistingSummary(
    result
) {

    const summary =
        result.decision_summary ||
        {};


    setText(

        "recommendedDistance",

        formatDistance(
            summary
                .recommended_distance_km
        )
    );


    setText(

        "alternativeDistance",

        formatDistance(
            summary
                .alternative_distance_km
        )
    );


    setText(

        "cmpRecDistance",

        formatDistance(
            summary
                .recommended_distance_km
        )
    );


    setText(

        "cmpAltDistance",

        formatDistance(
            summary
                .alternative_distance_km
        )
    );


    setText(

        "routeOverlap",

        formatPercent(
            summary
                .route_overlap_percent
        )
    );


    setText(

        "summaryHorizon",

        summary.routing_horizon
            ? `+${summary.routing_horizon}`
            : "—"
    );
}


// ============================================================
// ROUTE / HAZARD ALERTS
// ============================================================

function renderMissionAlerts(
    result
) {

    const hazards =
        result.hazards ||
        {};


    const recommended =
        hazards
            .recommended_route ||
        {};


    const alternative =
        hazards
            .alternative_route ||
        {};


    const recommendedAlerts =
        Array.isArray(
            recommended.alerts
        )
            ? recommended.alerts
            : [];


    const alternativeAlerts =
        Array.isArray(
            alternative.alerts
        )
            ? alternative.alerts
            : [];


    recommendedAlerts.forEach(

        item => {

            const message =
                typeof item ===
                    "string"

                    ? item

                    : item.message ||
                      JSON.stringify(
                          item
                      );


            addAlert(
                "warning",
                `Recommended route: ${message}`
            );
        }
    );


    alternativeAlerts.forEach(

        item => {

            const message =
                typeof item ===
                    "string"

                    ? item

                    : item.message ||
                      JSON.stringify(
                          item
                      );


            addAlert(
                "info",
                `Alternative route: ${message}`
            );
        }
    );


    const gridSummary =
        hazards
            .grid_summary;


    if (gridSummary) {

        console.log(
            "Hazard grid summary:",
            gridSummary
        );
    }
}


// ============================================================
// EXPORT MISSION JSON
// ============================================================

function exportMissionJson() {

    if (
        !state.missionResult
    ) {

        addAlert(
            "warning",
            "Run a mission before exporting."
        );

        return;
    }


    const blob =
        new Blob(

            [
                JSON.stringify(
                    state.missionResult,
                    null,
                    2
                )
            ],

            {
                type:
                    "application/json"
            }
        );


    const url =
        URL.createObjectURL(
            blob
        );


    const anchor =
        document.createElement(
            "a"
        );


    const date =
        state
            .missionResult
            .initialization_date ||
        "mission";


    anchor.href =
        url;


    anchor.download =
        `polarguard_mission_${date}.json`;


    document.body.appendChild(
        anchor
    );


    anchor.click();


    anchor.remove();


    URL.revokeObjectURL(
        url
    );


    addAlert(
        "safe",
        "Mission JSON exported."
    );
}


// ============================================================
// GEOJSON EXPORT BUTTONS
// ============================================================

function exportGeoJson(
    routeType
) {

    const data =
        routeType ===
            "recommended"

            ? state.recommendedData

            : state.alternativeData;


    if (!data) {

        addAlert(

            "warning",

            `No ${routeType} route available to export.`
        );

        return;
    }


    const blob =
        new Blob(

            [
                JSON.stringify(
                    data,
                    null,
                    2
                )
            ],

            {
                type:
                    "application/geo+json"
            }
        );


    const url =
        URL.createObjectURL(
            blob
        );


    const anchor =
        document.createElement(
            "a"
        );


    anchor.href =
        url;


    anchor.download =
        `polarguard_${routeType}_route.geojson`;


    document.body.appendChild(
        anchor
    );


    anchor.click();


    anchor.remove();


    URL.revokeObjectURL(
        url
    );
}


// ============================================================
// OPTIONAL EXPORT CONTROLS
// ============================================================

function addRouteExportControls() {

    if (
        getElement(
            "pgRouteExportControls"
        )
    ) {

        return;
    }


    const container =
        document.createElement(
            "div"
        );


    container.id =
        "pgRouteExportControls";


    container.style.cssText = `

        position:
            fixed;

        right:
            18px;

        bottom:
            18px;

        z-index:
            900;

        display:
            flex;

        gap:
            6px;
    `;


    container.innerHTML = `

        <button
            id="exportRecommendedBtn"
            style="
                padding:7px 9px;
                border-radius:7px;
                border:1px solid rgba(148,163,184,.25);
                background:rgba(7,17,31,.92);
                color:#7CFC00;
                cursor:pointer;
                font-size:10px;
            "
        >
            Export Recommended
        </button>


        <button
            id="exportAlternativeBtn"
            style="
                padding:7px 9px;
                border-radius:7px;
                border:1px solid rgba(148,163,184,.25);
                background:rgba(7,17,31,.92);
                color:#1e90ff;
                cursor:pointer;
                font-size:10px;
            "
        >
            Export Alternative
        </button>
    `;


    document.body.appendChild(
        container
    );


    getElement(
        "exportRecommendedBtn"
    )?.addEventListener(

        "click",

        () =>
            exportGeoJson(
                "recommended"
            )
    );


    getElement(
        "exportAlternativeBtn"
    )?.addEventListener(

        "click",

        () =>
            exportGeoJson(
                "alternative"
            )
    );
}


// ============================================================
// EXISTING HORIZON BUTTON EVENTS
// ============================================================

document
    .querySelectorAll(
        ".horizon-btn"
    )
    .forEach(

        button => {

            button.addEventListener(

                "click",

                () => {

                    const horizon =
                        button
                            .dataset
                            .horizon;


                    changeHorizon(
                        horizon
                    );


                    if (
                        horizon !==
                            "current" &&
                        getElement(
                            "missionHorizon"
                        )
                    ) {

                        getElement(
                            "missionHorizon"
                        ).value =
                            horizon;
                    }
                }
            );
        }
    );


// ============================================================
// API BUTTON
// ============================================================

const connectApiBtn =
    getElement(
        "connectApiBtn"
    );


if (
    connectApiBtn
) {

    connectApiBtn.addEventListener(
        "click",
        checkApi
    );
}


// ============================================================
// MANUAL RECOMMENDED ROUTE UPLOAD
// ============================================================

const recommendedFile =
    getElement(
        "recommendedFile"
    );


if (
    recommendedFile
) {

    recommendedFile
        .addEventListener(

            "change",

            async event => {

                const file =
                    event
                        .target
                        .files[0];


                if (!file) {

                    return;
                }


                try {

                    await loadGeoJsonFile(

                        file,

                        "recommended"
                    );
                }

                catch (error) {

                    addAlert(

                        "critical",

                        `Recommended route load failed: ${error.message}`
                    );
                }
            }
        );
}


// ============================================================
// MANUAL ALTERNATIVE ROUTE UPLOAD
// ============================================================

const alternativeFile =
    getElement(
        "alternativeFile"
    );


if (
    alternativeFile
) {

    alternativeFile
        .addEventListener(

            "change",

            async event => {

                const file =
                    event
                        .target
                        .files[0];


                if (!file) {

                    return;
                }


                try {

                    await loadGeoJsonFile(

                        file,

                        "alternative"
                    );
                }

                catch (error) {

                    addAlert(

                        "critical",

                        `Alternative route load failed: ${error.message}`
                    );
                }
            }
        );
}


// ============================================================
// EXISTING BUTTONS
// ============================================================

const clearRoutesBtn =
    getElement(
        "clearRoutesBtn"
    );


if (
    clearRoutesBtn
) {

    clearRoutesBtn.addEventListener(
        "click",
        clearRoutes
    );
}


const resetViewBtn =
    getElement(
        "resetViewBtn"
    );


if (
    resetViewBtn
) {

    resetViewBtn.addEventListener(
        "click",
        resetAntarcticView
    );
}


const fitRoutesBtn =
    getElement(
        "fitRoutesBtn"
    );


if (
    fitRoutesBtn
) {

    fitRoutesBtn.addEventListener(
        "click",
        fitRoutes
    );
}


// ============================================================
// EXISTING LAYER TOGGLES
// ============================================================

const showRecommended =
    getElement(
        "showRecommended"
    );


if (
    showRecommended
) {

    showRecommended.addEventListener(
        "change",
        refreshVisibility
    );
}


const showAlternative =
    getElement(
        "showAlternative"
    );


if (
    showAlternative
) {

    showAlternative.addEventListener(
        "change",
        refreshVisibility
    );
}


const showIceberg =
    getElement(
        "showIceberg"
    );


if (
    showIceberg
) {

    showIceberg.addEventListener(
        "change",
        refreshVisibility
    );
}


// ============================================================
// KEYBOARD SHORTCUTS
// ============================================================

document.addEventListener(

    "keydown",

    event => {

        if (
            event.target &&
            (
                event.target.tagName ===
                    "INPUT" ||
                event.target.tagName ===
                    "SELECT" ||
                event.target.tagName ===
                    "TEXTAREA"
            )
        ) {

            return;
        }


        if (
            event.key === "1"
        ) {

            changeHorizon(
                "current"
            );
        }


        if (
            event.key === "2"
        ) {

            changeHorizon(
                "24h"
            );
        }


        if (
            event.key === "3"
        ) {

            changeHorizon(
                "48h"
            );
        }


        if (
            event.key === "4"
        ) {

            changeHorizon(
                "72h"
            );
        }


        if (
            event.key.toLowerCase() ===
                "i"
        ) {

            focusIceberg();
        }


        if (
            event.key.toLowerCase() ===
                "r"
        ) {

            fitRoutes();
        }
    }
);


// ============================================================
// INITIAL STARTUP
// ============================================================

async function startPolarGuard() {

    addPolarGuardLegend();

    createMissionControlPanel();

    addRouteExportControls();


    const online =
        await checkApi();


    if (!online) {

        return;
    }


    await loadRealSeaIce();
}


startPolarGuard();