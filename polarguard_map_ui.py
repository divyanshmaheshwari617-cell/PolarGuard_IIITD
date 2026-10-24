from __future__ import annotations

import math
from typing import Any, Iterable

import folium
from folium import Element
from folium.plugins import Fullscreen, MeasureControl, MousePosition


# ============================================================
# POLARGUARD MAP V2
# Presentation-only helpers.
# Does NOT change ML / routing / risk calculations.
# ============================================================


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _safe_float(value: Any, default: float = 0.0) -> float:
    return float(value) if _finite(value) else default


def _escape(value: Any) -> str:
    text = str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


# ============================================================
# COLORS
# ============================================================


def sic_color(value: float) -> str:
    value = max(0.0, min(1.0, _safe_float(value)))

    if value < 0.10:
        return "#06253a"
    if value < 0.30:
        return "#075985"
    if value < 0.50:
        return "#0891b2"
    if value < 0.70:
        return "#facc15"
    if value < 0.85:
        return "#fb923c"

    return "#ef4444"


def uncertainty_color(value: float) -> str:
    value = max(0.0, _safe_float(value))

    if value < 0.015:
        return "#22c55e"
    if value < 0.030:
        return "#84cc16"
    if value < 0.050:
        return "#facc15"
    if value < 0.080:
        return "#f97316"

    return "#ef4444"


def risk_color(value: float) -> str:
    value = max(0.0, min(1.0, _safe_float(value)))

    if value < 0.25:
        return "#22c55e"
    if value < 0.50:
        return "#eab308"
    if value < 0.75:
        return "#f97316"

    return "#ef4444"


# ============================================================
# MAP CREATION
# ============================================================


def create_polarguard_map(
    *,
    center_lat: float = -75.0,
    center_lon: float = 0.0,
    zoom_start: int = 3,
) -> folium.Map:

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom_start,
        tiles=None,
        control_scale=True,
        prefer_canvas=True,
        zoom_control=True,
    )

    # Dark tactical basemap
    folium.TileLayer(
        tiles=(
            "https://{s}.basemaps.cartocdn.com/"
            "dark_all/{z}/{x}/{y}{r}.png"
        ),
        attr="© OpenStreetMap © CARTO",
        name="PolarGuard Dark",
        control=True,
        show=True,
        max_zoom=19,
    ).add_to(m)

    # Light satellite/geographic alternative
    folium.TileLayer(
        tiles="OpenStreetMap",
        name="Geographic Reference",
        control=True,
        show=False,
    ).add_to(m)

    Fullscreen(
        position="topleft",
        title="Fullscreen tactical map",
        title_cancel="Exit fullscreen",
        force_separate_button=True,
    ).add_to(m)

    MeasureControl(
        position="topleft",
        primary_length_unit="kilometers",
        secondary_length_unit="meters",
        primary_area_unit="sqkilometers",
    ).add_to(m)

    MousePosition(
        position="bottomleft",
        separator="  |  ",
        prefix="LAT / LON",
        num_digits=4,
    ).add_to(m)

    add_map_css(m)

    return m


# ============================================================
# ADVANCED MAP CSS
# ============================================================


