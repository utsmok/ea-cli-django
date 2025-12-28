"""Person-related functions for Osiris integration."""

import asyncio
import urllib.parse as _u

import bs4
import httpx
from loguru import logger

from apps.core.services.cache_service import cache_async_result
from apps.core.services.osiris.constants import FACULTY_ABBREVS, PEOPLE_SEARCH_URL
from apps.core.services.retry_logic import async_retry


@cache_async_result(timeout=604800, key_prefix="osiris_person", cache_name="queries")
@async_retry(max_retries=3, base_delay=1.0, max_delay=60.0)
async def fetch_person_data(name: str, client: httpx.AsyncClient) -> dict | None:
    """
    Fetch person data by scraping people.utwente.nl.

    Cached for 7 days because person information (email, faculty)
    changes very rarely.
    """
    url = f"{PEOPLE_SEARCH_URL}{_u.quote(name)}"

    try:
        resp = await client.get(url, follow_redirects=True)
        # Raise for HTTP errors - but 404 is expected (person not found)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()

        soup = bs4.BeautifulSoup(resp.text, "html.parser")

        # Check for direct profile page or search results
        # If we landed on a search page, pick the first result
        # (This heuristic matches legacy behavior)

        # If single result redirect happened, we are on profile page
        if "people.utwente.nl" in str(resp.url) and "overview" not in str(resp.url):
            return _parse_person_page(soup, str(resp.url), name)

        # Else parse search results
        results = soup.select("div.ut-person-tile")
        if not results:
            return None

        # Pick first
        first_result = results[0]
        link = first_result.select_one(".ut-person-tile__profilelink a")
        if link and link.has_attr("href"):
            profile_url = link["href"]
            if not str(profile_url).startswith("http"):
                profile_url = f"https://people.utwente.nl{profile_url}"

            # Fetch profile
            profile_resp = await client.get(str(profile_url), follow_redirects=True)
            if profile_resp.status_code == 200:
                profile_soup = bs4.BeautifulSoup(profile_resp.text, "html.parser")
                return _parse_person_page(profile_soup, str(profile_url), name)

        return None

    except Exception as e:
        logger.error(f"Error scraping person {name}: {e}")
        return None


def _parse_person_page(soup: bs4.BeautifulSoup, url: str, input_name: str) -> dict:
    """
    Parse a person's profile page from people.utwente.nl.

    Extracts:
    - main_name (from H1 header)
    - email (from mailto link)
    - faculty_abbrev (from organization links)

    Faculty extraction follows legacy pattern from ea-cli:
    Looks for widget-linklist with org abbreviations in format "Name (ABBR)"
    and identifies faculty by checking if abbreviation matches FACULTY_ABBREVS.
    """
    data = {
        "input_name": input_name,
        "people_page_url": url,
        "main_name": None,
        "email": None,
        "faculty_abbrev": None,
        "faculty_name": None,
    }

    # Name (H1)
    if h1 := soup.find("h1"):
        data["main_name"] = h1.get_text(strip=True)

    # Email
    if email_link := soup.select_one("a[href^='mailto:']"):
        data["email"] = email_link.get_text(strip=True)

    # Org / Faculty parsing
    # Look for organization links in the sidebar/widget
    # Format: "Organization Name (ABBR)"
    org_containers = soup.find_all(class_="widget-linklist--smallicons")
    if org_containers:
        container = org_containers[0]
        if isinstance(container, bs4.Tag):
            for org_tag in container.find_all(class_="widget-linklist__text"):
                if not isinstance(org_tag, bs4.Tag):
                    continue
                text_content = org_tag.string
                if not text_content or "(" not in text_content:
                    continue
                try:
                    org_name = text_content.split("(")[0].strip()
                    org_abbr = text_content.split("(")[1].split(")")[0].strip()
                    # Check if this is a faculty
                    if org_abbr in FACULTY_ABBREVS:
                        data["faculty_name"] = org_name
                        data["faculty_abbrev"] = org_abbr
                        logger.debug(
                            f"Found faculty {org_abbr} ({org_name}) for {input_name}"
                        )
                        break  # Use first faculty found
                except Exception as exc:
                    logger.debug(f"Org parse error for '{text_content}': {exc}")

    return data


async def fetch_and_parse_persons(
    names: set[str], max_concurrent: int = 20
) -> dict[str, dict]:
    """Fetch person data concurrently."""
    logger.info(f"Fetching {len(names)} persons concurrently...")

    semaphore = asyncio.Semaphore(max_concurrent)
    results = {}

    async def fetch_single(name: str):
        async with semaphore:
            # Skip if name is too short or generic?
            if len(name) < 3:
                return

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    data = await fetch_person_data(name, client)
                    if data:
                        results[name] = data
            except Exception as e:
                logger.error(f"Error fetching person {name}: {e}")

    tasks = [fetch_single(n) for n in names]
    await asyncio.gather(*tasks)

    return results
