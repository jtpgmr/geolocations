from geopandas.geodataframe import GeoDataFrame
from contextlib import asynccontextmanager
import asyncio
from sqlalchemy import Select, select, inspect, create_engine, Engine
from src.get_locations import insert_locations_to_database
from src.settings import getSettings
from src.database import Database

import os
import re
from pathlib import Path
import plotly.express as px


import geopandas as gpd
import httpx2
import pandas as pd
import pydeck as pdk
import streamlit as st
from shapely import wkb

from src.schema import Base, Cities as CitiesTable, States as StatesTable
from src.constants import _DEFAULT_TIMEOUT, EPSG

US_STATES_OUTLINES_URL = "https://raw.githubusercontent.com/PublicaMundi/MappingAPI"


@st.cache_resource
def getEngine(url: str) -> Engine:
    """One sync engine per process. pandas/geopandas can't use an async driver."""
    return create_engine(url=url, pool_pre_ping=True, pool_size=2, max_overflow=0)


@st.cache_data(show_spinner="Loading state outlines…")
async def loadStateOutlines(
    cache: Path = Path("./static/us-states.geojson"),
) -> gpd.GeoDataFrame:
    if not cache.exists():
        async with httpx2.AsyncClient(
            base_url=US_STATES_OUTLINES_URL, timeout=_DEFAULT_TIMEOUT
        ) as http_client:
            data = await http_client.get("/master/data/geojson/us-states.json")
            cache.write_bytes(data=data.content)

            print(f"Cached state outlines at {cache}")

    dataframe: GeoDataFrame = gpd.read_file(cache)
    # print(dataframe.to_crs(f"EPSG:{EPSG}"))
    return dataframe.to_crs(f"EPSG:{EPSG}")


@st.cache_data(ttl=600, show_spinner="Loading points from PostGIS…")
# Streamlit builds its cache key by hashing every argument, and it can't hash a SQLAlchemy `Engine`, so it raises that error.
# Streamlit skips hashing any argument whose name starts with an underscore (`_engine`).
def loadStateCentroidPoints(_engine: Engine) -> pd.DataFrame:
    get_states_statement: Select = select(*StatesTable.__table__.c)

    dataframe: gpd.GeoDataFrame = gpd.read_postgis(
        get_states_statement, _engine, geom_col="geo_point"
    )

    return dataframe.assign(lat=dataframe.geometry.y, lon=dataframe.geometry.x)


async def app():
    db_url = getSettings().db.dsn
    state_map_outlines = await loadStateOutlines()

    # st.set_page_config(page_title="US points", layout="wide")
    engine = getEngine(db_url)
    points = loadStateCentroidPoints(engine)
    print(points)

    fig = px.scatter_map(
        points,
        lat="lat",
        lon="lon",
        hover_name="name",
        center={"lat": 38, "lon": -96},
        zoom=3,
        map_style="white-bg",
        height=650,
    )
    fig.update_traces(marker={"size": 11, "color": "#2a6fdb"})
    fig.update_layout(
        map_layers=[
            {
                "source": state_map_outlines.__geo_interface__,
                "type": "line",
                "color": "#6b7785",
            }
        ],
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
    )
    st.plotly_chart(fig, width="stretch")


if __name__ == "__main__":
    asyncio.run(app())
