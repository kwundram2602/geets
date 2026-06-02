"""Sentinel-2 SR optical loader for Google Earth Engine."""
from __future__ import annotations

import ee

from .common import _BANDS_HARMONIZED, _S2_BANDS_SRC, _S2_SCALE

_S2_COLLECTION_ID  = "COPERNICUS/S2_SR_HARMONIZED"
_S2_CLOUD_PROPERTY = "CLOUDY_PIXEL_PERCENTAGE"

_S2_SCL_WATER = 6  # SCL Scene Classification class for water bodies


def _mask_s2_qa60(img: ee.Image) -> ee.Image:
    """Mask opaque clouds (bit 10) and cirrus (bit 11) using QA60."""
    qa = img.select("QA60")
    mask = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
    return img.updateMask(mask)


def _mask_s2_water_scl(img: ee.Image) -> ee.Image:
    """Mask water pixels using the SCL Scene Classification Layer (class 6).

    Must be called on raw S2_SR_HARMONIZED images before band selection or
    scaling — SCL is not preserved after _scale_s2.
    """
    return img.updateMask(img.select("SCL").neq(_S2_SCL_WATER))


def water_mask_mndwi(
    img: ee.Image,
    *,
    threshold: float = 0.0,
) -> ee.Image:
    """Compute a binary water mask from MNDWI on a scaled, harmonized image.

    Uses the Modified Normalized Difference Water Index (Xu 2006):
    MNDWI = (Green − SWIR1) / (Green + SWIR1).
    Pixels with MNDWI >= threshold are classified as water (mask value 1).

    Parameters
    ----------
    img       : scaled S2 image with harmonized band names (Green, SWIR1).
    threshold : MNDWI threshold to separate water from non-water (default 0.0).
                Lower values include more water; raise to reduce false positives
                in urban areas and shadows.

    Returns
    -------
    Single-band ee.Image named "water_mask" (1 = water, 0 = non-water).
    """
    mndwi = img.normalizedDifference(["Green", "SWIR1"])
    return mndwi.gte(threshold).rename("water_mask")


def _scale_s2(img: ee.Image) -> ee.Image:
    """Scale S2 SR integer DNs to physical reflectance [0, 1] (÷ 10 000)."""
    scaled = img.select(_S2_BANDS_SRC).multiply(_S2_SCALE)
    return scaled.copyProperties(img, img.propertyNames())


def _rename_s2(img: ee.Image) -> ee.Image:
    """Rename scaled S2 bands to harmonized names."""
    return img.rename(_BANDS_HARMONIZED)


def get_s2(
    start_date: str,
    end_date: str,
    aoi: ee.Geometry | None = None,
    *,
    bands: list[str] | None = None,
    max_cloud_cover: float = 20.0,
    mask_clouds: bool = True,
    mask_water: bool = False,
    clip: bool = True,
) -> ee.ImageCollection:
    """Load a cloud-masked, scaled, band-harmonized Sentinel-2 SR collection.

    Parameters
    ----------
    start_date, end_date : ISO date strings "YYYY-MM-DD" (half-open [a, b))
    aoi                  : optional AOI for bounds filtering and clipping
    bands                : band names to keep after scaling. Harmonized names
                           (Blue Green Red NIR SWIR1 SWIR2) trigger renaming;
                           any other name keeps the original sensor band name.
                           None keeps all six harmonized bands.
    max_cloud_cover      : maximum CLOUDY_PIXEL_PERCENTAGE (default 20)
    mask_clouds          : apply QA60 cloud/cirrus mask (default True)
    mask_water           : mask water pixels via SCL class 6 (default False)
    clip                 : clip each image to AOI when aoi is provided (default True)

    Returns
    -------
    ee.ImageCollection with scaled bands; renamed to harmonized names unless
    non-harmonized band names are requested.
    """
    print(f"[geets.sentinel2] Loading S2: {_S2_COLLECTION_ID}")
    print(f"[geets.sentinel2] Date range: {start_date} → {end_date}")
    print(f"[geets.sentinel2] max_cloud_cover={max_cloud_cover}%  "
          f"mask_clouds={mask_clouds}  mask_water={mask_water}  bands={bands or 'all'}")

    col = (
        ee.ImageCollection(_S2_COLLECTION_ID)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lte(_S2_CLOUD_PROPERTY, max_cloud_cover))
    )

    if aoi is not None:
        print("[geets.sentinel2] Applying AOI filter")
        col = col.filterBounds(aoi)

    if mask_clouds:
        col = col.map(_mask_s2_qa60)

    if mask_water:
        col = col.map(_mask_s2_water_scl)

    use_harmonized = bands is None or all(b in _BANDS_HARMONIZED for b in bands)
    col = col.map(_scale_s2)
    if use_harmonized:
        col = col.map(_rename_s2)

    if bands is not None:
        col = col.select(bands)

    if aoi is not None and clip:
        print("[geets.sentinel2] Clipping to AOI")
        col = col.map(lambda img: img.clip(aoi))

    n = col.size().getInfo()
    if n == 0:
        print("[geets.sentinel2] WARNING: S2 collection is EMPTY (0 images).")
        print(f"[geets.sentinel2]   → Check date range ({start_date} – {end_date}),")
        print(f"[geets.sentinel2]      max_cloud_cover={max_cloud_cover}%, and AOI.")
    else:
        print(f"[geets.sentinel2] S2 collection ready: {n} images")

    return col
