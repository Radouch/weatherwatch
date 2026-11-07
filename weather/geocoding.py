import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from weather.base import Coordinates


session = requests.Session()
retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retry)
session.mount("https://", adapter)


def geocode_city(
    city_name: str, country: str | None = None, admin1: str | None = None
) -> Coordinates:
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": city_name, "count": 10, "language": "en", "format": "json"}
    if country:
        params["country"] = country
    if admin1:
        params["admin1"] = admin1

    response = session.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    if "results" not in data or len(data["results"]) == 0:
        raise ValueError(
            f"City not found: {city_name}" + (f" in {country}" if country else "")
        )

    result = data["results"][0]
    return Coordinates(
        latitude=result["latitude"],
        longitude=result["longitude"],
        name=result.get("name", city_name),
    )


def geocode_city_full(
    city_name: str, country: str | None = None, admin1: str | None = None
) -> list[Coordinates]:
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": city_name, "count": 10, "language": "en", "format": "json"}
    if country:
        params["country"] = country
    if admin1:
        params["admin1"] = admin1

    response = session.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    if "results" not in data or len(data["results"]) == 0:
        return []

    return [
        Coordinates(
            latitude=r["latitude"],
            longitude=r["longitude"],
            name=r.get("name", city_name),
        )
        for r in data["results"]
    ]
