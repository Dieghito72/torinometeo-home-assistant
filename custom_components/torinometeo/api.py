"""Client and validated API response parsing for TorinoMeteo."""

from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
import math
import re
from typing import Any
from urllib.parse import urljoin, urlsplit

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import API_URL

SLUG_PATTERN = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")
SYMBOLS = {
    "clearsky": "sunny",
    "fair": "partlycloudy",
    "partlycloudy": "partlycloudy",
    "cloudy": "cloudy",
    "fog": "fog",
    "sunny": "sunny",
    "clear": "sunny",
    "lightrain": "rainy",
    "rain": "rainy",
    "heavyrain": "pouring",
    "lightsleet": "snowy-rainy",
    "sleet": "snowy-rainy",
    "heavysleet": "snowy-rainy",
    "lightsnow": "snowy",
    "snow": "snowy",
    "heavysnow": "snowy",
}
SIMPLE_CONDITIONS = {
    "sereno": "sunny",
    "cielo sereno": "sunny",
    "soleggiato": "sunny",
    "tempo soleggiato": "sunny",
    "poco nuvoloso": "partlycloudy",
    "parzialmente nuvoloso": "partlycloudy",
    "nuvoloso": "cloudy",
    "molto nuvoloso": "cloudy",
    "coperto": "cloudy",
    "nebbia": "fog",
    "pioggia": "rainy",
    "piogge": "rainy",
    "rovesci": "rainy",
    "temporali": "lightning-rainy",
    "neve": "snowy",
    "neve mista a pioggia": "snowy-rainy",
}
TEMPERATURE_PAIR = re.compile(
    r"(?:temperature\s*:\s*)?"
    r"(minim[ae]|massim[ae])\s*:?\s*([+−-]?\d+(?:[.,]\d+)?)\s*°\s*C?"
    r"\s*[,;/]\s*"
    r"(minim[ae]|massim[ae])\s*:?\s*([+−-]?\d+(?:[.,]\d+)?)\s*°\s*C?\.?",
    re.IGNORECASE,
)


class TorinoMeteoError(Exception):
    """The service could not supply the expected data."""


class StationNotFound(TorinoMeteoError):
    """The station has no observation or could not be found."""


class _PlainText(HTMLParser):
    """Convert the formatting used in the bulletin to plain text."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in {"br", "p", "div", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div", "li"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _plain_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    parser = _PlainText()
    parser.feed(value)
    parser.close()
    return "\n".join(
        line for raw in "".join(parser.parts).splitlines()
        if (line := " ".join(raw.split()))
    )


def _number(value: Any) -> float | None:
    if isinstance(value, str):
        value = value.strip().replace(",", ".").replace("−", "-")
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _icon_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        url = urljoin(API_URL, value.strip())
        parts = urlsplit(url)
        if parts.scheme in {"http", "https"} and parts.hostname:
            return url
    except ValueError:
        pass
    return None


def _simple_condition(text: str) -> str | None:
    return SIMPLE_CONDITIONS.get(text.casefold().strip(" .!"))


def _observed_condition(icon: dict[str, Any]) -> str | None:
    url = _icon_url(icon.get("icon"))
    if url:
        filename = urlsplit(url).path.rsplit("/", 1)[-1].split(".", 1)[0].lower()
        symbol, _, period = filename.partition("_")
        if symbol in {"clearsky", "clear", "sunny"} and period == "night":
            return "clear-night"
        if symbol.endswith("andthunder"):
            return "lightning-rainy"
        condition = SYMBOLS.get(symbol.removesuffix("showers"))
        if condition:
            return condition
    return _simple_condition(_plain_text(icon.get("text")))


@dataclass(frozen=True)
class Observation:
    """Latest measurements and weather symbol for a single station."""

    station_name: str
    observed_at: datetime
    condition: str | None
    condition_text: str
    temperature: float | None
    humidity: float | None
    pressure: float | None
    dewpoint: float | None
    wind_speed: float | None
    wind_bearing: float | None


@dataclass(frozen=True)
class ForecastDay:
    """A date and the publisher's regional outlook for that date."""

    date: date
    text: str
    temperatures: str
    winds: str
    reliability: float | None
    image12: str | None
    image24: str | None

    @property
    def condition(self) -> str | None:
        return _simple_condition(self.text)

    @property
    def temperature_pair(self) -> tuple[float | None, float | None]:
        """Extract only a single explicit low/high pair in degrees Celsius."""
        match = TEMPERATURE_PAIR.fullmatch(" ".join(self.temperatures.split()))
        if match:
            first_label, first, second_label, second = match.groups()
            values = {
                first_label.casefold()[:3]: _number(first),
                second_label.casefold()[:3]: _number(second),
            }
            low, high = values.get("min"), values.get("mas")
            if low is not None and high is not None and low <= high:
                return low, high
        return None, None


