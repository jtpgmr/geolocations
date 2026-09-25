from __future__ import annotations
from contextlib import asynccontextmanager
import asyncio
from sqlalchemy import Select, select, inspect
from src.get_locations import insert_locations_to_database
from src.settings import getSettings
from src.database import Database

import os
import re
from pathlib import Path

import geopandas as gpd
import httpx2
import pandas as pd
import pydeck as pdk
import streamlit as st
from shapely import wkb

from src.schema import Base, Cities as CitiesTable, States as StatesTable


# TODO: add support for sync driver (ie, psycopg3)
async def load_points(db: Database, db_url: str):
    get_states_statement: Select = select(*StatesTable.__table__.c)

    async with db.transaction() as session:
        result = await session.execute(get_states_statement)

        # print([dict(row) for row in result.mappings().all()])
        dataframe: gpd.GeoDataFrame = await gpd.read_postgis(
            get_states_statement, db_url, geom_col="geo_location"
        )

        print(dataframe)
        return result


async def app():
    db_url = getSettings().db.dsn
    db = Database(db_url)
    db.connect()

    st.set_page_config(page_title="US points", layout="wide")
    points = await load_points(db, db_url)

    points = points.assign(lat=points.geometry.y, lon=points.geometry.x)


if __name__ == "__main__":
    asyncio.run(app())
