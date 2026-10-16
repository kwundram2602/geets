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
OPTICAL = {"s2": get_s2, "l8l9": get_l8l9, "l8": get_l8, "l9": get_l9}
CLOUD_PROPERTY = {"s2": "CLOUDY_PIXEL_PERCENTAGE"}  # Landsat: CLOUD_COVER
MODIS = ("modis_ndvi", "modis_evi", "modis_lst_day", "modis_lst_night")
CLIMATE = tuple(f"era5:{d}" for d in ERA5_COLLECTIONS) + tuple(
    f"chirps:{d}" for d in CHIRPS_COLLECTIONS
)
DATASETS = tuple(OPTICAL) + MODIS + CLIMATE
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


def load_collection(
    dataset: str,
    start_date: str,
    end_date: str,
    aoi: ee.Geometry,
    *,
    bands: list[str] | None = None,
    max_cloud_cover: float = 20.0,
    mask_water: bool = False,
    use_s2cloudless: bool = False,
) -> ee.ImageCollection:
    """Masked and scaled collection for one of ``DATASETS`` (see module constants)."""
    if dataset in OPTICAL:
        if dataset == "s2":
            return get_s2(
                start_date,
                end_date,
                aoi,
                bands=bands or HARMONIZED_BANDS,
                max_cloud_cover=max_cloud_cover,
                mask_water=mask_water,
                use_s2cloudless=use_s2cloudless,
            )
        return OPTICAL[dataset](
            start_date,
            end_date,
            aoi,
            bands=bands or HARMONIZED_BANDS,
            scale=True,
            max_cloud_cover=max_cloud_cover,
            mask_clouds=True,
            clip=True,
        )
    if dataset in ("modis_ndvi", "modis_evi"):
        return load_modis_vi(
            start_date, end_date, aoi, band=dataset.split("_")[1].upper()
        )
    if dataset in ("modis_lst_day", "modis_lst_night"):
        return load_modis_lst(
            start_date, end_date, aoi, time_of_day=dataset.rsplit("_", 1)[1]
        )
    source, _, name = dataset.partition(":")
    if source == "era5" and name in ERA5_COLLECTIONS:
        return load_era5_daily(start_date, end_date, aoi, dataset=name, bands=bands)
    if source == "chirps" and name in CHIRPS_COLLECTIONS:
        return load_chirps_daily(start_date, end_date, aoi, dataset=name)
    raise ValueError(f"Unknown dataset {dataset!r}. Choose from: {list(DATASETS)}")


