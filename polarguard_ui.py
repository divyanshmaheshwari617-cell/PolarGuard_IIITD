from __future__ import annotations

import html
import textwrap

import streamlit as st


# ============================================================
# POLARGUARD ADVANCED STREAMLIT UI
# Presentation-only layer.
# ============================================================


def _safe(value) -> str:
    return html.escape(str(value))


def _prepare_html(content: str) -> str:
    """
    Convert indented multiline HTML into a compact HTML string.

    This prevents Streamlit's Markdown parser from interpreting
    nested HTML indentation as Markdown code blocks.
    """
    content = textwrap.dedent(content).strip()

    # Keep CSS/style blocks intact.
    if content.lstrip().startswith("<style"):
        return content

    # Compact regular HTML so Markdown cannot turn nested
    # indented lines into code blocks.
    return " ".join(
        line.strip()
        for line in content.splitlines()
        if line.strip()
    )


def _render_html(content: str) -> None:
    rendered = _prepare_html(content)

    # st.html renders HTML directly and avoids Markdown parsing.
    if hasattr(st, "html"):
        st.html(rendered)
    else:
        st.markdown(
            rendered,
            unsafe_allow_html=True,
        )


def _render_sidebar_html(content: str) -> None:
    rendered = _prepare_html(content)

    with st.sidebar:
        if hasattr(st, "html"):
            st.html(rendered)
        else:
            st.markdown(
                rendered,
                unsafe_allow_html=True,
            )


# ============================================================
# GLOBAL DESIGN SYSTEM
# ============================================================


