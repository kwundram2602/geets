"""MODIS Land Surface Temperature loader for Google Earth Engine.

Supported collections (product family: "lst"):
  MOD11A1  – Terra LST, 1 km, daily
  MOD11A2  – Terra LST, 1 km, 8-day composite
  MYD11A1  – Aqua  LST, 1 km, daily
  MYD11A2  – Aqua  LST, 1 km, 8-day composite

LST raw values are uint16; multiply by 0.02 to get Kelvin.
To convert to Celsius: (raw * 0.02) - 273.15.
QA bits 0-1: 00=good, 01=other quality, 10=TBD, 11=not produced.
"""

from __future__ import annotations

import ee

from .sets import MODIS_SETS

_LST_COLLECTIONS: dict[str, dict] = {
    k: v for k, v in MODIS_SETS.items() if v["product"] == "lst"
}

_LST_SCALE = 0.02  # raw → Kelvin

_LST_BANDS = {
    "day":   ("LST_Day_1km",   "QC_Day"),
    "night": ("LST_Night_1km", "QC_Night"),
}


def _mask_lst_qa(img: ee.Image, qc_band: str) -> ee.Image:
    # Keep only pixels where QC bits 0-1 == 0b00 (good quality).
    qc = img.select(qc_band)
    good = qc.bitwiseAnd(0b11).eq(0)
    return img.updateMask(good)


def _scale_lst(img: ee.Image, lst_band: str, qc_band: str) -> ee.Image:
    scaled = img.select(lst_band).multiply(_LST_SCALE)
    qc = img.select(qc_band)
    return scaled.addBands(qc).copyProperties(img, img.propertyNames())


def load_modis_lst(
    start_date: str,
    end_date: str,
    aoi: ee.Geometry | None = None,
    collection: str = "MOD11A2",
    time_of_day: str = "day",
    apply_scale: bool = True,
    mask_clouds: bool = True,
) -> ee.ImageCollection:
    """Load a MODIS Land Surface Temperature ImageCollection from GEE.

    Args:
        start_date: ISO date string, e.g. "2023-01-01".
        end_date: ISO date string, e.g. "2024-01-01".
        aoi: Optional AOI geometry for filtering and clipping.
        collection: One of MOD11A1, MOD11A2, MYD11A1, MYD11A2.
        time_of_day: "day" or "night".
        apply_scale: Multiply raw values by 0.02 to get Kelvin.
        mask_clouds: Apply QC bitmask (bits 0-1 must equal 00).

    Returns:
        ee.ImageCollection with LST band and QC band.
    """
    if collection not in _LST_COLLECTIONS:
        raise ValueError(
            f"Unknown collection '{collection}'. "
            f"Choose from: {sorted(_LST_COLLECTIONS)}"
        )
    if time_of_day not in _LST_BANDS:
        raise ValueError(
            f"Invalid time_of_day '{time_of_day}'. Choose 'day' or 'night'."
        )

    lst_band, qc_band = _LST_BANDS[time_of_day]
    collection_id = _LST_COLLECTIONS[collection]["id"]
    print(f"[geets.modis.lst] Loading: {collection_id}")
    print(f"[geets.modis.lst] Date range: {start_date} -> {end_date}")
    print(f"[geets.modis.lst] time_of_day={time_of_day}, band={lst_band}")

    col = (
        ee.ImageCollection(collection_id)
        .filterDate(start_date, end_date)
        .select([lst_band, qc_band])
    )

    if aoi is not None:
        col = col.filterBounds(aoi)

    if mask_clouds:
        col = col.map(lambda img: _mask_lst_qa(img, qc_band))

    if apply_scale:
        col = col.map(lambda img: _scale_lst(img, lst_band, qc_band))

    if aoi is not None:
        col = col.map(lambda img: img.clip(aoi))

    n = col.size().getInfo()
    if n == 0:
        print(f"[geets.modis.lst] WARNING: collection is EMPTY.")
    else:
        print(f"[geets.modis.lst] Collection ready: {n} images")

    return col