def composite(
    collection: ee.ImageCollection, reducer: str, dataset: str = ""
) -> ee.Image:
    """Reduce a collection to one image; ``least_cloudy`` picks a single scene."""
    if reducer not in REDUCERS:
        raise ValueError(f"Unknown reducer {reducer!r}. Choose from: {list(REDUCERS)}")
    if collection.size().getInfo() == 0:
        raise ValueError("No images found for this AOI, date range and cloud filter.")
    if reducer == "least_cloudy":
        prop = CLOUD_PROPERTY.get(dataset, "CLOUD_COVER")
        return ee.Image(collection.sort(prop).first())
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
    max_cloud_cover: float = 20.0,
    mask_water: bool = False,
    use_s2cloudless: bool = False,
    aoi_layer: str | None = None,
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
        max_cloud_cover, mask_water, use_s2cloudless: Optical scene filters
            (see get_s2).
        aoi_layer: Layer inside ``aoi_path`` (GeoPackage with several layers).
    """
    ensure_initialized()
    aoi = aoi_from_file(aoi_path, aoi_layer)
    col = load_collection(
        dataset,
        start_date,
        end_date,
        aoi,
        bands=bands,
        max_cloud_cover=max_cloud_cover,
        mask_water=mask_water,
        use_s2cloudless=use_s2cloudless,
    )
    scale = scale or native_scale(col)
    image = composite(col, reducer, dataset).clip(aoi)
    require_valid_pixels(image, aoi, scale, dataset)
    return download_checked(image, output_path, aoi, scale, crs)


def l_dem(
    aoi_path: str | Path,
    output_path: str | Path,
    *,
    source: str = "copernicus",
    products: list[str] | None = None,
    scale: float = 30.0,
    crs: str = "EPSG:4326",
    aoi_layer: str | None = None,
) -> Path:
    """DEM (optionally with slope/aspect/hillshade bands) over an AOI file as GeoTIFF.

    Args:
        source: "copernicus" (GLO-30), "srtm", "aster", "nasadem" or "fabdem".
        products: Any of "elevation", "slope", "aspect", "hillshade"; default elevation.
    """
    if source not in DEMS:
        raise ValueError(f"Unknown DEM source {source!r}. Choose from: {list(DEMS)}")
    ensure_initialized()
    aoi = aoi_from_file(aoi_path, aoi_layer)
    image = DEMS[source](aoi, products=products or ["elevation"])
    return download_checked(image, output_path, aoi, scale, crs)


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
) -> Path:
    """Per-image percentile/mean statistics of one band over an AOI file, as CSV.

    Args:
        dataset: See ``l_composite``.
        band: Band to reduce; default is the dataset's first band.
        scale: Reduction scale in metres; None uses the native resolution.
    """
    ensure_initialized()
    aoi = aoi_from_file(aoi_path, aoi_layer)
    col = load_collection(
        dataset,
        start_date,
        end_date,
        aoi,
        bands=[band] if band and dataset in OPTICAL else None,
        max_cloud_cover=max_cloud_cover,
    )
    band = band or ee.Image(col.first()).bandNames().get(0).getInfo()
    scale = scale or native_scale(col.select(band))
    df = reduce_region_stats(col, aoi, band, scale=int(scale), export_csv=False)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out)
    return out


def mosaic_per_day(collection: ee.ImageCollection) -> ee.ImageCollection:
    """One mosaic per acquisition day (e.g. adjacent Sentinel-2 tiles of one overpass).

    Each mosaic keeps ``system:time_start`` of its day and gets ``date`` (YYYY-MM-dd)
    and ``n_scenes``.
    """
    days = (
        collection.aggregate_array("system:time_start")
        .map(lambda t: ee.Date(t).format("YYYY-MM-dd"))
        .distinct()
        .sort()
    )

    def day_mosaic(day):
        start = ee.Date(day)
        scenes = collection.filterDate(start, start.advance(1, "day"))
        return (
            scenes.mosaic()
            .set("system:time_start", start.millis())
            .set("date", day)
            .set("n_scenes", scenes.size())
        )

    return ee.ImageCollection(days.map(day_mosaic))


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
    """``<prefix>_<YYYYMMDD>``, with ``_2``, ``_3``... for repeated dates."""
    names, seen = [], {}
    for date in dates:
        stem = f"{prefix}_{date.replace('-', '')}"
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
    max_cloud_cover: float = 20.0,
    mask_water: bool = False,
    use_s2cloudless: bool = False,
    per_day: bool = True,
    min_valid_fraction: float = 0.0,
    max_images: int = 30,
    prefix: str | None = None,
    aoi_layer: str | None = None,
) -> list[Path]:
    """Download every image of a dataset over an AOI file, one GeoTIFF per date.

    Args:
        dataset, bands, scale, crs, max_cloud_cover, mask_water, use_s2cloudless:
            As in ``l_composite``.
        output_dir: Folder for ``<prefix>_<YYYYMMDD>.tif`` files (created if missing).
        per_day: Mosaic all scenes of one day into one image (Sentinel-2 tiles,
            Landsat rows). Otherwise every scene is its own file.
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
        max_cloud_cover=max_cloud_cover,
        mask_water=mask_water,
        use_s2cloudless=use_s2cloudless,
    )
    series = mosaic_per_day(col) if per_day else col.sort("system:time_start")
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
        .map(lambda t: ee.Date(t).format("YYYY-MM-dd"))
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
