from __future__ import annotations

import uuid
from datetime import datetime as dt
from enum import StrEnum
from typing import Annotated

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Identity,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.constants import EPSG

__all__ = ["Base", "Cities", "States", "StateGeometries"]


class Base(DeclarativeBase):
    """Insert-only audit base."""

    __abstract__ = True

    serial_id: Mapped[int] = mapped_column(
        Identity(always=True),
        primary_key=True,
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        unique=True,
        server_default=text("gen_random_uuid()"),
        nullable=False,
    )
    created_at: Mapped[dt] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    created_by: Mapped[str] = mapped_column(
        nullable=False, server_default=text("CURRENT_USER::regrole")
    )


class UpdatableMixin:
    """Mixin for mutable tables; modified_* stamped by DB trigger on UPDATE."""

    modified_at: Mapped[dt | None] = mapped_column(DateTime(timezone=True))
    modified_by: Mapped[str | None] = mapped_column(nullable=True)


class Schema(StrEnum):
    LOCATIONS = "locations"


class LocationsSchema(Base, UpdatableMixin):
    __abstract__ = True
    __table_args__: tuple = ({"schema": Schema.LOCATIONS},)


GeoPoint = Annotated[
    WKBElement,
    mapped_column(
        Geometry(
            geometry_type="POINT",
            srid=EPSG,
            spatial_index=True,
        ),
        nullable=False,
    ),
]

GeoMultiPolygon = Annotated[
    WKBElement,
    mapped_column(
        Geometry(
            geometry_type="MULTIPOLYGON",  # optional; this is the default
            srid=EPSG,
            spatial_index=True,
        ),
        nullable=False,
    ),
]


class GeoTypeMixin:
    name: Mapped[str] = mapped_column(String(100))
    tigerweb_number: Mapped[str | int] = mapped_column(String())


class States(LocationsSchema, GeoTypeMixin):
    __tablename__ = "states"
    __table_args__ = (
        UniqueConstraint("abbreviation", name="uq_states_abbreviation"),
        UniqueConstraint("name", name="uq_states_name"),
        *LocationsSchema.__table_args__,
    )
    abbreviation: Mapped[str] = mapped_column(String(length=2))

    # name: Mapped[str] = mapped_column(String(100))
    # tigerweb_number: Mapped[str | int] = mapped_column(String())

    # geo_point: Mapped[GeoPoint]


class StateGeometries(LocationsSchema):
    __tablename__ = "state_geometries"
    __table_args__ = (
        UniqueConstraint("state_id", name="uq_state_geometries"),
        *LocationsSchema.__table_args__,
    )

    state_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{States.__table__}.id"), nullable=False
    )
    centroid: Mapped[GeoPoint]
    boundary: Mapped[GeoMultiPolygon]


class Cities(LocationsSchema, GeoTypeMixin):
    __tablename__ = "cities"
    __table_args__ = (
        UniqueConstraint("state_id", "name", name="uq_state_id_city_name"),
        *LocationsSchema.__table_args__,
    )

    state_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{States.__table__}.id"), nullable=False
    )

    # name: Mapped[str] = mapped_column(String(100))
    # tigerweb_number: Mapped[str | int] = mapped_column(String())

    # geo_point: Mapped[GeoPoint]


class Counties(LocationsSchema, GeoTypeMixin):
    __tablename__ = "counties"
    __table_args__ = (
        UniqueConstraint("state_id", "name", name="uq_state_id_county_name"),
        *LocationsSchema.__table_args__,
    )

    state_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{States.__table__}.id"), nullable=False
    )


class CountyCities(LocationsSchema):
    __tablename__ = "county_cities"

    __table_args__ = (
        UniqueConstraint("county_id", "city_id", name="uq_county_city"),
        *LocationsSchema.__table_args__,
    )

    county_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{Counties.__table__}.id"), nullable=False
    )

    city_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{Cities.__table__}.id"), nullable=False
    )
