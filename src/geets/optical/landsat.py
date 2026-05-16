"""Landsat-8 and Landsat-9 C2L2 SR optical loader for Google Earth Engine."""
from __future__ import annotations

import ee

from .common import _BANDS_HARMONIZED, _L8_BANDS_SRC, _L8_OFFSET, _L8_SCALE

_L8_COLLECTION_ID  = "LANDSAT/LC08/C02/T1_L2"
_L9_COLLECTION_ID  = "LANDSAT/LC09/C02/T1_L2"
_LC_CLOUD_PROPERTY = "CLOUD_COVER"
_LC_THERMAL_SCALE  = 0.00341802
_LC_THERMAL_OFFSET = 149.0
_EM_SLOPE          = 0.004
_EM_INTERCEPT      = 0.986
_LST_LAMBDA        = 0.00115   # thermal-band wavelength (µm)
_LST_C2            = 1.438     # radiation constant c₂ (mK)
_KELVIN_OFFSET     = 273.15


def _mask_lc_qa_pixel(img: ee.Image) -> ee.Image:
    """Mask clouds (bit 3) and cloud shadow (bit 4) using QA_PIXEL."""
    qa = img.select("QA_PIXEL")
    mask = qa.bitwiseAnd(1 << 3).eq(0).And(qa.bitwiseAnd(1 << 4).eq(0))
    return img.updateMask(mask)


def _scale_lc_sr(img: ee.Image) -> ee.Image:
    """Scale L8 C2L2 SR and ST_B* DNs while preserving other bands."""
    scaled = img.addBands(
        img.select("SR_B.*").multiply(_L8_SCALE).add(_L8_OFFSET),
        None,
        True,
    )
    scaled = thermal_scaling_lc(scaled)
    return ee.Image(scaled.copyProperties(img, img.propertyNames()))


def _rename_lc_sr(img: ee.Image) -> ee.Image:
    """Rename L8 SR_B2..SR_B7 bands to harmonized names."""
    sr = img.select(_L8_BANDS_SRC).rename(_BANDS_HARMONIZED)
    other = img.select(img.bandNames().removeAll(_L8_BANDS_SRC))
    return ee.Image(other.addBands(sr).copyProperties(img, img.propertyNames()))


def _ndvi_lc(img: ee.Image) -> ee.Image:
    """NDVI from unscaled L8 SR bands (SR_B5 = NIR, SR_B4 = Red)."""
    scaled = img.select(["SR_B5", "SR_B4"]).multiply(_L8_SCALE).add(_L8_OFFSET)
    return scaled.normalizedDifference(["SR_B5", "SR_B4"]).rename("NDVI")


def _proportion_of_vegetation(
    ndvi: ee.Image,
    ndvi_min: ee.Number,
    ndvi_max: ee.Number,
) -> ee.Image:
    """PV = ((NDVI − ndvi_min) / (ndvi_max − ndvi_min))²."""
    denom = ndvi_max.subtract(ndvi_min)
    safe_denom = ee.Number(ee.Algorithms.If(denom.eq(0), 1, denom))
    return ndvi.subtract(ndvi_min).divide(safe_denom).pow(2).rename("PV")


def _emissivity_lc(pv: ee.Image) -> ee.Image:
    """EM = 0.004 × PV + 0.986 (soil/vegetation mixture model)."""
    return pv.multiply(_EM_SLOPE).add(_EM_INTERCEPT).rename("EM")


def thermal_scaling_lc(img: ee.Image) -> ee.Image:
    """Scale L8 ST_B.* DNs to brightness temperature in Kelvin."""
    thermal_bands = (
        img.select("ST_B.*").multiply(_LC_THERMAL_SCALE).add(_LC_THERMAL_OFFSET)
    )
    return img.addBands(thermal_bands, None, True)


def land_surface_temperature_lc(
    img: ee.Image,
    emissivity: ee.Image | float = 0.95,
) -> ee.Image:
    """LST in Celsius from a scaled thermal band and emissivity.

    Parameters
    ----------
    img        : image with ST_B10 already scaled to Kelvin (via thermal_scaling_lc)
    emissivity : per-pixel ee.Image or a scalar float (default 0.95)

    Returns
    -------
    Single-band ee.Image named "LST" in degrees Celsius.
    """
    thermal = img.select("ST_B10")
    em = (
        emissivity
        if isinstance(emissivity, ee.Image)
        else ee.Image.constant(emissivity)
    )
    return thermal.expression(
        "(TB / (1 + (_lambda * (TB / _c2)) * log(em))) - _k",
        {
            "TB": thermal, "em": em,
            "_lambda": _LST_LAMBDA, "_c2": _LST_C2, "_k": _KELVIN_OFFSET,
        },
    ).rename("LST")


