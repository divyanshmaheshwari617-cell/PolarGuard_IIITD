from __future__ import annotations

import asyncio
import json
import os
from urllib.parse import urlparse

import requests
import streamlit as st


SEARCH_URL = "https://api.search.tinyfish.ai"
FETCH_URL = "https://api.fetch.tinyfish.ai"
BROWSER_URL = "https://api.browser.tinyfish.ai"
AGENT_RUN_URL = "https://agent.tinyfish.ai/v1/automation/run"

REQUEST_HEADERS = {
    "Content-Type": "application/json",
}


def _get_api_key() -> str | None:
    """Read the TinyFish key from Streamlit secrets or environment."""
    try:
        key = st.secrets.get("TINYFISH_API_KEY")
        if key:
            return str(key).strip()
    except Exception:
        pass

    key = os.environ.get("TINYFISH_API_KEY")
    return key.strip() if key else None


def _headers(api_key: str) -> dict[str, str]:
    return {
        **REQUEST_HEADERS,
        "X-API-Key": api_key,
    }


def _response_error(response: requests.Response) -> str:
    """Return a useful error without exposing credentials."""
    try:
        payload = response.json()
        detail = (
            payload.get("message")
            or payload.get("error")
            or payload.get("detail")
        )
        if detail:
            return f"HTTP {response.status_code}: {detail}"
    except (ValueError, AttributeError):
        pass

    return f"HTTP {response.status_code}: {response.text[:500]}"


def _search(
    *,
    api_key: str,
    query: str,
    domain_type: str,
    recency_minutes: int | None,
    include_domains: str,
    purpose: str,
) -> list[dict]:
    params: dict[str, str | int] = {
        "query": query,
        "domain_type": domain_type,
        "location": "US",
        "language": "en",
        "page": 0,
    }

    if recency_minutes is not None:
        params["recency_minutes"] = recency_minutes

    if include_domains.strip():
        params["include_domains"] = include_domains.strip()

    if purpose.strip():
        params["purpose"] = purpose.strip()[:2000]

    response = requests.get(
        SEARCH_URL,
        params=params,
        headers={"X-API-Key": api_key},
        timeout=45,
    )

    if not response.ok:
        raise RuntimeError(_response_error(response))

    payload = response.json()
    results = payload.get("results", [])

    if not isinstance(results, list):
        raise RuntimeError("TinyFish returned an unexpected search response.")

    return results[:10]


def _fetch_pages(
    *,
    api_key: str,
    urls: list[str],
) -> dict:
    response = requests.post(
        FETCH_URL,
        headers=_headers(api_key),
        json={
            "urls": urls[:10],
            "format": "markdown",
        },
        timeout=90,
    )

    if not response.ok:
        raise RuntimeError(_response_error(response))

    return response.json()


def _run_agent(
    *,
    api_key: str,
    url: str,
    goal: str,
) -> dict:
    response = requests.post(
        AGENT_RUN_URL,
        headers=_headers(api_key),
        json={
            "url": url,
            "goal": goal,
        },
        timeout=180,
    )

    if not response.ok:
        raise RuntimeError(_response_error(response))

    return response.json()


def _validate_public_https_url(value: str) -> str:
    url = value.strip()
    parsed = urlparse(url)

    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("Enter a complete public URL beginning with https://")

    return url


async def _read_browser_page(cdp_url: str, url: str) -> dict[str, str]:
    """Connect to a TinyFish remote browser and read the rendered page."""
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.connect_over_cdp(cdp_url)

        try:
            context = (
                browser.contexts[0]
                if browser.contexts
                else await browser.new_context()
            )

            page = (
                context.pages[0]
                if context.pages
                else await context.new_page()
            )

            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            title = await page.title()
            body_text = await page.locator("body").inner_text(timeout=20000)

            return {
                "title": title,
                "url": page.url,
                "text": body_text[:12000],
            }
        finally:
            await browser.close()


def _browse_with_tinyfish(api_key: str, url: str) -> dict[str, str]:
    """Create, use, and then explicitly close a TinyFish browser session."""
    response = requests.post(
        BROWSER_URL,
        headers=_headers(api_key),
        json={"url": url},
        timeout=60,
    )

    if not response.ok:
        raise RuntimeError(_response_error(response))

    session = response.json()
    session_id = session.get("session_id")
    cdp_url = session.get("cdp_url")

    if not session_id or not cdp_url:
        raise RuntimeError("TinyFish did not return a browser session.")

    try:
        return asyncio.run(_read_browser_page(cdp_url, url))
    finally:
        # Do not leave a remote browser session running.
        requests.delete(
            f"{BROWSER_URL}/{session_id}",
            headers={"X-API-Key": api_key},
            timeout=20,
        )


