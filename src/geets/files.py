"""File-based entry points: AOI file in, GeoTIFF/CSV out.

These chain the lazy geets loaders with a temporal reducer and a local download, so
that callers without an Earth Engine session of their own (scripts, the QGIS plugin)
get finished files. Earth Engine is initialized from the geets .env file on demand.
"""

from __future__ import annotations

from pathlib import Path

import ee
import geopandas as gpd

from .climate.chirps import CHIRPS_COLLECTIONS, load_chirps_daily
from .climate.era5 import ERA5_COLLECTIONS, load_era5_daily
from .config import ensure_initialized
from .drive import l_export_and_pull
from .modis import load_modis_lst, load_modis_vi
from .optical.landsat import get_l8, get_l8l9, get_l9
from .optical.sentinel2 import get_s2
from .terrain.dem import (
    load_aster,
    load_copernicus_dem,
    load_fabdem,
    load_nasadem,
    load_srtm,
)
from .timeseries.reduce import reduce_region_stats
from .utils.exports import l_download_image
from .utils.gee import shapely_to_ee

HARMONIZED_BANDS = ["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2"]
REDUCERS = ("median", "mean", "min", "max", "sum", "least_cloudy")
OPTICAL = ("s2", "l8l9", "l8", "l9")
MODIS = ("modis_ndvi", "modis_evi", "modis_lst_day", "modis_lst_night")
CLIMATE = tuple(f"era5:{d}" for d in ERA5_COLLECTIONS) + tuple(
    f"chirps:{d}" for d in CHIRPS_COLLECTIONS
)
DATASETS = tuple(OPTICAL) + MODIS + CLIMATE
# Masking and scene-filter options a caller may set per dataset family; scaling,
# clipping and band naming stay fixed by the file API. Defaults: see the loaders.
MASK_OPTIONS = {
    "s2": (
        "max_cloud_cover",
        "mask_clouds",
        "mask_cirrus",
        "mask_water",
        "use_s2cloudless",
        "cld_prb_thresh",
        "nir_drk_thresh",
        "cld_prj_dist",
        "buffer",
        "scl_classes",
    ),
    "landsat": ("max_cloud_cover", "mask_clouds", "qa_bits", "mask_saturated"),
    "modis_vi": ("mask_clouds", "max_qa"),
    "modis_lst": ("mask_clouds",),
    "climate": (),
}
DEMS = {
    "copernicus": load_copernicus_dem,
    "srtm": load_srtm,
    "aster": load_aster,
    "nasadem": load_nasadem,
    "fabdem": load_fabdem,
}


def aoi_from_file(aoi_path: str | Path, layer: str | None = None) -> ee.Geometry:
    """Dissolve all features of a vector file into one EPSG:4326 ee.Geometry."""
    gdf = gpd.read_file(aoi_path, layer=layer)
    if gdf.empty:
        raise ValueError(f"AOI file {aoi_path} has no features")
    if gdf.crs is None:
        raise ValueError(f"AOI file {aoi_path} has no CRS")
    geom = gdf.to_crs("EPSG:4326").union_all()
    if geom.area == 0:
        # a point or line AOI silently yields a one-pixel (or empty) download
        raise ValueError(
            f"AOI file {aoi_path} has no area ({geom.geom_type}); use a polygon layer"
        )
    return shapely_to_ee(geom)


def dataset_family(dataset: str) -> str:
    """Key of ``MASK_OPTIONS`` for a dataset; raises for unknown datasets."""
    if dataset == "s2":
        return "s2"
    if dataset in ("l8l9", "l8", "l9"):
        return "landsat"
    if dataset in ("modis_ndvi", "modis_evi"):
        return "modis_vi"
    if dataset in ("modis_lst_day", "modis_lst_night"):
        return "modis_lst"
    if dataset in CLIMATE:
        return "climate"
    raise ValueError(f"Unknown dataset {dataset!r}. Choose from: {list(DATASETS)}")


