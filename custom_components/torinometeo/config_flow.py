"""Configure a TorinoMeteo station from the Home Assistant UI."""

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SLUG_PATTERN, StationNotFound, TorinoMeteoClient, TorinoMeteoError
from .const import CONF_STATION, DOMAIN

DEFAULT_STATION = "torino-regio-parco"


class TorinoMeteoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Validate the station identifier before creating a configuration entry."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            slug = user_input[CONF_STATION].strip().lower()
            if not SLUG_PATTERN.fullmatch(slug):
                errors[CONF_STATION] = "invalid_station"
            else:
                await self.async_set_unique_id(slug)
                self._abort_if_unique_id_configured()
                client = TorinoMeteoClient(async_get_clientsession(self.hass))
                try:
                    observation = await client.async_observation(slug)
                except StationNotFound:
                    errors[CONF_STATION] = "station_not_found"
                except TorinoMeteoError:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title=f"TorinoMeteo {observation.station_name}",
                        data={CONF_STATION: slug},
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_STATION, default=DEFAULT_STATION): str,
            }),
            errors=errors,
        )
