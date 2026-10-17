"""Sentinel-2 SR optical loader for Google Earth Engine."""
from __future__ import annotations

import ee
from collections.abc import Iterable

from .common import _BANDS_HARMONIZED, _S2_BANDS_SRC, _S2_SCALE

_S2_COLLECTION_ID  = "COPERNICUS/S2_SR_HARMONIZED"
_S2_CLOUD_PROPERTY = "CLOUDY_PIXEL_PERCENTAGE"

_S2_SCL_WATER = 6  # SCL Scene Classification class for water bodies
# Scene Classification Layer (SCL) classes of S2 L2A
SCL_CLASSES = {
    "saturated_defective": 1,
    "dark": 2,
    "cloud_shadow": 3,
    "vegetation": 4,
    "bare_soil": 5,
    "water": 6,
    "cloud_low": 7,  # cloud low probability / unclassified
    "cloud_medium": 8,
    "cloud_high": 9,
    "cirrus": 10,
    "snow": 11,
}
CLOUD_FILTER = 60
CLD_PRB_THRESH = 50
NIR_DRK_THRESH = 0.15
CLD_PRJ_DIST = 1
BUFFER = 50

def _mask_s2_qa60(img: ee.Image, mask_cirrus: bool = True) -> ee.Image:
    """Mask opaque clouds (bit 10) and, optionally, cirrus (bit 11) using QA60."""
    qa = img.select("QA60")
    mask = qa.bitwiseAnd(1 << 10).eq(0)
    if mask_cirrus:
        mask = mask.And(qa.bitwiseAnd(1 << 11).eq(0))
    return img.updateMask(mask)

def _add_cloud_bands(img: ee.Image, cld_prb_thresh: float = CLD_PRB_THRESH) -> ee.Image:
    """Add s2cloudless probability and binary cloud mask bands to the image."""
    cld_prb = ee.Image(img.get("s2cloudless")).select("probability")
    is_cloud = cld_prb.gt(cld_prb_thresh).rename("clouds")
    return img.addBands(ee.Image([cld_prb, is_cloud]))


def _add_shadow_bands(
    img: ee.Image,
    nir_drk_thresh: float = NIR_DRK_THRESH,
    cld_prj_dist: float = CLD_PRJ_DIST,
) -> ee.Image:
    """Add dark_pixels, cloud_transform, and shadows bands for shadow detection.

    Requires 'clouds' band (from _add_cloud_bands), SCL, and B8 on the image.
    """
    not_water = img.select("SCL").neq(_S2_SCL_WATER)
    dark_pixels = (
        img.select("B8").lt(nir_drk_thresh * 1e4).multiply(not_water).rename("dark_pixels")
    )
    shadow_azimuth = ee.Number(90).subtract(
        ee.Number(img.get("MEAN_SOLAR_AZIMUTH_ANGLE"))
    )
    cld_proj = (
        img.select("clouds")
        .directionalDistanceTransform(shadow_azimuth, cld_prj_dist * 10)
        .reproject(crs=img.select(0).projection(), scale=100)
        .select("distance")
        .mask()
        .rename("cloud_transform")
    )
    shadows = cld_proj.multiply(dark_pixels).rename("shadows")
    return img.addBands(ee.Image([dark_pixels, cld_proj, shadows]))


def _add_cld_shdw_mask(
    img: ee.Image,
    cld_prb_thresh: float = CLD_PRB_THRESH,
    nir_drk_thresh: float = NIR_DRK_THRESH,
    cld_prj_dist: float = CLD_PRJ_DIST,
    buffer: float = BUFFER,
) -> ee.Image:
    """Add combined cloud+shadow mask band ('cloudmask') to the image.

    Applies morphological cleanup: focalMin(2) to remove small patches, then
    focalMax(buffer*2/20) to dilate edges; both at 20 m scale.
    """
    img_cloud = _add_cloud_bands(img, cld_prb_thresh)
    img_cloud_shadow = _add_shadow_bands(img_cloud, nir_drk_thresh, cld_prj_dist)
    is_cld_shdw = (
        img_cloud_shadow.select("clouds").add(img_cloud_shadow.select("shadows")).gt(0)
    )
    is_cld_shdw = (
        is_cld_shdw.focalMin(2)
        .focalMax(buffer * 2 / 20)
        .reproject(crs=img.select(0).projection(), scale=20)
        .rename("cloudmask")
    )
    return img_cloud_shadow.addBands(is_cld_shdw)