def apply_polarguard_theme() -> None:

    _render_html(
        """
        <style>

        :root {
            --pg-bg: #02070d;
            --pg-bg-soft: #04101a;

            --pg-panel: rgba(6,18,30,.94);
            --pg-panel-soft: rgba(8,25,41,.88);

            --pg-border: rgba(148,163,184,.12);
            --pg-border-cyan: rgba(34,211,238,.28);

            --pg-white: #effbff;
            --pg-soft: #b5cad7;
            --pg-muted: #678597;

            --pg-cyan: #22d3ee;
            --pg-cyan-soft: #67e8f9;

            --pg-lime: #a3e635;
            --pg-yellow: #facc15;
            --pg-orange: #fb923c;
            --pg-red: #fb7185;
        }


        /* =====================================================
           APP
        ===================================================== */

        html,
        body,
        [data-testid="stAppViewContainer"],
        [data-testid="stSidebar"] {
            font-family:
                Inter,
                "Segoe UI",
                system-ui,
                -apple-system,
                BlinkMacSystemFont,
                sans-serif !important;
        }


        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(
                    circle at 15% 0%,
                    rgba(6,182,212,.11),
                    transparent 27%
                ),
                radial-gradient(
                    circle at 95% 8%,
                    rgba(132,204,22,.05),
                    transparent 25%
                ),
                linear-gradient(
                    180deg,
                    #02070d 0%,
                    #030c14 48%,
                    #02070c 100%
                );

            color: var(--pg-white);
        }


        .main .block-container {
            max-width: 1580px !important;
            padding: 1rem 2rem 5rem !important;
        }


        #MainMenu {
            visibility: hidden;
        }


        footer {
            visibility: hidden;
        }


        [data-testid="stHeader"] {
            background: rgba(2,7,13,.64) !important;
            backdrop-filter: blur(18px);
            border-bottom:
                1px solid rgba(148,163,184,.06);
        }


        h1,
        h2,
        h3,
        h4 {
            color: var(--pg-white) !important;
            letter-spacing: -.025em !important;
        }


        /* =====================================================
           COMMAND BAR
        ===================================================== */

        .pg-commandbar {
            display: flex;
            align-items: center;
            justify-content: space-between;

            gap: 24px;

            padding: 16px 19px;

            margin-bottom: 14px;

            border:
                1px solid var(--pg-border);

            border-radius: 20px;

            background:
                linear-gradient(
                    125deg,
                    rgba(7,22,36,.97),
                    rgba(3,12,21,.96)
                );

            box-shadow:
                0 20px 60px rgba(0,0,0,.22);
        }


        .pg-brand {
            display: flex;
            align-items: center;
            gap: 13px;
        }


        .pg-logo {
            width: 46px;
            height: 46px;

            display: grid;
            place-items: center;

            border:
                1px solid rgba(34,211,238,.32);

            border-radius: 14px;

            background:
                radial-gradient(
                    circle at 35% 30%,
                    rgba(34,211,238,.20),
                    rgba(4,14,25,.90)
                );

            color: white;

            font-weight: 950;
            letter-spacing: -.05em;

            box-shadow:
                0 0 26px rgba(34,211,238,.08);
        }


        .pg-brand-title {
            color: #f4fcff;
            font-size: 20px;
            font-weight: 900;
            letter-spacing: -.035em;
        }


        .pg-brand-sub {
            margin-top: 2px;

            color: #68879a;

            font-size: 8px;
            font-weight: 850;

            letter-spacing: .15em;
        }


        .pg-current {
            display: inline-flex;
            align-items: center;
            gap: 8px;

            padding: 8px 12px;

            border:
                1px solid rgba(163,230,53,.22);

            border-radius: 999px;

            background:
                rgba(163,230,53,.06);

            color: #d9f99d;

            font-size: 9px;
            font-weight: 900;

            letter-spacing: .09em;
        }


        .pg-current-dot {
            width: 7px;
            height: 7px;

            border-radius: 50%;

            background: var(--pg-lime);

            box-shadow:
                0 0 9px rgba(163,230,53,.90);

            animation:
                pgPulse 2s ease-in-out infinite;
        }


        @keyframes pgPulse {
            0%,
            100% {
                opacity: 1;
                transform: scale(1);
            }

            50% {
                opacity: .45;
                transform: scale(.80);
            }
        }


        /* =====================================================
           HERO
        ===================================================== */

        .pg-hero {
            position: relative;
            overflow: hidden;

            padding: 32px 30px;
            margin-bottom: 18px;

            border:
                1px solid var(--pg-border);

            border-radius: 22px;

            background:
                linear-gradient(
                    125deg,
                    rgba(5,21,35,.98),
                    rgba(3,12,21,.96)
                );
        }


        .pg-hero::after {
            content: "";

            position: absolute;

            right: -80px;
            top: -150px;

            width: 340px;
            height: 340px;

            border-radius: 50%;

            border:
                1px solid rgba(34,211,238,.10);

            box-shadow:
                0 0 75px rgba(34,211,238,.07);

            pointer-events: none;
        }


        .pg-kicker {
            color: var(--pg-cyan-soft);

            font-size: 9px;
            font-weight: 900;

            letter-spacing: .16em;
        }


        .pg-hero-title {
            margin: 8px 0;

            max-width: 900px;

            color: white;

            font-size:
                clamp(
                    34px,
                    4vw,
                    58px
                );

            font-weight: 900;

            line-height: 1;

            letter-spacing: -.045em;
        }


        .pg-hero-copy {
            max-width: 830px;

            color: #89a6b8;

            font-size: 12px;

            line-height: 1.7;
        }


        .pg-tag-row {
            display: flex;
            flex-wrap: wrap;

            gap: 7px;

            margin-top: 17px;
        }


        .pg-tag {
            padding: 6px 9px;

            border:
                1px solid rgba(148,163,184,.12);

            border-radius: 999px;

            background:
                rgba(15,23,42,.42);

            color: #96adbd;

            font-size: 8px;
            font-weight: 850;

            letter-spacing: .07em;
        }


        .pg-tag.active {
            border-color:
                rgba(34,211,238,.22);

            color:
                #67e8f9;
        }


        /* =====================================================
           SECTION HEADERS
        ===================================================== */

        .pg-section-head {
            display: flex;
            align-items: end;
            justify-content: space-between;

            gap: 20px;

            margin:
                28px 0 12px;
        }


        .pg-section-kicker {
            color: #5f8196;

            font-size: 8px;
            font-weight: 900;

            letter-spacing: .14em;
        }


        .pg-section-title {
            margin-top: 4px;

            color: #edfaff;

            font-size: 23px;
            font-weight: 850;
        }


        .pg-section-desc {
            max-width: 620px;

            color: #678497;

            font-size: 10px;

            line-height: 1.6;
        }


        /* =====================================================
           METRICS
        ===================================================== */

        [data-testid="stMetric"] {
            position: relative;
            overflow: hidden;

            min-height: 120px;

            padding:
                16px 17px !important;

            border:
                1px solid rgba(148,163,184,.12);

            border-radius: 15px;

            background:
                linear-gradient(
                    135deg,
                    rgba(7,23,38,.96),
                    rgba(4,15,25,.94)
                );

            transition:
                .18s ease;
        }


        [data-testid="stMetric"]:hover {
            transform:
                translateY(-2px);

            border-color:
                rgba(34,211,238,.30);
        }


        [data-testid="stMetric"]::after {
            content: "";

            position: absolute;

            left: 0;
            right: 0;
            top: 0;

            height: 1px;

            background:
                linear-gradient(
                    90deg,
                    transparent,
                    rgba(34,211,238,.34),
                    transparent
                );
        }


        [data-testid="stMetricLabel"] {
            color:
                #64849a !important;

            font-size:
                8px !important;

            font-weight:
                900 !important;

            letter-spacing:
                .10em !important;

            text-transform:
                uppercase;
        }


        [data-testid="stMetricValue"] {
            color:
                #f2fbff !important;

            font-size:
                26px !important;

            font-weight:
                850 !important;

            letter-spacing:
                -.035em;
        }


        /* =====================================================
           BUTTONS
        ===================================================== */

        .stButton > button,
        .stDownloadButton > button,
        [data-testid="stFormSubmitButton"] button {

            min-height:
                43px;

            border:
                1px solid rgba(34,211,238,.18) !important;

            border-radius:
                10px !important;

            background:
                linear-gradient(
                    180deg,
                    rgba(9,31,49,.95),
                    rgba(5,18,30,.95)
                ) !important;

            color:
                #dbf8ff !important;

            font-size:
                10px !important;

            font-weight:
                850 !important;

            letter-spacing:
                .04em;

            transition:
                .16s ease !important;
        }


        .stButton > button:hover,
        .stDownloadButton > button:hover {

            transform:
                translateY(-1px);

            border-color:
                rgba(34,211,238,.55) !important;

            box-shadow:
                0 0 22px rgba(34,211,238,.08);
        }


        .stButton > button[kind="primary"] {

            border-color:
                rgba(163,230,53,.34) !important;

            background:
                linear-gradient(
                    90deg,
                    rgba(132,204,22,.18),
                    rgba(34,211,238,.10)
                ) !important;

            color:
                #d9f99d !important;
        }


        /* =====================================================
           INPUTS
        ===================================================== */

        [data-baseweb="input"] > div,
        [data-baseweb="select"] > div,
        [data-baseweb="textarea"] > div {

            border:
                1px solid rgba(148,163,184,.14) !important;

            border-radius:
                10px !important;

            background:
                rgba(4,15,26,.95) !important;
        }


        [data-baseweb="input"] input,
        [data-baseweb="textarea"] textarea {
            color:
                #e7f8ff !important;
        }


        label[data-testid="stWidgetLabel"] p {
            color:
                #7694a8 !important;

            font-size:
                9px !important;

            font-weight:
                850 !important;
        }


        /* =====================================================
           EXPANDERS
        ===================================================== */

        [data-testid="stExpander"] {
            overflow: hidden;

            border:
                1px solid rgba(148,163,184,.12) !important;

            border-radius:
                15px !important;

            background:
                rgba(6,20,33,.80) !important;
        }


        [data-testid="stExpander"] summary {
            color:
                #dff5ff !important;

            font-weight:
                800 !important;
        }


        /* =====================================================
           ALERTS
        ===================================================== */

        [data-testid="stAlert"] {
            border:
                1px solid rgba(148,163,184,.10) !important;

            border-radius:
                12px !important;

            background:
                rgba(6,19,31,.88) !important;
        }


        /* =====================================================
           TABS
        ===================================================== */

        [data-baseweb="tab-list"] {
            gap: 6px;

            padding: 5px;

            border:
                1px solid rgba(148,163,184,.10);

            border-radius:
                12px;

            background:
                rgba(3,13,22,.70);
        }


        [data-baseweb="tab"] {
            border-radius:
                8px;

            color:
                #7895a8;

            font-size:
                9px;

            font-weight:
                850;
        }


        [aria-selected="true"][data-baseweb="tab"] {
            background:
                rgba(34,211,238,.08);

            color:
                #67e8f9;
        }


        /* =====================================================
           SIDEBAR
        ===================================================== */

        [data-testid="stSidebar"] {
            border-right:
                1px solid rgba(148,163,184,.08);

            background:
                linear-gradient(
                    180deg,
                    #030c15,
                    #04111c
                ) !important;
        }


        .pg-sidebrand {
            padding: 14px;

            margin-bottom: 14px;

            border:
                1px solid rgba(34,211,238,.14);

            border-radius:
                14px;

            background:
                linear-gradient(
                    135deg,
                    rgba(8,28,44,.85),
                    rgba(4,15,25,.90)
                );
        }


        .pg-sidebrand-title {
            color:
                #f2fbff;

            font-size:
                17px;

            font-weight:
                900;
        }


        .pg-sidebrand-sub {
            margin-top:
                2px;

            color:
                #628399;

            font-size:
                7px;

            font-weight:
                850;

            letter-spacing:
                .13em;
        }


        .pg-side-label {
            margin-top:
                18px;

            margin-bottom:
                6px;

            color:
                #55768c;

            font-size:
                7px;

            font-weight:
                900;

            letter-spacing:
                .14em;
        }


        .pg-feed {
            display:
                flex;

            justify-content:
                space-between;

            align-items:
                center;

            padding:
                7px 0;

            border-bottom:
                1px solid rgba(148,163,184,.05);

            color:
                #8eabba;

            font-size:
                9px;
        }


        .pg-feed-state {
            display:
                flex;

            align-items:
                center;

            gap:
                5px;

            color:
                #c7e79c;

            font-size:
                7px;

            font-weight:
                900;
        }


        .pg-feed-state::before {
            content:
                "";

            width:
                5px;

            height:
                5px;

            border-radius:
                50%;

            background:
                var(--pg-lime);

            box-shadow:
                0 0 6px rgba(163,230,53,.70);
        }


        /* =====================================================
           CURRENT CONDITIONS
        ===================================================== */

        .pg-current-grid {
            display:
                grid;

            grid-template-columns:
                repeat(4,minmax(0,1fr));

            gap:
                10px;

            margin:
                10px 0 18px;
        }


        .pg-current-card {
            padding:
                15px;

            border:
                1px solid rgba(148,163,184,.11);

            border-radius:
                14px;

            background:
                linear-gradient(
                    135deg,
                    rgba(7,23,38,.94),
                    rgba(4,15,25,.92)
                );
        }


        .pg-current-card-top {
            display:
                flex;

            align-items:
                center;

            justify-content:
                space-between;
        }


        .pg-current-card-label {
            color:
                #628398;

            font-size:
                7px;

            font-weight:
                900;

            letter-spacing:
                .12em;
        }


        .pg-current-pill {
            color:
                #c9ed99;

            font-size:
                7px;

            font-weight:
                900;
        }


        .pg-current-value {
            margin-top:
                11px;

            color:
                #eefcff;

            font-size:
                25px;

            font-weight:
                900;

            letter-spacing:
                -.04em;
        }


        .pg-current-source {
            margin-top:
                5px;

            color:
                #58788c;

            font-size:
                8px;

            font-weight:
                750;
        }


        /* =====================================================
           TIMELINE
        ===================================================== */

        .pg-timeline {
            display:
                grid;

            grid-template-columns:
                repeat(4,1fr);

            gap:
                8px;

            margin:
                12px 0 18px;
        }


        .pg-time {
            position:
                relative;

            padding:
                12px 12px 11px;

            border:
                1px solid rgba(148,163,184,.11);

            border-radius:
                12px;

            background:
                rgba(6,19,31,.75);
        }


        .pg-time.active {
            border-color:
                rgba(34,211,238,.38);

            background:
                linear-gradient(
                    135deg,
                    rgba(8,41,59,.86),
                    rgba(5,20,32,.86)
                );
        }


        .pg-time-label {
            color:
                #edfaff;

            font-size:
                11px;

            font-weight:
                900;
        }


        .pg-time-sub {
            margin-top:
                3px;

            color:
                #628297;

            font-size:
                7px;

            font-weight:
                800;
        }


        /* =====================================================
           GENERIC PANEL
        ===================================================== */

        .pg-panel {
            padding:
                16px;

            border:
                1px solid rgba(148,163,184,.11);

            border-radius:
                15px;

            background:
                linear-gradient(
                    135deg,
                    rgba(7,23,38,.94),
                    rgba(4,15,25,.92)
                );
        }


        .pg-panel-title {
            color:
                #eefbff;

            font-size:
                12px;

            font-weight:
                900;
        }


        .pg-panel-sub {
            margin-top:
                3px;

            color:
                #668598;

            font-size:
                8px;

            line-height:
                1.5;
        }


        /* =====================================================
           ICEBERG ID
        ===================================================== */

        .pg-iceberg-badge {
            display:
                inline-flex;

            align-items:
                center;

            gap:
                6px;

            padding:
                6px 9px;

            border:
                1px solid rgba(56,189,248,.24);

            border-radius:
                999px;

            background:
                rgba(56,189,248,.07);

            color:
                #dff7ff;

            font-size:
                9px;

            font-weight:
                950;
        }


        .pg-iceberg-badge::before {
            content:
                "◆";

            color:
                #38bdf8;

            text-shadow:
                0 0 8px rgba(56,189,248,.80);
        }


        /* =====================================================
           RESPONSIVE
        ===================================================== */

        @media(max-width:900px) {

            .pg-current-grid {
                grid-template-columns:
                    repeat(2,1fr);
            }

            .pg-commandbar {
                align-items:
                    flex-start;

                flex-direction:
                    column;
            }

            .pg-timeline {
                grid-template-columns:
                    repeat(2,1fr);
            }
        }

        </style>
        """
    )


