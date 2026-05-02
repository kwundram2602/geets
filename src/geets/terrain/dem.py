"""DEM collection metadata and loaders for Google Earth Engine."""

from __future__ import annotations

from typing import Literal

import ee

DemProduct = Literal["elevation", "slope", "aspect", "hillshade"]

DEM_COLLECTIONS: dict[str, str] = {
    "GLO30":   "COPERNICUS/DEM/GLO30",
    "SRTM":    "USGS/SRTMGL1_003",
    "ASTER":   "NASA/ASTER_GED/AG100_003",
    "NASADEM": "NASA/NASADEM_HGT/001",
}

_VALID_PRODUCTS: frozenset[str] = frozenset(
    {"elevation", "slope", "aspect", "hillshade"}
)


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
