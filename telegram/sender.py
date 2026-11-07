import requests
from datetime import datetime
from weather.base import WeatherData, CurrentWeather, ForecastDay


ATTRIBUTE_LABELS = {
    "temperature_2m": ("Temperature", "°C", "🌡️"),
    "apparent_temperature": ("Feels like", "°C", "🌡️"),
    "relative_humidity_2m": ("Humidity", "%", "💧"),
    "dew_point_2m": ("Dew point", "°C", "💧"),
    "precipitation": ("Precipitation", " mm", "🌧️"),
    "rain": ("Rain", " mm", "🌧️"),
    "showers": ("Showers", " mm", "🌧️"),
    "snowfall": ("Snowfall", " cm", "❄️"),
    "cloud_cover": ("Cloud cover", "%", "☁️"),
    "sea_level_pressure": ("Pressure", " hPa", "📊"),
    "surface_pressure": ("Surface pressure", " hPa", "📊"),
    "wind_speed_10m": ("Wind", " km/h", "💨"),
    "wind_direction_10m": ("Wind direction", "°", "💨"),
    "wind_gusts_10m": ("Wind gusts", " km/h", "💨"),
    "weather_code": ("Condition", "", "🌤️"),
    "is_day": ("Day/Night", "", "🌙"),
    "temperature_2m_max": ("High", "°C", "⬆️"),
    "temperature_2m_min": ("Low", "°C", "⬇️"),
    "temperature_2m_mean": ("Mean temp", "°C", "🌡️"),
    "apparent_temperature_max": ("Feels high", "°C", "🌡️"),
    "apparent_temperature_min": ("Feels low", "°C", "🌡️"),
    "precipitation_sum": ("Precipitation", " mm", "🌧️"),
    "rain_sum": ("Rain", " mm", "🌧️"),
    "snowfall_sum": ("Snow", " cm", "❄️"),
    "precipitation_probability_max": ("Rain chance", "%", "🌧️"),
    "sunrise": ("Sunrise", "", "🌅"),
    "sunset": ("Sunset", "", "🌇"),
    "daylight_duration": ("Daylight", "h", "☀️"),
    "sunshine_duration": ("Sunshine", "h", "☀️"),
    "wind_speed_10m_max": ("Max wind", " km/h", "💨"),
    "wind_gusts_10m_max": ("Max gusts", " km/h", "💨"),
    "wind_direction_10m_dominant": ("Wind dir", "°", "💨"),
    "uv_index_max": ("UV index", "", "🔆"),
}


class TelegramSender:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{token}"

    def send(self, text: str) -> bool:
        url = f"{self.api_url}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"}
        try:
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception:
            return False

    def send_weather(self, weather: WeatherData) -> bool:
        text = self.format_weather_message(weather)
        return self.send(text)

    def format_weather_message(self, weather: WeatherData) -> str:
        lines = []
        location = weather.location
        date_str = datetime.now().strftime("%a %b %d, %Y")
        lines.append(f"🌤️ *{location} Weather* - {date_str}\n")

        if weather.current and weather.current.data:
            lines.append("*Current:*")
            for param, label_unit_emoji in ATTRIBUTE_LABELS.items():
                if param in weather.current.data:
                    value = weather.current.data[param]
                    label, unit, emoji = label_unit_emoji
                    if param == "weather_code":
                        from weather.openmeteo import format_weather_code

                        value_str = format_weather_code(value)
                        lines.append(f"{emoji} {label}: {value_str}")
                    elif param == "is_day":
                        lines.append(f"{emoji} {'Day' if value == 1 else 'Night'}")
                    elif param in ("sunrise", "sunset"):
                        lines.append(f"{emoji} {label}: {value}")
                    else:
                        lines.append(f"{emoji} {label}: {value}{unit}")
            lines.append("")

        if weather.forecast:
            for day in weather.forecast:
                day_name = self._format_day_name(day.date)
                lines.append(f"*Forecast ({day_name}):*")
                for param, label_unit_emoji in ATTRIBUTE_LABELS.items():
                    if param in day.data:
                        value = day.data[param]
                        label, unit, emoji = label_unit_emoji
                        if param == "weather_code":
                            from weather.openmeteo import format_weather_code

                            value_str = format_weather_code(value)
                            lines.append(f"{emoji} {label}: {value_str}")
                        elif param in ("sunrise", "sunset"):
                            lines.append(f"{emoji} {label}: {value}")
                        elif param == "daylight_duration":
                            hours = value / 3600
                            lines.append(f"{emoji} {label}: {hours:.1f}h")
                        elif param == "sunshine_duration":
                            hours = value / 3600
                            lines.append(f"{emoji} {label}: {hours:.1f}h")
                        else:
                            lines.append(f"{emoji} {label}: {value}{unit}")
                lines.append("")

        return "\n".join(lines).strip()

    def _format_day_name(self, date_str: str) -> str:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            today = datetime.now()
            if dt.date() == today.date():
                return "Today"
            elif dt.date() == today.date().__add__(
                __import__("datetime").timedelta(days=1)
            ):
                return "Tomorrow"
            return dt.strftime("%a")
        except Exception:
            return date_str
