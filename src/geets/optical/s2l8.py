"""
S2/L8 optical loaders for Google Earth Engine.

Pipeline (layered):
  Level 1 – private per-image transforms (_mask_*, _scale_*, _rename_*)
  Level 2 – public per-image transform: to_surface_reflection
  Level 3 – utils.image_utils.get_image_with_least_cc (imported separately)
  Level 4 – full-pipeline loaders: get_s2, get_l8

Harmonized output bands: Blue, Green, Red, NIR, SWIR1, SWIR2

Usage example::

    from geets import initialize_ee, get_s2, get_l8
    from geets.utils import get_image_with_least_cc
    import ee

    initialize_ee()
    aoi = ee.Geometry.Rectangle([10.5, 47.2, 11.2, 47.8])
    col = get_s2("2022-06-01", "2022-09-01", aoi, max_cloud_cover=20)
    img = get_image_with_least_cc(col, "CLOUDY_PIXEL_PERCENTAGE")
"""
from __future__ import annotations

import ee

# ── Collection metadata ────────────────────────────────────────────────────

_S2_COLLECTION_ID  = "COPERNICUS/S2_SR_HARMONIZED"
_L8_COLLECTION_ID  = "LANDSAT/LC08/C02/T1_L2"

_S2_CLOUD_PROPERTY = "CLOUDY_PIXEL_PERCENTAGE"
_L8_CLOUD_PROPERTY = "CLOUD_COVER"

_S2_BANDS_SRC     = ["B2",    "B3",    "B4",    "B8",    "B11",   "B12"  ]
_L8_BANDS_SRC     = ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"]
_BANDS_HARMONIZED = ["Blue",  "Green", "Red",   "NIR",   "SWIR1", "SWIR2" ]

_S2_SCALE  = 1e-4      # ÷ 10 000
_L8_SCALE  = 2.75e-5   # × 0.0000275
_L8_OFFSET = -0.2


# ── Level 1: private per-image transforms ─────────────────────────────────

def _mask_s2_qa60(img: ee.Image) -> ee.Image:
    """Mask opaque clouds (bit 10) and cirrus (bit 11) using QA60."""
    qa = img.select("QA60")
    mask = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
    return img.updateMask(mask)


def _mask_l8_qa_pixel(img: ee.Image) -> ee.Image:
    """Mask clouds (bit 3) and cloud shadow (bit 4) using QA_PIXEL."""
    qa = img.select("QA_PIXEL")
    mask = qa.bitwiseAnd(1 << 3).eq(0).And(qa.bitwiseAnd(1 << 4).eq(0))
    return img.updateMask(mask)


def _scale_s2(img: ee.Image) -> ee.Image:
    """Scale S2 SR integer DNs to physical reflectance [0, 1] (÷ 10 000)."""
    scaled = img.select(_S2_BANDS_SRC).multiply(_S2_SCALE)
    return scaled.copyProperties(img, img.propertyNames())


def _scale_l8(img: ee.Image) -> ee.Image:
    """Scale L8 C2L2 SR integer DNs to physical reflectance [0, 1] (× 0.0000275 − 0.2)."""
    scaled = img.select(_L8_BANDS_SRC).multiply(_L8_SCALE).add(_L8_OFFSET)
    return scaled.copyProperties(img, img.propertyNames())


def _rename_s2(img: ee.Image) -> ee.Image:
    """Rename scaled S2 bands to harmonized names."""
    return img.rename(_BANDS_HARMONIZED)


def _rename_l8(img: ee.Image) -> ee.Image:
    """Rename scaled L8 bands to harmonized names."""
    return img.rename(_BANDS_HARMONIZED)


# ── Level 2: public per-image transform ───────────────────────────────────

def to_surface_reflection(img: ee.Image, sensor: str) -> ee.Image:
    """Scale a single image to physical surface reflectance [0, 1].

    Parameters
    ----------
    img    : ee.Image with original DN bands for the given sensor.
    sensor : "S2" scales by ÷ 10 000; "L8" scales by × 0.0000275 − 0.2.

    Raises
    ------
    ValueError for unknown sensor strings.
    """
    if sensor == "S2":
        return _scale_s2(img)
    if sensor == "L8":
        return _scale_l8(img)
    raise ValueError(f"Unknown sensor '{sensor}'. Choose 'S2' or 'L8'.")


# ── Level 4: full-pipeline loaders ────────────────────────────────────────

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

    print(f"[geets.s2l8] Loading S2: {_S2_COLLECTION_ID}")
    print(f"[geets.s2l8] Date range: {start_date} → {end_date}")
    print(f"[geets.s2l8] max_cloud_cover={max_cloud_cover}%  "
          f"mask_clouds={mask_clouds}  bands={bands or 'all'}")

    col = (
        ee.ImageCollection(_S2_COLLECTION_ID)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lte(_S2_CLOUD_PROPERTY, max_cloud_cover))
    )

    if aoi is not None:
        print("[geets.s2l8] Applying AOI filter")
        col = col.filterBounds(aoi)

    if mask_clouds:
        col = col.map(_mask_s2_qa60)

    col = col.map(_scale_s2).map(_rename_s2)

    if bands is not None:
        col = col.select(bands)

    if aoi is not None and clip:
        print("[geets.s2l8] Clipping to AOI")
        col = col.map(lambda img: img.clip(aoi))

    n = col.size().getInfo()
    if n == 0:
        print(f"[geets.s2l8] WARNING: S2 collection is EMPTY (0 images).")
        print(f"[geets.s2l8]   → Check date range ({start_date} – {end_date}),")
        print(f"[geets.s2l8]      max_cloud_cover={max_cloud_cover}%, and AOI.")
    else:
        print(f"[geets.s2l8] S2 collection ready: {n} images")

    return col