# ============================================================
# COMMAND BAR
# ============================================================


def render_commandbar() -> None:

    _render_html(
        """
        <div class="pg-commandbar">

            <div class="pg-brand">

                <div class="pg-logo">
                    PG
                </div>

                <div>

                    <div class="pg-brand-title">
                        PolarGuard
                    </div>

                    <div class="pg-brand-sub">
                        ANTARCTIC NAVIGATION INTELLIGENCE
                    </div>

                </div>

            </div>

            <div class="pg-current">
                <span class="pg-current-dot"></span>
                CURRENT
            </div>

        </div>
        """
    )


# ============================================================
# HERO
# ============================================================


def render_hero() -> None:

    _render_html(
        """
        <div class="pg-hero">

            <div class="pg-kicker">
                POLARGUARD / COMMAND CENTER
            </div>

            <div class="pg-hero-title">
                Antarctic Navigation Intelligence
            </div>

            <div class="pg-hero-copy">
                AI-assisted Antarctic sea-ice forecasting,
                observed iceberg intelligence,
                environmental awareness,
                uncertainty analysis,
                hazard assessment and explainable
                risk-aware route planning.
            </div>

            <div class="pg-tag-row">

                <div class="pg-tag active">
                    SEA-ICE AI
                </div>

                <div class="pg-tag">
                    ICEBERG TRACKING
                </div>

                <div class="pg-tag active">
                    CURRENT CONDITIONS
                </div>

                <div class="pg-tag">
                    RISK ENGINE
                </div>

                <div class="pg-tag active">
                    A* NAVIGATION
                </div>

            </div>

        </div>
        """
    )


