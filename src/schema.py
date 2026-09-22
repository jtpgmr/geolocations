from __future__ import annotations

from enum import StrEnum
import uuid
from datetime import datetime as dt

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import DateTime, Identity, text, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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


class LocationsSchema(Base):
    __abstract__ = True
    __table_args__: tuple = ({"schema": Schema.LOCATIONS},)


# from sqlalchemy.orm import Mapped, mapped_column

# from database import Base


class State(LocationsSchema):
    __tablename__ = "states"
    __table_args__ = (*LocationsSchema.__table_args__,)


class City(LocationsSchema):
    __tablename__ = "city"
    __table_args__ = (*LocationsSchema.__table_args__,)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state_code: Mapped[str] = mapped_column(String(2))
    state_name: Mapped[str] = mapped_column(String(50))
    city: Mapped[str] = mapped_column(String(50))
    county: Mapped[str] = mapped_column(String(50))
    geo_location: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True)
    )