def add_map_css(m: folium.Map) -> None:

    css = """
    <style>

    .leaflet-container {
        background:
            radial-gradient(
                circle at 50% 50%,
                #08263a 0%,
                #03111d 58%,
                #01070c 100%
            ) !important;

        font-family:
            Inter,
            ui-sans-serif,
            system-ui,
            sans-serif !important;
    }

    .leaflet-control-layers,
    .leaflet-bar {
        background:
            rgba(3, 14, 24, 0.92) !important;

        border:
            1px solid rgba(34, 211, 238, 0.18) !important;

        border-radius:
            10px !important;

        box-shadow:
            0 10px 30px rgba(0,0,0,.25) !important;

        color:
            #dff7ff !important;

        backdrop-filter:
            blur(14px);
    }

    .leaflet-control-layers-expanded {
        padding:
            12px 14px !important;

        color:
            #b9d2df !important;
    }

    .leaflet-control-layers label {
        color:
            #b9d2df !important;

        font-size:
            11px !important;
    }

    .leaflet-bar a {
        background:
            rgba(4, 18, 30, .96) !important;

        color:
            #8feeff !important;

        border-bottom:
            1px solid rgba(148,163,184,.10) !important;
    }

    .leaflet-bar a:hover {
        background:
            rgba(8, 36, 56, .98) !important;
    }

    .leaflet-control-attribution {
        background:
            rgba(2, 8, 15, .74) !important;

        color:
            #526d80 !important;

        font-size:
            8px !important;
    }

    .leaflet-control-attribution a {
        color:
            #6e9cb5 !important;
    }

    .leaflet-popup-content-wrapper {
        background:
            rgba(3, 15, 25, .97) !important;

        border:
            1px solid rgba(34, 211, 238, .22);

        border-radius:
            14px !important;

        color:
            #dff7ff !important;

        box-shadow:
            0 18px 50px rgba(0,0,0,.38) !important;
    }

    .leaflet-popup-tip {
        background:
            #06131e !important;
    }

    .leaflet-popup-content {
        margin:
            15px 16px !important;
    }

    .pg-popup-kicker {
        color:
            #5c8298;

        font-size:
            8px;

        font-weight:
            800;

        letter-spacing:
            .12em;

        text-transform:
            uppercase;
    }

    .pg-popup-title {
        margin-top:
            3px;

        color:
            #f0fbff;

        font-size:
            17px;

        font-weight:
            850;
    }

    .pg-popup-grid {
        display:
            grid;

        grid-template-columns:
            1fr 1fr;

        gap:
            8px;

        margin-top:
            12px;
    }

    .pg-popup-stat {
        padding:
            8px;

        border:
            1px solid rgba(148,163,184,.10);

        border-radius:
            8px;

        background:
            rgba(255,255,255,.025);
    }

    .pg-popup-stat span {
        display:
            block;

        color:
            #58788d;

        font-size:
            7px;

        font-weight:
            800;

        letter-spacing:
            .08em;

        text-transform:
            uppercase;
    }

    .pg-popup-stat strong {
        display:
            block;

        margin-top:
            2px;

        color:
            #dff7ff;

        font-size:
            11px;
    }

    /* -------------------------------------------------------
       ICEBERG MARKER
    ------------------------------------------------------- */

    .pg-iceberg-marker {
        position:
            relative;

        width:
            17px;

        height:
            17px;

        transform:
            rotate(45deg);

        border:
            2px solid #e6fbff;

        background:
            linear-gradient(
                135deg,
                #7dd3fc,
                #0284c7
            );

        box-shadow:
            0 0 0 4px rgba(56,189,248,.10),
            0 0 18px rgba(56,189,248,.72);
    }

    .pg-iceberg-marker::after {
        content:
            "";

        position:
            absolute;

        inset:
            4px;

        background:
            rgba(255,255,255,.72);
    }

    .pg-iceberg-label {
        position:
            absolute;

        left:
            19px;

        top:
            -8px;

        min-width:
            max-content;

        transform:
            rotate(-45deg);

        padding:
            4px 7px;

        border:
            1px solid rgba(125,211,252,.24);

        border-radius:
            6px;

        background:
            rgba(2, 12, 21, .90);

        color:
            #dff7ff;

        font-size:
            9px;

        font-weight:
            900;

        letter-spacing:
            .06em;

        box-shadow:
            0 7px 18px rgba(0,0,0,.28);

        pointer-events:
            none;
    }

    /* -------------------------------------------------------
       START / DESTINATION
    ------------------------------------------------------- */

    .pg-route-marker {
        width:
            28px;

        height:
            28px;

        display:
            grid;

        place-items:
            center;

        border:
            2px solid white;

        border-radius:
            50%;

        color:
            #04101a;

        font-size:
            11px;

        font-weight:
            950;

        box-shadow:
            0 0 0 5px rgba(255,255,255,.08),
            0 0 24px rgba(255,255,255,.28);
    }

    .pg-start {
        background:
            #a3e635;
    }

    .pg-destination {
        background:
            #22d3ee;
    }

    /* -------------------------------------------------------
       MAP HUD
    ------------------------------------------------------- */

    .pg-map-hud {
        position:
            absolute;

        top:
            14px;

        left:
            56px;

        z-index:
            999;

        min-width:
            230px;

        padding:
            12px 14px;

        border:
            1px solid rgba(34,211,238,.18);

        border-radius:
            12px;

        background:
            rgba(2, 11, 19, .88);

        backdrop-filter:
            blur(14px);

        box-shadow:
            0 12px 34px rgba(0,0,0,.25);

        pointer-events:
            none;
    }

    .pg-map-hud-kicker {
        color:
            #67e8f9;

        font-size:
            7px;

        font-weight:
            900;

        letter-spacing:
            .14em;
    }

    .pg-map-hud-title {
        margin-top:
            3px;

        color:
            #eefcff;

        font-size:
            13px;

        font-weight:
            850;
    }

    .pg-map-hud-meta {
        margin-top:
            5px;

        color:
            #66879a;

        font-size:
            8px;

        font-weight:
            700;
    }

    .pg-live-dot {
        display:
            inline-block;

        width:
            6px;

        height:
            6px;

        margin-right:
            5px;

        border-radius:
            50%;

        background:
            #a3e635;

        box-shadow:
            0 0 8px rgba(163,230,53,.8);
    }

    /* -------------------------------------------------------
       LEGEND
    ------------------------------------------------------- */

    .pg-map-legend {
        position:
            absolute;

        right:
            12px;

        bottom:
            28px;

        z-index:
            999;

        width:
            184px;

        padding:
            12px;

        border:
            1px solid rgba(148,163,184,.14);

        border-radius:
            12px;

        background:
            rgba(2, 11, 19, .90);

        color:
            #a7c0cf;

        backdrop-filter:
            blur(14px);

        box-shadow:
            0 12px 30px rgba(0,0,0,.24);

        pointer-events:
            none;
    }

    .pg-map-legend-title {
        margin-bottom:
            8px;

        color:
            #e7f9ff;

        font-size:
            9px;

        font-weight:
            900;

        letter-spacing:
            .09em;
    }

    .pg-legend-row {
        display:
            flex;

        align-items:
            center;

        justify-content:
            space-between;

        margin:
            5px 0;

        font-size:
            8px;
    }

    .pg-legend-left {
        display:
            flex;

        align-items:
            center;

        gap:
            6px;
    }

    .pg-legend-swatch {
        width:
            9px;

        height:
            9px;

        border-radius:
            3px;
    }

    </style>
    """

    m.get_root().header.add_child(
        Element(css)
    )