def load_collection(
    dataset: str,
    start_date: str,
    end_date: str,
    aoi: ee.Geometry,
    *,
    bands: list[str] | None = None,
    **options,
) -> ee.ImageCollection:
    """Scaled collection for one of ``DATASETS``, masked as requested.

    ``options`` are the masking/scene-filter arguments of the dataset's loader, listed
    per dataset family in ``MASK_OPTIONS``:

    - s2 (``get_s2``): max_cloud_cover, mask_clouds (QA60), mask_cirrus, mask_water
      (SCL), scl_classes, use_s2cloudless, cld_prb_thresh, nir_drk_thresh,
      cld_prj_dist, buffer
    - Landsat (``get_l8``/``get_l9``/``get_l8l9``): max_cloud_cover, mask_clouds
      (default True here), qa_bits, mask_saturated
    - MODIS VI (``load_modis_vi``): mask_clouds, max_qa; MODIS LST: mask_clouds
    - ERA5 / CHIRPS: none

    An option that does not apply to the dataset raises ValueError instead of being
    ignored silently.
    """
    family = dataset_family(dataset)
    allowed = MASK_OPTIONS[family]
    unknown = sorted(set(options) - set(allowed))
    if unknown:
        raise ValueError(
            f"Option(s) {unknown} not available for {dataset}; "
            f"available: {list(allowed) or 'none'}"
        )
    if family == "s2":
        return get_s2(
            start_date, end_date, aoi, bands=bands or HARMONIZED_BANDS, **options
        )
    if family == "landsat":
        loader = {"l8l9": get_l8l9, "l8": get_l8, "l9": get_l9}[dataset]
        return loader(
            start_date,
            end_date,
            aoi,
            bands=bands or HARMONIZED_BANDS,
            scale=True,
            clip=True,
            **{"mask_clouds": True, **options},
        )
    if family == "modis_vi":
        band = dataset.split("_")[1].upper()
        return load_modis_vi(start_date, end_date, aoi, band=band, **options)
    if family == "modis_lst":
        time_of_day = dataset.rsplit("_", 1)[1]
        return load_modis_lst(
            start_date, end_date, aoi, time_of_day=time_of_day, **options
        )
    source, _, name = dataset.partition(":")
    if source == "era5":
        return load_era5_daily(start_date, end_date, aoi, dataset=name, bands=bands)
    return load_chirps_daily(start_date, end_date, aoi, dataset=name)


def composite(
    collection: ee.ImageCollection,
    reducer: str,
    dataset: str = "",
    aoi: ee.Geometry | None = None,
) -> ee.Image:
    """Reduce a collection to one image.

    ``least_cloudy`` picks one overpass (its tiles mosaicked, see
    ``mosaic_per_overpass``): the one with the largest unmasked share of ``aoi``.
    With cloud masking on (the default) that is the most cloud-free overpass over
    the AOI; scene-wide cloud percentages are not used, as they describe whole tiles.
    """
    if reducer not in REDUCERS:
        raise ValueError(f"Unknown reducer {reducer!r}. Choose from: {list(REDUCERS)}")
    if collection.size().getInfo() == 0:
        raise ValueError("No images found for this AOI, date range and cloud filter.")
    if reducer == "least_cloudy":
        if aoi is None:
            raise ValueError("least_cloudy needs the AOI to rank overpasses.")
        overpasses = mosaic_per_overpass(collection, overpass_keys(dataset))
        ranked = with_valid_fraction(overpasses, aoi)
        return ee.Image(ranked.sort("valid_fraction", False).first())
    return getattr(collection, reducer)()


def native_scale(collection: ee.ImageCollection) -> float:
    """Nominal pixel size (m) of the collection's first band."""
    return ee.Image(collection.first()).select(0).projection().nominalScale().getInfo()


def require_valid_pixels(
    image: ee.Image, aoi: ee.Geometry, scale: float, dataset: str = ""
) -> None:
    """Raise if the image has no unmasked pixel in the AOI.

    Otherwise the download succeeds and writes an all-nodata GeoTIFF, which looks
    like a bug. Typical cause: MODIS land products have no data over open water.
    """
    counts = (
        image.select(0)
        .reduceRegion(ee.Reducer.count(), aoi, scale, bestEffort=True, maxPixels=1e8)
        .values()
        .getInfo()
    )
    if not any(counts):
        hint = (
            " MODIS land products have no data over water."
            if "modis" in dataset
            else ""
        )
        raise ValueError(
            f"No valid pixels in the AOI for {dataset or 'this image'} (all masked: "
            f"no coverage, clouds or QA filter).{hint}"
        )


def download_checked(
    image: ee.Image,
    output_path: str | Path,
    region: ee.Geometry,
    scale: float,
    crs: str = "EPSG:4326",
) -> Path:
    """``l_download_image`` to an exact path; raises if nothing was written.

    geemap only prints download errors (e.g. over the ~32 MB request limit), so the
    file is checked here instead of returning a path that does not exist.
    """
    out = Path(output_path)
    out.unlink(missing_ok=True)
    path = l_download_image(
        image.toFloat(), out.parent, out.stem, region=region, scale=scale, crs=crs
    )
    if not path.is_file():
        raise RuntimeError(
            f"Earth Engine download failed for {out.name} (see log). Usual cause: "
            "the request exceeds ~32 MB; use a larger scale, fewer bands or a "
            "smaller AOI."
        )
    if path != out:
        path.replace(out)
    return out


