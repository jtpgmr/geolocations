from typing import Final

import httpx2
from pydantic import BaseModel, Field

BASE = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "TIGERweb/Places_CouSub_ConCity_SubMCD/MapServer"
)

BASE_URL: Final = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/"


class TigerWebEndpointParams(BaseModel):
    out_fields: list[str] = Field(alias="outFields")
    return_geometry: bool = Field(default=False, alias="returnGeometry")
    where: Final = "1=1"
    f: Final = "json"


class TigerWebEndpoint(BaseModel):
    route: str
    # schema: DeclarativeBase
    query: str | int
    params: TigerWebEndpointParams


TIGER_WEB_ENDPOINTS: list[TigerWebEndpoint] = [
    TigerWebEndpoint(
        route="State_County",
        query=0,
        params=TigerWebEndpointParams(
            outFields=[
                "NAME",
                "STATE",
                "STUSAB",
            ]
        ),
    )
]
# for state, replace `Places_CouSub_ConCity_SubMCD` with `State_County`
LAYER = {
    "states": {
        0: {
            "where": "1=1",
            "outFields": "STATE,STUSAB,NAME",
            "returnGeometry": "false",
            "f": "json",
        }
    },
    "cities": {
        4: {
            "where": "1=1",
            "outFields": "GEOID,STATE,BASENAME,NAME,CENTLAT,CENTLON",
            "returnGeometry": "false",
            "f": "json",
        },
        5: {
            "where": "1=1",
            "outFields": "GEOID,STATE,BASENAME,NAME,CENTLAT,CENTLON",
            "returnGeometry": "false",
            "f": "json",
        },
    },
}

if __name__ == "__main__":
    # rows = []

    # for layer in (4, 5):
    #     response = httpx2.get(f"{BASE}/{layer}/query", params=params)
    #     response.raise_for_status()

    #     for feature in response.json()["features"]:
    #         attributes = feature["attributes"]
    #         print(attributes)

    #     rows.extend(feature["attributes"] for feature in response.json()["features"])

    for domain, layer in LAYER.items():
        for layer_id, params in layer.items():
            response = httpx2.get(f"{BASE}/{layer_id}/query", params=params)
            print(response.url)
            continue
            response.raise_for_status()

            rows = []
            # if domain == "cities":
            #     print("here")
            #     for feature in response.json()["features"][:1]:
            #         attributes = feature["attributes"]
            #         print(attributes)

            if domain == "states":
                # for feature in response.json():
                # attributes = feature["attributes"]
                print(response.json())

            # rows.extend(
            #     feature["attributes"] for feature in response.json()["features"]
            # )

    # print(rows[0])
    # print(len(rows))

    # seen = set()

    # for row in rows:
    #     geoid = row["GEOID"]

    #     if geoid not in seen:
    #         seen.add(geoid)
    #         continue

    #     print(geoid)
