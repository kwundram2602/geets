"""MODIS Fire and Burned Area loader for Google Earth Engine.

Supported collections (product family: "fire"):
  MCD64A1  – Terra+Aqua Burned Area, 500 m, monthly
  MOD14A1  – Terra Active Fire / FRP, 1 km, daily
  MOD14A2  – Terra Active Fire / FRP, 1 km, 8-day

Fire products have no standard cloud QA; mask_clouds=False by default.
"""

from __future__ import annotations

import ee

from .sets import MODIS_SETS

_FIRE_COLLECTIONS: dict[str, dict] = {
    k: v for k, v in MODIS_SETS.items() if v["product"] == "fire"
}


def load_modis_fire(
    start_date: str,
    end_date: str,
    aoi: ee.Geometry | None = None,
    collection: str = "MCD64A1",
    mask_clouds: bool = False,
) -> ee.ImageCollection:
    """Load a MODIS Fire or Burned Area ImageCollection from GEE.

    Args:
        start_date: ISO date string, e.g. "2023-01-01".
        end_date: ISO date string, e.g. "2024-01-01".
        aoi: Optional AOI geometry for filtering and clipping.
        collection: One of MCD64A1, MOD14A1, MOD14A2.
        mask_clouds: No standard cloud QA exists for fire products;
            this flag is accepted for API consistency but does nothing.

    Returns:
        ee.ImageCollection with all native bands.
    """
    if collection not in _FIRE_COLLECTIONS:
        raise ValueError(
            f"Unknown collection '{collection}'. "
            f"Choose from: {sorted(_FIRE_COLLECTIONS)}"
        )

    collection_id = _FIRE_COLLECTIONS[collection]["id"]
    print(f"[geets.modis.fire] Loading: {collection_id}")
    print(f"[geets.modis.fire] Date range: {start_date} -> {end_date}")

    col = ee.ImageCollection(collection_id).filterDate(start_date, end_date)

    if aoi is not None:
        col = col.filterBounds(aoi)
        col = col.map(lambda img: img.clip(aoi))

    n = col.size().getInfo()
    if n == 0:
        print(f"[geets.modis.fire] WARNING: collection is EMPTY.")
    else:
        print(f"[geets.modis.fire] Collection ready: {n} images")

    return col