def _render_search_and_fetch(api_key: str) -> None:
    st.subheader("Search polar information")

    topic = st.selectbox(
        "Choose a search topic",
        [
            "Antarctic sea-ice conditions and updates",
            "Antarctic iceberg sightings and reports",
            "Antarctic shipping and voyage notices",
            "Sea-ice and iceberg drift research",
            "Custom search",
        ],
    )

    default_query = {
        "Antarctic sea-ice conditions and updates":
            "Antarctic sea ice conditions update",
        "Antarctic iceberg sightings and reports":
            "Antarctic iceberg sightings tracking reports",
        "Antarctic shipping and voyage notices":
            "Antarctic shipping voyage notices ice conditions",
        "Sea-ice and iceberg drift research":
            "Antarctic sea ice iceberg drift research",
        "Custom search": "",
    }

    query = st.text_input(
        "Search query",
        value=default_query[topic],
        help="Search results are web sources, not PolarGuard model outputs.",
    )

    search_type = st.selectbox(
        "Result type",
        ["Web", "News", "Research papers"],
    )
    domain_type = {
        "Web": "web",
        "News": "news",
        "Research papers": "research_paper",
    }[search_type]

    source_choice = st.selectbox(
        "Limit to a source (optional)",
        [
            "All sources",
            "NSIDC",
            "NOAA",
            "EUMETSAT OSI SAF",
            "British Antarctic Survey",
            "Custom domains",
        ],
    )

    domain_options = {
        "All sources": "",
        "NSIDC": "nsidc.org",
        "NOAA": "noaa.gov",
        "EUMETSAT OSI SAF": "osi-saf.eumetsat.int",
        "British Antarctic Survey": "bas.ac.uk",
        "Custom domains": "",
    }

    custom_domains = ""
    if source_choice == "Custom domains":
        custom_domains = st.text_input(
            "Domains, comma-separated",
            placeholder="nsidc.org,noaa.gov",
        )

    include_domains = (
        custom_domains
        if source_choice == "Custom domains"
        else domain_options[source_choice]
    )

    freshness = st.selectbox(
        "Freshness",
        [
            "Any date",
            "Past 24 hours",
            "Past 7 days",
            "Past 30 days",
        ],
    )

    recency_minutes = {
        "Any date": None,
        "Past 24 hours": 24 * 60,
        "Past 7 days": 7 * 24 * 60,
        "Past 30 days": 30 * 24 * 60,
    }[freshness]

    purpose = st.text_input(
        "Search purpose",
        value="Find relevant, source-linked information for Antarctic polar monitoring.",
    )

    if st.button("Search with TinyFish", type="primary"):
        if not query.strip():
            st.warning("Enter a search query.")
        else:
            try:
                with st.spinner("Searching current web sources..."):
                    results = _search(
                        api_key=api_key,
                        query=query.strip(),
                        domain_type=domain_type,
                        recency_minutes=recency_minutes,
                        include_domains=include_domains,
                        purpose=purpose,
                    )

                st.session_state["tinyfish_results"] = results
                st.session_state["tinyfish_query"] = query.strip()
                st.session_state["tinyfish_fetch_output"] = None

            except requests.Timeout:
                st.error("TinyFish Search timed out. Try again.")
            except (requests.RequestException, RuntimeError, ValueError) as exc:
                st.error(f"TinyFish Search failed: {exc}")

    results = st.session_state.get("tinyfish_results", [])

    if results:
        st.caption(
            f"Search results for: {st.session_state.get('tinyfish_query', '')}"
        )

        selectable_results = []
        for index, item in enumerate(results, start=1):
            title = item.get("title") or "Untitled result"
            url = item.get("url")
            site_name = item.get("site_name") or ""
            snippet = item.get("snippet") or ""
            date_value = item.get("date")
            publisher = item.get("publisher")

            with st.expander(f"{index}. {title}", expanded=index == 1):
                metadata = [value for value in (site_name, publisher, date_value) if value]
                if metadata:
                    st.caption(" · ".join(metadata))
                if snippet:
                    st.write(snippet)
                if url:
                    st.markdown(f"[Open source page]({url})")
                    selected = st.checkbox(
                        "Select this page to fetch its content",
                        key=f"tinyfish_fetch_{index}_{url}",
                    )
                    if selected:
                        selectable_results.append(url)

        if st.button("Fetch selected pages"):
            if not selectable_results:
                st.warning("Select at least one result to fetch.")
            else:
                try:
                    with st.spinner("Fetching selected page content..."):
                        fetched = _fetch_pages(
                            api_key=api_key,
                            urls=selectable_results[:10],
                        )
                    st.session_state["tinyfish_fetch_output"] = fetched
                except requests.Timeout:
                    st.error("TinyFish Fetch timed out. Try fewer pages.")
                except (requests.RequestException, RuntimeError, ValueError) as exc:
                    st.error(f"TinyFish Fetch failed: {exc}")

    fetched = st.session_state.get("tinyfish_fetch_output")
    if fetched:
        st.subheader("Fetched page content")

        for page in fetched.get("results", []):
            with st.expander(page.get("title") or page.get("url") or "Fetched page"):
                if page.get("url"):
                    st.markdown(f"[Open source page]({page['url']})")
                if page.get("text"):
                    st.markdown(page["text"][:12000])

        for error in fetched.get("errors", []):
            st.warning(
                f"Could not fetch {error.get('url', 'a selected page')}: "
                f"{error.get('error', 'unknown error')}"
            )