def deliver(
    image: ee.Image,
    output_path: str | Path,
    region: ee.Geometry,
    scale: float,
    crs: str = "EPSG:4326",
    *,
    via_drive: bool = False,
    drive_folder: str = "geets",
) -> Path:
    """Write ``image`` to ``output_path``: direct download, or via a Drive export.

    ``via_drive`` exports to Google Drive (no ~32 MB limit), waits for the task and
    pulls the result to ``output_path`` (tiled exports merged into that one file).
    """
    if not via_drive:
        return download_checked(image, output_path, region, scale, crs)
    return l_export_and_pull(
        image.toFloat(), output_path, region, scale, crs, folder=drive_folder
    )


def l_composite(
    aoi_path: str | Path,
    start_date: str,
    end_date: str,
    output_path: str | Path,
    *,
    dataset: str = "s2",
    bands: list[str] | None = None,
    reducer: str = "median",
    scale: float | None = None,
    crs: str = "EPSG:4326",
    aoi_layer: str | None = None,
    via_drive: bool = False,
    drive_folder: str = "geets",
    **options,
) -> Path:
    """Temporal composite of a dataset over an AOI file, downloaded as GeoTIFF.

    Args:
        aoi_path: Vector file; all features are dissolved into one AOI.
        start_date, end_date: ISO dates, half-open [start, end).
        output_path: GeoTIFF to write (``.tif``).
        dataset: One of ``DATASETS``: "s2", "l8l9", "l8", "l9", "modis_ndvi",
            "modis_evi", "modis_lst_day", "modis_lst_night", "era5:<name>",
            "chirps:<name>".
        bands: Bands to keep (optical: harmonized names, default all six;
            ERA5: band names).
        reducer: "median", "mean", "min", "max", "sum" or "least_cloudy" (optical).
        scale: Pixel size in metres; None uses the dataset's native resolution.
        crs: CRS of the GeoTIFF.
        aoi_layer: Layer inside ``aoi_path`` (GeoPackage with several layers).
        via_drive: Export via Google Drive instead of downloading directly (for
            results over ~32 MB); see ``deliver``.
        drive_folder: Drive folder for ``via_drive``.
        **options: Masking and scene filters of the dataset (``MASK_OPTIONS``,
            documented in ``load_collection``), e.g. ``mask_clouds=False``,
            ``qa_bits=["cloud", "cloud_shadow"]``, ``cld_prb_thresh=40``.
    """
    ensure_initialized()
    aoi = aoi_from_file(aoi_path, aoi_layer)
    col = load_collection(
        dataset,
        start_date,
        end_date,
        aoi,
        bands=bands,
        **options,
    )
    scale = scale or native_scale(col)
    image = composite(col, reducer, dataset, aoi).clip(aoi)
    require_valid_pixels(image, aoi, scale, dataset)
    return deliver(
        image,
        output_path,
        aoi,
        scale,
        crs,
        via_drive=via_drive,
        drive_folder=drive_folder,
    )


def l_dem(
    aoi_path: str | Path,
    output_path: str | Path,
    *,
    source: str = "copernicus",
    products: list[str] | None = None,
    scale: float = 30.0,
    crs: str = "EPSG:4326",
    aoi_layer: str | None = None,
    via_drive: bool = False,
    drive_folder: str = "geets",
) -> Path:
    """DEM (optionally with slope/aspect/hillshade bands) over an AOI file as GeoTIFF.

    Args:
        source: "copernicus" (GLO-30), "srtm", "aster", "nasadem" or "fabdem".
        products: Any of "elevation", "slope", "aspect", "hillshade"; default elevation.
        via_drive, drive_folder: Export via Google Drive (see ``deliver``).
    """
    if source not in DEMS:
        raise ValueError(f"Unknown DEM source {source!r}. Choose from: {list(DEMS)}")
    ensure_initialized()
    aoi = aoi_from_file(aoi_path, aoi_layer)
    image = DEMS[source](aoi, products=products or ["elevation"])
    return deliver(
        image,
        output_path,
        aoi,
        scale,
        crs,
        via_drive=via_drive,
        drive_folder=drive_folder,
    )


