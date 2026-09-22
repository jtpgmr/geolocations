from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from src.models import CitySchema, StateModel
from src.schema import Base, State, City

import httpx2
from pydantic import BaseModel, Field, field_serializer

BASE = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "TIGERweb/Places_CouSub_ConCity_SubMCD/MapServer"
)

BASE_URL: Final = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb"


def generateURL(service: str, layer: int | str):
    return f"{BASE_URL}/{service}/MapServer/{layer}/query"


class GeoTypeNames(StrEnum):
    CITY = "city"
    STATE = "state"


GEO_TYPE_ORDER = {
    GeoTypeNames.STATE: 0,
    GeoTypeNames.CITY: 1,
}


@dataclass
class GeoType:
    name: GeoTypeNames
    db_schema: type[Base]
    model: type[BaseModel]


class TigerWebEndpointParams(BaseModel):
    out_fields: list[str] = Field(alias="outFields")
    return_geometry: bool = Field(default=False, alias="returnGeometry")
    where: str = "1=1"
    f: str = "json"

    @field_serializer("out_fields")
    def serialize_out_fields(self, out_fields) -> str:
        return ",".join(out_fields)


class TigerWebEndpoint(BaseModel):
    geotype: GeoType
    service: str
    layer: str | int
    params: TigerWebEndpointParams


TIGER_WEB_ENDPOINTS: list[TigerWebEndpoint] = [
    TigerWebEndpoint(
        geotype=GeoType(name=GeoTypeNames.STATE, db_schema=State, model=StateModel),
        service="State_County",
        layer=0,
        params=TigerWebEndpointParams(
            outFields=[
                "NAME",
                "STATE",
                "STUSAB",
            ]
        ),
    ),
    TigerWebEndpoint(
        geotype=GeoType(name=GeoTypeNames.CITY, db_schema=City, model=CitySchema),
        service="Places_CouSub_ConCity_SubMCD",
        layer=4,
        params=TigerWebEndpointParams(
            outFields=["GEOID", "STATE", "BASENAME", "NAME", "CENTLAT", "CENTLON"]
        ),
    ),
    TigerWebEndpoint(
        geotype=GeoType(name=GeoTypeNames.CITY, db_schema=City, model=CitySchema),
        service="Places_CouSub_ConCity_SubMCD",
        layer=5,
        params=TigerWebEndpointParams(
            outFields=["GEOID", "STATE", "BASENAME", "NAME", "CENTLAT", "CENTLON"]
        ),
    ),
]


if __name__ == "__main__":
    TIGER_WEB_ENDPOINTS.sort(key=lambda endpoint: GEO_TYPE_ORDER[endpoint.geotype.name])

    for tw_endpoint in TIGER_WEB_ENDPOINTS:
        tw_endpoint: TigerWebEndpoint

        url = generateURL(tw_endpoint.service, tw_endpoint.layer)
        params = tw_endpoint.params.model_dump(by_alias=True)

        response = httpx2.get(url, params=params)
        response.raise_for_status()

        location_data = [
            feature["attributes"] for feature in response.json()["features"]
        ]

        print(len(location_data))
