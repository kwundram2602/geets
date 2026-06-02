"""Sentinel-2 SR optical loader for Google Earth Engine."""
from __future__ import annotations

import ee

from .common import _BANDS_HARMONIZED, _S2_BANDS_SRC, _S2_SCALE

_S2_COLLECTION_ID  = "COPERNICUS/S2_SR_HARMONIZED"
_S2_CLOUD_PROPERTY = "CLOUDY_PIXEL_PERCENTAGE"

_S2_SCL_WATER = 6  # SCL Scene Classification class for water bodies
CLOUD_FILTER = 60
CLD_PRB_THRESH = 50
NIR_DRK_THRESH = 0.15
CLD_PRJ_DIST = 1
BUFFER = 50

def _mask_s2_qa60(img: ee.Image) -> ee.Image:
    """Mask opaque clouds (bit 10) and cirrus (bit 11) using QA60."""
    qa = img.select("QA60")
    mask = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
    return img.updateMask(mask)

def _add_cloud_bands(img: ee.Image) -> ee.Image:
    """Add s2cloudless probability and binary cloud mask bands to the image."""
    cld_prb = ee.Image(img.get("s2cloudless")).select("probability")
    is_cloud = cld_prb.gt(CLD_PRB_THRESH).rename("clouds")
    return img.addBands(ee.Image([cld_prb, is_cloud]))


def _add_shadow_bands(img: ee.Image) -> ee.Image:
    """Add dark_pixels, cloud_transform, and shadows bands for shadow detection.

    Requires 'clouds' band (from _add_cloud_bands), SCL, and B8 on the image.
    """
    not_water = img.select("SCL").neq(_S2_SCL_WATER)
    dark_pixels = (
        img.select("B8").lt(NIR_DRK_THRESH * 1e4).multiply(not_water).rename("dark_pixels")
    )
    shadow_azimuth = ee.Number(90).subtract(
        ee.Number(img.get("MEAN_SOLAR_AZIMUTH_ANGLE"))
    )
    cld_proj = (
        img.select("clouds")
        .directionalDistanceTransform(shadow_azimuth, CLD_PRJ_DIST * 10)
        .reproject(crs=img.select(0).projection(), scale=100)
        .select("distance")
        .mask()
        .rename("cloud_transform")
    )
    shadows = cld_proj.multiply(dark_pixels).rename("shadows")
    return img.addBands(ee.Image([dark_pixels, cld_proj, shadows]))


def _add_cld_shdw_mask(img: ee.Image) -> ee.Image:
    """Add combined cloud+shadow mask band ('cloudmask') to the image.

    Applies morphological cleanup: focalMin(2) to remove small patches, then
    focalMax(BUFFER*2/20) to dilate edges; both at 20 m scale.
    """
    img_cloud = _add_cloud_bands(img)
    img_cloud_shadow = _add_shadow_bands(img_cloud)
    is_cld_shdw = (
        img_cloud_shadow.select("clouds").add(img_cloud_shadow.select("shadows")).gt(0)
    )
    is_cld_shdw = (
        is_cld_shdw.focalMin(2)
        .focalMax(BUFFER * 2 / 20)
        .reproject(crs=img.select(0).projection(), scale=20)
        .rename("cloudmask")
    )
    return img_cloud_shadow.addBands(is_cld_shdw)


def _apply_cld_shdw_mask(img: ee.Image) -> ee.Image:
    """Apply the 'cloudmask' band as a pixel mask over all bands."""
    return img.updateMask(img.select("cloudmask").Not())


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
    use_s2cloudless: bool = False,
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
    use_s2cloudless      : join COPERNICUS/S2_CLOUD_PROBABILITY and apply
                           probabilistic cloud+shadow masking (default False).
                           Uses module-level CLD_PRB_THRESH, NIR_DRK_THRESH,
                           CLD_PRJ_DIST, and BUFFER constants.
    clip                 : clip each image to AOI when aoi is provided (default True)

    Returns
    -------
    ee.ImageCollection with scaled bands; renamed to harmonized names unless
    non-harmonized band names are requested.
    """
    print(f"[geets.sentinel2] Loading S2: {_S2_COLLECTION_ID}")
    print(f"[geets.sentinel2] Date range: {start_date} → {end_date}")
    print(
        f"[geets.sentinel2] max_cloud_cover={max_cloud_cover}%  "
        f"mask_clouds={mask_clouds}  mask_water={mask_water}  "
        f"use_s2cloudless={use_s2cloudless}  bands={bands or 'all'}"
    )

    col = (
        ee.ImageCollection(_S2_COLLECTION_ID)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lte(_S2_CLOUD_PROPERTY, max_cloud_cover))
    )

    if aoi is not None:
        print("[geets.sentinel2] Applying AOI filter")
        col = col.filterBounds(aoi)

    if use_s2cloudless:
        print("[geets.sentinel2] Joining COPERNICUS/S2_CLOUD_PROBABILITY")
        s2_cloudless_col = ee.ImageCollection("COPERNICUS/S2_CLOUD_PROBABILITY").filterDate(
            start_date, end_date
        )
        if aoi is not None:
            s2_cloudless_col = s2_cloudless_col.filterBounds(aoi)
        col = ee.ImageCollection(
            ee.Join.saveFirst("s2cloudless").apply(
                primary=col,
                secondary=s2_cloudless_col,
                condition=ee.Filter.equals(
                    leftField="system:index",
                    rightField="system:index",
                ),
            )
        )
        col = col.map(_add_cld_shdw_mask).map(_apply_cld_shdw_mask)

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
