import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from weather.base import WeatherSource, CurrentWeather, ForecastDay


session = requests.Session()
retry = Retry(
    total=5, backoff_factor=2, status_forcelist=[500, 502, 503, 504], connect=3, read=3
)
adapter = HTTPAdapter(max_retries=retry)
session.mount("https://", adapter)


ATTRIBUTE_NAMES = {
    "temperature_2m": "Temperature",
    "relative_humidity_2m": "Humidity",
    "wind_speed_10m": "Wind",
    "weather_code": "Condition",
    "precipitation": "Precipitation",
    "temperature_2m_max": "High",
    "temperature_2m_min": "Low",
    "precipitation_probability_max": "Precipitation chance",
}


class OpenMeteoSource(WeatherSource):
    def __init__(self, units: dict | None = None):
        self.units = units or {}

    def get_current(
        self, lat: float, lon: float, params: list[str]
    ) -> CurrentWeather | None:
        if not params:
            return None

        url = "https://api.open-meteo.com/v1/forecast"
        weather_code = self._get_weather_code(lat, lon)
        current_params = params + ["weather_code"]
        current_params = list(set(current_params))

        params_dict = {
            "latitude": lat,
            "longitude": lon,
            "current": ",".join(current_params),
            **self._build_unit_params(current_params),
        }

        response = session.get(url, params=params_dict, timeout=30)
        response.raise_for_status()
        data = response.json()

        if "current" not in data:
            return None

        current_data = data["current"]
        if weather_code:
            current_data["weather_code"] = weather_code

        return CurrentWeather(data=current_data)

    def get_forecast(
        self, lat: float, lon: float, params: list[str], days: int
    ) -> list[ForecastDay]:
        if not params:
            return []

        url = "https://api.open-meteo.com/v1/forecast"
        params_dict = {
            "latitude": lat,
            "longitude": lon,
            "daily": ",".join(params),
            "forecast_days": days,
            **self._build_unit_params(params),
        }

        response = session.get(url, params=params_dict, timeout=30)
        response.raise_for_status()
        data = response.json()

        if "daily" not in data:
            return []

        daily = data["daily"]
        dates = daily.get("time", [])
        forecasts = []

        for i, date in enumerate(dates):
            day_data = {}
            for param in params:
                if param in daily:
                    values = daily[param]
                    if i < len(values):
                        day_data[param] = values[i]
            forecasts.append(ForecastDay(date=date, data=day_data))

        return forecasts

    def _build_unit_params(self, params: list[str]) -> dict:
        unit_map = {
            "temperature_2m": "temperature_2m",
            "temperature_2m_max": "temperature_2m_max",
            "temperature_2m_min": "temperature_2m_min",
            "wind_speed_10m": "wind_speed_10m",
            "precipitation": "precipitation",
            "precipitation_probability_max": "precipitation_probability_max",
        }
        units = {}
        for param, api_param in unit_map.items():
            if param in params:
                unit = self.units.get(param.split("_")[0], "celsius")
                if param.startswith("temperature"):
                    units[f"{api_param}_unit"] = unit
                elif param.startswith("wind"):
                    wind_unit = self.units.get("wind_speed", "kmh")
                    units[f"{api_param}_unit"] = wind_unit
                elif param.startswith("precipitation"):
                    units[f"{api_param}_unit"] = self.units.get("precipitation", "mm")
        return units

    def _get_weather_code(self, lat: float, lon: float) -> int | None:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {"latitude": lat, "longitude": lon, "current": "weather_code"}
        try:
            response = session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get("current", {}).get("weather_code")
        except Exception:
            return None


def format_weather_code(code: int) -> str:
    codes = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Rain",
        65: "Heavy rain",
        71: "Slight snow",
        73: "Snow",
        75: "Heavy snow",
        80: "Slight rain showers",
        81: "Rain showers",
        82: "Violent rain",
        95: "Thunderstorm",
        96: "Thunderstorm with hail",
        99: "Thunderstorm heavy hail",
    }
    return codes.get(code, f"Code {code}")