# ============================================================
# SECTION
# ============================================================


def render_section(
    title: str,
    description: str = "",
    kicker: str = "MISSION MODULE",
) -> None:

    desc = ""

    if description:
        desc = (
            '<div class="pg-section-desc">'
            f"{_safe(description)}"
            "</div>"
        )

    _render_html(
        f"""
        <div class="pg-section-head">

            <div>

                <div class="pg-section-kicker">
                    {_safe(kicker)}
                </div>

                <div class="pg-section-title">
                    {_safe(title)}
                </div>

            </div>

            {desc}

        </div>
        """
    )


# ============================================================
# SIDEBAR
# ============================================================


def render_sidebar() -> None:

    _render_sidebar_html(
        """
        <div class="pg-sidebrand">

            <div class="pg-sidebrand-title">
                PolarGuard
            </div>

            <div class="pg-sidebrand-sub">
                ANTARCTIC COMMAND SYSTEM
            </div>

        </div>

        <div class="pg-side-label">
            OPERATIONAL DATA
        </div>

        <div class="pg-feed">

            <span>
                NOAA / NSIDC
            </span>

            <span class="pg-feed-state">
                CURRENT
            </span>

        </div>

        <div class="pg-feed">

            <span>
                BYU / NIC
            </span>

            <span class="pg-feed-state">
                CURRENT
            </span>

        </div>

        <div class="pg-feed">

            <span>
                ECMWF
            </span>

            <span class="pg-feed-state">
                CURRENT
            </span>

        </div>

        <div class="pg-feed">

            <span>
                COPERNICUS
            </span>

            <span class="pg-feed-state">
                CURRENT
            </span>

        </div>
        """
    )


