#!/usr/bin/env python3
import os
import sys
import json
import logging
import signal
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

import requests
import schedule
from dotenv import load_dotenv

from weather import OpenMeteoSource, geocode_city, WeatherData
from telegram.sender import TelegramSender
from scheduler.schedule import TimeScheduler


# Load secrets from a .env file (gitignored) next to the working directory.
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

CONFIG_PATH = os.environ.get("WEATHERWATCH_CONFIG", "config.json")


@dataclass
class Place:
    name: str
    city: str
    country: str | None = None
    admin1: str | None = None
    latitude: float = 0.0
    longitude: float = 0.0
    display_name: str = ""


class WeatherWatch:
    def __init__(self, config_path: str = CONFIG_PATH):
        self.config = self.load_config(config_path)
        self.places: list[Place] = []
        self.weather_source = OpenMeteoSource(self.config.get("units"))
        self.telegram = TelegramSender(
            self.config["telegram_token"], self.config["chat_id"]
        )
        # Only this chat may trigger bot commands; everything else is ignored.
        self.authorized_chat_id = str(self.config["chat_id"])
        self.scheduler = TimeScheduler(self.config.get("schedule", []))
        self.running = True
        self.last_update_id = 0

    def load_config(self, path: str) -> dict:
        config_file = Path(path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(config_file) as f:
            config = json.load(f)

        # Secrets must live outside version control. Resolution order:
        # environment (or .env) first, config.json kept as a legacy fallback.
        config["telegram_token"] = (
            os.environ.get("TELEGRAM_TOKEN") or config.get("telegram_token", "")
        )
        config["chat_id"] = os.environ.get("CHAT_ID") or config.get("chat_id", "")

        required = ["telegram_token", "chat_id"]
        missing = [k for k in required if not config.get(k)]
        if missing:
            raise ValueError(
                f"Missing required config keys: {missing}. "
                "Set TELEGRAM_TOKEN and CHAT_ID in the .env file or in the "
                "environment instead of config.json."
            )

        if "places" not in config:
            raise ValueError("Missing required config key: places")

        return config

    def setup(self):
        self.places = self._parse_places(self.config["places"])
        logger.info(f"Setting up weather watch for {len(self.places)} places")

        for place in self.places:
            if place.latitude and place.longitude:
                logger.info(
                    f"  - {place.name}: {place.latitude}, {place.longitude} (from config)"
                )
            else:
                coords = geocode_city(place.city, place.country, place.admin1)
                place.latitude = coords.latitude
                place.longitude = coords.longitude
                place.display_name = coords.name
                logger.info(f"  - {place.name}: {coords.latitude}, {coords.longitude}")

        self.scheduler.schedule_job(self.send_weather_update)
        self.setup_telegram_bot()

    def _parse_places(self, places_config: list[dict]) -> list[Place]:
        places = []
        for p in places_config:
            name = p.get("name") or p.get("city")
            place = Place(
                name=name,
                city=p.get("city", name),
                country=p.get("country"),
                admin1=p.get("admin1"),
            )
            if "latitude" in p and "longitude" in p:
                place.latitude = p["latitude"]
                place.longitude = p["longitude"]
                place.display_name = p.get("name", p.get("city", ""))
            places.append(place)
        return places

    def test_telegram(self) -> bool:
        try:
            response = self.api_request("getMe")
            logger.info(f"Telegram bot verified: @{response['result']['username']}")

            response = self.api_request("getWebhookInfo")
            if response.get("result", {}).get("url"):
                logger.warning("Bot has webhook set - polling won't work!")
                return False

            logger.info("Telegram bot is ready (no webhook set)")
            return True
        except Exception as e:
            logger.error(f"Telegram test failed: {self._mask(str(e))}")
            return False

    def _mask(self, text: str) -> str:
        """Redact the bot token from error texts before logging.

        requests/urllib3 connection errors embed the full API URL path, which
        contains the bot token, so raw exception text must never hit the logs.
        """
        token = self.config.get("telegram_token", "")
        return text.replace(token, "<redacted>") if token else text

    def setup_telegram_bot(self):
        self.telegram_bot_token = self.config["telegram_token"]
        self.api_url = f"https://api.telegram.org/bot{self.telegram_bot_token}"

        if not self.test_telegram():
            logger.warning("Telegram bot may not receive commands - check for webhooks")

    def api_request(
        self,
        method: str,
        data: dict | None = None,
        request_timeout: float | tuple[float, float] = 10,
    ) -> dict:
        url = f"{self.api_url}/{method}"
        logger.debug(f"API request: {method}")
        response = requests.post(url, json=data or {}, timeout=request_timeout)
        if response.status_code != 200:
            logger.warning(
                f"API error {response.status_code}: {self._mask(response.text)}"
            )
        response.raise_for_status()
        return response.json()

    def get_weather(self, place: Place) -> WeatherData:
        current = self.weather_source.get_current(
            place.latitude, place.longitude, self.config.get("current_weather", [])
        )

        forecast = self.weather_source.get_forecast(
            place.latitude,
            place.longitude,
            self.config.get("forecast", []),
            self.config.get("forecast_days", 3),
        )

        return WeatherData(
            location=place.display_name or place.name,
            current=current,
            forecast=forecast,
        )

    def send_weather_update(self):
        logger.info("Fetching weather update for all places...")
        for place in self.places:
            try:
                weather = self.get_weather(place)
                success = self.telegram.send_weather(weather)
                if success:
                    logger.info(f"Weather update for {place.name} sent successfully")
                else:
                    logger.error(f"Failed to send weather update for {place.name}")
            except Exception as e:
                logger.exception(f"Error sending weather update for {place.name}: {e}")

    def handle_telegram_updates(self):
        try:
            response = self.api_request(
                "getUpdates",
                {"offset": self.last_update_id + 1, "timeout": 10},
                request_timeout=(5, 15),
            )
            updates = response.get("result", [])

            if updates:
                logger.info(f"Received {len(updates)} Telegram updates")

            for update in updates:
                self.last_update_id = max(self.last_update_id, update["update_id"])
                if "message" not in update:
                    continue
                message = update["message"]
                chat_id = message["chat"]["id"]

                # Only the configured chat may trigger actions. Without this
                # check, anyone who finds the bot username could spam weather
                # fetches and receive a confirmation in their own chat.
                if str(chat_id) != self.authorized_chat_id:
                    logger.warning(f"Ignored message from unauthorized chat: {chat_id}")
                    continue

                text = message.get("text", "")
                logger.info(f"Message from {chat_id}: {text}")

                if text == "/weather":
                    logger.info("Processing /weather command")
                    self.send_weather_update()
                    self.api_request(
                        "sendMessage",
                        {
                            "chat_id": chat_id,
                            "text": "Weather update sent!",
                        },
                    )
                elif text == "/start":
                    self.api_request(
                        "sendMessage",
                        {
                            "chat_id": chat_id,
                            "text": "WeatherWatch bot is running! Use /weather to get current weather.",
                        },
                    )
        except Exception as e:
            logger.warning(f"Telegram polling error: {self._mask(str(e))}")

    def run(self):
        self.setup()

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info("WeatherWatch started")

        while self.running:
            self.scheduler.run_pending()
            self.handle_telegram_updates()

    def _signal_handler(self, sig, frame):
        logger.info("Shutting down...")
        self.running = False


def main():
    try:
        app = WeatherWatch()
        app.run()
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
