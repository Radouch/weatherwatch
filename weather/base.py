from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class Coordinates:
    latitude: float
    longitude: float
    name: str = ""


@dataclass
class CurrentWeather:
    data: dict[str, Any]


@dataclass
class ForecastDay:
    date: str
    data: dict[str, Any]


@dataclass
class WeatherData:
    location: str
    current: CurrentWeather | None
    forecast: list[ForecastDay]


class WeatherSource(ABC):
    @abstractmethod
    def get_current(
        self, lat: float, lon: float, params: list[str]
    ) -> CurrentWeather | None:
        pass

    @abstractmethod
    def get_forecast(
        self, lat: float, lon: float, params: list[str], days: int
    ) -> list[ForecastDay]:
        pass
