import asyncio
import uuid
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
    LocationModel,
    TigerWebEndpoint,
    TigerWebEndpointParams,
)
from src.clients.tigerweb.models import (
    City as CityModel,
)
from src.clients.tigerweb.models import (
    County as CountyModel,
)
from src.clients.tigerweb.models import (
    State as StateModel,
)
from src.clients.tigerweb.models import SubStateRegion as SubStateRegionModel
from src.constants import GEO_TYPE_ORDER, GeoTypeNames
from src.database import Database
from src.schema import Cities as CitiesTable
from src.schema import CityGeometries as CityGeometriesTable
from src.schema import Counties as CountiesTable
from src.schema import CountyGeometries as CountyGeometriesTable
from src.schema import GeometriesMixin, GeoTypeMixin, SubStateRegionTableBase
from src.schema import StateGeometries as StateGeometriesTable
from src.schema import States as StatesTable
from src.settings import getSettings

logger: structlog.stdlib.BoundLogger = getLogger(__name__)


@dataclass
class GeoType:
    name: GeoTypeNames
    db_handler: Callable[
        # [AsyncSession, list, tuple | None, TigerWebEndpointParams | None],
        ...,
        Awaitable[None],
    ]
    model: type[LocationModel]
    db_tables: (
        tuple[type[GeoTypeMixin], type[GeometriesMixin], str, GeoTypeNames | None]
        | None
    ) = None


