from __future__ import annotations

from pathlib import Path

import ee
import geemap


def l_download_image(
    image: ee.Image,
    outdir: str | Path,
    filename: str,
    *,
    region: ee.Geometry | None = None,
    scale: float = 30.0,
    crs: str = "EPSG:4326",
) -> Path:
    """Download a single GEE image to local disk as GeoTIFF.

    Limited to ~32 MB per file. For larger areas use export_image_to_drive.
    """
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{filename}.tif"
    geemap.ee_export_image(
        image,
        filename=str(path),
        scale=scale,
        region=region,
        crs=crs,
        file_per_band=False,
    )
    return path


def l_download_imagecollection(
    collection: ee.ImageCollection,
    outdir: str | Path,
    prefix: str,
    *,
    region: ee.Geometry | None = None,
    scale: float = 30.0,
    crs: str = "EPSG:4326",
) -> list[Path]:
    """Download every image in a collection to local disk as GeoTIFF.

    Files are named <prefix>_<YYYYMMDD>.tif. Limited to ~32 MB per file.
    """
    out = Path(outdir)
    images = collection.toList(collection.size())
    n = collection.size().getInfo()
    paths: list[Path] = []
    for i in range(n):
        img = ee.Image(images.get(i))
        date = img.date().format("YYYYMMdd").getInfo()
        filename = f"{prefix}_{date}"
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
    region: ee.Geometry | None = None,
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
        region=region,
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
    region: ee.Geometry | None = None,
    scale: float = 30.0,
    crs: str = "EPSG:4326",
    max_pixels: int = int(1e13),
    skip_empty_tiles: bool = False,
) -> list[ee.batch.Task]:
    """Submit async Google Drive export tasks for every image in a collection.

    Each task gets description and fileNamePrefix suffixed with _<YYYYMMDD>.
    Tasks are started immediately; this function does not wait for completion.
    """
    images = collection.toList(collection.size())
    n = collection.size().getInfo()
    tasks: list[ee.batch.Task] = []
    for i in range(n):
        img = ee.Image(images.get(i))
        date = img.date().format("YYYYMMdd").getInfo()
        task = export_image_to_drive(
            img,
            description=f"{description}_{date}",
            folder=folder,
            file_name_prefix=f"{file_name_prefix}_{date}",
            region=region,
            scale=scale,
            crs=crs,
            max_pixels=max_pixels,
            skip_empty_tiles=skip_empty_tiles,
        )
        tasks.append(task)
    return tasks
