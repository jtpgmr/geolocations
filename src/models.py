from __future__ import annotations
from uuid import UUID
from typing import Annotated
from geoalchemy2.shape import to_shape
from geoalchemy2 import Geometry, WKBElement
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from pydantic import (
    BaseModel,
    PositiveInt,
    Field,
    ConfigDict,
    computed_field,
    InstanceOf,
)
from pydantic_extra_types.coordinate import (
    Latitude as PydanticLatitude,
    Longitude as PydanticLongitude,
)

from src.schema import States
from src.constants import EPSG

__all__ = ["City", "County", "State"]
# "BASENAME", "STATE", "STUSAB", "CENTLAT", "CENTLON"

Name = Annotated[str, Field(validation_alias="BASENAME")]
Latitude = Annotated[PydanticLatitude, Field(validation_alias="CENTLAT")]
Longitude = Annotated[PydanticLongitude, Field(validation_alias="CENTLON")]
StateTigerWebNumber = Annotated[
    str, Field(alias="state_number", validation_alias="STATE")
]


class NearbyCitiesSchema(BaseModel):
    city: str
    county: str
    state_code: str
    km_within: PositiveInt


class NearbyCitiesByCoordsSchema(BaseModel):
    lat: Latitude
    long: Longitude
    km_within: PositiveInt


class State(BaseModel):
    name: Name
    abbreviation: str = Field(validation_alias="STUSAB")
    latitude: Latitude
    longitude: Longitude
    tigerweb_number: str = Field(alias="state_number", validation_alias="STATE")

    @computed_field
    def geo_point(self) -> InstanceOf[WKBElement]:
        # x = longitude, y = latitude
        return from_shape(Point(self.longitude, self.latitude), srid=EPSG)

    def to_orm(self) -> dict:
        return {
            "name": self.name,
            "abbreviation": self.abbreviation,
            "tigerweb_number": self.tigerweb_number,
            "geo_point": self.geo_point,
        }


# https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1/query?outFields=GEOID%2CSTATE%2CCOUNTY%2CBASENAME%2CNAME%2CCENTLAT%2CCENTLON&returnGeometry=false&where=1%3D1&f=json
class County(BaseModel):
    """"""


class City(BaseModel):
    city: Name
    # TODO: use geolocational data to map city-county mapping with data from us_cities.csv file
    # county: str
    state_tigerweb_number: StateTigerWebNumber
    latitude: Latitude
    longitude: Longitude
    tigerweb_number: str = Field(alias="city_number", validation_alias="GEOID")

    @computed_field
    def geo_point(self) -> InstanceOf[WKBElement]:
        # x = longitude, y = latitude
        return from_shape(Point(self.longitude, self.latitude), srid=EPSG)

    def to_orm(self, state_id: UUID) -> dict:
        return {
            "state_id": state_id,
            "name": self.city,
            "tigerweb_number": self.tigerweb_number,
            "geo_point": self.geo_point,
        }