def add_lst_lc(img: ee.Image, aoi: ee.Geometry, *, scale: int = 30) -> ee.Image:
    """Add a derived LST band (°C) to a raw Landsat 8 C2L2 image.

    Derives emissivity from an NDVI-based Proportion of Vegetation model
    (EM = 0.004 × PV + 0.986), then computes LST from the thermal band.

    Requires SR_B4, SR_B5 (unscaled reflectance) and ST_B10 (unscaled
    thermal) to be present — call before any get_l8 band renaming.
    Intended for use with .map() on the raw collection.

    Parameters
    ----------
    img   : single Landsat 8 C2L2 image with SR and thermal bands
    aoi   : geometry for per-image NDVI min/max reduction
    scale : pixel resolution for NDVI reduction in metres (default 30)

    Returns
    -------
    Input image with "LST" band appended (°C).
    """
    ndvi = _ndvi_lc(img)

    stats = ndvi.reduceRegion(
        reducer=ee.Reducer.minMax(),
        geometry=aoi,
        scale=scale,
        maxPixels=1e9,
        bestEffort=True,
    )
    ndvi_min = ee.Number(
        ee.Algorithms.If(stats.get("NDVI_min"), stats.get("NDVI_min"), 0.2)
    )
    ndvi_max = ee.Number(
        ee.Algorithms.If(stats.get("NDVI_max"), stats.get("NDVI_max"), 0.8)
    )

    pv = _proportion_of_vegetation(ndvi, ndvi_min, ndvi_max)
    em = _emissivity_lc(pv)

    img_scaled_thermal = thermal_scaling_lc(img)
    lst = land_surface_temperature_lc(img_scaled_thermal, em)
    return ee.Image(img.addBands(lst).copyProperties(img, img.propertyNames()))


def _load_lc_collection(
    collection_id: str,
    start_date: str,
    end_date: str,
    aoi: ee.Geometry | None,
    *,
    bands: list[str] | None,
    scale: bool,
    max_cloud_cover: float,
    mask_clouds: bool,
    clip: bool,
    sensor_label: str,
) -> ee.ImageCollection:
    """Shared loader for any LC08/LC09 C2L2 collection.

    Parameters
    ----------
    collection_id        : Earth Engine collection ID
    start_date, end_date : ISO date strings "YYYY-MM-DD" (half-open [a, b))
    aoi                  : optional AOI for bounds filtering and clipping
    bands                : band names to keep after processing
    scale                : scale SR_B* to reflectance and ST_B* to Kelvin
    max_cloud_cover      : maximum CLOUD_COVER
    mask_clouds          : apply QA_PIXEL cloud/shadow mask
    clip                 : clip each image to AOI when aoi is provided
    sensor_label         : label for logging (e.g., "L8" or "L9")

    Returns
    -------
    ee.ImageCollection with requested bands; scaling and harmonization are
    applied only when requested.
    """
    print(f"[geets.landsat] Loading {sensor_label}: {collection_id}")
    print(f"[geets.landsat] Date range: {start_date} → {end_date}")
    print(f"[geets.landsat] max_cloud_cover={max_cloud_cover}%  "
          f"mask_clouds={mask_clouds}  scale={scale}  bands={bands or 'all'}")

    col = (
        ee.ImageCollection(collection_id)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lte(_LC_CLOUD_PROPERTY, max_cloud_cover))
    )

    if aoi is not None:
        print("[geets.landsat] Applying AOI filter")
        col = col.filterBounds(aoi)

    if mask_clouds:
        col = col.map(_mask_lc_qa_pixel)

    requested_harmonized: list[str] = []
    requested_native_sr: list[str] = []
    if bands is not None:
        requested_harmonized = [b for b in bands if b in _BANDS_HARMONIZED]
        requested_native_sr = [b for b in bands if b in _L8_BANDS_SRC]
        if requested_harmonized and requested_native_sr:
            raise ValueError("bands cannot mix harmonized and native SR band names")

    if scale:
        col = col.map(_scale_lc_sr)
    if requested_harmonized:
        col = col.map(_rename_lc_sr)

    if bands is not None:
        col = col.select(bands)

    if aoi is not None and clip:
        print("[geets.landsat] Clipping to AOI")
        col = col.map(lambda img: img.clip(aoi))

    n = col.size().getInfo()
    if n == 0:
        print(f"[geets.landsat] WARNING: {sensor_label} collection is EMPTY.")
        print(f"[geets.landsat]   → Check date range ({start_date} – {end_date}),")
        print(f"[geets.landsat]      max_cloud_cover={max_cloud_cover}%, and AOI.")
    else:
        print(f"[geets.landsat] {sensor_label} collection ready: {n} images")

    return col


