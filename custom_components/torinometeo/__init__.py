"""TorinoMeteo custom integration for Home Assistant."""

from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TorinoMeteoClient
from .const import CONF_STATION, DOMAIN
from .coordinator import BulletinCoordinator, RuntimeData, StationCoordinator

PLATFORMS = [Platform.WEATHER, Platform.IMAGE]
type TorinoMeteoConfigEntry = ConfigEntry[RuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: TorinoMeteoConfigEntry) -> bool:
    """Set up one station and subscribe to the regional bulletin."""
    client = TorinoMeteoClient(async_get_clientsession(hass))
    station = StationCoordinator(hass, entry, client, entry.data[CONF_STATION])
    await station.async_config_entry_first_refresh()

    timezone = await hass.async_add_executor_job(ZoneInfo, "Europe/Rome")
    bulletin = hass.data.get(DOMAIN)
    if bulletin is None:
        bulletin = hass.data[DOMAIN] = BulletinCoordinator(hass, client)
        await bulletin.async_register_shutdown()
    if bulletin.data is None:
        await bulletin.async_refresh()

    entry.runtime_data = RuntimeData(station, bulletin, timezone, client)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TorinoMeteoConfigEntry) -> bool:
    """Unload the weather platform and its coordinator listeners."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
