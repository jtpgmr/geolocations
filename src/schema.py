from __future__ import annotations

import logging
import uuid
from datetime import datetime as dt
from enum import StrEnum

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import (
    Constraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column
from sqlalchemy.schema import ColumnCollectionConstraint

from src.constants import EPSG

logger: logging.Logger = logging.getLogger(__name__)

__all__ = [
    "Base",
    "Cities",
    "CityGeometries",
    "Counties",
    "CountyCities",
    "CountyGeometries",
    "GeometriesMixin",
    "StateGeometries",
    "States",
    "SubStateRegionTableBase",
]


def setLocationsTableForeignKey(
    fk_table: type[Base], nullable: bool = False
) -> Mapped[uuid.UUID]:
    return mapped_column(ForeignKey(f"{fk_table.__table__}.id"), nullable=nullable)


def setUniqueConstraintName(constraint: Constraint, table: Table) -> str:
    if isinstance(constraint, ColumnCollectionConstraint):
        cols = [c.name for c in constraint.columns]
        return cols[0] if len(cols) == 1 else "_".join(cols)

    return constraint.table.name


def setGeometryMappedColumn(
    geometry_type: GeometryTypes, nullable: bool = False
) -> Mapped[WKBElement]:
    return mapped_column(
        Geometry(
            geometry_type=geometry_type,
            srid=EPSG,
            spatial_index=True,
        ),
        nullable=nullable,
    )


NAMING_CONVENTION = {
    "uqConstraint": setUniqueConstraintName,
    "pk": "pk_%(table_name)s",
    # "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(uqConstraint)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    # "ck": "ck_%(table_name)s_%(constraint_name)s",
}


class Base(DeclarativeBase):
    """Insert-only audit base."""

    __abstract__ = True
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    @declared_attr.directive
    def __table_args__(cls) -> tuple:
        return ()

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

    __table_args__: tuple = ({"schema": Schema.LOCATIONS}, *Base.__table_args__)


class GeometryTypes(StrEnum):
    POINT = "POINT"
    MULTIPOLYGON = "MULTIPOLYGON"


class GeoTypeMixin:
    name: Mapped[str] = mapped_column(String(100))
    tigerweb_number: Mapped[str | int] = mapped_column(String())


class GeometriesMixin:
    centroid: Mapped[WKBElement] = setGeometryMappedColumn(GeometryTypes.POINT)
    boundary: Mapped[WKBElement] = setGeometryMappedColumn(GeometryTypes.MULTIPOLYGON)


class States(LocationsSchema, GeoTypeMixin):
    __tablename__ = "states"
    __table_args__ = (
        UniqueConstraint("abbreviation"),
        UniqueConstraint("name"),
        *LocationsSchema.__table_args__,
    )

    abbreviation: Mapped[str] = mapped_column(String(length=2))


class HasStateIdFkMixin:
    state_id = setLocationsTableForeignKey(States)


class StateGeometries(LocationsSchema, GeometriesMixin, HasStateIdFkMixin):
    __tablename__ = "state_geometries"
    __table_args__ = (UniqueConstraint("state_id"), *LocationsSchema.__table_args__)


class SubStateRegionTableBase(LocationsSchema, GeoTypeMixin, HasStateIdFkMixin):
    __abstract__ = True

    @declared_attr.directive
    def __table_args__(cls) -> tuple:
        return (
            UniqueConstraint(
                "state_id", "name", name=f"uq_{cls.__tablename__}_state_id_name"
            ),
            *LocationsSchema.__table_args__,
        )


class Cities(SubStateRegionTableBase):
    __tablename__ = "cities"


class CityGeometries(LocationsSchema, GeometriesMixin):
    __tablename__ = "city_geometries"
    __table_args__ = (UniqueConstraint("city_id"), *LocationsSchema.__table_args__)

    city_id = setLocationsTableForeignKey(Cities)


class Counties(SubStateRegionTableBase):
    __tablename__ = "counties"


class CountyGeometries(LocationsSchema, GeometriesMixin):
    __tablename__ = "county_geometries"
    __table_args__ = (UniqueConstraint("county_id"), *LocationsSchema.__table_args__)

    county_id = setLocationsTableForeignKey(Counties)


class CountyCities(LocationsSchema):
    __tablename__ = "county_cities"

    __table_args__ = (
        UniqueConstraint("county_id", "city_id"),
        *LocationsSchema.__table_args__,
    )

    county_id = setLocationsTableForeignKey(Counties)
    city_id = setLocationsTableForeignKey(Cities)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    for table in Base.metadata.tables.values():
        for constraint in table.constraints:
            logger.debug(type(constraint))

            if isinstance(constraint, (UniqueConstraint, ForeignKeyConstraint)):
                logger.debug(
                    "%s: %s. %s\n",
                    table.fullname,
                    constraint.name,
                    [c.name for c in constraint.columns],
                )

    print("Registered tables:", list(Base.metadata.tables.keys()))
