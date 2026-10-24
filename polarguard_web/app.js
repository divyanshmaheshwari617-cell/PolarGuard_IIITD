const API_BASE =
    "http://127.0.0.1:8000";


// ============================================================
// STATE
// ============================================================

const state = {

    apiOnline:
        false,

    currentPage:
        "dashboard",

    seaIce:
        null,

    iceberg:
        null,

    mission:
        null,

    horizon:
        "current",

    viewers: {},

    layers: {

        seaIce: true,
        uncertainty: true,
        iceberg: true,
        routes: true
    }
};


// ============================================================
// DOM HELPERS
// ============================================================

function el(id) {

    return document.getElementById(
        id
    );
}


function numberValue(
    id,
    fallback = null
) {

    const element =
        el(id);

    if (!element) {

        return fallback;
    }

    const value =
        Number(
            element.value
        );

    return Number.isFinite(value)
        ? value
        : fallback;
}


function textValue(
    id,
    fallback = ""
) {

    const element =
        el(id);

    return element
        ? element.value
        : fallback;
}


function setText(
    id,
    text
) {

    const element =
        el(id);

    if (element) {

        element.textContent =
            text ?? "—";
    }
}


function km(value) {

    const number =
        Number(
            value
        );

    return Number.isFinite(number)
        ? `${number.toFixed(1)} km`
        : "—";
}


function percent(value) {

    const number =
        Number(
            value
        );

    return Number.isFinite(number)
        ? `${number.toFixed(1)}%`
        : "—";
}


// ============================================================
// TOAST
// ============================================================

function toast(
    message,
    type = "info"
) {

    const container =
        el(
            "toastContainer"
        );

    const item =
        document.createElement(
            "div"
        );

    item.className =
        `toast ${type}`;

    item.textContent =
        message;

    container.appendChild(
        item
    );

    setTimeout(
        () => {

            item.remove();

        },
        4000
    );
}


// ============================================================
// PAGE NAVIGATION
// ============================================================

const pageMeta = {

    dashboard: {

        title:
            "Mission Dashboard",

        subtitle:
            "Antarctic sea-ice, iceberg and navigation decision support"
    },

    seaIce: {

        title:
            "Sea-Ice Intelligence",

        subtitle:
            "Current conditions, 24/48/72h forecasts and uncertainty"
    },

    iceberg: {

        title:
            "Iceberg Trajectory",

        subtitle:
            "Environment-aware Antarctic iceberg displacement forecasting"
    },

    risk: {

        title:
            "Risk & Hazard Intelligence",

        subtitle:
            "Sea ice, iceberg proximity and uncertainty-aware decision support"
    },

    routing: {

        title:
            "Safe Route Planning",

        subtitle:
            "Vessel-aware A* navigation through forecast hazards"
    },

    mission: {

        title:
            "Integrated Mission",

        subtitle:
            "Complete PolarGuard end-to-end forecast and navigation pipeline"
    },

    operations: {

        title:
            "3D Operations",

        subtitle:
            "Synchronized Antarctic operational visualization"
    }
};


function openPage(
    page
) {

    state.currentPage =
        page;


    document
        .querySelectorAll(
            ".page"
        )
        .forEach(

            section => {

                section.classList.remove(
                    "active"
                );
            }
        );


    el(
        `page-${page}`
    )?.classList.add(
        "active"
    );


    document
        .querySelectorAll(
            ".nav-btn"
        )
        .forEach(

            button => {

                button.classList.toggle(

                    "active",

                    button.dataset.page ===
                        page
                );
            }
        );


    setText(
        "pageTitle",
        pageMeta[page]?.title ||
        "PolarGuard"
    );


    setText(
        "pageSubtitle",
        pageMeta[page]?.subtitle ||
        ""
    );


    if (
        page ===
        "operations"
    ) {

        setTimeout(
            ensureOperationsViewer,
            100
        );
    }


    if (
        page ===
        "seaIce"
    ) {

        setTimeout(
            ensureSeaIceViewer,
            100
        );
    }


    if (
        page ===
        "iceberg"
    ) {

        setTimeout(
            ensureIcebergViewer,
            100
        );
    }


    if (
        page ===
        "routing"
    ) {

        setTimeout(
            ensureRoutingViewer,
            100
        );
    }


    if (
        page ===
        "mission"
    ) {

        setTimeout(
            ensureMissionViewer,
            100
        );
    }
}


// ============================================================
// BACKEND
// ============================================================

async function apiFetch(
    url,
    options = {}
) {

    const response =
        await fetch(
            `${API_BASE}${url}`,
            options
        );


    let data = null;


    try {

        data =
            await response.json();
    }

    catch {

        data = null;
    }


    if (
        !response.ok
    ) {

        throw new Error(

            data?.detail ||
            `HTTP ${response.status}`
        );
    }


    return data;
}


async function checkApi() {

    try {

        const health =
            await apiFetch(
                "/health"
            );


        state.apiOnline =
            true;


        el(
            "apiDot"
        ).className =
            "status-dot online";


        setText(
            "apiStatus",
            "API Online"
        );


        setText(
            "dashApiStatus",
            "Connected"
        );


        toast(
            "PolarGuard backend connected.",
            "success"
        );


        return health;
    }

    catch (error) {

        state.apiOnline =
            false;


        el(
            "apiDot"
        ).className =
            "status-dot offline";


        setText(
            "apiStatus",
            "API Offline"
        );


        setText(
            "dashApiStatus",
            "Offline"
        );


        toast(
            `Backend unavailable: ${error.message}`,
            "error"
        );


        return null;
    }
}


// ============================================================
// CESIUM VIEWER FACTORY
// ============================================================

