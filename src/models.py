from geoalchemy2.shape import to_shape
from pydantic import BaseModel, PositiveInt, field_validator, Field
from pydantic_extra_types.coordinate import Latitude, Longitude

__all__ = ["City", "State"]


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
    name: str
    abbreviation: str
    latitude: float
    longitude: float
    tigerweb_number: str | int


# https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1/query?outFields=GEOID%2CSTATE%2CCOUNTY%2CBASENAME%2CNAME%2CCENTLAT%2CCENTLON&returnGeometry=false&where=1%3D1&f=json
class County(BaseModel):
    """"""


class City(BaseModel):
    city: str
    county: str
    state_tigerweb_number: str
    latitude: float
    longitude: float
    tigerweb_geoid: str = Field(alias="geoid")
    # geo_location: str

    # @field_validator("geo_location", mode="before")
    # def turn_geo_location_into_wkt(cls, value):
    #     return to_shape(value).wkt