def get_l8(
    start_date: str,
    end_date: str,
    aoi: ee.Geometry | None = None,
    *,
    bands: list[str] | None = None,
    scale: bool = False,
    max_cloud_cover: float = 20.0,
    mask_clouds: bool = False,
    clip: bool = False,
) -> ee.ImageCollection:
    """Load a Landsat-8 C2L2 SR collection with optional scaling/harmonization.

    Parameters
    ----------
    start_date, end_date : ISO date strings "YYYY-MM-DD" (half-open [a, b))
    aoi                  : optional AOI for bounds filtering and clipping
    bands                : band names to keep after processing. Harmonized names
                           (Blue Green Red NIR SWIR1 SWIR2) trigger renaming;
                           any other name keeps the original sensor band name.
                           Do not mix harmonized and native SR band names.
                           None keeps all bands in the source collection.
    scale                : scale SR_B* to reflectance and ST_B* to Kelvin
                           (default False)
    max_cloud_cover      : maximum CLOUD_COVER (default 20)
    mask_clouds          : apply QA_PIXEL cloud/shadow mask (default False)
    clip                 : clip each image to AOI when aoi is provided (default False)

    Returns
    -------
    ee.ImageCollection with requested bands; scaling and harmonization are
    applied only when requested.
    """
    return _load_lc_collection(
        _L8_COLLECTION_ID,
        start_date,
        end_date,
        aoi,
        bands=bands,
        scale=scale,
        max_cloud_cover=max_cloud_cover,
        mask_clouds=mask_clouds,
        clip=clip,
        sensor_label="L8",
    )


def get_l9(
    start_date: str,
    end_date: str,
    aoi: ee.Geometry | None = None,
    *,
    bands: list[str] | None = None,
    scale: bool = False,
    max_cloud_cover: float = 20.0,
    mask_clouds: bool = False,
    clip: bool = False,
) -> ee.ImageCollection:
    """Load a Landsat-9 C2L2 SR collection with optional scaling/harmonization.

    Landsat 9 uses the same C2L2 format, band names, scale constants, and
    QA_PIXEL structure as Landsat 8. Data is available from ~2022-02-01.

    Parameters
    ----------
    start_date, end_date : ISO date strings "YYYY-MM-DD" (half-open [a, b))
    aoi                  : optional AOI for bounds filtering and clipping
    bands                : band names to keep after processing. Harmonized names
                           (Blue Green Red NIR SWIR1 SWIR2) trigger renaming;
                           any other name keeps the original sensor band name.
                           Do not mix harmonized and native SR band names.
                           None keeps all bands in the source collection.
    scale                : scale SR_B* to reflectance and ST_B* to Kelvin
                           (default False)
    max_cloud_cover      : maximum CLOUD_COVER (default 20)
    mask_clouds          : apply QA_PIXEL cloud/shadow mask (default False)
    clip                 : clip each image to AOI when aoi is provided (default False)

    Returns
    -------
    ee.ImageCollection with requested bands; scaling and harmonization are
    applied only when requested.
    """
    return _load_lc_collection(
        _L9_COLLECTION_ID,
        start_date,
        end_date,
        aoi,
        bands=bands,
        scale=scale,
        max_cloud_cover=max_cloud_cover,
        mask_clouds=mask_clouds,
        clip=clip,
        sensor_label="L9",
    )


def get_l8l9(
    start_date: str,
    end_date: str,
    aoi: ee.Geometry | None = None,
    *,
    bands: list[str] | None = None,
    scale: bool = False,
    max_cloud_cover: float = 20.0,
    mask_clouds: bool = False,
    clip: bool = False,
) -> ee.ImageCollection:
    """Load a merged Landsat-8 + Landsat-9 C2L2 SR collection.

    Both sensors share identical band names, scale constants, and QA_PIXEL
    structure. The merged collection retains each image's SPACECRAFT_ID
    property ("LANDSAT_8" or "LANDSAT_9") for downstream filtering.

    Landsat 9 data is only available from ~2022-02-01. Requests with
    end_date before that date will return only L8 images.

    Parameters
    ----------
    start_date, end_date : ISO date strings "YYYY-MM-DD" (half-open [a, b))
    aoi                  : optional AOI for bounds filtering and clipping
    bands                : band names to keep after processing. Harmonized names
                           (Blue Green Red NIR SWIR1 SWIR2) trigger renaming;
                           any other name keeps the original sensor band name.
                           Do not mix harmonized and native SR band names.
                           None keeps all bands in the source collection.
    scale                : scale SR_B* to reflectance and ST_B* to Kelvin
    max_cloud_cover      : maximum CLOUD_COVER (default 20)
    mask_clouds          : apply QA_PIXEL cloud/shadow mask (default False)
    clip                 : clip each image to AOI when aoi is provided

    Returns
    -------
    ee.ImageCollection sorted by acquisition date, containing images from
    both satellites within the requested window.
    """
    shared = dict(
        bands=bands,
        scale=scale,
        max_cloud_cover=max_cloud_cover,
        mask_clouds=mask_clouds,
        clip=clip,
    )
    col_l8 = _load_lc_collection(
        _L8_COLLECTION_ID, start_date, end_date, aoi, sensor_label="L8", **shared
    )
    col_l9 = _load_lc_collection(
        _L9_COLLECTION_ID, start_date, end_date, aoi, sensor_label="L9", **shared
    )
    return col_l8.merge(col_l9).sort("system:time_start")
