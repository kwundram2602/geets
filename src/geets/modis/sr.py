"""MODIS Surface Reflectance loader for Google Earth Engine.

Supported collections (product family: "sr"):
  MOD09GQ  – Terra SR, 250 m, daily (bands 1-2)
  MOD09GA  – Terra SR, 500 m, daily (bands 1-7)
  MOD09A1  – Terra SR, 500 m, 8-day composite (bands 1-7)
  MOD09Q1  – Terra SR, 250 m, 8-day composite (bands 1-2)
  MYD09GQ  – Aqua  SR, 250 m, daily (bands 1-2)
  MYD09GA  – Aqua  SR, 500 m, daily (bands 1-7)

Scale factor 0.0001 for all reflectance bands.
"""

from __future__ import annotations

import ee

from .sets import MODIS_SETS

_SR_COLLECTIONS: dict[str, dict] = {
    k: v for k, v in MODIS_SETS.items() if v["product"] == "sr"
}

_SR_SCALE = 0.0001

# Reflectance band names per collection (excludes QA band).
_SR_REFL_BANDS: dict[str, list[str]] = {
    "MOD09GQ": ["sur_refl_b01_1", "sur_refl_b02_1"],
    "MYD09GQ": ["sur_refl_b01_1", "sur_refl_b02_1"],
    "MOD09Q1": ["sur_refl_b01", "sur_refl_b02"],
    "MOD09GA": [f"sur_refl_b0{i}" for i in range(1, 8)],
    "MYD09GA": [f"sur_refl_b0{i}" for i in range(1, 8)],
    "MOD09A1": [f"sur_refl_b0{i}" for i in range(1, 8)],
}

# QA band and cloud-bit mask per collection.
# StateQA/state_1km bit 10 = internal cloud algorithm flag.
# QC_250m bits 2-3 = band 1 quality (00=ideal).
_SR_QA: dict[str, tuple[str, int]] = {
    "MOD09GQ": ("QC_250m", 0b1100),  # bits 2-3 must be 0
    "MYD09GQ": ("QC_250m", 0b1100),
    "MOD09Q1": ("QC_250m", 0b1100),
    "MOD09GA": ("state_1km", 1 << 10),  # bit 10 = cloud
    "MYD09GA": ("state_1km", 1 << 10),
    "MOD09A1": ("StateQA", 1 << 10),
}


def _mask_sr_qa(img: ee.Image, qa_band: str, cloud_bit: int) -> ee.Image:
    qa = img.select(qa_band)
    clear = qa.bitwiseAnd(cloud_bit).eq(0)
    return img.updateMask(clear)


def _scale_sr(img: ee.Image, refl_bands: list[str]) -> ee.Image:
    scaled = img.select(refl_bands).multiply(_SR_SCALE)
    return scaled.copyProperties(img, img.propertyNames())


def load_modis_sr(
    start_date: str,
    end_date: str,
    aoi: ee.Geometry | None = None,
    collection: str = "MOD09A1",
    bands: list[str] | None = None,
    apply_scale: bool = True,
    mask_clouds: bool = True,
) -> ee.ImageCollection:
    """Load a MODIS Surface Reflectance ImageCollection from GEE.

    Args:
        start_date: ISO date string, e.g. "2023-01-01".
        end_date: ISO date string, e.g. "2024-01-01".
        aoi: Optional AOI geometry for filtering and clipping.
        collection: One of MOD09GQ, MOD09GA, MOD09A1, MOD09Q1, MYD09GQ, MYD09GA.
        bands: Reflectance bands to select. None = all bands for collection.
        apply_scale: Multiply raw int values by 0.0001.
        mask_clouds: Apply QA cloud mask.

    Returns:
        ee.ImageCollection
    """
    if collection not in _SR_COLLECTIONS:
        raise ValueError(
            f"Unknown collection '{collection}'. Choose from: {sorted(_SR_COLLECTIONS)}"
        )

    refl_bands = bands if bands is not None else _SR_REFL_BANDS[collection]
    qa_band, cloud_bit = _SR_QA[collection]
    collection_id = _SR_COLLECTIONS[collection]["id"]
    print(f"[geets.modis.sr] Loading: {collection_id}")
    print(f"[geets.modis.sr] Date range: {start_date} -> {end_date}")

    col = ee.ImageCollection(collection_id).filterDate(start_date, end_date)

    if aoi is not None:
        col = col.filterBounds(aoi)

    if mask_clouds:
        col = col.map(lambda img: _mask_sr_qa(img, qa_band, cloud_bit))

    col = col.select(refl_bands)

    if apply_scale:
        col = col.map(lambda img: _scale_sr(img, refl_bands))

    if aoi is not None:
        col = col.map(lambda img: img.clip(aoi))

    n = col.size().getInfo()
    if n == 0:
        print("[geets.modis.sr] WARNING: collection is EMPTY.")
    else:
        print(f"[geets.modis.sr] Collection ready: {n} images")

    return col