function createViewer(
    containerId
) {

    const viewer =
        new Cesium.Viewer(
            containerId,
            {

                animation:
                    false,

                timeline:
                    false,

                baseLayerPicker:
                    false,

                geocoder:
                    false,

                homeButton:
                    false,

                navigationHelpButton:
                    false,

                sceneModePicker:
                    false,

                fullscreenButton:
                    false,

                infoBox:
                    true,

                selectionIndicator:
                    true,

                terrainProvider:
                    new Cesium
                        .EllipsoidTerrainProvider(),

                imageryProvider:
                    new Cesium
                        .OpenStreetMapImageryProvider({

                            url:
                                "https://tile.openstreetmap.org/"
                        })
            }
        );


    viewer.scene.globe.enableLighting =
        true;


    viewer.scene.backgroundColor =
        Cesium.Color
            .fromCssColorString(
                "#020817"
            );


    viewer.camera.setView({

        destination:
            Cesium.Cartesian3
                .fromDegrees(
                    0,
                    -86,
                    5100000
                ),

        orientation: {

            heading:
                0,

            pitch:
                Cesium.Math
                    .toRadians(
                        -90
                    ),

            roll:
                0
        }
    });


    return viewer;
}


// ============================================================
// VIEWERS
// ============================================================

function ensureSeaIceViewer() {

    if (
        state.viewers.seaIce
    ) {

        state.viewers
            .seaIce
            .resize();

        return state.viewers
            .seaIce;
    }


    state.viewers.seaIce =
        createViewer(
            "seaIceMap"
        );


    return state.viewers
        .seaIce;
}


function ensureIcebergViewer() {

    if (
        state.viewers.iceberg
    ) {

        state.viewers
            .iceberg
            .resize();

        return state.viewers
            .iceberg;
    }


    state.viewers.iceberg =
        createViewer(
            "icebergMap"
        );


    return state.viewers
        .iceberg;
}


function ensureRoutingViewer() {

    if (
        state.viewers.routing
    ) {

        state.viewers
            .routing
            .resize();

        return state.viewers
            .routing;
    }


    state.viewers.routing =
        createViewer(
            "routingMap"
        );


    return state.viewers
        .routing;
}


function ensureMissionViewer() {

    if (
        state.viewers.mission
    ) {

        state.viewers
            .mission
            .resize();

        return state.viewers
            .mission;
    }


    state.viewers.mission =
        createViewer(
            "missionMap"
        );


    return state.viewers
        .mission;
}


function ensureOperationsViewer() {

    if (
        state.viewers.operations
    ) {

        state.viewers
            .operations
            .resize();


        renderOperations();

        return state.viewers
            .operations;
    }


    state.viewers.operations =
        createViewer(
            "operationsCesium"
        );


    renderOperations();


    return state.viewers
        .operations;
}


// ============================================================
// COLORS
// ============================================================

function sicColor(
    value
) {

    if (
        value < 0.15
    ) {

        return Cesium.Color
            .fromCssColorString(
                "#bfdbfe"
            )
            .withAlpha(
                0.35
            );
    }


    if (
        value < 0.40
    ) {

        return Cesium.Color
            .fromCssColorString(
                "#60a5fa"
            )
            .withAlpha(
                0.43
            );
    }


    if (
        value < 0.70
    ) {

        return Cesium.Color
            .fromCssColorString(
                "#2563eb"
            )
            .withAlpha(
                0.52
            );
    }


    return Cesium.Color
        .fromCssColorString(
            "#1e3a8a"
        )
        .withAlpha(
            0.60
        );
}


function uncertaintyColor(
    value
) {

    if (
        value < .02
    ) {

        return Cesium.Color.GOLD
            .withAlpha(
                .08
            );
    }


    if (
        value < .04
    ) {

        return Cesium.Color.ORANGE
            .withAlpha(
                .11
            );
    }


    return Cesium.Color.RED
        .withAlpha(
            .14
        );
}


// ============================================================
// CLEAR VIEWER
// ============================================================

function clearViewer(
    viewer
) {

    if (!viewer) {

        return;
    }

    viewer.entities.removeAll();
}


// ============================================================
// SEA ICE RENDERER
// ============================================================

function renderSeaIceLayer(
    viewer,
    data,
    horizon,
    showUncertainty = true
) {

    if (
        !viewer ||
        !data
    ) {

        return;
    }


    clearViewer(
        viewer
    );


    const horizonData =
        data.horizons?.[
            horizon
        ];


    if (!horizonData) {

        return;
    }


    const cells =
        horizonData
            .sic_cells ||
        [];


    let meanSic =
        0;


    let sicCount =
        0;


    cells.forEach(

        cell => {

            const lat =
                Number(
                    cell.latitude
                );

            const lon =
                Number(
                    cell.longitude
                );

            const value =
                Number(
                    cell.value
                );


            if (
                !Number.isFinite(lat) ||
                !Number.isFinite(lon) ||
                !Number.isFinite(value)
            ) {

                return;
            }


            meanSic +=
                value;

            sicCount +=
                1;


            viewer.entities.add({

                position:
                    Cesium.Cartesian3
                        .fromDegrees(
                            lon,
                            lat,
                            1200
                        ),

                ellipse: {

                    semiMajorAxis:
                        36000,

                    semiMinorAxis:
                        36000,

                    material:
                        sicColor(
                            value
                        ),

                    height:
                        1100,

                    outline:
                        false
                }
            });
        }
    );


    if (
        showUncertainty &&
        horizon !==
            "current"
    ) {

        const uncertainty =
            horizonData
                .uncertainty_cells ||
            [];


        const stride =
            Math.max(
                1,
                Math.ceil(
                    uncertainty.length /
                    700
                )
            );


        for (
            let i = 0;
            i < uncertainty.length;
            i += stride
        ) {

            const cell =
                uncertainty[i];


            const lat =
                Number(
                    cell.latitude
                );

            const lon =
                Number(
                    cell.longitude
                );

            const value =
                Number(
                    cell.value
                );


            if (
                !Number.isFinite(lat) ||
                !Number.isFinite(lon) ||
                !Number.isFinite(value)
            ) {

                continue;
            }


            viewer.entities.add({

                position:
                    Cesium.Cartesian3
                        .fromDegrees(
                            lon,
                            lat,
                            2200
                        ),

                ellipse: {

                    semiMajorAxis:
                        25000,

                    semiMinorAxis:
                        25000,

                    material:
                        uncertaintyColor(
                            value
                        ),

                    height:
                        2000
                }
            });
        }
    }


    return {

        count:
            sicCount,

        mean:
            sicCount > 0
                ? meanSic /
                  sicCount
                : null
    };
}


