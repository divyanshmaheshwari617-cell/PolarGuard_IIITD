import requests
import streamlit as st
from datetime import datetime, timezone


TINYFISH_SEARCH_URL = "https://api.search.tinyfish.ai"


def render_polar_updates():
    st.header("Polar Updates")
    st.write(
        "Search for web information related to Antarctic sea ice. "
        "These results are separate from PolarGuard's model forecasts."
    )

    try:
        api_key = st.secrets["TINYFISH_API_KEY"]
    except Exception:
        st.error(
            "TinyFish API key was not found. Add TINYFISH_API_KEY "
            "to this app's .streamlit/secrets.toml file."
        )
        return

    query = st.text_input(
        "Search topic",
        value="Antarctic sea ice concentration updates",
        help="Search results are web pages and snippets, not model predictions.",
    )

    source_choice = st.selectbox(
        "Preferred source",
        [
            "All sources",
            "NSIDC",
            "NOAA",
            "EUMETSAT OSI SAF",
        ],
    )

    site_filters = {
        "All sources": "",
        "NSIDC": " site:nsidc.org",
        "NOAA": " site:noaa.gov",
        "EUMETSAT OSI SAF": " site:osi-saf.eumetsat.int",
    }

    if st.button("Search with TinyFish", type="primary"):
        if not query.strip():
            st.warning("Enter a search topic first.")
            return

        search_query = query.strip() + site_filters[source_choice]

        try:
            response = requests.get(
                TINYFISH_SEARCH_URL,
                params={"query": search_query},
                headers={"X-API-Key": api_key},
                timeout=30,
            )

            if response.status_code == 401:
                st.error(
                    "TinyFish rejected the API key. Check the key in "
                    ".streamlit/secrets.toml."
                )
                return

            response.raise_for_status()
            payload = response.json()
            results = payload.get("results", [])

        except requests.Timeout:
            st.error("TinyFish took too long to respond. Try again.")
            return
        except requests.RequestException as exc:
            st.error(f"TinyFish request failed: {exc}")
            return
        except ValueError:
            st.error("TinyFish returned a response that could not be read.")
            return

        st.caption(
            "Retrieved "
            + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            + ". Open the source to verify its details."
        )

        if not results:
            st.info("TinyFish returned no results for this search.")
            return

        for index, item in enumerate(results[:10], start=1):
            title = item.get("title") or "Untitled result"
            url = item.get("url")
            snippet = item.get("snippet") or ""
            site_name = item.get("site_name") or ""

            st.markdown(f"**{index}. {title}**")
            if site_name:
                st.caption(site_name)
            if snippet:
                st.write(snippet)
            if url:
                st.markdown(f"[Open source page]({url})")
            st.divider()

    st.info(
        "Web search results are not sea-ice forecasts or route-safety "
        "assessments. Verify information with the original data provider."
    )