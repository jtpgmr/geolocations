from enum import StrEnum

import httpx2

_DEFAULT_TIMEOUT_SECONDS: float = 10.0
_DEFAULT_TIMEOUT = httpx2.Timeout(_DEFAULT_TIMEOUT_SECONDS)

EPSG = 4326


class GeoTypeNames(StrEnum):
    CITY = "city"
    STATE = "state"
    COUNTY = "county"


GEO_TYPE_ORDER = {
    GeoTypeNames.STATE: 0,
    GeoTypeNames.CITY: 1,
    GeoTypeNames.COUNTY: 2,
}