// ============================================================
// SEA ICE MODULE
// ============================================================

async function runSeaIce() {

    try {

        toast(
            "Generating sea-ice forecast..."
        );


        const date =
            textValue(
                "seaIceDate",
                "2025-12-28"
            );


        const step =
            Number(
                textValue(
                    "seaIceSampleStep",
                    "6"
                )
            );


        const data =
            await apiFetch(

                `/visualization/sea-ice` +
                `?date=${encodeURIComponent(date)}` +
                `&sample_step=${step}`
            );


        state.seaIce =
            data;


        state.horizon =
            "current";


        document
            .querySelectorAll(
                ".forecast-btn"
            )
            .forEach(

                button => {

                    button.classList.toggle(

                        "active",

                        button.dataset.horizon ===
                            "current"
                    );
                }
            );


        renderSeaIceModule(
            "current"
        );


        toast(
            "Sea-ice forecast generated.",
            "success"
        );
    }

    catch (error) {

        toast(
            `Sea-ice forecast failed: ${error.message}`,
            "error"
        );
    }
}


function renderSeaIceModule(
    horizon
) {

    if (
        !state.seaIce
    ) {

        return;
    }


    state.horizon =
        horizon;


    const viewer =
        ensureSeaIceViewer();


    const stats =
        renderSeaIceLayer(

            viewer,
            state.seaIce,
            horizon,
            true
        );


    const horizonData =
        state
            .seaIce
            .horizons?.[
                horizon
            ];


    setText(

        "sicCurrentHorizon",

        horizon ===
            "current"
            ? "Current"
            : `+${horizon}`
    );


    setText(

        "sicCellCount",

        stats?.count ??
        "—"
    );


    setText(

        "sicMean",

        Number.isFinite(
            stats?.mean
        )
            ? `${(
                stats.mean * 100
            ).toFixed(1)}%`
            : "—"
    );


    const uncCells =
        horizonData
            ?.uncertainty_cells ||
        [];


    if (
        uncCells.length
    ) {

        const values =
            uncCells
                .map(
                    item =>
                        Number(
                            item.value
                        )
                )
                .filter(
                    Number.isFinite
                );


        const mean =
            values.reduce(
                (a,b) =>
                    a+b,
                0
            ) /
            values.length;


        setText(

            "sicUncertainty",

            `${(
                mean * 100
            ).toFixed(2)} pp`
        );
    }

    else {

        setText(
            "sicUncertainty",
            "Observation"
        );
    }
}


// ============================================================
// ICEBERG REQUEST
// ============================================================

function icebergRequest(
    prefix = "ib"
) {

    const mission =
        prefix ===
        "m";


    const id =
        key => {

            const table = {

                date:
                    mission
                        ? "missionDate"
                        : "icebergDate",

                lat3:
                    mission
                        ? "mLat3"
                        : "ibLat3",

                lon3:
                    mission
                        ? "mLon3"
                        : "ibLon3",

                lat2:
                    mission
                        ? "mLat2"
                        : "ibLat2",

                lon2:
                    mission
                        ? "mLon2"
                        : "ibLon2",

                lat1:
                    mission
                        ? "mLat1"
                        : "ibLat1",

                lon1:
                    mission
                        ? "mLon1"
                        : "ibLon1",

                lat0:
                    mission
                        ? "mLat0"
                        : "ibLat0",

                lon0:
                    mission
                        ? "mLon0"
                        : "ibLon0",

                windU:
                    mission
                        ? "mWindU"
                        : "ibWindU",

                windV:
                    mission
                        ? "mWindV"
                        : "ibWindV",

                oceanU:
                    mission
                        ? "mOceanU"
                        : "ibOceanU",

                oceanV:
                    mission
                        ? "mOceanV"
                        : "ibOceanV"
            };


            return table[key];
        };


    return {

        lat_tm3:
            numberValue(
                id("lat3")
            ),

        lon_tm3:
            numberValue(
                id("lon3")
            ),

        lat_tm2:
            numberValue(
                id("lat2")
            ),

        lon_tm2:
            numberValue(
                id("lon2")
            ),

        lat_tm1:
            numberValue(
                id("lat1")
            ),

        lon_tm1:
            numberValue(
                id("lon1")
            ),

        current_latitude:
            numberValue(
                id("lat0")
            ),

        current_longitude:
            numberValue(
                id("lon0")
            ),

        date:
            textValue(
                id("date")
            ),

        wind_u10:
            numberValue(
                id("windU")
            ),

        wind_v10:
            numberValue(
                id("windV")
            ),

        ocean_uo:
            numberValue(
                id("oceanU")
            ),

        ocean_vo:
            numberValue(
                id("oceanV")
            )
    };
}


// ============================================================
// ICEBERG MODULE
// ============================================================

