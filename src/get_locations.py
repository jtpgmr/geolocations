import asyncio
from collections.abc import Callable, Awaitable
from src.settings import getSettings
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, TypeVar

from src.database import Database
from src.models import (
    City as CityModel,
    State as StateModel,
)
from src.schema import Base, Cities as CitiesTable, States as StatesTable

import httpx2
from pydantic import BaseModel, Field, field_serializer, TypeAdapter
from sqlalchemy import select

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.dialects.postgresql.dml import Insert
from sqlalchemy.ext.asyncio import AsyncSession


BASE = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "TIGERweb/Places_CouSub_ConCity_SubMCD/MapServer"
)

BASE_URL: Final = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb"


def generateEndpoint(service: str, layer: int | str):
    return f"/{service}/MapServer/{layer}/query"


def generateURL(service: str, layer: int | str):
    return f"{BASE_URL}{generateEndpoint(service, layer)}"


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
    # db_table: type[Base]
    db_handler: Callable[[AsyncSession, list], Awaitable[None]]
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


async def addStateToDatabase(session: AsyncSession, states: list[StateModel]) -> None:
    values: list[dict] = [state.to_orm() for state in states]

    add_city_statement: Insert = insert(StatesTable).values(values)

    add_city_statement = add_city_statement.on_conflict_do_nothing()

    await session.execute(add_city_statement)


async def addCityToDatabase(session: AsyncSession, cities: list[CityModel]) -> None:
    values: list[dict] = [city.model_dump() for city in cities]

    add_city_statement: Insert = insert(CitiesTable).values(values)

    # await session.execute(add_city_statement)


class GeoTypes:
    CITY = GeoType(
        name=GeoTypeNames.CITY, db_handler=addCityToDatabase, model=CityModel
    )
    STATE = GeoType(
        name=GeoTypeNames.STATE, db_handler=addStateToDatabase, model=StateModel
    )


TIGER_WEB_ENDPOINTS: list[TigerWebEndpoint] = [
    TigerWebEndpoint(
        geotype=GeoTypes.STATE,
        service="State_County",
        layer=0,
        params=TigerWebEndpointParams(
            outFields=["BASENAME", "STATE", "STUSAB", "CENTLAT", "CENTLON"]
        ),
    ),
    # TigerWebEndpoint(
    #     geotype=GeoTypes.CITY,
    #     service="Places_CouSub_ConCity_SubMCD",
    #     layer=4,
    #     params=TigerWebEndpointParams(
    #         outFields=["GEOID", "STATE", "BASENAME", "NAME", "CENTLAT", "CENTLON"]
    #     ),
    # ),
    # TigerWebEndpoint(
    #     geotype=GeoTypes.CITY,
    #     service="Places_CouSub_ConCity_SubMCD",
    #     layer=5,
    #     params=TigerWebEndpointParams(
    #         outFields=["GEOID", "STATE", "BASENAME", "NAME", "CENTLAT", "CENTLON"]
    #     ),
    # ),
]


# TODO: release prints with logs
async def insert_locations_to_database(db: Database):
    async with (
        db.transaction(read_only=False) as session,
        httpx2.AsyncClient(base_url=BASE_URL) as http_client,
    ):
        for tw_endpoint in TIGER_WEB_ENDPOINTS:
            tw_endpoint: TigerWebEndpoint

            endpoint = generateEndpoint(tw_endpoint.service, tw_endpoint.layer)
            params = tw_endpoint.params.model_dump(by_alias=True)

            response = await http_client.get(endpoint, params=params)
            response.raise_for_status()
            print(response.url)

            location_data: list[dict] = [
                feature["attributes"] for feature in response.json()["features"]
            ]

            locations = [
                tw_endpoint.geotype.model.model_validate(record)
                for record in location_data
            ]

            print(locations)
            print(len(locations))

            await tw_endpoint.geotype.db_handler(session, locations)


if __name__ == "__main__":
    TIGER_WEB_ENDPOINTS.sort(key=lambda endpoint: GEO_TYPE_ORDER[endpoint.geotype.name])

    db_url = getSettings().db.dsn
    db = Database(db_url)
    db.connect()

    asyncio.run(insert_locations_to_database(db))
