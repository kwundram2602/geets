from __future__ import annotations

import ee
import shapely
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry


DEFAULT_EE_PROJECT = "dummy"


def authenticate_ee(**kwargs) -> None:
    """Run Earth Engine authentication flow."""
    ee.Authenticate(**kwargs)


def initialize_ee(project: str = DEFAULT_EE_PROJECT, **kwargs) -> None:
    """Initialize Earth Engine with default project `dummy`."""
    ee.Initialize(project=project, **kwargs)


def force_2d(geom: BaseGeometry) -> BaseGeometry:
    """Strip Z coordinates from a Shapely geometry.

    GEE rejects geometries that carry a Z axis.  Pass any Shapely geometry
    through this function before converting it to ``ee.Geometry``.
    """
    return shapely.force_2d(geom)


def shapely_to_ee(geom: BaseGeometry) -> ee.Geometry:
    """Convert a Shapely geometry to ``ee.Geometry``, stripping Z coordinates.

    Equivalent to ``ee.Geometry(mapping(force_2d(geom)))``.
    """
    return ee.Geometry(mapping(force_2d(geom)))


def authenticate_and_initialize_ee(
    project: str = DEFAULT_EE_PROJECT,
    authenticate_kwargs: dict | None = None,
    initialize_kwargs: dict | None = None,
) -> None:
    """Authenticate first and then initialize Earth Engine."""
    authenticate_ee(**(authenticate_kwargs or {}))
    initialize_ee(project=project, **(initialize_kwargs or {}))