# ============================================================
# MAP HUD
# ============================================================


def add_map_hud(
    m: folium.Map,
    *,
    horizon: str,
    initialization_date: str,
    iceberg_count: int,
    vessel_profile: str,
    uncertainty_available: bool,
) -> None:

    uncertainty_text = (
        "UNCERTAINTY ACTIVE"
        if uncertainty_available
        else "CURRENT OBSERVATION"
    )

    html = f"""
    <div class="pg-map-hud">

        <div class="pg-map-hud-kicker">
            POLARGUARD / TACTICAL VIEW
        </div>

        <div class="pg-map-hud-title">
            Antarctic Navigation Grid
        </div>

        <div class="pg-map-hud-meta">
            <span class="pg-live-dot"></span>
            { _escape(horizon) }
            &nbsp;•&nbsp;
            { _escape(initialization_date) }
            &nbsp;•&nbsp;
            {int(iceberg_count)} ICEBERGS
            <br>
            VESSEL { _escape(vessel_profile) }
            &nbsp;•&nbsp;
            {uncertainty_text}
        </div>

    </div>
    """

    m.get_root().html.add_child(
        Element(html)
    )


# ============================================================
# SIC LEGEND
# ============================================================


def add_navigation_legend(
    m: folium.Map,
    *,
    show_uncertainty: bool = True,
) -> None:

    uncertainty_html = ""

    if show_uncertainty:
        uncertainty_html = """
        <div style="
            margin-top:9px;
            padding-top:8px;
            border-top:1px solid rgba(148,163,184,.10);
        ">
            <div class="pg-legend-row">
                <div class="pg-legend-left">
                    <span
                        class="pg-legend-swatch"
                        style="background:#a855f7;"
                    ></span>
                    Forecast uncertainty
                </div>
            </div>
        </div>
        """

    html = f"""
    <div class="pg-map-legend">

        <div class="pg-map-legend-title">
            NAVIGATION INTELLIGENCE
        </div>

        <div class="pg-legend-row">
            <div class="pg-legend-left">
                <span
                    class="pg-legend-swatch"
                    style="background:#075985;"
                ></span>
                Low SIC
            </div>
            <span>0–30%</span>
        </div>

        <div class="pg-legend-row">
            <div class="pg-legend-left">
                <span
                    class="pg-legend-swatch"
                    style="background:#0891b2;"
                ></span>
                Moderate
            </div>
            <span>30–50%</span>
        </div>

        <div class="pg-legend-row">
            <div class="pg-legend-left">
                <span
                    class="pg-legend-swatch"
                    style="background:#facc15;"
                ></span>
                Elevated
            </div>
            <span>50–70%</span>
        </div>

        <div class="pg-legend-row">
            <div class="pg-legend-left">
                <span
                    class="pg-legend-swatch"
                    style="background:#ef4444;"
                ></span>
                Severe
            </div>
            <span>85–100%</span>
        </div>

        <div style="
            margin-top:9px;
            padding-top:8px;
            border-top:1px solid rgba(148,163,184,.10);
        ">

            <div class="pg-legend-row">
                <div class="pg-legend-left">
                    <span
                        class="pg-legend-swatch"
                        style="
                            background:#38bdf8;
                            transform:rotate(45deg);
                        "
                    ></span>
                    Observed iceberg
                </div>
            </div>

            <div class="pg-legend-row">
                <div class="pg-legend-left">
                    <span
                        class="pg-legend-swatch"
                        style="background:#a3e635;"
                    ></span>
                    Recommended route
                </div>
            </div>

            <div class="pg-legend-row">
                <div class="pg-legend-left">
                    <span
                        class="pg-legend-swatch"
                        style="background:#2563eb;"
                    ></span>
                    Alternative route
                </div>
            </div>

        </div>

        {uncertainty_html}

    </div>
    """

    m.get_root().html.add_child(
        Element(html)
    )


