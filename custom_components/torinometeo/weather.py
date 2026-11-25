"""Weather entity combining a station with TorinoMeteo's regional outlook."""

from __future__ import annotations

from datetime import UTC, datetime, time
from typing import TYPE_CHECKING, Any

from homeassistant.components.weather import Forecast, WeatherEntity, WeatherEntityFeature
from homeassistant.const import UnitOfPressure, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import ForecastDay
from .const import CONF_STATION
from .coordinator import RuntimeData, StationCoordinator

if TYPE_CHECKING:
    from . import TorinoMeteoConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TorinoMeteoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add one weather entity for this station."""
    async_add_entities([
        TorinoMeteoWeather(entry.runtime_data, entry.title, entry.data[CONF_STATION])
    ])


class TorinoMeteoWeather(CoordinatorEntity[StationCoordinator], WeatherEntity):
    """Expose station observations and serve the cached daily forecasts."""

    _attr_has_entity_name = True
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_supported_features = WeatherEntityFeature.FORECAST_DAILY

    def __init__(self, runtime: RuntimeData, name: str, slug: str) -> None:
        super().__init__(runtime.station)
        self._attr_name = name
        self._attr_unique_id = slug
        self._slug = slug
        self._bulletin = runtime.bulletin
        self._timezone = runtime.timezone
        self._apply_observation()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._bulletin.async_add_listener(self._async_bulletin_updated))

    @property
    def available(self) -> bool:
        """Keep the bulletin accessible during a station outage."""
        return super().available or bool(self._current_days())

    @callback
    def _apply_observation(self) -> None:
        observation = self.coordinator.data if self.coordinator.last_update_success else None
        self._attr_condition = observation.condition if observation else None
        self._attr_native_temperature = observation.temperature if observation else None
        self._attr_humidity = observation.humidity if observation else None
        self._attr_native_pressure = observation.pressure if observation else None
        self._attr_native_dew_point = observation.dewpoint if observation else None
        self._attr_native_wind_speed = observation.wind_speed if observation else None
        self._attr_wind_bearing = observation.wind_bearing if observation else None

    @callback
    def _handle_coordinator_update(self) -> None:
        self._apply_observation()
        super()._handle_coordinator_update()

    @callback
    def _async_bulletin_updated(self) -> None:
        self.async_write_ha_state()
        self.hass.async_create_task(self.async_update_listeners(["daily"]))

    def _current_days(self) -> list[ForecastDay]:
        bulletin = self._bulletin.data
        if bulletin is None:
            return []
        today = datetime.now(self._timezone).date()
        return [day for day in bulletin.days if day.date >= today]

    async def async_forecast_daily(self) -> list[Forecast]:
        """Return days from the latest published regional bulletin."""
        forecasts: list[Forecast] = []
        for day in self._current_days():
            local_noon = datetime.combine(day.date, time(12), self._timezone)
            forecast = Forecast(datetime=local_noon.astimezone(UTC).isoformat())
            if day.condition is not None:
                forecast["condition"] = day.condition
            low, high = day.temperature_pair
            if low is not None and high is not None:
                forecast["native_templow"] = low
                forecast["native_temperature"] = high
            forecasts.append(forecast)
        return forecasts

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the bulletin text and when the station last reported."""
        attrs: dict[str, Any] = {
            "attribution": "Misure e bollettino: TorinoMeteo. Icone realtime: MET Norway / Yr.",
            "station_slug": self._slug,
            "station_url": f"https://www.torinometeo.org/realtime/{self._slug}",
            "bulletin_url": "https://www.torinometeo.org/previsioni/",
            "bulletin_update_ok": self._bulletin.last_update_success,
        }
        if observation := self.coordinator.data:
            observed_at = observation.observed_at
            if observed_at.tzinfo is None:
                observed_at = observed_at.replace(tzinfo=self._timezone)
            attrs["observed_at"] = observed_at.isoformat()
            if self.coordinator.last_update_success and observation.condition_text:
                attrs["condition_text"] = observation.condition_text

        if bulletin := self._bulletin.data:
            attrs["bulletin_date"] = bulletin.date.isoformat()
            days = self._current_days()
            if days:
                attrs["bulletin_summary"] = bulletin.pattern
            attrs["bulletin_days"] = [
                {
                    "date": day.date.isoformat(),
                    "text": day.text,
                    "temperatures": day.temperatures,
                    "winds": day.winds,
                    "reliability": day.reliability,
                    "image12": day.image12,
                    "image24": day.image24,
                }
                for day in days
            ]
        return attrs
