from __future__ import annotations
import logging
from functools import reduce
from collections.abc import Sequence
from shapely import make_valid, symmetric_difference_all

from abc import ABC, abstractmethod
from typing import Annotated

from geoalchemy2 import WKBElement
from geoalchemy2.shape import from_shape
from pydantic import (
    BaseModel,
    Field,
    InstanceOf,
    PositiveInt,
    computed_field,
    field_serializer,
)
from pydantic_extra_types.coordinate import (
    Latitude as PydanticLatitude,
)
from pydantic_extra_types.coordinate import (
    Longitude as PydanticLongitude,
)
from shapely.geometry import Point, MultiPolygon, Polygon

from src.constants import EPSG, GeoTypeNames

__all__ = [
    "COMMON_TIGERWEB_OUT_FIELDS",
    "City",
    "County",
    "GeoTypeModel",
    "LocationModel",
    "LocationGeometriesModel",
    "State",
    "TigerWebEndpoint",
    "TigerWebEndpointParams",
]
# "BASENAME", "STATE", "STUSAB", "CENTLAT", "CENTLON"

logger: logging.Logger = logging.getLogger(__name__)


Name = Annotated[str, Field(validation_alias="BASENAME")]
CentroidLatitude = Annotated[PydanticLatitude, Field(validation_alias="CENTLAT")]
CentroidLongitude = Annotated[PydanticLongitude, Field(validation_alias="CENTLON")]
StateTigerWebNumber = Annotated[
    str, Field(alias="state_number", validation_alias="STATE")
]
TigerWebNumber = lambda alias_geotype, validation_alias="GEOID": Field(
    alias=f"{alias_geotype}_number",
    validation_alias=validation_alias,
)


class NearbyCitiesSchema(BaseModel):
    city: str
    county: str
    state_code: str
    km_within: PositiveInt


class NearbyCitiesByCoordsSchema(BaseModel):
    lat: PydanticLatitude
    long: PydanticLongitude
    km_within: PositiveInt


class GeoTypeModel(BaseModel, ABC):
    name: Name
    # latitude: CentroidLatitude
    # longitude: CentroidLongitude
    tigerweb_number: str

    # @computed_field
    # def geo_point(self) -> InstanceOf[WKBElement]:
    #     # x = longitude, y = latitude
    #     return from_shape(Point(self.longitude, self.latitude), srid=EPSG)

    def to_orm(self, **kwargs) -> dict:
        return {
            "name": self.name,
            "tigerweb_number": self.tigerweb_number,
            # "geo_point": self.geo_point,
        }

    def toOrmAttributes(self, **kwargs) -> dict:
        return {
            "name": self.name,
            "tigerweb_number": self.tigerweb_number,
            # "geo_point": self.geo_point,
        }


class LocationGeometriesModel(BaseModel, ABC):
    central_latitude: CentroidLatitude
    central_longitude: CentroidLongitude
    rings: Sequence[Sequence[Sequence[float]]] | None

    @computed_field
    def centroid(self) -> InstanceOf[WKBElement]:
        # x = longitude, y = latitude
        return from_shape(
            Point(self.central_longitude, self.central_latitude), srid=EPSG
        )

    @computed_field
    def boundary(
        self,
        # rings: Sequence[Sequence[Sequence[float]]],
    ) -> InstanceOf[WKBElement] | None:
        """Convert ArcGIS polygon `rings` into a MultiPolygon.

        Rings are combined with the even-odd rule (symmetric difference), so holes
            are cut out of their shells regardless of winding order.
        """
        if not self.rings:
            return None

        count_invalid_polygons: int = 0
        # polygons: list[Polygon] = [
        #     make_valid(Polygon(ring)) for ring in self.rings if len(ring) >= 4
        # ]
        polygons: list[Polygon] = []

        for ring in self.rings:
            if len(ring) >= 4:
                polygons.append(make_valid(Polygon(ring)))
                continue
            count_invalid_polygons += 1

        if count_invalid_polygons:
            logger.warning(f"{count_invalid_polygons} invalid polygons found")

        if not polygons:
            raise ValueError("No usable rings (each needs at least 4 points)")

        shape: Polygon | MultiPolygon = reduce(
            lambda a, b: a.symmetric_difference(b), polygons
        )

        if isinstance(shape, Polygon):
            shape = MultiPolygon([shape])
        # if isinstance(shape, MultiPolygon):
        #     return shape
        return from_shape(shape, EPSG)

    def toOrmGeometries(self, **kwargs) -> dict:
        return {
            "centroid": self.centroid,
            "boundary": self.boundary,
        }


class LocationModel(GeoTypeModel, LocationGeometriesModel):
    pass


class State(LocationModel):
    abbreviation: str = Field(validation_alias="STUSAB")
    # tigerweb_number: str = TigerWebNumber(
    #     GeoTypeNames.STATE.lower(), GeoTypeNames.STATE.upper()
    # )
    tigerweb_number: StateTigerWebNumber

    def toOrmAttributes(self, **kwargs) -> dict:
        return {"abbreviation": self.abbreviation, **super().to_orm()}


# Shared Class for County and City
class SubStateRegion(GeoTypeModel, ABC):
    state_tigerweb_number: StateTigerWebNumber
    latitude: CentroidLatitude
    longitude: CentroidLongitude

    def to_orm(self, **kwargs) -> dict:
        return {"state_id": kwargs["state_id"], **super().to_orm()}


# https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1/query?outFields=GEOID%2CSTATE%2CCOUNTY%2CBASENAME%2CNAME%2CCENTLAT%2CCENTLON&returnGeometry=false&where=1%3D1&f=json
# TODO: use geolocational data to map city-county mapping with data from us_cities.csv file
class County(SubStateRegion):
    # county: Name
    tigerweb_number: str = TigerWebNumber(GeoTypeNames.COUNTY)


class City(SubStateRegion):
    # city: Name
    tigerweb_number: str = TigerWebNumber(GeoTypeNames.CITY)


COMMON_TIGERWEB_OUT_FIELDS = ["BASENAME", "STATE", "CENTLAT", "CENTLON"]


class TigerWebEndpointParams(BaseModel):
    out_fields: list[str] = Field(default=COMMON_TIGERWEB_OUT_FIELDS, alias="outFields")
    # TODO: Expand data collection to account for polygon/boundary geometries
    return_geometry: bool = Field(default=False, alias="returnGeometry")
    where: str = "1=1"
    f: str = "json"
    # output Spatial Referemce (coordinate system being used)
    out_sr: int | None = Field(default=None, alias="outSR")
    max_allowable_offset: float | None = Field(default=None, alias="maxAllowableOffset")

    @field_serializer("out_fields")
    def serialize_out_fields(self, out_fields) -> str:
        return ",".join(out_fields)


class TigerWebEndpoint(BaseModel):
    service: str
    layer: str | int
    params: TigerWebEndpointParams
