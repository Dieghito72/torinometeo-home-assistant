"""Constants for TorinoMeteo."""

from datetime import timedelta

DOMAIN = "torinometeo"
CONF_STATION = "station"
API_URL = "https://www.torinometeo.org/api/v1"
REALTIME_INTERVAL = timedelta(minutes=10)
FORECAST_INTERVAL = timedelta(hours=1)