@dataclass(frozen=True)
class Bulletin:
    """The latest published regional bulletin."""

    date: date
    pattern: str
    days: tuple[ForecastDay, ...]


def parse_observation(payload: Any, slug: str) -> Observation:
    if not isinstance(payload, dict):
        raise TorinoMeteoError("Risposta realtime inattesa")
    station = payload.get("station")
    if not isinstance(station, dict) or station.get("slug") != slug:
        raise TorinoMeteoError("La rilevazione non corrisponde alla stazione richiesta")
    try:
        observed_at = datetime.fromisoformat(payload["datetime"])
    except (KeyError, TypeError, ValueError) as err:
        raise TorinoMeteoError("Data della rilevazione non valida") from err
    icon = payload.get("weather_icon")
    if not isinstance(icon, dict):
        icon = {}
    bearing = _number(payload.get("wind_dir"))
    return Observation(
        station_name=_plain_text(station.get("name")) or slug,
        observed_at=observed_at,
        condition=_observed_condition(icon),
        condition_text=_plain_text(icon.get("text")),
        temperature=_number(payload.get("temperature")),
        humidity=_number(payload.get("relative_humidity")),
        pressure=_number(payload.get("pressure")),
        dewpoint=_number(payload.get("dewpoint")),
        wind_speed=_number(payload.get("wind_strength")),
        wind_bearing=bearing if bearing is not None and 0 <= bearing <= 360 else None,
    )


def parse_bulletin(payload: Any) -> Bulletin:
    if not isinstance(payload, dict) or not isinstance(payload.get("day_forecasts"), list):
        raise TorinoMeteoError("Risposta del bollettino inattesa")
    try:
        issued_on = date.fromisoformat(payload["date"])
    except (KeyError, TypeError, ValueError) as err:
        raise TorinoMeteoError("Data del bollettino non valida") from err

    days = {}
    for item in payload["day_forecasts"]:
        if not isinstance(item, dict):
            continue
        try:
            day = date.fromisoformat(item["date"])
        except (KeyError, TypeError, ValueError):
            continue
        days[day] = ForecastDay(
            date=day,
            text=_plain_text(item.get("text")),
            temperatures=_plain_text(item.get("temperatures")),
            winds=_plain_text(item.get("winds")),
            reliability=_number(item.get("reliability")),
            image12=_icon_url(item.get("image12")),
            image24=_icon_url(item.get("image24")),
        )
    if payload["day_forecasts"] and not days:
        raise TorinoMeteoError("Il bollettino contiene solo giorni non validi")
    return Bulletin(issued_on, _plain_text(payload.get("pattern")), tuple(
        days[day] for day in sorted(days)
    ))


class TorinoMeteoClient:
    """Read public TorinoMeteo endpoints through the shared HA session."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session

    async def async_observation(self, slug: str) -> Observation:
        if not SLUG_PATTERN.fullmatch(slug):
            raise StationNotFound("Identificativo della stazione non valido")
        payload = await self._async_get(f"realtime/data/{slug}", station=True)
        if payload is None or payload == []:
            raise StationNotFound("Nessuna rilevazione per la stazione")
        return parse_observation(payload, slug)

    async def async_bulletin(self) -> Bulletin:
        return parse_bulletin(await self._async_get("forecast/get-last/"))

    async def _async_get(self, path: str, *, station: bool = False) -> Any:
        try:
            async with self._session.get(
                f"{API_URL}/{path}",
                headers={"Accept": "application/json"},
                timeout=ClientTimeout(total=15),
            ) as response:
                if station and response.status in {404, 204}:
                    raise StationNotFound("Nessuna rilevazione per la stazione")
                response.raise_for_status()
                return await response.json()
        except (ClientError, TimeoutError, ValueError) as err:
            raise TorinoMeteoError(f"Richiesta {path} fallita: {err}") from err
