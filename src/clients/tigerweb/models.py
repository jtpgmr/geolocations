from __future__ import annotations

import logging
from abc import ABC
from collections.abc import Sequence
from functools import reduce
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
from shapely import get_parts, make_valid, unary_union
from shapely.geometry import MultiPolygon, Point, Polygon

from src.constants import EPSG, GeoTypeNames

logger: logging.Logger = logging.getLogger(__name__)


__all__ = [
    "COMMON_TIGERWEB_OUT_FIELDS",
    "City",
    "County",
    "GeoTypeModel",
    "LocationGeometriesModel",
    "LocationModel",
    "State",
    "TigerWebEndpoint",
    "TigerWebEndpointParams",
]

# TODO: Major refactor to include and distinguish both the FIPS code and GEOID
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
    tigerweb_number: str

    def toOrmAttributes(self, **kwargs) -> dict:
        return {
            "name": self.name,
            "tigerweb_number": self.tigerweb_number,
        }


class LocationGeometriesModel(BaseModel, ABC):
    central_latitude: CentroidLatitude
    central_longitude: CentroidLongitude
    rings: Sequence[Sequence[Sequence[float]]] | None = None

    @computed_field
    def centroid(self) -> InstanceOf[WKBElement]:
        # x = longitude, y = latitude
        return from_shape(
            Point(self.central_longitude, self.central_latitude), srid=EPSG
        )

    @computed_field
    def boundary(
        self,
    ) -> InstanceOf[WKBElement] | None:
        """Convert ArcGIS polygon `rings` into a MultiPolygon.

        Rings are combined with the even-odd rule (symmetric difference), so holes
            are cut out of their shells regardless of winding order.
        """
        if not self.rings:
            return None

        count_invalid_polygons: int = 0

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

        if shape.geom_type == "GeometryCollection":
            polygons = [
                part
                for part in get_parts(shape)
                if isinstance(part, (Polygon, MultiPolygon))
            ]

            if not polygons:
                raise ValueError("Geometry contains no polygons")

            result = unary_union(polygons)
            shape = MultiPolygon([result]) if isinstance(result, Polygon) else result

        return from_shape(shape, EPSG)

    def toOrmGeometries(self, **kwargs) -> dict:
        return {"centroid": self.centroid, "boundary": self.boundary}


class LocationModel(GeoTypeModel, LocationGeometriesModel):
    pass


class State(LocationModel):
    abbreviation: str = Field(validation_alias="STUSAB")
    tigerweb_number: StateTigerWebNumber

    def toOrmAttributes(self, **kwargs) -> dict:
        return {"abbreviation": self.abbreviation, **super().toOrmAttributes()}


# Shared Class for County and City
class SubStateRegion(LocationModel, ABC):
    state_tigerweb_number: StateTigerWebNumber
    latitude: CentroidLatitude
    longitude: CentroidLongitude


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