async def addStateToDatabase(
    session: AsyncSession,
    states: list[StateModel],
    *,
    request_params: TigerWebEndpointParams | None = None,
    **kwargs,
) -> None:
    attribute_values: list[dict] = [state.toOrmAttributes() for state in states]

    add_state_statement: Insert = insert(StatesTable)

    add_state_statement = add_state_statement.on_conflict_do_nothing()

    await session.execute(add_state_statement, attribute_values)

    if request_params and not request_params.return_geometry:
        return

    tigerweb_numbers = {state.tigerweb_number for state in states}

    result = await session.execute(
        select(StatesTable.id, StatesTable.tigerweb_number).where(
            StatesTable.tigerweb_number.in_(tigerweb_numbers)
        )
    )

    state_id_lookup: dict[str, uuid.UUID] = {
        tigerweb_number: state_id for state_id, tigerweb_number in result.all()
    }

    geometry_values: list[dict] = []

    for state in states:
        state_id = state_id_lookup.get(state.tigerweb_number)

        if state_id is None:
            logger.warning(
                "State not found in db",
                name=state.name,
                abbreviation=state.abbreviation,
                db_table=StatesTable.__tablename__,
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


async def addSubStateRegionToDatabase(
    session: AsyncSession,
    substate_regions: list[SubStateRegionModel],
    *,
    db_tables: tuple[type[SubStateRegionTableBase], type[GeometriesMixin], str],
    request_params: TigerWebEndpointParams | None = None,
) -> None:
    result = await session.execute(select(StatesTable))

    state_lookup = {state.tigerweb_number: state.id for state in result.scalars().all()}

    values: list[dict] = []
    for region in substate_regions:
        region_state_id = state_lookup.get(region.state_tigerweb_number)

        if not region_state_id:
            continue

        values.append({**region.toOrmAttributes(), "state_id": region_state_id})

    SubStateRegionTable = db_tables[0]
    add_region_statement: Insert = insert(SubStateRegionTable)

    add_region_statement = add_region_statement.on_conflict_do_nothing(
        index_elements=["state_id", "name"]
    )

    await session.execute(add_region_statement, values)

    if request_params and not request_params.return_geometry:
        return

    result = await session.execute(
        select(SubStateRegionTable.id, SubStateRegionTable.tigerweb_number)
    )

    region_id_lookup: dict[str, uuid.UUID] = {
        tigerweb_number: id for id, tigerweb_number in result.all()
    }

    geometry_values: list[dict] = []

    # TODO: handle gracefully
    try:
        base_to_geometries_table_fk = db_tables[2]
    except IndexError:
        raise ValueError(
            "Missing foreign key input parameter for function `addSubStateRegionToDatabase`"
        )

    for region in substate_regions:
        region_id = region_id_lookup.get(region.tigerweb_number)

        # TODO: Add clearer logging to display if a city is not in the DB or is a duplicate 'city' record
        # NOTE: Waukesha, WI have records with the tigerweb_number 5584275 and 5584250
        if not region_id:
            logger.warning(
                "Record not found in db",
                name=region.name,
                tigerweb_number=region.tigerweb_number,
                state_tigerweb_number=region.state_tigerweb_number,
                db_table=SubStateRegionTable.__tablename__,
            )
            continue

        geometry_values.append(
            {**region.toOrmGeometries(), base_to_geometries_table_fk: region_id}
        )

    if not geometry_values:
        return

    GeometriesTable = db_tables[1]
    add_geometry_statement: Insert = insert(GeometriesTable)

    add_geometry_statement = add_geometry_statement.on_conflict_do_nothing(
        index_elements=[base_to_geometries_table_fk]
    )

    await session.execute(add_geometry_statement, geometry_values)


class GeoTypes:
    CITY = GeoType(
        name=GeoTypeNames.CITY,
        db_handler=addSubStateRegionToDatabase,
        model=CityModel,
        db_tables=(CitiesTable, CityGeometriesTable, "city_id", GeoTypeNames.CITY),
    )
    COUNTY = GeoType(
        name=GeoTypeNames.COUNTY,
        db_handler=addSubStateRegionToDatabase,
        model=CountyModel,
        db_tables=(
            CountiesTable,
            CountyGeometriesTable,
            "county_id",
            GeoTypeNames.COUNTY,
        ),
    )
    STATE = GeoType(
        name=GeoTypeNames.STATE,
        db_handler=addStateToDatabase,
        model=StateModel,
    )


@dataclass
class TigerWebEndpointHandler:
    endpoint: TigerWebEndpoint
    geotype: GeoType


# https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1/query?outFields=GEOID%2CSTATE%2CCOUNTY%2CBASENAME%2CNAME%2CCENTLAT%2CCENTLON&returnGeometry=false&where=1%3D1&f=json
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
    TigerWebEndpointHandler(
        geotype=GeoTypes.CITY,
        endpoint=TigerWebEndpoint(
            service="Places_CouSub_ConCity_SubMCD",
            layer=4,
            params=TigerWebEndpointParams(
                outFields=[*COMMON_TIGERWEB_OUT_FIELDS, "GEOID", "NAME"],
                returnGeometry=True,
            ),
        ),
    ),
    TigerWebEndpointHandler(
        geotype=GeoTypes.CITY,
        endpoint=TigerWebEndpoint(
            service="Places_CouSub_ConCity_SubMCD",
            layer=5,
            params=TigerWebEndpointParams(
                outFields=[*COMMON_TIGERWEB_OUT_FIELDS, "GEOID", "NAME"],
                returnGeometry=True,
            ),
        ),
    ),
    TigerWebEndpointHandler(
        geotype=GeoTypes.COUNTY,
        endpoint=TigerWebEndpoint(
            service="State_County",
            layer=1,
            params=TigerWebEndpointParams(
                outFields=[*COMMON_TIGERWEB_OUT_FIELDS, "GEOID", "NAME"],
                returnGeometry=True,
            ),
        ),
    ),
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

            await geotype.db_handler(
                session,
                locations,
                db_tables=geotype.db_tables,
                request_params=endpoint.params,
            )

            logger.info(
                "addLocationsToDatabase",
                handler=geotype.db_handler.__name__,  # ty: ignore[unresolved-attribute]
                count=len(locations),
                geotype=geotype.name,
                api_service=endpoint.service,
                layer=endpoint.layer,
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