def _apply_cld_shdw_mask(img: ee.Image) -> ee.Image:
    """Apply the 'cloudmask' band as a pixel mask over all bands."""
    return img.updateMask(img.select("cloudmask").Not())


def resolve_scl_classes(classes: Iterable[int | str] | None) -> list[int]:
    """SCL class values from names (see ``SCL_CLASSES``) or numbers 1-11."""
    values = []
    for cls in classes or []:
        if isinstance(cls, str):
            if cls not in SCL_CLASSES:
                raise ValueError(
                    f"Unknown SCL class {cls!r}. Choose from: {list(SCL_CLASSES)}"
                )
            cls = SCL_CLASSES[cls]
        if int(cls) not in SCL_CLASSES.values():
            raise ValueError(f"SCL class {cls} out of range 1-11")
        values.append(int(cls))
    return values


def _mask_s2_scl(img: ee.Image, classes: list[int]) -> ee.Image:
    """Mask pixels whose SCL class is in ``classes``.

    Must be called on raw S2_SR_HARMONIZED images before band selection or
    scaling — SCL is not preserved after _scale_s2.
    """
    scl = img.select("SCL")
    keep = ee.Image.constant(1)
    for cls in classes:
        keep = keep.And(scl.neq(cls))
    return img.updateMask(keep)


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
    mask_cirrus: bool = True,
    cld_prb_thresh: float = CLD_PRB_THRESH,
    nir_drk_thresh: float = NIR_DRK_THRESH,
    cld_prj_dist: float = CLD_PRJ_DIST,
    buffer: float = BUFFER,
    scl_classes: Iterable[int | str] | None = None,
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
    mask_clouds          : apply QA60 opaque-cloud mask (default True). QA60 has
                           no cloud information from 2022-01-25 to 2024-02-28
                           (inclusive; masked per the GEE catalog, all 0 in
                           practice), so it removes nothing there; use
                           use_s2cloudless for those dates.
    mask_cirrus          : with mask_clouds, also mask QA60 cirrus (default True)
    mask_water           : mask water pixels via SCL class 6 (default False);
                           shorthand for adding 6 to scl_classes
    scl_classes          : SCL classes to mask, by number (1-11) or name from
                           SCL_CLASSES: 1 saturated/defective, 2 dark, 3 cloud
                           shadow, 4 vegetation, 5 bare soil, 6 water, 7 cloud low
                           probability/unclassified, 8 cloud medium, 9 cloud high,
                           10 cirrus, 11 snow/ice (default None = no SCL mask)
    use_s2cloudless      : join COPERNICUS/S2_CLOUD_PROBABILITY and apply
                           probabilistic cloud+shadow masking (default False).
                           Independent of mask_clouds; both can be combined.
    cld_prb_thresh       : s2cloudless cloud probability threshold in % (default 50)
    nir_drk_thresh       : NIR reflectance below which a pixel may be shadow
                           (default 0.15)
    cld_prj_dist         : max cloud-to-shadow projection distance in km (default 1)
    buffer               : dilation of the cloud/shadow mask in m (default 50)
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
        print(
            "[geets.sentinel2] Joining COPERNICUS/S2_CLOUD_PROBABILITY "
            f"(cld_prb_thresh={cld_prb_thresh}, nir_drk_thresh={nir_drk_thresh}, "
            f"cld_prj_dist={cld_prj_dist} km, buffer={buffer} m)"
        )
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
        col = col.map(
            lambda img: _add_cld_shdw_mask(
                img, cld_prb_thresh, nir_drk_thresh, cld_prj_dist, buffer
            )
        ).map(_apply_cld_shdw_mask)

    if mask_clouds:
        col = col.map(lambda img: _mask_s2_qa60(img, mask_cirrus))

    scl = resolve_scl_classes(scl_classes)
    if mask_water and _S2_SCL_WATER not in scl:
        scl.append(_S2_SCL_WATER)
    if scl:
        print(f"[geets.sentinel2] Masking SCL classes: {sorted(scl)}")
        col = col.map(lambda img: _mask_s2_scl(img, scl))

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
