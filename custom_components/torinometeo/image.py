"""Still webcam images for TorinoMeteo stations."""

from __future__ import annotations

from asyncio import Lock
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import WebcamSnapshot
from .const import CONF_STATION
from .coordinator import RuntimeData, StationCoordinator

if TYPE_CHECKING:
    from . import TorinoMeteoConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TorinoMeteoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add a webcam image when the station publishes a supported URL."""
    runtime = entry.runtime_data
    if runtime.station.data.webcam_urls:
        async_add_entities([TorinoMeteoWebcam(hass, runtime, entry.data[CONF_STATION])])


class TorinoMeteoWebcam(CoordinatorEntity[StationCoordinator], ImageEntity):
    """Serve the station's snapshot on demand through Home Assistant."""

    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, runtime: RuntimeData, slug: str) -> None:
        CoordinatorEntity.__init__(self, runtime.station)
        ImageEntity.__init__(self, hass, verify_ssl=True)
        self._attr_name = f"{runtime.station.data.station_name} Webcam"
        self._attr_unique_id = f"{slug}_webcam"
        self._attr_image_last_updated = datetime.now(UTC)
        self._api = runtime.client
        self._image_lock = Lock()
        self._requested: tuple[datetime, tuple[str, ...]] | None = None
        self._snapshot: WebcamSnapshot | None = None

    @property
    def available(self) -> bool:
        """A temporary realtime API failure leaves the known webcam URL usable."""
        return bool(self.coordinator.data.webcam_urls)

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_image_last_updated = datetime.now(UTC)
        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        """Load at most one snapshot per coordinator update."""
        async with self._image_lock:
            urls = self.coordinator.data.webcam_urls
            request = (self._attr_image_last_updated, urls)
            if request != self._requested:
                self._snapshot = await self._api.async_webcam(urls)
                self._requested = request
            if self._snapshot is None:
                return None
            self._attr_content_type = self._snapshot.content_type
            return self._snapshot.content
