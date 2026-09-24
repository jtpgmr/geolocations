from __future__ import annotations
from typing import Annotated

from enum import StrEnum
import uuid
from datetime import datetime as dt

from sqlalchemy import (
    DateTime,
    Identity,
    text,
    Integer,
    String,
    SmallInteger,
    UniqueConstraint,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from geoalchemy2 import Geometry, WKBElement
from geoalchemy2.shape import to_shape
from geoalchemy2.shape import from_shape
from shapely.geometry import Point


__all__ = ["Base", "City", "State"]


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
    modified_by: Mapped[str | None] = mapped_column(
        nullable=True, server_default=text("CURRENT_USER::regrole")
    )


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
            srid=4326,
            spatial_index=True,
        ),
        nullable=False,
    ),
]


class States(LocationsSchema):
    __tablename__ = "states"
    __table_args__ = (
        UniqueConstraint("abbreviation", name="uq_states_abbreviation"),
        UniqueConstraint("name", name="uq_states_name"),
        *LocationsSchema.__table_args__,
    )

    name: Mapped[str] = mapped_column(String(100))
    abbreviation: Mapped[str] = mapped_column(String(2))
    tigerweb_number: Mapped[str | int] = mapped_column(String())
    geo_point: Mapped[GeoPoint]


class Cities(LocationsSchema):
    __tablename__ = "cities"
    __table_args__ = (*LocationsSchema.__table_args__,)

    state_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{States.__table__}.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100))

    tigerweb_number: Mapped[str | int] = mapped_column(String())
    geo_point: Mapped[GeoPoint]


class Counties(LocationsSchema):
    __tablename__ = "counties"
    __table_args__ = (*LocationsSchema.__table_args__,)


class CountyCities(LocationsSchema):
    __tablename__ = "county_cities"

    __table_args__ = (
        UniqueConstraint("county_id", "city_id", name="uq_county_city"),
        *LocationsSchema.__table_args__,
    )

    county_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{States.__table__}.id"), nullable=False
    )

    city_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{Cities.__table__}.id"), nullable=False
    )
