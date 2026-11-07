import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from weather.base import Coordinates


logger = logging.getLogger(__name__)

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

session = requests.Session()
retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retry)
session.mount("https://", adapter)


# The geocoding API has no country/admin1 query parameters - it ignores them
# and sorts results by relevance/population. So the selection below is done
# client-side. The alias table covers country names that differ from the
# API's (canonical English) naming.
COUNTRY_CODE_ALIASES = {
    "czech republic": "CZ",
    "united states": "US",
    "united states of america": "US",
    "usa": "US",
    "united kingdom": "GB",
    "great britain": "GB",
    "south korea": "KR",
    "north korea": "KP",
    "netherlands": "NL",
    "turkey": "TR",
    "türkiye": "TR",
}


def _fetch_results(name: str, count: int = 10) -> list[dict]:
    params = {"name": name, "count": count, "language": "en", "format": "json"}
    response = session.get(GEOCODING_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json().get("results", [])


def _country_matches(result: dict, want: str) -> bool:
    want = want.strip().lower()
    code = want.upper() if len(want) == 2 else COUNTRY_CODE_ALIASES.get(want)
    if code and result.get("country_code", "").upper() == code:
        return True
    return result.get("country", "").strip().lower() == want


def _admin1_matches(result: dict, admin1: str | None) -> bool:
    if not admin1:
        return True
    return result.get("admin1", "").strip().lower() == admin1.strip().lower()


def _filter_results(
    results: list[dict], country: str | None = None, admin1: str | None = None
) -> list[dict]:
    return [
        result
        for result in results
        if (not country or _country_matches(result, country))
        and _admin1_matches(result, admin1)
    ]


def select_result(
    results: list[dict], country: str | None = None, admin1: str | None = None
) -> dict | None:
    """Pick the first geocoding result matching country and admin1.

    Matching is exact (case-insensitive) against the API's fields:
    country_code/country name (see COUNTRY_CODE_ALIASES) and admin1. Returns
    None when nothing matches - callers should fail loudly rather than
    silently report weather for the wrong town.
    """
    matches = _filter_results(results, country, admin1)
    return matches[0] if matches else None


def geocode_city(
    city_name: str, country: str | None = None, admin1: str | None = None
) -> Coordinates:
    results = _fetch_results(city_name)
    if not results:
        raise ValueError(
            f"City not found: {city_name}" + (f" in {country}" if country else "")
        )

    result = select_result(results, country, admin1)
    if result is None:
        candidates = "; ".join(
            f"{r.get('name', '?')} ({r.get('admin1', '?')}, {r.get('country', '?')})"
            for r in results[:8]
        )
        raise ValueError(
            f"No geocoding match for {city_name!r} with country={country!r}, "
            f"admin1={admin1!r}. Options found: {candidates}. "
            "Use the names the geocoding service returns, or pin "
            "latitude/longitude in config.json."
        )

    return Coordinates(
        latitude=result["latitude"],
        longitude=result["longitude"],
        name=result.get("name", city_name),
    )


def geocode_city_full(
    city_name: str, country: str | None = None, admin1: str | None = None
) -> list[Coordinates]:
    results = _fetch_results(city_name)
    return [
        Coordinates(
            latitude=result["latitude"],
            longitude=result["longitude"],
            name=result.get("name", city_name),
        )
        for result in _filter_results(results, country, admin1)
    ]
