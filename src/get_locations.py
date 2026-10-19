import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.dialects.postgresql.dml import Insert
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import getLogger

from src.clients import TigerWebClient
from src.clients.tigerweb.models import (
    COMMON_TIGERWEB_OUT_FIELDS,
    GeoTypeModel,
    LocationModel,
    TigerWebEndpoint,
    TigerWebEndpointParams,
)
from src.clients.tigerweb.models import (
    City as CityModel,
)
from src.clients.tigerweb.models import (
    State as StateModel,
)
from src.constants import GEO_TYPE_ORDER, GeoTypeNames
from src.database import Database
from src.schema import Cities as CitiesTable
from src.schema import States as StatesTable
from src.schema import StateGeometries as StateGeometriesTable
from src.settings import getSettings

logger: structlog.stdlib.BoundLogger = getLogger(__name__)


@dataclass
class GeoType:
    name: GeoTypeNames
    db_handler: Callable[[AsyncSession, list], Awaitable[None]]
    model: type[LocationModel]


async def addStateToDatabase(session: AsyncSession, states: list[StateModel]) -> None:
    attribute_values: list[dict] = [state.toOrmAttributes() for state in states]

    add_state_statement: Insert = insert(StatesTable)

    add_state_statement = add_state_statement.on_conflict_do_nothing()

    await session.execute(add_state_statement, attribute_values)

    tigerweb_numbers = {state.tigerweb_number for state in states}

    result = await session.execute(
        select(StatesTable.id, StatesTable.tigerweb_number).where(
            StatesTable.tigerweb_number.in_(tigerweb_numbers)
        )
    )

    state_id_lookup: dict[str, int] = {
        tigerweb_number: state_id for state_id, tigerweb_number in result.all()
    }

    geometry_values: list[dict] = []

    for state in states:
        state_id = state_id_lookup.get(state.tigerweb_number)

        if state_id is None:
            logger.warning(
                "state not found in db",
                tigerweb_number=state.tigerweb_number,
            )
            continue

        geometry_values.append({**state.toOrmGeometries(), "state_id": state_id})

    if not geometry_values:
        return

    add_geometry_statement: Insert = insert(StateGeometriesTable)

    add_geometry_statement = add_geometry_statement.on_conflict_do_nothing(
        index_elements=["state_id"]
    )

    await session.execute(add_geometry_statement, geometry_values)


async def addCityToDatabase(session: AsyncSession, cities: list[CityModel]) -> None:
    state_tigerweb_numbers = {city.state_tigerweb_number for city in cities}

    result = await session.execute(
        select(StatesTable).where(
            StatesTable.tigerweb_number.in_(state_tigerweb_numbers)
        )
    )

    states = result.scalars().all()

    state_lookup = {state.tigerweb_number: state.id for state in states}

    values: list[dict] = []

    for city in cities:
        city_state_id = state_lookup.get(city.state_tigerweb_number)

        if not city_state_id:
            continue

        values.append(city.to_orm(state_id=city_state_id))

    add_city_statement: Insert = insert(CitiesTable)

    add_city_statement = add_city_statement.on_conflict_do_nothing(
        index_elements=["state_id", "name"]
    )

    await session.execute(add_city_statement, values)


class GeoTypes:
    # CITY = GeoType(
    #     name=GeoTypeNames.CITY, db_handler=addCityToDatabase, model=CityModel
    # )
    STATE = GeoType(
        name=GeoTypeNames.STATE, db_handler=addStateToDatabase, model=StateModel
    )


@dataclass
class TigerWebEndpointHandler:
    endpoint: TigerWebEndpoint
    geotype: GeoType


TIGER_WEB_ENDPOINT_HANDLERS: list[TigerWebEndpointHandler] = [
    TigerWebEndpointHandler(
        geotype=GeoTypes.STATE,
        endpoint=TigerWebEndpoint(
            service="State_County",
            layer=0,
            params=TigerWebEndpointParams(
                outFields=[*COMMON_TIGERWEB_OUT_FIELDS, "STUSAB"], returnGeometry=True
            ),
        ),
    ),
    # TigerWebEndpointHandler(
    #     geotype=GeoTypes.CITY,
    #     endpoint=TigerWebEndpoint(
    #         service="Places_CouSub_ConCity_SubMCD",
    #         layer=4,
    #         params=TigerWebEndpointParams(
    #             outFields=[*COMMON_TIGERWEB_OUT_FIELDS, "GEOID", "NAME"]
    #         ),
    #     ),
    # ),
    # TigerWebEndpointHandler(
    #     geotype=GeoTypes.CITY,
    #     endpoint=TigerWebEndpoint(
    #         service="Places_CouSub_ConCity_SubMCD",
    #         layer=5,
    #         params=TigerWebEndpointParams(
    #             outFields=[*COMMON_TIGERWEB_OUT_FIELDS, "GEOID", "NAME"]
    #         ),
    #     ),
    # ),
]


async def addLocationsToDatabase(db: Database):
    async with (
        db.transaction(read_only=False) as session,
        TigerWebClient() as http_client,
    ):
        for handler in TIGER_WEB_ENDPOINT_HANDLERS:
            handler: TigerWebEndpointHandler
            endpoint: TigerWebEndpoint = handler.endpoint
            geotype: GeoType = handler.geotype

            locations: list[LocationModel] = await http_client.getLocationsByGeoType(
                endpoint.service, endpoint.layer, geotype.model, endpoint.params
            )

            # print(locations[0])
            print(locations[0].toOrmAttributes())
            print(locations[0].toOrmGeometries())

            await geotype.db_handler(session, locations)

            logger.info(
                "addLocationsToDatabase",
                handler=geotype.db_handler.__name__,  # ty: ignore[unresolved-attribute]
                count=len(locations),
                geotype=geotype.name,
                api_service=endpoint.service,
            )


if __name__ == "__main__":
    from .settings import configureLogging

    settings = getSettings()

    configureLogging(settings)

    TIGER_WEB_ENDPOINT_HANDLERS.sort(
        key=lambda endpoint: GEO_TYPE_ORDER[endpoint.geotype.name]
    )

    db_url = getSettings().db.dsn
    db = Database(db_url)
    db.connect()

    asyncio.run(addLocationsToDatabase(db))