# ============================================================
# CURRENT CONDITION CARDS
# ============================================================


def render_current_conditions(
    sea_ice: str = "READY",
    iceberg_count: str = "READY",
    wind: str = "READY",
    ocean_current: str = "READY",
) -> None:

    cards = [
        (
            "SEA ICE",
            sea_ice,
            "NOAA / NSIDC",
        ),
        (
            "ICEBERGS",
            iceberg_count,
            "BYU / NIC",
        ),
        (
            "WIND",
            wind,
            "ECMWF",
        ),
        (
            "OCEAN CURRENT",
            ocean_current,
            "COPERNICUS",
        ),
    ]

    parts = []

    for label, value, source in cards:

        parts.append(
            f"""
            <div class="pg-current-card">

                <div class="pg-current-card-top">

                    <div class="pg-current-card-label">
                        {_safe(label)}
                    </div>

                    <div class="pg-current-pill">
                        ● CURRENT
                    </div>

                </div>

                <div class="pg-current-value">
                    {_safe(value)}
                </div>

                <div class="pg-current-source">
                    {_safe(source)}
                </div>

            </div>
            """
        )

    _render_html(
        f"""
        <div class="pg-current-grid">
            {''.join(parts)}
        </div>
        """
    )


# ============================================================
# FORECAST TIMELINE
# ============================================================


