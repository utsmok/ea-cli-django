
import asyncio
import httpx
import bs4
import urllib.parse as _u
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PEOPLE_SEARCH_URL = "https://people.utwente.nl/overview?query="

async def fetch_person_data(name: str, client: httpx.AsyncClient) -> dict | None:
    """Fetch person data by scraping people.utwente.nl."""
    url = f"{PEOPLE_SEARCH_URL}{_u.quote(name)}"
    print(f"Fetching {url}")

    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code != 200:
            print(f"Status {resp.status_code}")
            return None

        soup = bs4.BeautifulSoup(resp.text, "html.parser")

        # Check for direct profile page or search results
        if "people.utwente.nl" in str(resp.url) and "overview" not in str(resp.url):
             print("Redirected to profile page")
             return _parse_person_page(soup, str(resp.url), name)

        # Else parse search results
        results = soup.select("div.ut-person-tile")
        print(f"Search results found: {len(results)}")

        if not results:
             print("No results found.")
             return None

        # Pick first
        first_result = results[0]
        link = first_result.select_one(".ut-person-tile__profilelink a")
        if link and link.has_attr("href"):
             profile_url = link["href"]
             if not profile_url.startswith("http"):
                  profile_url = f"https://people.utwente.nl{profile_url}"

             print(f"Found profile URL: {profile_url}")
             # Fetch profile
             profile_resp = await client.get(profile_url, follow_redirects=True)
             if profile_resp.status_code == 200:
                 profile_soup = bs4.BeautifulSoup(profile_resp.text, "html.parser")
                 return _parse_person_page(profile_soup, profile_url, name)
        else:
             print("Link not found in tile")

        return None

    except Exception as e:
        logger.error(f"Error scraping person {name}: {e}")
        return None

def _parse_person_page(soup: bs4.BeautifulSoup, url: str, input_name: str) -> dict:
    data = {
        "input_name": input_name,
        "people_page_url": url,
        "main_name": None,
        "email": None,
        "faculty_abbrev": None,
    }

    # Name (H1)
    if h1 := soup.find("h1"):
        data["main_name"] = h1.get_text(strip=True)

    # Email
    if email_link := soup.select_one("a[href^='mailto:']"):
        data["email"] = email_link.get_text(strip=True)

    # Faculty from sidebar org unit
    # From dump: <a class="org-unit-link" href="..."> or in .ut-person-tile__orgs for search results
    # On profile page? Let's assume there is organization info.
    # We'll just leave faculty extraction simple for now.

    print(f"Parsed data: {data}")
    return data

async def main():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test with a known name
        name = "Havinga"
        data = await fetch_person_data(name, client)
        print(f"Result for {name}: {data}")

if __name__ == "__main__":
    asyncio.run(main())
