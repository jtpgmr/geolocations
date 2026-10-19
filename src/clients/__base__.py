"""Resilient async HTTP client shared by the source toolkits.

A thin wrapper over ``httpx.AsyncClient`` that centralizes the concerns each
source would otherwise duplicate: a bounded timeout, a browser-ish
User-Agent, retry-with-backoff for idempotent GETs (honoring ``Retry-After``
on 429), ``raise_for_status``, and error bodies surfaced on failure.

Lifecycle follows the project convention: cheap constructor, resource built
on ``__aenter__`` and disposed on ``__aexit__``. An ``httpx.AsyncClient`` may
be injected for connection pooling across calls or for testing; an injected
client is never closed by this wrapper (``_owns_client``).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol, Self

import httpx2

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 10.0
_DEFAULT_MAX_RETRIES = 2
_MAX_RETRY_AFTER = 30.0
_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
_UNSENT_ERRORS = (httpx2.ConnectError, httpx2.ConnectTimeout, httpx2.PoolTimeout)


class HttpClientError(Exception):
    """An HTTP request failed after exhausting retries.

    Surfaces the response body so a failing call is debuggable rather than
    hiding behind a bare status code.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class APIAuthInterface(Protocol):
    def getAccessToken(self) -> str: ...

    async def getNewAccessToken(self) -> str: ...

    async def handleAccessToken(self, access_token) -> None: ...

    async def refreshAccessToken(self, access_token) -> None: ...


class AsyncHttpClient:
    """Async GET client with retry/backoff and context-managed lifecycle.

    Args:
        client: Optional ``httpx.AsyncClient`` for pooling/testing. When
            provided it is used as-is and never closed here.
        timeout: Per-request timeout in seconds.
        max_retries: Retry attempts for idempotent GETs on transient errors.
        base_headers: Default headers merged into every request; defaults to
            a browser-like User-Agent (some sources 403 default clients).
    """

    def __init__(
        self,
        *,
        base_url: str,
        client: httpx2.AsyncClient | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        base_headers: dict[str, str] | None = None,
        auth: APIAuthInterface | None = None,
    ) -> None:
        self.base_url = base_url
        self._client = client
        self._owns_client = client is None
        self._timeout = timeout
        self._max_retries = max_retries
        self._base_headers = base_headers or {"User-Agent": _DEFAULT_USER_AGENT}
        self._closed: bool = False

        self._auth = auth

    async def __aenter__(self) -> Self:
        self._getClient()
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()

        self._client = None
        self._closed = True

    def _getClient(self) -> httpx2.AsyncClient:
        if self._closed:
            raise HttpClientError(
                f"{type(self).__name__} for {self.base_url} is closed; "
                "construct a new instance rather than reusing this one"
            )

        if self._client is None:
            self._client = httpx2.AsyncClient(
                base_url=self.base_url,
                timeout=self._timeout,
                follow_redirects=True,
                headers=self._base_headers,
            )

            self._owns_client = True
        return self._client

    async def call(
        self,
        endpoint: str,
        *,
        method: str = "GET",
        params: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx2.Response:
        client = self._getClient()
        method = method.upper()
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        request_headers = httpx2.Headers(self._base_headers)
        request_headers.update(headers or {})

        use_auth = self._auth is not None and "Authorization" not in request_headers
        token = self._auth.getAccessToken() if use_auth else None

        refreshed = False
        attempt = 0

        while True:
            if token is not None:
                request_headers["Authorization"] = f"Bearer {token}"

            try:
                response = await client.request(
                    method, url, params=params, headers=request_headers
                )
            except httpx2.TransportError as exc:
                retryable = isinstance(exc, _UNSENT_ERRORS)
                if not retryable or attempt >= self._max_retries:
                    raise HttpClientError(
                        f"{method} {url} failed after {attempt + 1} attempt(s): {exc!r}"
                    ) from exc

                delay = self._requestDelay(attempt)
                attempt += 1
                await asyncio.sleep(delay)
                continue

            status = response.status_code

            if status == 401 and use_auth and not refreshed:
                refreshed = True
                logger.warning("%s %s -> 401, refreshing access token", method, url)
                token = await self._auth.refreshAccessToken(access_token=token)
                continue

            # 429 means the server rejected the request before processing it,
            if (
                status in _RETRYABLE_STATUS
                and status == 429
                and attempt < self._max_retries
            ):
                retry_after = self._getRetryAfter(response)
                delay = (
                    min(retry_after, _MAX_RETRY_AFTER)
                    if retry_after is not None
                    else self._requestDelay(attempt)
                )
                attempt += 1
                await asyncio.sleep(delay)
                continue

            if not response.is_success:
                raise HttpClientError(
                    f"{method} {url} failed: {status} {response.reason_phrase}",
                    status_code=status,
                    response_body=response.text,
                )

            return response

    @staticmethod
    def _requestDelay(attempt: int) -> float:
        return 0.5 * (2**attempt)

    @staticmethod
    def _getRetryAfter(response: httpx2.Response) -> float | None:
        raw = response.headers.get("Retry-After")
        if raw is None:
            return None
        try:
            return float(raw)
        except ValueError:
            return None