# ============================================================
# CURRENT ICEBERGS WITH VISIBLE IDs
# ============================================================


def add_current_icebergs(
    m: folium.Map,
    icebergs: Iterable[dict[str, Any]],
    *,
    show_labels: bool = True,
) -> int:

    group = folium.FeatureGroup(
        name="Observed Icebergs • BYU/NIC",
        show=True,
    )

    count = 0

    for item in icebergs:

        lat = item.get("latitude")
        lon = item.get("longitude")

        if not (_finite(lat) and _finite(lon)):
            continue

        iceberg_id = str(
            item.get(
                "iceberg_id",
                "UNKNOWN",
            )
        ).upper()

        observation_date = item.get(
            "observation_date",
            "Unknown",
        )

        age_days = item.get(
            "age_days",
            "N/A",
        )

        freshness = item.get(
            "freshness_status",
            "Unknown",
        )

        label_html = (
            f'<div class="pg-iceberg-label">'
            f'{_escape(iceberg_id)}'
            f'</div>'
            if show_labels
            else ""
        )

        icon_html = f"""
        <div class="pg-iceberg-marker">
            {label_html}
        </div>
        """

        popup_html = f"""
        <div style="min-width:220px;">

            <div class="pg-popup-kicker">
                OBSERVED ICEBERG
            </div>

            <div class="pg-popup-title">
                {_escape(iceberg_id)}
            </div>

            <div class="pg-popup-grid">

                <div class="pg-popup-stat">
                    <span>Latitude</span>
                    <strong>
                        {float(lat):.4f}°
                    </strong>
                </div>

                <div class="pg-popup-stat">
                    <span>Longitude</span>
                    <strong>
                        {float(lon):.4f}°
                    </strong>
                </div>

                <div class="pg-popup-stat">
                    <span>Observation</span>
                    <strong>
                        {_escape(observation_date)}
                    </strong>
                </div>

                <div class="pg-popup-stat">
                    <span>Age</span>
                    <strong>
                        {_escape(age_days)} day(s)
                    </strong>
                </div>

            </div>

            <div style="
                margin-top:10px;
                color:#79a2b8;
                font-size:9px;
            ">
                {_escape(freshness)}
            </div>

            <div style="
                margin-top:9px;
                color:#4f7186;
                font-size:8px;
            ">
                BYU / NIC latest available observation
            </div>

        </div>
        """

        folium.Marker(
            location=[
                float(lat),
                float(lon),
            ],
            icon=folium.DivIcon(
                icon_size=(20, 20),
                icon_anchor=(10, 10),
                html=icon_html,
            ),
            tooltip=(
                f"Iceberg {iceberg_id} • "
                f"{observation_date}"
            ),
            popup=folium.Popup(
                popup_html,
                max_width=320,
            ),
        ).add_to(group)

        count += 1

    group.add_to(m)

    return count