def l_region_timeseries_csv(
    aoi_path: str | Path,
    start_date: str,
    end_date: str,
    output_path: str | Path,
    *,
    dataset: str = "modis_ndvi",
    band: str | None = None,
    scale: float | None = None,
    max_cloud_cover: float = 20.0,
    aoi_layer: str | None = None,
    **options,
) -> Path:
    """Percentile/mean statistics of one band over an AOI file per overpass, as CSV.

    Scenes of one overpass (adjacent tiles) are mosaicked first, so every row covers
    the whole AOI; the ``date`` column holds date and time (``YYYY-MM-ddTHH:mm``), so
    two overpasses on one day stay apart.

    Args:
        dataset: See ``l_composite``.
        band: Band to reduce; default is the dataset's first band.
        scale: Reduction scale in metres; None uses the native resolution.
        max_cloud_cover: Scene filter for optical datasets; not used for others.
        **options: Further masking options of the dataset (see ``load_collection``).
    """
    if dataset in OPTICAL:
        options.setdefault("max_cloud_cover", max_cloud_cover)
    ensure_initialized()
    aoi = aoi_from_file(aoi_path, aoi_layer)
    col = load_collection(
        dataset,
        start_date,
        end_date,
        aoi,
        bands=[band] if band and dataset in OPTICAL else None,
        **options,
    )
    band = band or ee.Image(col.first()).bandNames().get(0).getInfo()
    scale = scale or native_scale(col.select(band))
    overpasses = mosaic_per_overpass(col, overpass_keys(dataset))
    df = reduce_region_stats(
        overpasses,
        aoi,
        band,
        scale=int(scale),
        date_format="YYYY-MM-dd'T'HH:mm",
        export_csv=False,
    )
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out)
    return out


# Scene properties that tell overpasses apart: one day can hold several (e.g. S2A and
# S2B ten minutes apart in overlapping orbits), and those must never be mosaicked.
OVERPASS_KEYS = {
    "s2": ["SPACECRAFT_NAME", "SENSING_ORBIT_NUMBER"],
    "landsat": ["SPACECRAFT_ID", "WRS_PATH"],
}


def overpass_keys(dataset: str) -> list[str]:
    """Properties that, together with the date, identify one overpass of ``dataset``."""
    return OVERPASS_KEYS.get(dataset_family(dataset), [])


def mosaic_per_overpass(
    collection: ee.ImageCollection, keys: list[str] | None = None
) -> ee.ImageCollection:
    """One mosaic per overpass: the adjacent tiles or rows of one acquisition.

    Scenes are grouped by date plus ``keys`` (see ``overpass_keys``), so two
    satellites passing on the same day give two images instead of one image stitched
    from both. Each mosaic gets ``system:time_start`` of its first scene, ``date``
    (YYYY-MM-dd), ``overpass`` and ``n_scenes``; the result is in time order.
    """
    keys = keys or []

    def tag(img):
        parts = [img.date().format("YYYY-MM-dd")] + [img.get(k) for k in keys]
        return img.set("overpass", ee.List(parts).join("_"))

    tagged = collection.map(tag)

    def overpass_mosaic(key):
        scenes = tagged.filter(ee.Filter.eq("overpass", key))
        start = ee.Date(scenes.aggregate_min("system:time_start"))
        return (
            scenes.mosaic()
            .set("system:time_start", start.millis())
            .set("date", start.format("YYYY-MM-dd"))
            .set("overpass", key)
            .set("n_scenes", scenes.size())
        )

    overpasses = tagged.aggregate_array("overpass").distinct()
    return ee.ImageCollection(overpasses.map(overpass_mosaic)).sort("system:time_start")


def with_valid_fraction(
    collection: ee.ImageCollection, aoi: ee.Geometry
) -> ee.ImageCollection:
    """Add ``valid_fraction``: share of the AOI covered by unmasked pixels (0..1).

    Measured on the first band on a ~200 x 200 sample grid over the AOI, so the
    check stays cheap for large AOIs. Both counts use the same EPSG:4326 grid: in a
    scene's own UTM grid the same nominal scale yields cos(lat) times fewer pixels.
    """
    check_scale = max(aoi.area(maxError=1).getInfo() ** 0.5 / 200, 10)
    total = (
        ee.Image(1)
        .clip(aoi)
        .reduceRegion(
            ee.Reducer.count(), aoi, check_scale, crs="EPSG:4326", maxPixels=1e8
        )
        .values()
        .get(0)
    )

    def add(img):
        valid = (
            img.select(0)
            .reduceRegion(
                ee.Reducer.count(), aoi, check_scale, crs="EPSG:4326", maxPixels=1e8
            )
            .values()
            .get(0)
        )
        return img.set("valid_fraction", ee.Number(valid).divide(total))

    return collection.map(add)


