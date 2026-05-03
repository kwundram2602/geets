"""DEM collection metadata and loaders for Google Earth Engine."""

from __future__ import annotations

import typing
from typing import Literal

import ee

DemProduct = Literal["elevation", "slope", "aspect", "hillshade"]

DEM_COLLECTIONS: dict[str, str] = {
    "GLO30":   "COPERNICUS/DEM/GLO30",
    "SRTM":    "USGS/SRTMGL1_003",
    "ASTER":   "NASA/ASTER_GED/AG100_003",
    "NASADEM": "NASA/NASADEM_HGT/001",
}

_VALID_PRODUCTS: frozenset[str] = frozenset(typing.get_args(DemProduct))


def _load_dem(
    collection_id: str,
    elev_band: str,
    is_tiled: bool,
    aoi: ee.Geometry | None,
    clip: bool,
    products: list[DemProduct],
) -> ee.Image:
    invalid = [p for p in products if p not in _VALID_PRODUCTS]
    if invalid:
        raise ValueError(
            f"[geets.terrain] Unknown product(s) {invalid}. "
            f"Choose from: {sorted(_VALID_PRODUCTS)}"
        )

    print(f"[geets.terrain] Loading DEM: {collection_id}")
    print(f"[geets.terrain] products={products}")

    col = ee.ImageCollection(collection_id)
    if aoi is not None:
        col = col.filterBounds(aoi)

    img = col.mosaic() if is_tiled else col.first()
    img = img.select(elev_band).rename("elevation")

    if any(p != "elevation" for p in products):
        img = ee.Terrain.products(img)

    img = img.select(products)

    if aoi is not None and clip:
        img = img.clip(aoi)

    return img


def load_copernicus_dem(
    aoi: ee.Geometry | None = None,
    *,
    products: list[DemProduct] | None = None,
    clip: bool = True,
) -> ee.Image:
    """Load Copernicus DEM GLO-30 (30 m global DEM).

    Args:
        aoi: Optional AOI geometry for filtering and clipping.
        products: Terrain products to include. Defaults to ["elevation"].
            Valid values: "elevation", "slope", "aspect", "hillshade".
        clip: Clip to AOI when aoi is provided.

    Returns:
        ee.Image with requested bands.
    """
    return _load_dem(
        DEM_COLLECTIONS["GLO30"], "DEM", True, aoi, clip, products or ["elevation"]
    )


def load_srtm(
    aoi: ee.Geometry | None = None,
    *,
    products: list[DemProduct] | None = None,
    clip: bool = True,
) -> ee.Image:
    """Load USGS SRTM 30m DEM.

    Args:
        aoi: Optional AOI geometry for filtering and clipping.
        products: Terrain products to include. Defaults to ["elevation"].
            Valid values: "elevation", "slope", "aspect", "hillshade".
        clip: Clip to AOI when aoi is provided.

    Returns:
        ee.Image with requested bands.
    """
    return _load_dem(
        DEM_COLLECTIONS["SRTM"], "elevation", False, aoi, clip,
        products or ["elevation"],
    )


def load_aster(
    aoi: ee.Geometry | None = None,
    *,
    products: list[DemProduct] | None = None,
    clip: bool = True,
) -> ee.Image:
    """Load ASTER GDEM (30 m global DEM, elevation band from AG100_003).

    Args:
        aoi: Optional AOI geometry for filtering and clipping.
        products: Terrain products to include. Defaults to ["elevation"].
            Valid values: "elevation", "slope", "aspect", "hillshade".
        clip: Clip to AOI when aoi is provided.

    Returns:
        ee.Image with requested bands.
    """
    return _load_dem(
        DEM_COLLECTIONS["ASTER"], "elevation", False, aoi, clip,
        products or ["elevation"],
    )


def load_nasadem(
    aoi: ee.Geometry | None = None,
    *,
    products: list[DemProduct] | None = None,
    clip: bool = True,
) -> ee.Image:
    """Load NASA NASADEM 30m DEM.

    Args:
        aoi: Optional AOI geometry for filtering and clipping.
        products: Terrain products to include. Defaults to ["elevation"].
            Valid values: "elevation", "slope", "aspect", "hillshade".
        clip: Clip to AOI when aoi is provided.

    Returns:
        ee.Image with requested bands.
    """
    return _load_dem(
        DEM_COLLECTIONS["NASADEM"], "elevation", False, aoi, clip,
        products or ["elevation"],
    )
