"""Landsat-8 C2L2 SR optical loader for Google Earth Engine."""
from __future__ import annotations

import ee

from .common import _BANDS_HARMONIZED, _L8_BANDS_SRC, _L8_OFFSET, _L8_SCALE

_L8_COLLECTION_ID  = "LANDSAT/LC08/C02/T1_L2"
_L8_CLOUD_PROPERTY = "CLOUD_COVER"


def _mask_l8_qa_pixel(img: ee.Image) -> ee.Image:
    """Mask clouds (bit 3) and cloud shadow (bit 4) using QA_PIXEL."""
    qa = img.select("QA_PIXEL")
    mask = qa.bitwiseAnd(1 << 3).eq(0).And(qa.bitwiseAnd(1 << 4).eq(0))
    return img.updateMask(mask)


def _scale_l8(img: ee.Image) -> ee.Image:
    """Scale L8 C2L2 SR DNs to physical reflectance [0, 1] (× 0.0000275 − 0.2)."""
    scaled = img.select(_L8_BANDS_SRC).multiply(_L8_SCALE).add(_L8_OFFSET)
    return scaled.copyProperties(img, img.propertyNames())


def _rename_l8(img: ee.Image) -> ee.Image:
    """Rename scaled L8 bands to harmonized names."""
    return img.rename(_BANDS_HARMONIZED)


def get_l8(
    start_date: str,
    end_date: str,
    aoi: ee.Geometry | None = None,
    *,
    bands: list[str] | None = None,
    max_cloud_cover: float = 20.0,
    mask_clouds: bool = True,
    clip: bool = True,
) -> ee.ImageCollection:
    """Load a cloud-masked, scaled, band-harmonized Landsat-8 C2L2 SR collection.

    Parameters
    ----------
    start_date, end_date : ISO date strings "YYYY-MM-DD" (half-open [a, b))
    aoi                  : optional AOI for bounds filtering and clipping
    bands                : subset of harmonized names, e.g. ["Red", "NIR"].
                           None keeps all six: Blue Green Red NIR SWIR1 SWIR2
    max_cloud_cover      : maximum CLOUD_COVER (default 20)
    mask_clouds          : apply QA_PIXEL cloud/shadow mask (default True)
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

    print(f"[geets.landsat] Loading L8: {_L8_COLLECTION_ID}")
    print(f"[geets.landsat] Date range: {start_date} → {end_date}")
    print(f"[geets.landsat] max_cloud_cover={max_cloud_cover}%  "
          f"mask_clouds={mask_clouds}  bands={bands or 'all'}")

    col = (
        ee.ImageCollection(_L8_COLLECTION_ID)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lte(_L8_CLOUD_PROPERTY, max_cloud_cover))
    )

    if aoi is not None:
        print("[geets.landsat] Applying AOI filter")
        col = col.filterBounds(aoi)

    if mask_clouds:
        col = col.map(_mask_l8_qa_pixel)

    col = col.map(_scale_l8).map(_rename_l8)

    if bands is not None:
        col = col.select(bands)

    if aoi is not None and clip:
        print("[geets.landsat] Clipping to AOI")
        col = col.map(lambda img: img.clip(aoi))

    n = col.size().getInfo()
    if n == 0:
        print("[geets.landsat] WARNING: L8 collection is EMPTY (0 images).")
        print(f"[geets.landsat]   → Check date range ({start_date} – {end_date}),")
        print(f"[geets.landsat]      max_cloud_cover={max_cloud_cover}%, and AOI.")
    else:
        print(f"[geets.landsat] L8 collection ready: {n} images")

    return col
