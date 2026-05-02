# exports.py — Download & Drive Export Functions

**Date:** 2026-05-02  
**Status:** Approved

## Summary

Replace the unfinished `Exporter` class in `src/geets/utils/exports.py` with four standalone functions that follow the library's functional style. Two functions download GEE images to local disk; two submit async Google Drive batch export tasks.

## Functions

### Local downloads (`l_` prefix)

```python
def l_download_image(
    image: ee.Image,
    outdir: str | Path,
    filename: str,           # stem only, .tif appended automatically
    *,
    region: ee.Geometry | None = None,
    scale: float = 30.0,
    crs: str = "EPSG:4326",
) -> Path
```

```python
def l_download_imagecollection(
    collection: ee.ImageCollection,
    outdir: str | Path,
    prefix: str,             # each file named <prefix>_<YYYYMMDD>.tif
    *,
    region: ee.Geometry | None = None,
    scale: float = 30.0,
    crs: str = "EPSG:4326",
) -> list[Path]
```

### Drive exports (no prefix — async, server-side)

```python
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
) -> ee.batch.Task
```

```python
def export_imagecollection_to_drive(
    collection: ee.ImageCollection,
    description: str,
    folder: str,
    file_name_prefix: str,   # per-image: <file_name_prefix>_<YYYYMMDD>
    *,
    region: ee.Geometry | None = None,
    scale: float = 30.0,
    crs: str = "EPSG:4326",
    max_pixels: int = int(1e13),
    skip_empty_tiles: bool = False,
) -> list[ee.batch.Task]
```

## Behaviour

### `l_download_image`
- Creates `outdir` if it does not exist.
- Writes `<outdir>/<filename>.tif` via `geemap.ee_export_image` (≤32 MB limit, same mechanism as `export_pairs`).
- Returns the `Path` of the written file.

### `l_download_imagecollection`
- Calls `collection.size().getInfo()` for the count, then iterates via `.toList()`.
- Per image: fetches date with `img.date().format("YYYYMMdd").getInfo()`, builds filename `<prefix>_<YYYYMMDD>`, delegates to `l_download_image`.
- Prints progress line per image (consistent with `export_pairs` style).
- Returns `list[Path]` of all written files.

### `export_image_to_drive`
- Builds one `ee.batch.Export.image.toDrive` task and calls `.start()`.
- Returns the started `ee.batch.Task` so the caller can poll `.status()`.

### `export_imagecollection_to_drive`
- Same iteration pattern as the collection download.
- Per-image `description` → `<description>_<YYYYMMDD>`, `fileNamePrefix` → `<file_name_prefix>_<YYYYMMDD>`.
- Starts all tasks; does **not** wait or poll (fire-and-forget).
- Returns `list[ee.batch.Task]`.

## File changes

| File | Change |
|------|--------|
| `src/geets/utils/exports.py` | Replace `Exporter` class with 4 standalone functions |
| `src/geets/__init__.py` | Re-export all 4 functions in `__all__` |

## Out of scope

- Task polling / progress monitoring for Drive exports.
- The `map_thumb_preview` stub (broken, unrelated — delete it).
- `geemap.ee_export_image` size limit workaround (use `export_*_to_drive` for large areas).