# ============================================================
# START / DESTINATION
# ============================================================


def add_route_endpoints(
    m: folium.Map,
    *,
    start_lat: float,
    start_lon: float,
    destination_lat: float,
    destination_lon: float,
) -> None:

    start_icon = """
    <div class="pg-route-marker pg-start">
        S
    </div>
    """

    destination_icon = """
    <div class="pg-route-marker pg-destination">
        D
    </div>
    """

    folium.Marker(
        location=[
            start_lat,
            start_lon,
        ],
        icon=folium.DivIcon(
            icon_size=(30, 30),
            icon_anchor=(15, 15),
            html=start_icon,
        ),
        tooltip="Route Start",
        popup=(
            f"<b>Route Start</b><br>"
            f"{start_lat:.5f}, {start_lon:.5f}"
        ),
    ).add_to(m)

    folium.Marker(
        location=[
            destination_lat,
            destination_lon,
        ],
        icon=folium.DivIcon(
            icon_size=(30, 30),
            icon_anchor=(15, 15),
            html=destination_icon,
        ),
        tooltip="Route Destination",
        popup=(
            f"<b>Route Destination</b><br>"
            f"{destination_lat:.5f}, "
            f"{destination_lon:.5f}"
        ),
    ).add_to(m)


# ============================================================
# ROUTE
# ============================================================


def _route_coordinates(
    route: Any,
) -> list[list[float]]:

    if route is None:
        return []

    if isinstance(route, dict):
        route = route.get(
            "path_coordinates",
            [],
        )

    output = []

    for point in route:

        if isinstance(point, dict):
            lat = point.get("latitude")
            lon = point.get("longitude")

        elif (
            isinstance(point, (list, tuple))
            and len(point) >= 2
        ):
            lat = point[0]
            lon = point[1]

        else:
            continue

        if _finite(lat) and _finite(lon):
            output.append(
                [
                    float(lat),
                    float(lon),
                ]
            )

    return output


def add_recommended_route(
    m: folium.Map,
    route: Any,
    *,
    label: str = "PolarGuard Recommended Route",
) -> int:

    coordinates = _route_coordinates(route)

    if len(coordinates) < 2:
        return 0

    group = folium.FeatureGroup(
        name="Recommended Safe Route",
        show=True,
    )

    # Outer glow
    folium.PolyLine(
        coordinates,
        color="#071019",
        weight=11,
        opacity=0.76,
    ).add_to(group)

    # Lime route
    folium.PolyLine(
        coordinates,
        color="#a3e635",
        weight=6,
        opacity=0.96,
        tooltip=label,
    ).add_to(group)

    # Bright center
    folium.PolyLine(
        coordinates,
        color="#ecfccb",
        weight=1.5,
        opacity=0.85,
    ).add_to(group)

    group.add_to(m)

    return len(coordinates)


def add_alternative_route(
    m: folium.Map,
    route: Any,
) -> int:

    coordinates = _route_coordinates(route)

    if len(coordinates) < 2:
        return 0

    group = folium.FeatureGroup(
        name="Alternative Safe Route",
        show=True,
    )

    folium.PolyLine(
        coordinates,
        color="#2563eb",
        weight=5,
        opacity=0.88,
        dash_array="10, 8",
        tooltip="PolarGuard Alternative Route",
    ).add_to(group)

    group.add_to(m)

    return len(coordinates)


# ============================================================
# TRAJECTORY
# ============================================================


