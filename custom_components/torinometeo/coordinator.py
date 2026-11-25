"""Independent polling for station observations and regional forecasts."""

from dataclasses import dataclass
import logging
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import Bulletin, Observation, TorinoMeteoClient, TorinoMeteoError
from .const import FORECAST_INTERVAL, REALTIME_INTERVAL

LOGGER = logging.getLogger(__name__)


class StationCoordinator(DataUpdateCoordinator[Observation]):
    """Poll the latest report for the configured station."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: TorinoMeteoClient, slug: str
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"TorinoMeteo {slug}",
            update_interval=REALTIME_INTERVAL,
        )
        self._client = client
        self._slug = slug

    async def _async_update_data(self) -> Observation:
        try:
            return await self._client.async_observation(self._slug)
        except TorinoMeteoError as err:
            raise UpdateFailed(str(err)) from err


class BulletinCoordinator(DataUpdateCoordinator[Bulletin]):
    """Poll the same regional bulletin once for all configured stations."""

    def __init__(self, hass: HomeAssistant, client: TorinoMeteoClient) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=None,
            name="TorinoMeteo bollettino",
            update_interval=FORECAST_INTERVAL,
        )
        self._client = client

    async def _async_update_data(self) -> Bulletin:
        try:
            return await self._client.async_bulletin()
        except TorinoMeteoError as err:
            raise UpdateFailed(str(err)) from err


@dataclass
class RuntimeData:
    station: StationCoordinator
    bulletin: BulletinCoordinator
    timezone: ZoneInfo
    client: TorinoMeteoClient
