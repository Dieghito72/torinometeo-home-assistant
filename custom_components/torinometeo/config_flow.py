"""Configure a TorinoMeteo station from the Home Assistant UI."""

from collections import Counter
from urllib.parse import unquote, urlsplit

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorMode,
)

from .api import SLUG_PATTERN, StationNotFound, TorinoMeteoClient, TorinoMeteoError
from .const import CONF_STATION, DOMAIN

def _station_slug(value: str) -> str | None:
    """Accept a station identifier or a TorinoMeteo station-page URL."""
    value = value.strip()
    if "://" in value:
        try:
            url = urlsplit(value)
            path = url.path.strip("/").split("/")
            if (
                url.scheme not in {"http", "https"}
                or url.hostname not in {"torinometeo.org", "www.torinometeo.org"}
                or path[0] != "realtime"
                or len(path) < 2
            ):
                return None
            value = unquote(path[1])
        except ValueError:
            return None

    slug = value.lower()
    return slug if SLUG_PATTERN.fullmatch(slug) else None


class TorinoMeteoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Validate the station identifier before creating a configuration entry."""

    VERSION = 1
    _station_options: list[SelectOptionDict] | None = None

    async def async_step_user(self, user_input=None):
        errors = {}
        client = TorinoMeteoClient(async_get_clientsession(self.hass))
        if user_input is not None:
            slug = _station_slug(user_input[CONF_STATION])
            if slug is None:
                errors[CONF_STATION] = "invalid_station"
            else:
                await self.async_set_unique_id(slug)
                self._abort_if_unique_id_configured()
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

        if self._station_options is None:
            try:
                stations = await client.async_stations()
            except TorinoMeteoError:
                stations = {}
            name_counts = Counter(name.casefold() for name in stations.values())
            self._station_options = [
                {
                    "value": slug,
                    "label": f"{name} ({slug})" if name_counts[name.casefold()] > 1 else name,
                }
                for slug, name in sorted(
                    stations.items(), key=lambda item: (item[1].casefold(), item[0])
                )
            ]

        station_field = (
            SelectSelector({
                "options": self._station_options,
                "mode": SelectSelectorMode.DROPDOWN,
                "custom_value": True,
            })
            if self._station_options
            else str
        )
        schema = vol.Schema({vol.Required(CONF_STATION): station_field})
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )
