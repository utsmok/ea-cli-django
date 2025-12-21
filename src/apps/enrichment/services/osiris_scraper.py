import urllib.parse
from typing import Any

import bs4
import httpx
import Levenshtein
from django.conf import settings
from loguru import logger


class OsirisScraperService:
    """
    Service for fetching and parsing course and person data from Osiris and People Page.
    """

    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client or httpx.AsyncClient(
            headers=settings.OSIRIS_HEADERS, timeout=30.0
        )
        self.base_url = settings.OSIRIS_BASE_URL

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def fetch_course_details(self, course_code: int) -> dict[str, Any]:
        """
        Fetch course data from Osiris.
        """
        logger.info(f"Fetching course data for {course_code}...")

        # Search for the course
        search_url = f"{self.base_url}/student/osiris/student/cursussen/zoeken"

        # Build search body (replicated from legacy)
        # Note: year is hardcoded to 2024-2025 like in legacy for now,
        # but could be made dynamic
        body = (
            '{"from":0,"size":25,"sort":[{"cursus_lange_naam.raw":{"order":"asc"}},'
            '{"cursus":{"order":"asc"}},{"collegejaar":{"order":"desc"}}],'
            '"query":{"bool":{"must":[{"multi_match":{"query":"'
            + str(course_code)
            + '",'
            '"type":"phrase_prefix","fields":["cursus","cursus_korte_naam","cursus_lange_naam"],'
            '"max_expansions":200}}]}}}'
        )

        try:
            headers = self.client.headers.copy()
            headers.update(
                {
                    "host": "utwente.osiris-student.nl",
                    "connection": "keep-alive",
                    "content-length": str(len(body)),
                }
            )
            response = await self.client.post(search_url, content=body, headers=headers)
            response.raise_for_status()
            results = response.json().get("hits", {}).get("hits", [])

            if not results:
                logger.warning(f"No results found for course {course_code}")
                return {}

            raw_data = results[0].get("_source", {})
            internal_id = raw_data.get("id_cursus")

            course_info = {
                "cursuscode": course_code,
                "internal_id": internal_id,
                "name": raw_data.get("cursus_lange_naam"),
                "short_name": raw_data.get("cursus_korte_naam"),
                "faculty_abbr": raw_data.get("faculteit"),
                "faculty_name": raw_data.get("faculteit_naam"),
                "programme": raw_data.get("coordinerend_onderdeel_oms"),
                "year": raw_data.get("collegejaar"),
                "teachers": set(),
                "contacts": set(),
            }

            # If we have an internal ID, fetch details (contacts/teachers)
            if internal_id:
                await self._fetch_extended_course_details(course_info)

            return course_info

        except Exception as e:
            logger.error(f"Error fetching course {course_code}: {e}")
            return {}

    async def _fetch_extended_course_details(self, course_info: dict[str, Any]):
        """Fetch detailed course page to extract contacts and teachers."""
        internal_id = course_info["internal_id"]
        url = f"{self.base_url}/student/osiris/owc/cursussen/{internal_id}"

        try:
            headers = self.client.headers.copy()
            headers.update(
                {
                    "host": "utwente.osiris-student.nl",
                    "connection": "keep-alive",
                }
            )
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            details = response.json()

            for item in details.get("items", []):
                if item.get("rubriek") == "rubriek-docenten":
                    velden = item.get("velden", [])
                    for veld in velden:
                        waarde = veld.get("waarde", [])
                        for role_group in waarde:
                            role_name = role_group.get("omschrijving")
                            for person_entry in role_group.get("velden", []):
                                person_name = person_entry.get("docent")
                                if person_name:
                                    if role_name == "Contactpersoon":
                                        course_info["contacts"].add(person_name)
                                    else:
                                        course_info["teachers"].add(person_name)

            # Convert sets to lists for better handling later
            course_info["teachers"] = list(course_info["teachers"])
            course_info["contacts"] = list(course_info["contacts"])

        except Exception as e:
            logger.warning(
                f"Could not fetch extended details for course {internal_id}: {e}"
            )

    async def fetch_person_data(self, person_name: str) -> dict[str, Any]:
        """
        Fetch person data from people.utwente.nl.
        """
        logger.info(f"Searching for person: {person_name}")

        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        }

        try:
            encoded_query = urllib.parse.quote(person_name)
            search_url = f"https://people.utwente.nl/overview?query={encoded_query}"

            response = await self.client.get(search_url, headers=headers)
            response.raise_for_status()

            soup = bs4.BeautifulSoup(response.text, "lxml")
            tiles = soup.find_all("div", class_="ut-person-tile")

            if not tiles:
                logger.warning(f"No person tiles found for {person_name}")
                return {}

            # Score matches using Levenshtein (simplified version of legacy logic)
            matches = []
            compare_name = person_name.lower().strip()

            for tile in tiles[:5]:
                name_tag = tile.find("h3", class_="ut-person-tile__title")
                if not name_tag:
                    continue

                full_name = name_tag.get_text(strip=True)
                data_link = tile.get("data-link")
                if not data_link:
                    continue

                url = f"https://people.utwente.nl/{data_link}"

                # Basic ratio check
                ratio = Levenshtein.ratio(full_name.lower(), compare_name)
                matches.append({"name": full_name, "url": url, "ratio": ratio})

            if not matches:
                return {}

            matches.sort(key=lambda x: x["ratio"], reverse=True)
            best_match = matches[0]

            if best_match["ratio"] < 0.5:
                logger.warning(
                    f"Low confidence match for {person_name}: {best_match['name']} ({best_match['ratio']})"
                )
                return {}

            # Fetch detail page
            detail_response = await self.client.get(best_match["url"], headers=headers)
            detail_response.raise_for_status()
            detail_soup = bs4.BeautifulSoup(detail_response.text, "lxml")

            # Extract email
            email = ""
            for a in detail_soup.find_all("a", href=True):
                if str(a["href"]).startswith("mailto:"):
                    email = str(a["href"]).replace("mailto:", "")
                    break

            # Extract organizations
            orgs = []
            org_container = detail_soup.find("ul", class_="widget-linklist--smallicons")
            if org_container:
                for li in org_container.find_all("li"):
                    text = li.get_text(strip=True)
                    if "(" in text:
                        name = text.split("(")[0].strip()
                        abbr = text.split("(")[1].split(")")[0].strip()
                        orgs.append({"name": name, "abbr": abbr})

            return {
                "input_name": person_name,
                "main_name": best_match["name"],
                "match_confidence": best_match["ratio"],
                "email": email,
                "orgs": orgs,
                "people_page_url": best_match["url"],
            }

        except Exception as e:
            logger.error(f"Error fetching person {person_name}: {e}")
            return {}
