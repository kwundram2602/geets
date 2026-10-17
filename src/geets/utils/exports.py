from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import ee
import geemap

# Scene properties naming the tile of an image: Sentinel-2 MGRS tile, Landsat path/row
_TILE_PROPERTIES = ["MGRS_TILE", "WRS_PATH", "WRS_ROW"]


def _normalize_region(
    region: ee.Geometry | ee.FeatureCollection | None,
) -> ee.Geometry | None:
    """Resolve a region to a plain Geometry GEE can export against.

    FeatureCollections and computed geometries fail at export time with
    "Setting the CRS on a computed Geometry is not supported" unless
    .transform() is called first to materialize the projection.
    """
    if region is None:
        return None
    if isinstance(region, ee.FeatureCollection):
        region = region.geometry()
    return region.transform("EPSG:4326", maxError=1)


def _image_meta(collection: ee.ImageCollection) -> list[dict]:
    """Time, tile and index of every image, fetched in one request."""

    def meta(img):
        return ee.Feature(
            None, {"t": img.date().millis(), "index": img.get("system:index")}
        ).copyProperties(img, _TILE_PROPERTIES)

    features = collection.map(meta).getInfo()["features"]
    metas = []
    for f in features:
        p = f["properties"]
        if p.get("MGRS_TILE"):
            tile = p["MGRS_TILE"]
        elif p.get("WRS_PATH") is not None and p.get("WRS_ROW") is not None:
            tile = f"{int(p['WRS_PATH']):03d}{int(p['WRS_ROW']):03d}"
        else:
            tile = ""
        metas.append({"t": p["t"], "tile": tile, "index": p.get("index") or ""})
    return metas


def export_suffixes(metas: list[dict]) -> list[str]:
    """Unique file-name suffixes: ``YYYYMMDD``, or ``YYYYMMDDTHHMM_<tile>`` on days
    with several images (tiles of one overpass, or several overpasses).

    ``metas`` as returned by ``_image_meta``: ``t`` (ms), ``tile`` and ``index``
    (used when there is no tile). Names still repeated get ``_2``, ``_3``...
    """
    times = [datetime.fromtimestamp(m["t"] / 1000, UTC) for m in metas]
    days = Counter(t.strftime("%Y%m%d") for t in times)
    names, seen = [], Counter()
    for m, t in zip(metas, times, strict=True):
        day = t.strftime("%Y%m%d")
        name = (
            day
            if days[day] == 1
            else f"{t.strftime('%Y%m%dT%H%M')}_{m['tile'] or m['index']}"
        )
        seen[name] += 1
        names.append(name if seen[name] == 1 else f"{name}_{seen[name]}")
    return names


def l_download_image(
    image: ee.Image,
    outdir: str | Path,
    filename: str,
    *,
    region: ee.Geometry | ee.FeatureCollection | None = None,
    scale: float = 30.0,
    crs: str = "EPSG:4326",
) -> Path:
    """Download a single GEE image to local disk as GeoTIFF.

    Limited to ~32 MB per file. For larger areas use export_image_to_drive.

    Args:
        image: GEE image to download.
        outdir: Local directory to write the file into (created if missing).
        filename: Output file stem; `.tif` is appended automatically.
        region: Export region geometry. If None, uses the image's footprint.
        scale: Pixel size in metres.
        crs: Coordinate reference system of the output GeoTIFF.

    Returns:
        Path to the written GeoTIFF file.
    """
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{filename}.tif"
    geemap.ee_export_image(
        image,
        filename=str(path),
        scale=scale,
        region=_normalize_region(region),
        crs=crs,
        file_per_band=False,
    )
    return path


def l_download_imagecollection(
    collection: ee.ImageCollection,
    outdir: str | Path,
    prefix: str,
    *,
    region: ee.Geometry | ee.FeatureCollection | None = None,
    scale: float = 30.0,
    crs: str = "EPSG:4326",
) -> list[Path]:
    """Download every image in a collection to local disk as GeoTIFF.

    Files are named <prefix>_<YYYYMMDD>.tif; on days with several images (tiles
    or overpasses) <prefix>_<YYYYMMDD>T<HHMM>_<tile>.tif (see ``export_suffixes``),
    so no file overwrites another. Limited to ~32 MB per file.
    """
    out = Path(outdir)
    images = collection.toList(collection.size())
    n = collection.size().getInfo()
    suffixes = export_suffixes(_image_meta(collection)) if n else []
    paths: list[Path] = []
    for i in range(n):
        img = ee.Image(images.get(i))
        filename = f"{prefix}_{suffixes[i]}"
        print(f"[geets.exports] {i + 1}/{n}  → {filename}.tif")
        path = l_download_image(img, out, filename, region=region, scale=scale, crs=crs)
        paths.append(path)
    if n:
        print(f"[geets.exports] Done.  {n} image(s) downloaded to {out}/")
    return paths


def export_image_to_drive(
    image: ee.Image,
    description: str,
    folder: str,
    file_name_prefix: str,
    *,
    region: ee.Geometry | ee.FeatureCollection | None = None,
    scale: float = 30.0,
    crs: str = "EPSG:4326",
    max_pixels: int = int(1e13),
    skip_empty_tiles: bool = False,
) -> ee.batch.Task:
    """Submit an async Google Drive export task for a single GEE image.

    Returns the started task; call task.status() to poll progress.
    """
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=description,
        folder=folder,
        fileNamePrefix=file_name_prefix,
        region=_normalize_region(region),
        scale=scale,
        crs=crs,
        maxPixels=max_pixels,
        skipEmptyTiles=skip_empty_tiles,
    )
    task.start()
    return task


def export_imagecollection_to_drive(
    collection: ee.ImageCollection,
    description: str,
    folder: str,
    file_name_prefix: str,
    *,
    region: ee.Geometry | ee.FeatureCollection | None = None,
    scale: float = 30.0,
    crs: str = "EPSG:4326",
    max_pixels: int = int(1e13),
    skip_empty_tiles: bool = False,
) -> list[ee.batch.Task]:
    """Submit async Google Drive export tasks for every image in a collection.

    Each task gets description and fileNamePrefix suffixed with _<YYYYMMDD>, or
    _<YYYYMMDD>T<HHMM>_<tile> on days with several images (see ``export_suffixes``).
    Tasks are started immediately; this function does not wait for completion.
    """
    images = collection.toList(collection.size())
    n = collection.size().getInfo()
    suffixes = export_suffixes(_image_meta(collection)) if n else []
    tasks: list[ee.batch.Task] = []
    for i in range(n):
        img = ee.Image(images.get(i))
        task = export_image_to_drive(
            img,
            description=f"{description}_{suffixes[i]}",
            folder=folder,
            file_name_prefix=f"{file_name_prefix}_{suffixes[i]}",
            region=region,
            scale=scale,
            crs=crs,
            max_pixels=max_pixels,
            skip_empty_tiles=skip_empty_tiles,
        )
        tasks.append(task)
    return tasks