def render_timeline(
    active: str = "CURRENT",
) -> None:

    options = [
        (
            "CURRENT",
            "OBSERVATION",
        ),
        (
            "+24H",
            "AI FORECAST",
        ),
        (
            "+48H",
            "AI FORECAST",
        ),
        (
            "+72H",
            "AI FORECAST",
        ),
    ]

    active = str(active).upper()

    parts = []

    for label, subtitle in options:

        css_class = (
            "pg-time active"
            if label == active
            else "pg-time"
        )

        parts.append(
            f"""
            <div class="{css_class}">

                <div class="pg-time-label">
                    {label}
                </div>

                <div class="pg-time-sub">
                    {subtitle}
                </div>

            </div>
            """
        )

    _render_html(
        f"""
        <div class="pg-timeline">
            {''.join(parts)}
        </div>
        """
    )


# ============================================================
# ICEBERG BADGE
# ============================================================


def render_iceberg_badge(
    iceberg_id: str,
) -> None:

    _render_html(
        f"""
        <span class="pg-iceberg-badge">
            {_safe(str(iceberg_id).upper())}
        </span>
        """
    )


# ============================================================
# GENERIC PANEL
# ============================================================


def render_panel(
    title: str,
    subtitle: str = "",
) -> None:

    _render_html(
        f"""
        <div class="pg-panel">

            <div class="pg-panel-title">
                {_safe(title)}
            </div>

            <div class="pg-panel-sub">
                {_safe(subtitle)}
            </div>

        </div>
        """
    )