def select_series(
    dates: list[str], fractions: list[float | None], min_valid_fraction: float = 0.0
) -> list[int]:
    """Indices of images worth downloading: some valid pixels and at least the
    requested share of the AOI covered."""
    return [
        i
        for i, fraction in enumerate(fractions)
        if fraction and fraction >= min_valid_fraction
    ]


def series_filenames(prefix: str, dates: list[str]) -> list[str]:
    """``<prefix>_<YYYYMMDD>`` from ``YYYY-MM-dd`` or ``YYYY-MM-ddTHH:mm`` strings.

    Days with several images get the time (``<prefix>_<YYYYMMDD>T<HHMM>``); names
    that are still repeated get ``_2``, ``_3``...
    """
    days = [d.split("T")[0] for d in dates]
    names, seen = [], {}
    for day, date in zip(days, dates, strict=True):
        stamp = date if days.count(day) > 1 else day
        stem = f"{prefix}_{stamp.replace('-', '').replace(':', '')}"
        seen[stem] = seen.get(stem, 0) + 1
        names.append(stem if seen[stem] == 1 else f"{stem}_{seen[stem]}")
    return names


def l_image_series(
    aoi_path: str | Path,
    start_date: str,
    end_date: str,
    output_dir: str | Path,
    *,
    dataset: str = "s2",
    bands: list[str] | None = None,
    scale: float | None = None,
    crs: str = "EPSG:4326",
    per_day: bool = True,
    min_valid_fraction: float = 0.0,
    max_images: int = 30,
    prefix: str | None = None,
    aoi_layer: str | None = None,
    **options,
) -> list[Path]:
    """Download every image of a dataset over an AOI file, one GeoTIFF per date.

    Args:
        dataset, bands, scale, crs, **options: As in ``l_composite``.
        output_dir: Folder for ``<prefix>_<YYYYMMDD>.tif`` files (created if missing).
        per_day: Mosaic the scenes of one overpass into one image (adjacent
            Sentinel-2 tiles, Landsat rows; see ``mosaic_per_overpass``). Two
            overpasses on the same day stay separate files with the time in the
            name. Otherwise every scene is its own file.
        min_valid_fraction: Skip images whose unmasked pixels cover less than this
            share of the AOI (0..1). Images without any valid pixel are always skipped.
        max_images: Refuse longer series instead of starting a huge download.
        prefix: File name prefix; default is the dataset name.

    Returns:
        Paths of the written GeoTIFFs in date order.
    """
    ensure_initialized()
    aoi = aoi_from_file(aoi_path, aoi_layer)
    col = load_collection(
        dataset,
        start_date,
        end_date,
        aoi,
        bands=bands,
        **options,
    )
    series = (
        mosaic_per_overpass(col, overpass_keys(dataset))
        if per_day
        else col.sort("system:time_start")
    )
    n = series.size().getInfo()
    if n == 0:
        raise ValueError("No images found for this AOI, date range and cloud filter.")
    if n > max_images:
        raise ValueError(
            f"{n} images in this period (more than max_images={max_images}); "
            "shorten the date range or raise the limit."
        )
    # the native scale must come from the source scenes: a mosaic has a 1° default grid
    scale = scale or native_scale(col)
    series = with_valid_fraction(series.map(lambda img: img.clip(aoi)), aoi)
    dates = (
        series.aggregate_array("system:time_start")
        .map(lambda t: ee.Date(t).format("YYYY-MM-dd'T'HH:mm"))
        .getInfo()
    )
    fractions = series.aggregate_array("valid_fraction").getInfo()
    keep = select_series(dates, fractions, min_valid_fraction)
    skipped = len(dates) - len(keep)
    print(
        f"[geets.files] {len(dates)} images, {len(keep)} to download, "
        f"{skipped} skipped (valid AOI share below {min_valid_fraction:.0%} or empty)"
    )
    images = series.toList(n)
    names = series_filenames(prefix or dataset.replace(":", "_").lower(), dates)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for count, i in enumerate(keep, 1):
        print(
            f"[geets.files] {count}/{len(keep)}  {dates[i]}  {fractions[i]:.0%} valid"
        )
        image = ee.Image(images.get(i))
        paths.append(download_checked(image, out / f"{names[i]}.tif", aoi, scale, crs))
    return paths
