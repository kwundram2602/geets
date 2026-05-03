"""Sentinel-2 SR optical loader for Google Earth Engine."""
from __future__ import annotations

import ee

from .common import _BANDS_HARMONIZED, _S2_BANDS_SRC, _S2_SCALE

_S2_COLLECTION_ID  = "COPERNICUS/S2_SR_HARMONIZED"
_S2_CLOUD_PROPERTY = "CLOUDY_PIXEL_PERCENTAGE"


def _mask_s2_qa60(img: ee.Image) -> ee.Image:
    """Mask opaque clouds (bit 10) and cirrus (bit 11) using QA60."""
    qa = img.select("QA60")
    mask = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
    return img.updateMask(mask)


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
    clip: bool = True,
) -> ee.ImageCollection:
    """Load a cloud-masked, scaled, band-harmonized Sentinel-2 SR collection.

    Parameters
    ----------
    start_date, end_date : ISO date strings "YYYY-MM-DD" (half-open [a, b))
    aoi                  : optional AOI for bounds filtering and clipping
    bands                : subset of harmonized names, e.g. ["Red", "NIR"].
                           None keeps all six: Blue Green Red NIR SWIR1 SWIR2
    max_cloud_cover      : maximum CLOUDY_PIXEL_PERCENTAGE (default 20)
    mask_clouds          : apply QA60 cloud/cirrus mask (default True)
    clip                 : clip each image to AOI when aoi is provided (default True)

    Returns
    -------
    ee.ImageCollection with harmonized bands scaled to [0, 1]
    """
    if bands is not None:
        unknown = [b for b in bands if b not in _BANDS_HARMONIZED]
        if unknown:
            raise ValueError(
                f"Unknown band(s) {unknown}. "
                f"Choose from harmonized names: {_BANDS_HARMONIZED}"
            )

    print(f"[geets.sentinel2] Loading S2: {_S2_COLLECTION_ID}")
    print(f"[geets.sentinel2] Date range: {start_date} → {end_date}")
    print(f"[geets.sentinel2] max_cloud_cover={max_cloud_cover}%  "
          f"mask_clouds={mask_clouds}  bands={bands or 'all'}")

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

    col = col.map(_scale_s2).map(_rename_s2)

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
