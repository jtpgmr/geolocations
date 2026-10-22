from __future__ import annotations

from typing import Final, Self

import httpx2

from src.clients.__base__ import AsyncHttpClient
from src.clients.tigerweb.models import (
    GeoTypeModel,
    LocationGeometriesModel,
    LocationModel,
    TigerWebEndpointParams,
)
from src.constants import EPSG


class TigerWebClient:
    _BASE_URL: Final = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb"

    def __init__(self, http: AsyncHttpClient | None = None) -> None:
        self._http: AsyncHttpClient = http or AsyncHttpClient(base_url=self._BASE_URL)
        self._owns_http = http is None

    async def __aenter__(self) -> Self:
        if self._owns_http:
            await self._http.__aenter__()
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._owns_http:
            return await self._http.__aexit__(*exc)

    def _generateEndpoint(self, service: str, layer: int | str) -> str:
        return f"/{service}/MapServer/{layer}/query"

    def _generateURL(self, service: str, layer: int | str) -> str:
        return f"{self._BASE_URL}{self._generateEndpoint(service, layer)}"

    async def call(
        self,
        endpoint: str,
        *,
        method: str = "GET",
        params: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx2.Response:
        return await self._http.call(
            endpoint=endpoint, method=method, params=params, headers=headers
        )

    def filterAPIQueryMetadata(
        self,
        response: httpx2.Response,
        model: type[LocationModel],
    ) -> list[LocationModel]:
        """Filters `attributes` and `geometry` data from the TIGERweb API"""
        location_data: list[LocationModel] = []

        for feature in response.json()["features"]:
            feature: dict
            attributes, geometry = (
                feature.get("attributes"),
                feature.get("geometry") or {},
            )

            data = (model or LocationModel).model_validate({**attributes, **geometry})

            location_data.append(data)

        return location_data

    async def getLocationsByGeoType(
        self,
        service: str,
        layer: int | str,
        model: type[LocationModel],
        params: TigerWebEndpointParams,
    ) -> list[LocationModel]:
        endpoint = self._generateEndpoint(service, layer)

        if params.return_geometry and (
            not params.out_sr or not params.max_allowable_offset
        ):
            params.out_sr = params.out_sr or EPSG
            params.max_allowable_offset = params.max_allowable_offset or 0.001

        params: dict = params.model_dump(by_alias=True)

        response: httpx2.Response = await self.call(endpoint, params=params)

        locations = self.filterAPIQueryMetadata(response, model)

        return locations
