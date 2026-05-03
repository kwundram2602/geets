"""MODIS Vegetation Index loader for Google Earth Engine.

Supported collections (product family: "vi"):
  MOD13Q1  – Terra NDVI/EVI, 250 m, 16-day
  MOD13A1  – Terra NDVI/EVI, 500 m, 16-day
  MOD13A3  – Terra NDVI/EVI, 1 km, monthly
  MYD13Q1  – Aqua  NDVI/EVI, 250 m, 16-day
"""

from __future__ import annotations

import ee

from .sets import MODIS_SETS

_VI_COLLECTIONS: dict[str, dict] = {
    k: v for k, v in MODIS_SETS.items() if v["product"] == "vi"
}

_VI_META: dict[str, dict] = {
    "MOD13Q1": {
        "ndvi": "NDVI",
        "evi": "EVI",
        "qa": "SummaryQA",
        "scale_factor": 0.0001,
    },
    "MOD13A1": {
        "ndvi": "NDVI",
        "evi": "EVI",
        "qa": "SummaryQA",
        "scale_factor": 0.0001,
    },
    "MOD13A3": {
        "ndvi": "NDVI",
        "evi": "EVI",
        "qa": "SummaryQA",
        "scale_factor": 0.0001,
    },
    "MYD13Q1": {
        "ndvi": "NDVI",
        "evi": "EVI",
        "qa": "SummaryQA",
        "scale_factor": 0.0001,
    },
}

# SummaryQA: 0=good, 1=marginal, 2=snow/ice, 3=cloudy
_QA_MARGINAL = 1


def _mask_qa(img: ee.Image, max_qa: int) -> ee.Image:
    qa = img.select("SummaryQA")
    return img.updateMask(qa.lte(max_qa))


def _scale_vi(img: ee.Image, scale_factor: float, qa_band: str) -> ee.Image:
    scaled = img.select(["NDVI", "EVI"]).multiply(scale_factor)
    qa = img.select(qa_band)
    return scaled.addBands(qa).copyProperties(img, img.propertyNames())


def load_modis_vi(
    start_date: str,
    end_date: str,
    aoi: ee.Geometry | None = None,
    collection: str = "MOD13Q1",
    band: str | None = "NDVI",
    apply_scale: bool = True,
    mask_clouds: bool = True,
    max_qa: int = _QA_MARGINAL,
) -> ee.ImageCollection:
    """Load a MODIS NDVI/EVI ImageCollection from GEE.

    Args:
        start_date: ISO date string, e.g. "2023-01-01".
        end_date: ISO date string, e.g. "2024-01-01".
        aoi: Optional AOI geometry for filtering and clipping.
        collection: One of MOD13Q1, MOD13A1, MOD13A3, MYD13Q1.
        band: "NDVI", "EVI", or None to keep both.
        apply_scale: Multiply raw int values by 0.0001.
        mask_clouds: Apply SummaryQA mask.
        max_qa: Max accepted QA value (0=good only, 1=good+marginal).

    Returns:
        ee.ImageCollection
    """
    if collection not in _VI_COLLECTIONS:
        raise ValueError(
            f"Unknown collection '{collection}'. "
            f"Choose from: {sorted(_VI_COLLECTIONS)}"
        )

    meta = _VI_META[collection]
    collection_id = _VI_COLLECTIONS[collection]["id"]
    print(f"[geets.modis.vi] Loading: {collection_id}")
    print(f"[geets.modis.vi] Date range: {start_date} -> {end_date}")

    col = (
        ee.ImageCollection(collection_id)
        .filterDate(start_date, end_date)
        .select(["NDVI", "EVI", meta["qa"]])
    )

    if aoi is not None:
        col = col.filterBounds(aoi)

    if mask_clouds:
        col = col.map(lambda img: _mask_qa(img, max_qa))

    if apply_scale:
        sf = meta["scale_factor"]
        col = col.map(lambda img: _scale_vi(img, sf, meta["qa"]))

    if band is not None:
        col = col.select([band, meta["qa"]])

    if aoi is not None:
        col = col.map(lambda img: img.clip(aoi))

    n = col.size().getInfo()
    if n == 0:
        print("[geets.modis.vi] WARNING: collection is EMPTY.")
    else:
        print(f"[geets.modis.vi] Collection ready: {n} images")

    return col


def load_modis_ndvi(
    start_date: str,
    end_date: str,
    aoi: ee.Geometry | None = None,
    collection: str = "MOD13Q1",
    band: str | None = "NDVI",
    apply_scale: bool = True,
    mask_clouds: bool = True,
    max_qa: int = _QA_MARGINAL,
) -> ee.ImageCollection:
    """Backward-compatible alias for `load_modis_vi`."""
    return load_modis_vi(
        start_date=start_date,
        end_date=end_date,
        aoi=aoi,
        collection=collection,
        band=band,
        apply_scale=apply_scale,
        mask_clouds=mask_clouds,
        max_qa=max_qa,
    )