async function runIceberg() {

    try {

        toast(
            "Predicting iceberg trajectory..."
        );


        const payload =
            icebergRequest();


        const result =
            await apiFetch(
                "/iceberg",
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


        state.iceberg =
            result;


        renderIcebergModule();


        toast(
            "Iceberg trajectory generated.",
            "success"
        );
    }

    catch (error) {

        toast(
            `Iceberg prediction failed: ${error.message}`,
            "error"
        );
    }
}


function getIcebergForecast(
    result
) {

    return result
        ?.iceberg
        ?.forecast ||
        result
        ?.forecast ||
        {};
}


function renderIcebergModule() {

    const result =
        state.iceberg;


    if (!result) {

        return;
    }


    const forecast =
        getIcebergForecast(
            result
        );


    [
        "24h",
        "48h",
        "72h"
    ].forEach(

        horizon => {

            const point =
                forecast[
                    horizon
                ];


            if (!point) {

                return;
            }


            setText(

                horizon ===
                    "24h"
                    ? "ib24Result"
                    : horizon ===
                        "48h"
                        ? "ib48Result"
                        : "ib72Result",

                `${Number(
                    point.latitude
                ).toFixed(4)}, ` +
                `${Number(
                    point.longitude
                ).toFixed(4)}`
            );
        }
    );


    const viewer =
        ensureIcebergViewer();


    clearViewer(
        viewer
    );


    renderIcebergTrajectory(

        viewer,
        icebergRequest(),
        forecast
    );
}


// ============================================================
// ICEBERG TRAJECTORY RENDERING
// ============================================================

function renderIcebergTrajectory(
    viewer,
    input,
    forecast
) {

    if (
        !viewer
    ) {

        return;
    }


    const history = [

        {
            label:
                "t-3",

            latitude:
                input.lat_tm3,

            longitude:
                input.lon_tm3
        },

        {
            label:
                "t-2",

            latitude:
                input.lat_tm2,

            longitude:
                input.lon_tm2
        },

        {
            label:
                "t-1",

            latitude:
                input.lat_tm1,

            longitude:
                input.lon_tm1
        },

        {
            label:
                "Current",

            latitude:
                input.current_latitude,

            longitude:
                input.current_longitude
        }
    ];


    const path =
        history.map(

            point =>

                Cesium.Cartesian3
                    .fromDegrees(

                        point.longitude,
                        point.latitude,
                        7000
                    )
        );


    viewer.entities.add({

        polyline: {

            positions:
                path,

            width:
                3,

            material:
                Cesium.Color
                    .LIGHTGRAY
                    .withAlpha(
                        .8
                    )
        }
    });


    history.forEach(

        point => {

            viewer.entities.add({

                position:
                    Cesium.Cartesian3
                        .fromDegrees(

                            point.longitude,
                            point.latitude,
                            9000
                        ),

                point: {

                    pixelSize:
                        point.label ===
                            "Current"
                            ? 14
                            : 8,

                    color:
                        point.label ===
                            "Current"
                            ? Cesium.Color.GOLD
                            : Cesium.Color
                                .LIGHTGRAY,

                    outlineColor:
                        Cesium.Color.WHITE,

                    outlineWidth:
                        2
                },

                label: {

                    text:
                        point.label,

                    font:
                        "11px sans-serif",

                    fillColor:
                        Cesium.Color.WHITE,

                    pixelOffset:
                        new Cesium
                            .Cartesian2(
                                0,
                                -20
                            )
                }
            });
        }
    );


    const forecastPath = [

        Cesium.Cartesian3
            .fromDegrees(

                input.current_longitude,
                input.current_latitude,
                8000
            )
    ];


    const colors = {

        "24h":
            Cesium.Color.LIME,

        "48h":
            Cesium.Color
                .DODGERBLUE,

        "72h":
            Cesium.Color
                .MEDIUMPURPLE
    };


    [
        "24h",
        "48h",
        "72h"
    ].forEach(

        horizon => {

            const point =
                forecast[
                    horizon
                ];


            if (!point) {

                return;
            }


            forecastPath.push(

                Cesium.Cartesian3
                    .fromDegrees(

                        Number(
                            point.longitude
                        ),

                        Number(
                            point.latitude
                        ),

                        9000
                    )
            );


            viewer.entities.add({

                position:
                    Cesium.Cartesian3
                        .fromDegrees(

                            Number(
                                point.longitude
                            ),

                            Number(
                                point.latitude
                            ),

                            10000
                        ),

                point: {

                    pixelSize:
                        15,

                    color:
                        colors[
                            horizon
                        ],

                    outlineColor:
                        Cesium.Color.WHITE,

                    outlineWidth:
                        2
                },

                label: {

                    text:
                        `+${horizon}`,

                    font:
                        "bold 11px sans-serif",

                    fillColor:
                        Cesium.Color.WHITE,

                    outlineColor:
                        Cesium.Color.BLACK,

                    outlineWidth:
                        2,

                    style:
                        Cesium.LabelStyle
                            .FILL_AND_OUTLINE,

                    pixelOffset:
                        new Cesium
                            .Cartesian2(
                                0,
                                -24
                            )
                }
            });
        }
    );


    if (
        forecastPath.length > 1
    ) {

        viewer.entities.add({

            polyline: {

                positions:
                    forecastPath,

                width:
                    5,

                material:
                    Cesium.Color.CYAN
            }
        });
    }


    viewer.camera.flyTo({

        destination:
            Cesium.Cartesian3
                .fromDegrees(

                    input.current_longitude,
                    input.current_latitude,
                    350000
                ),

        duration:
            1
    });
}


// ============================================================
// MISSION REQUEST
// ============================================================

function buildMissionPayload(
    routeSource = "mission"
) {

    const ib =
        icebergRequest(
            "m"
        );


    let startLat =
        numberValue(
            "mStartLat"
        );

    let startLon =
        numberValue(
            "mStartLon"
        );

    let destLat =
        numberValue(
            "mDestLat"
        );

    let destLon =
        numberValue(
            "mDestLon"
        );

    let horizon =
        textValue(
            "missionHorizon",
            "24h"
        );

    let vessel =
        textValue(
            "missionVessel",
            "MEDIUM"
        );

    let safety =
        numberValue(
            "mSafetyRadius",
            10
        );


    if (
        routeSource ===
        "routing"
    ) {

        startLat =
            numberValue(
                "routeStartLat"
            );

        startLon =
            numberValue(
                "routeStartLon"
            );

        destLat =
            numberValue(
                "routeDestLat"
            );

        destLon =
            numberValue(
                "routeDestLon"
            );

        horizon =
            textValue(
                "routeHorizon",
                "24h"
            );

        vessel =
            textValue(
                "routeVessel",
                "MEDIUM"
            );

        safety =
            numberValue(
                "routeSafetyRadius",
                10
            );
    }


    return {

        initialization_date:
            ib.date,

        lat_tm3:
            ib.lat_tm3,

        lon_tm3:
            ib.lon_tm3,

        lat_tm2:
            ib.lat_tm2,

        lon_tm2:
            ib.lon_tm2,

        lat_tm1:
            ib.lat_tm1,

        lon_tm1:
            ib.lon_tm1,

        current_latitude:
            ib.current_latitude,

        current_longitude:
            ib.current_longitude,

        wind_u10:
            ib.wind_u10,

        wind_v10:
            ib.wind_v10,

        ocean_uo:
            ib.ocean_uo,

        ocean_vo:
            ib.ocean_vo,

        routing_horizon:
            horizon,

        start_lat:
            startLat,

        start_lon:
            startLon,

        destination_lat:
            destLat,

        destination_lon:
            destLon,

        vessel_profile:
            vessel,

        safety_radius_km:
            safety,

        sample_step:
            6
    };
}


// ============================================================
// RUN MISSION
// ============================================================

async function runMission(
    source = "mission"
) {

    const status =
        el(
            "missionStatus"
        );


    try {

        if (status) {

            status.textContent =
                "Running sea ice → iceberg → risk → route...";
        }


        toast(
            "Running complete PolarGuard mission..."
        );


        const payload =
            buildMissionPayload(
                source
            );


        const result =
            await apiFetch(
                "/mission",
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


        state.mission =
            result;


        state.seaIce =
            result.sea_ice ||
            state.seaIce;


        renderMissionResult(
            result
        );


        renderRiskResult(
            result
        );


        if (
            source ===
            "routing"
        ) {

            renderRoutingResult(
                result
            );
        }


        if (status) {

            status.textContent =
                "Mission completed.";
        }


        toast(
            "PolarGuard mission completed.",
            "success"
        );
    }

    catch (error) {

        if (status) {

            status.textContent =
                `Mission failed: ${error.message}`;
        }


        toast(
            `Mission failed: ${error.message}`,
            "error"
        );
    }
}


// ============================================================
// MISSION RESULT
// ============================================================

function renderMissionResult(
    result
) {

    const navigation =
        result.navigation ||
        {};


    const summary =
        result.decision_summary ||
        {};


    setText(

        "missionRouteStatus",

        navigation.success
            ? "ROUTE AVAILABLE"
            : "NO ROUTE"
    );


    setText(

        "missionRecommendedDistance",

        km(
            summary
                .recommended_distance_km
        )
    );


    setText(

        "missionAlternativeDistance",

        km(
            summary
                .alternative_distance_km
        )
    );


    setText(

        "missionHazard",

        summary
            .hazard_level ||
        summary
            .risk_level ||
        "Analysed"
    );


    const viewer =
        ensureMissionViewer();


    renderMissionOnViewer(

        viewer,
        result,
        result.routing_horizon ||
        "24h"
    );


    updateOperationsHud(
        result
    );
}


// ============================================================
// RISK RESULT
// ============================================================

function riskNumber(
    obj,
    keys
) {

    for (
        const key
        of keys
    ) {

        const value =
            Number(
                obj?.[key]
            );


        if (
            Number.isFinite(
                value
            )
        ) {

            return value;
        }
    }


    return null;
}


function renderRiskResult(
    result
) {

    const hazards =
        result.hazards ||
        {};


    const grid =
        hazards.grid_summary ||
        {};


    const sic =
        riskNumber(

            grid,

            [
                "max_sea_ice_risk",
                "mean_sea_ice_risk",
                "max_sic_risk"
            ]
        );


    const iceberg =
        riskNumber(

            grid,

            [
                "max_iceberg_risk",
                "mean_iceberg_risk"
            ]
        );


    const uncertainty =
        riskNumber(

            grid,

            [
                "max_uncertainty_risk",
                "mean_uncertainty_risk"
            ]
        );


    updateRiskCard(
        "riskSicValue",
        "riskSicBar",
        sic
    );


    updateRiskCard(
        "riskIcebergValue",
        "riskIcebergBar",
        iceberg
    );


    updateRiskCard(
        "riskUncertaintyValue",
        "riskUncertaintyBar",
        uncertainty
    );


    const values =
        [
            sic,
            iceberg,
            uncertainty
        ].filter(
            Number.isFinite
        );


    const overall =
        values.length
            ? Math.max(
                ...values
            )
            : null;


    if (
        overall !== null
    ) {

        const level =
            overall < .25
                ? "LOW"
                : overall < .50
                    ? "MODERATE"
                    : overall < .75
                        ? "HIGH"
                        : "VERY HIGH";


        setText(
            "overallRiskValue",
            `${(
                overall * 100
            ).toFixed(1)}%`
        );


        setText(
            "overallRiskBadge",
            level
        );
    }


    renderHazardAlerts(
        result
    );
}


function updateRiskCard(
    valueId,
    barId,
    value
) {

    const display =
        Number.isFinite(
            value
        )
            ? `${(
                value * 100
            ).toFixed(1)}%`
            : "—";


    setText(
        valueId,
        display
    );


    const bar =
        el(
            barId
        );


    if (bar) {

        bar.style.width =
            Number.isFinite(
                value
            )
                ? `${Math.min(
                    100,
                    value * 100
                )}%`
                : "0%";
    }
}


// ============================================================
// HAZARD ALERTS
// ============================================================

function renderHazardAlerts(
    result
) {

    const container =
        el(
            "hazardAlerts"
        );


    if (!container) {

        return;
    }


    container.innerHTML =
        "";


    const hazards =
        result.hazards ||
        {};


    const recommended =
        hazards
            .recommended_route ||
        {};


    const alerts =
        recommended.alerts ||
        [];


    if (
        !alerts.length
    ) {

        container.innerHTML = `

            <div class="alert-item safe">
                No major route alert returned by the prototype hazard engine.
            </div>
        `;

        return;
    }


    alerts.forEach(

        item => {

            const message =
                typeof item ===
                    "string"
                    ? item
                    : item.message ||
                      JSON.stringify(
                          item
                      );


            const div =
                document
                    .createElement(
                        "div"
                    );


            div.className =
                "alert-item warning";


            div.textContent =
                message;


            container.appendChild(
                div
            );
        }
    );
}


// ============================================================
// ROUTING
// ============================================================

async function runRouting() {

    await runMission(
        "routing"
    );
}


function renderRoutingResult(
    result
) {

    const nav =
        result.navigation ||
        {};


    const recommended =
        nav
            .recommended_route ||
        {};


    const alternative =
        nav
            .alternative_route ||
        {};


    const summary =
        result.decision_summary ||
        {};


    setText(

        "recommendedDistance",

        km(
            summary
                .recommended_distance_km ||
            recommended
                .distance_km
        )
    );


    setText(

        "alternativeDistance",

        km(
            summary
                .alternative_distance_km ||
            alternative
                .distance_km
        )
    );


    setText(

        "routeOverlap",

        percent(
            summary
                .route_overlap_percent
        )
    );


    const viewer =
        ensureRoutingViewer();


    renderMissionOnViewer(

        viewer,
        result,
        result.routing_horizon ||
        "24h"
    );
}


// ============================================================
// ROUTE GEOJSON
// ============================================================

function addGeoJsonRoute(
    viewer,
    geojson,
    recommended = true
) {

    if (
        !viewer ||
        !geojson?.features?.length
    ) {

        return;
    }


    const feature =
        geojson
            .features[0];


    const coordinates =
        feature
            ?.geometry
            ?.coordinates;


    if (
        !Array.isArray(
            coordinates
        )
    ) {

        return;
    }


    const positions =
        coordinates.map(

            item =>

                Cesium.Cartesian3
                    .fromDegrees(

                        Number(
                            item[0]
                        ),

                        Number(
                            item[1]
                        ),

                        11000
                    )
        );


    viewer.entities.add({

        name:
            recommended
                ? "Recommended Route"
                : "Alternative Route",

        polyline: {

            positions:
                positions,

            width:
                recommended
                    ? 7
                    : 5,

            material:
                recommended

                    ? Cesium.Color.LIME

                    : new Cesium
                        .PolylineDashMaterialProperty({

                            color:
                                Cesium.Color
                                    .DODGERBLUE,

                            dashLength:
                                16
                        })
        }
    });
}


// ============================================================
// MISSION VIEWER
// ============================================================

function renderMissionOnViewer(
    viewer,
    result,
    horizon
) {

    if (
        !viewer ||
        !result
    ) {

        return;
    }


    clearViewer(
        viewer
    );


    const seaIce =
        result.sea_ice;


    if (seaIce) {

        const horizonData =
            seaIce
                .horizons?.[
                    horizon
                ];


        horizonData
            ?.sic_cells
            ?.forEach(

                cell => {

                    const lat =
                        Number(
                            cell.latitude
                        );

                    const lon =
                        Number(
                            cell.longitude
                        );

                    const value =
                        Number(
                            cell.value
                        );


                    if (
                        !Number.isFinite(lat) ||
                        !Number.isFinite(lon) ||
                        !Number.isFinite(value)
                    ) {

                        return;
                    }


                    viewer.entities.add({

                        position:
                            Cesium.Cartesian3
                                .fromDegrees(
                                    lon,
                                    lat,
                                    1000
                                ),

                        ellipse: {

                            semiMajorAxis:
                                34000,

                            semiMinorAxis:
                                34000,

                            material:
                                sicColor(
                                    value
                                ),

                            height:
                                900
                        }
                    });
                }
            );
    }


    const iceberg =
        result.iceberg;


    if (iceberg) {

        const history =
            iceberg.history ||
            [];


        const current =
            iceberg.current;


        const forecast =
            iceberg.forecast ||
            {};


        const path = [];


        history.forEach(

            point => {

                const lat =
                    Number(
                        point.latitude
                    );

                const lon =
                    Number(
                        point.longitude
                    );


                if (
                    !Number.isFinite(lat) ||
                    !Number.isFinite(lon)
                ) {

                    return;
                }


                path.push(

                    Cesium.Cartesian3
                        .fromDegrees(
                            lon,
                            lat,
                            8000
                        )
                );
            }
        );


        if (current) {

            path.push(

                Cesium.Cartesian3
                    .fromDegrees(

                        Number(
                            current.longitude
                        ),

                        Number(
                            current.latitude
                        ),

                        8000
                    )
            );


            viewer.entities.add({

                position:
                    Cesium.Cartesian3
                        .fromDegrees(

                            Number(
                                current.longitude
                            ),

                            Number(
                                current.latitude
                            ),

                            10000
                        ),

                point: {

                    pixelSize:
                        15,

                    color:
                        Cesium.Color.GOLD,

                    outlineColor:
                        Cesium.Color.WHITE,

                    outlineWidth:
                        2
                }
            });
        }


        if (
            path.length > 1
        ) {

            viewer.entities.add({

                polyline: {

                    positions:
                        path,

                    width:
                        3,

                    material:
                        Cesium.Color
                            .LIGHTGRAY
                }
            });
        }


        const f =
            forecast[
                horizon
            ];


        if (f) {

            viewer.entities.add({

                position:
                    Cesium.Cartesian3
                        .fromDegrees(

                            Number(
                                f.longitude
                            ),

                            Number(
                                f.latitude
                            ),

                            11000
                        ),

                point: {

                    pixelSize:
                        17,

                    color:
                        Cesium.Color.CYAN,

                    outlineColor:
                        Cesium.Color.WHITE,

                    outlineWidth:
                        2
                },

                label: {

                    text:
                        `+${horizon}`,

                    font:
                        "bold 12px sans-serif",

                    fillColor:
                        Cesium.Color.WHITE,

                    outlineColor:
                        Cesium.Color.BLACK,

                    outlineWidth:
                        2,

                    style:
                        Cesium.LabelStyle
                            .FILL_AND_OUTLINE,

                    pixelOffset:
                        new Cesium
                            .Cartesian2(
                                0,
                                -25
                            )
                }
            });
        }
    }


    const navigation =
        result.navigation ||
        {};


    const recommended =
        navigation
            .recommended_route;


    const alternative =
        navigation
            .alternative_route;


    if (
        recommended?.geojson
    ) {

        addGeoJsonRoute(
            viewer,
            recommended.geojson,
            true
        );
    }


    if (
        alternative?.geojson
    ) {

        addGeoJsonRoute(
            viewer,
            alternative.geojson,
            false
        );
    }


    if (
        recommended?.geojson
    ) {

        const coords =
            recommended
                .geojson
                .features?.[0]
                ?.geometry
                ?.coordinates;


        if (
            Array.isArray(coords) &&
            coords.length
        ) {

            const center =
                coords[
                    Math.floor(
                        coords.length /
                        2
                    )
                ];


            viewer.camera.flyTo({

                destination:
                    Cesium.Cartesian3
                        .fromDegrees(

                            Number(
                                center[0]
                            ),

                            Number(
                                center[1]
                            ),

                            700000
                        ),

                duration:
                    1
            });
        }
    }
}


// ============================================================
// 3D OPERATIONS
// ============================================================

function renderOperations() {

    const viewer =
        state
            .viewers
            .operations;


    if (!viewer) {

        return;
    }


    clearViewer(
        viewer
    );


    const horizon =
        state.horizon;


    const data =
        state.mission ||
        (
            state.seaIce
                ? {
                    sea_ice:
                        state.seaIce
                }
                : null
        );


    if (!data) {

        return;
    }


    if (
        state.layers.seaIce &&
        data.sea_ice
    ) {

        const horizonData =
            data
                .sea_ice
                .horizons?.[
                    horizon
                ];


        horizonData
            ?.sic_cells
            ?.forEach(

                cell => {

                    const lat =
                        Number(
                            cell.latitude
                        );

                    const lon =
                        Number(
                            cell.longitude
                        );

                    const value =
                        Number(
                            cell.value
                        );


                    if (
                        !Number.isFinite(lat) ||
                        !Number.isFinite(lon) ||
                        !Number.isFinite(value)
                    ) {

                        return;
                    }


                    viewer.entities.add({

                        position:
                            Cesium.Cartesian3
                                .fromDegrees(
                                    lon,
                                    lat,
                                    900
                                ),

                        ellipse: {

                            semiMajorAxis:
                                35000,

                            semiMinorAxis:
                                35000,

                            material:
                                sicColor(
                                    value
                                ),

                            height:
                                800
                        }
                    });
                }
            );
    }


    if (
        state.layers
            .uncertainty &&
        horizon !==
            "current" &&
        data.sea_ice
    ) {

        const cells =
            data
                .sea_ice
                .horizons?.[
                    horizon
                ]
                ?.uncertainty_cells ||
            [];


        const stride =
            Math.max(
                1,
                Math.ceil(
                    cells.length /
                    700
                )
            );


        for (
            let i = 0;
            i < cells.length;
            i += stride
        ) {

            const cell =
                cells[i];


            viewer.entities.add({

                position:
                    Cesium.Cartesian3
                        .fromDegrees(

                            Number(
                                cell.longitude
                            ),

                            Number(
                                cell.latitude
                            ),

                            1600
                        ),

                ellipse: {

                    semiMajorAxis:
                        25000,

                    semiMinorAxis:
                        25000,

                    material:
                        uncertaintyColor(
                            Number(
                                cell.value
                            )
                        ),

                    height:
                        1500
                }
            });
        }
    }


    if (
        state.layers.iceberg &&
        data.iceberg
    ) {

        const iceberg =
            data.iceberg;


        const current =
            iceberg.current;


        const forecast =
            iceberg.forecast ||
            {};


        if (current) {

            viewer.entities.add({

                position:
                    Cesium.Cartesian3
                        .fromDegrees(

                            Number(
                                current.longitude
                            ),

                            Number(
                                current.latitude
                            ),

                            10000
                        ),

                point: {

                    pixelSize:
                        15,

                    color:
                        Cesium.Color.GOLD,

                    outlineColor:
                        Cesium.Color.WHITE,

                    outlineWidth:
                        2
                }
            });
        }


        if (
            horizon !==
                "current" &&
            forecast[horizon]
        ) {

            const point =
                forecast[
                    horizon
                ];


            viewer.entities.add({

                position:
                    Cesium.Cartesian3
                        .fromDegrees(

                            Number(
                                point.longitude
                            ),

                            Number(
                                point.latitude
                            ),

                            12000
                        ),

                point: {

                    pixelSize:
                        18,

                    color:
                        Cesium.Color.CYAN,

                    outlineColor:
                        Cesium.Color.WHITE,

                    outlineWidth:
                        2
                }
            });
        }
    }


    if (
        state.layers.routes &&
        data.navigation
    ) {

        if (
            data.navigation
                .recommended_route
                ?.geojson
        ) {

            addGeoJsonRoute(

                viewer,

                data.navigation
                    .recommended_route
                    .geojson,

                true
            );
        }


        if (
            data.navigation
                .alternative_route
                ?.geojson
        ) {

            addGeoJsonRoute(

                viewer,

                data.navigation
                    .alternative_route
                    .geojson,

                false
            );
        }
    }


    updateOperationsHud(
        data
    );
}


// ============================================================
// OPERATIONS HUD
// ============================================================

function updateOperationsHud(
    data
) {

    setText(

        "hudFrame",

        state.horizon ===
            "current"
            ? "Current"
            : `+${state.horizon}`
    );


    const sicCells =
        data
            ?.sea_ice
            ?.horizons?.[
                state.horizon
            ]
            ?.sic_cells ||
        [];


    setText(

        "hudSic",

        sicCells.length
            ? `${sicCells.length} cells`
            : "—"
    );


    const iceberg =
        data
            ?.iceberg;


    setText(

        "hudIceberg",

        iceberg
            ? "Tracked"
            : "—"
    );


    const route =
        data
            ?.navigation
            ?.recommended_route;


    setText(

        "hudRoute",

        route?.available
            ? km(
                route
                    .distance_km
            )
            : route
                ? "Unavailable"
                : "—"
    );
}


// ============================================================
// EVENT BINDING
// ============================================================

document
    .querySelectorAll(
        ".nav-btn"
    )
    .forEach(

        button => {

            button.addEventListener(

                "click",

                () =>
                    openPage(
                        button.dataset.page
                    )
            );
        }
    );


document
    .querySelectorAll(
        "[data-open-page]"
    )
    .forEach(

        button => {

            button.addEventListener(

                "click",

                () =>
                    openPage(
                        button.dataset.openPage
                    )
            );
        }
    );


el(
    "checkApiBtn"
)?.addEventListener(
    "click",
    checkApi
);


el(
    "runSeaIceBtn"
)?.addEventListener(
    "click",
    runSeaIce
);


el(
    "runIcebergBtn"
)?.addEventListener(
    "click",
    runIceberg
);


el(
    "runMissionBtn"
)?.addEventListener(

    "click",

    () =>
        runMission(
            "mission"
        )
);


el(
    "runRouteBtn"
)?.addEventListener(
    "click",
    runRouting
);


// ============================================================
// SEA ICE HORIZON BUTTONS
// ============================================================

document
    .querySelectorAll(
        ".forecast-btn"
    )
    .forEach(

        button => {

            button.addEventListener(

                "click",

                () => {

                    document
                        .querySelectorAll(
                            ".forecast-btn"
                        )
                        .forEach(

                            item =>
                                item
                                    .classList
                                    .remove(
                                        "active"
                                    )
                        );


                    button
                        .classList
                        .add(
                            "active"
                        );


                    renderSeaIceModule(
                        button.dataset.horizon
                    );
                }
            );
        }
    );


// ============================================================
// OPERATIONS HORIZON
// ============================================================

document
    .querySelectorAll(
        ".ops-horizon"
    )
    .forEach(

        button => {

            button.addEventListener(

                "click",

                () => {

                    state.horizon =
                        button.dataset.horizon;


                    document
                        .querySelectorAll(
                            ".ops-horizon"
                        )
                        .forEach(

                            item =>
                                item
                                    .classList
                                    .remove(
                                        "active"
                                    )
                        );


                    button
                        .classList
                        .add(
                            "active"
                        );


                    renderOperations();
                }
            );
        }
    );


// ============================================================
// LAYER SWITCHES
// ============================================================

el(
    "layerSic"
)?.addEventListener(

    "change",

    event => {

        state.layers.seaIce =
            event.target.checked;

        renderOperations();
    }
);


el(
    "layerUncertainty"
)?.addEventListener(

    "change",

    event => {

        state.layers.uncertainty =
            event.target.checked;

        renderOperations();
    }
);


el(
    "layerIceberg"
)?.addEventListener(

    "change",

    event => {

        state.layers.iceberg =
            event.target.checked;

        renderOperations();
    }
);


el(
    "layerRoutes"
)?.addEventListener(

    "change",

    event => {

        state.layers.routes =
            event.target.checked;

        renderOperations();
    }
);


// ============================================================
// SLIDERS
// ============================================================

el(
    "routeSafetyRadius"
)?.addEventListener(

    "input",

    event => {

        setText(

            "routeSafetyValue",

            `${event.target.value} km`
        );
    }
);


el(
    "mSafetyRadius"
)?.addEventListener(

    "input",

    event => {

        setText(

            "mSafetyValue",

            `${event.target.value} km`
        );
    }
);


// ============================================================
// INITIALIZE
// ============================================================

async function initialize() {

    openPage(
        "dashboard"
    );


    await checkApi();
}


initialize();