def add_iceberg_trajectory(
    m: folium.Map,
    points: Iterable[dict[str, Any]],
    *,
    iceberg_id: str | None = None,
) -> int:

    valid_points = []

    for point in points:

        lat = point.get("latitude")
        lon = point.get("longitude")

        if _finite(lat) and _finite(lon):
            valid_points.append(point)

    if not valid_points:
        return 0

    group = folium.FeatureGroup(
        name="Iceberg Trajectory",
        show=True,
    )

    coords = [
        [
            float(point["latitude"]),
            float(point["longitude"]),
        ]
        for point in valid_points
    ]

    if len(coords) >= 2:

        folium.PolyLine(
            coords,
            color="#22d3ee",
            weight=4,
            opacity=0.90,
            dash_array="6, 6",
            tooltip=(
                f"{iceberg_id} predicted trajectory"
                if iceberg_id
                else "Predicted iceberg trajectory"
            ),
        ).add_to(group)

    for index, point in enumerate(valid_points):

        stage = str(
            point.get(
                "stage",
                point.get(
                    "horizon",
                    f"T{index}",
                ),
            )
        )

        folium.CircleMarker(
            location=[
                float(point["latitude"]),
                float(point["longitude"]),
            ],
            radius=6 if index else 8,
            color="#e6fbff",
            weight=2,
            fill=True,
            fill_color=(
                "#22d3ee"
                if index
                else "#f59e0b"
            ),
            fill_opacity=1,
            tooltip=(
                f"{iceberg_id + ' • ' if iceberg_id else ''}"
                f"{stage}"
            ),
        ).add_to(group)

    group.add_to(m)

    return len(valid_points)


# ============================================================
# UNCERTAINTY POINT OVERLAY
# ============================================================


def add_uncertainty_cells(
    m: folium.Map,
    cells: Iterable[dict[str, Any]],
    *,
    show: bool = False,
    max_points: int = 4500,
) -> int:
    """
    Lightweight uncertainty visualization.

    Expected cell fields:
        latitude
        longitude
        uncertainty

    IMPORTANT:
    This is display sampling only.
    It does not change the full routing grid.
    """

    group = folium.FeatureGroup(
        name="Forecast Uncertainty",
        show=show,
    )

    valid = []

    for cell in cells:

        lat = cell.get("latitude")
        lon = cell.get("longitude")
        uncertainty = cell.get("uncertainty")

        if (
            _finite(lat)
            and _finite(lon)
            and _finite(uncertainty)
        ):
            valid.append(cell)

    if not valid:
        return 0

    stride = max(
        math.ceil(
            len(valid) / max_points
        ),
        1,
    )

    count = 0

    for cell in valid[::stride]:

        uncertainty = float(
            cell["uncertainty"]
        )

        folium.CircleMarker(
            location=[
                float(cell["latitude"]),
                float(cell["longitude"]),
            ],
            radius=3.2,
            stroke=False,
            fill=True,
            fill_color=uncertainty_color(
                uncertainty
            ),
            fill_opacity=0.43,
            tooltip=(
                "Historical validation RMSE: "
                f"{uncertainty * 100:.2f} SIC pp"
            ),
        ).add_to(group)

        count += 1

    group.add_to(m)

    return count


# ============================================================
# RISK / HAZARD CELLS
# ============================================================


def add_risk_cells(
    m: folium.Map,
    cells: Iterable[dict[str, Any]],
    *,
    show: bool = False,
    max_points: int = 4500,
) -> int:

    group = folium.FeatureGroup(
        name="Combined Navigation Risk",
        show=show,
    )

    valid = []

    for cell in cells:

        lat = cell.get("latitude")
        lon = cell.get("longitude")
        risk = cell.get("combined_risk")

        if (
            _finite(lat)
            and _finite(lon)
            and _finite(risk)
        ):
            valid.append(cell)

    if not valid:
        return 0

    stride = max(
        math.ceil(
            len(valid) / max_points
        ),
        1,
    )

    count = 0

    for cell in valid[::stride]:

        risk = float(
            cell["combined_risk"]
        )

        if risk < 0.25:
            continue

        folium.CircleMarker(
            location=[
                float(cell["latitude"]),
                float(cell["longitude"]),
            ],
            radius=3.4,
            stroke=False,
            fill=True,
            fill_color=risk_color(risk),
            fill_opacity=0.48,
            tooltip=(
                "Combined navigation risk: "
                f"{risk:.2f}"
            ),
        ).add_to(group)

        count += 1

    group.add_to(m)

    return count


# ============================================================
# LAYER CONTROL
# ============================================================


def finalize_polarguard_map(
    m: folium.Map,
) -> folium.Map:

    folium.LayerControl(
        position="topright",
        collapsed=False,
    ).add_to(m)

    return m