def _render_agent(api_key: str) -> None:
    st.subheader("Ask TinyFish Agent to inspect a public page")

    url_input = st.text_input(
        "Public HTTPS page URL",
        placeholder="https://nsidc.org/...",
        key="tinyfish_agent_url",
    )

    goal = st.text_area(
        "Task",
        value=(
            "Read this public page and return a concise summary of the "
            "Antarctic sea-ice or iceberg information it contains. Include "
            "the page title, any publication or observation date shown, and "
            "the source URL. If the page does not contain relevant information, say so."
        ),
        height=130,
        key="tinyfish_agent_goal",
    )

    st.warning(
        "Agent runs can use paid TinyFish credits. It will only run when you click the button."
    )

    if st.button("Run TinyFish Agent", type="primary"):
        try:
            url = _validate_public_https_url(url_input)
            if not goal.strip():
                st.warning("Enter a task for the Agent.")
                return

            with st.spinner("TinyFish Agent is navigating the page..."):
                result = _run_agent(
                    api_key=api_key,
                    url=url,
                    goal=goal.strip(),
                )
            st.session_state["tinyfish_agent_result"] = result

        except ValueError as exc:
            st.warning(str(exc))
        except requests.Timeout:
            st.error("TinyFish Agent timed out. Try a shorter task.")
        except (requests.RequestException, RuntimeError, ValueError) as exc:
            st.error(f"TinyFish Agent failed: {exc}")

    result = st.session_state.get("tinyfish_agent_result")
    if result:
        st.subheader("Agent result")
        st.json(result)


def _render_browser(api_key: str) -> None:
    st.subheader("Navigate a public website")

    url_input = st.text_input(
        "Public HTTPS URL",
        placeholder="https://nsidc.org/...",
        key="tinyfish_browser_url",
    )

    st.warning(
        "Browser sessions may incur charges and can take 10–30 seconds to start. "
        "This reads a public webpage; it does not assess vessel-route safety."
    )

    if st.button("Open with TinyFish Browser", type="primary"):
        try:
            url = _validate_public_https_url(url_input)
            with st.spinner("Starting remote browser and reading the page..."):
                page = _browse_with_tinyfish(api_key, url)
            st.session_state["tinyfish_browser_page"] = page

        except ValueError as exc:
            st.warning(str(exc))
        except requests.Timeout:
            st.error("TinyFish Browser timed out. Try again.")
        except ImportError:
            st.error(
                "Browser support needs Playwright installed. "
                "Add `playwright` to requirements.txt and redeploy."
            )
        except Exception as exc:
            st.error(f"TinyFish Browser failed: {exc}")

    page = st.session_state.get("tinyfish_browser_page")
    if page:
        st.markdown(f"**{page.get('title') or 'Webpage'}**")
        st.markdown(f"[Open page]({page.get('url', '')})")
        st.text_area(
            "Rendered page text",
            value=page.get("text", ""),
            height=350,
            disabled=True,
        )


def render_polar_updates() -> None:
    st.header("Polar Updates")
    st.write(
        "Search and inspect public web sources about Antarctic sea ice, "
        "icebergs, and polar operations. These tools are separate from "
        "PolarGuard model forecasts and route-safety calculations."
    )

    api_key = _get_api_key()
    if not api_key:
        st.error(
            "TinyFish API key was not found. Add TINYFISH_API_KEY "
            "to Streamlit Cloud secrets."
        )
        return

    search_tab, agent_tab, browser_tab = st.tabs(
        ["Search & Fetch", "Agent", "Browser"]
    )

    with search_tab:
        _render_search_and_fetch(api_key)

    with agent_tab:
        _render_agent(api_key)

    with browser_tab:
        _render_browser(api_key)

    st.info(
        "TinyFish web results are not validated satellite measurements, "
        "forecasts, or route-safety assessments. Verify information with "
        "the original provider before using it."
    )