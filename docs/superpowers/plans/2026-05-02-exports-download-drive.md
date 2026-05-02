# exports.py — Download & Drive Export Functions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken `Exporter` class in `exports.py` with four standalone functions: two for local GeoTIFF downloads and two for async Google Drive batch exports.

**Architecture:** Flat module of four pure functions. Local downloads delegate to `geemap.ee_export_image` (same as `export_pairs`). Drive exports build and start `ee.batch.Export.image.toDrive` tasks, returning them to the caller for status polling. The collection variants iterate via `.toList()` and delegate to the single-image functions.

**Tech Stack:** Python 3.13, `ee` (Google Earth Engine), `geemap`, `pathlib.Path`, `unittest.mock` for tests.

---

## File Map

| File | Action |
|------|--------|
| `src/geets/utils/exports.py` | **Rewrite** — delete `Exporter` class, add 4 functions |
| `src/geets/__init__.py` | **Modify** — add import + `__all__` entries for all 4 functions |
| `tests/unit/test_exports.py` | **Create** — unit tests for all 4 functions |

---

### Task 1: `l_download_image`

**Files:**
- Modify: `src/geets/utils/exports.py`
- Create: `tests/unit/test_exports.py`

- [ ] **Step 1: Create the test file with two failing tests**

Create `tests/unit/test_exports.py`:

```python
from unittest.mock import MagicMock, patch
from pathlib import Path


def test_l_download_image_creates_outdir_and_calls_geemap(tmp_path):
    from geets.utils.exports import l_download_image

    mock_image = MagicMock()
    outdir = tmp_path / "downloads"

    with patch("geets.utils.exports.geemap.ee_export_image") as mock_export:
        result = l_download_image(mock_image, outdir, "test_img", scale=10.0, crs="EPSG:32636")

    assert outdir.exists()
    assert result == outdir / "test_img.tif"
    mock_export.assert_called_once_with(
        mock_image,
        filename=str(outdir / "test_img.tif"),
        scale=10.0,
        region=None,
        crs="EPSG:32636",
        file_per_band=False,
    )


def test_l_download_image_appends_tif_extension(tmp_path):
    from geets.utils.exports import l_download_image

    with patch("geets.utils.exports.geemap.ee_export_image"):
        result = l_download_image(MagicMock(), tmp_path, "myfile")

    assert result == tmp_path / "myfile.tif"
```

- [ ] **Step 2: Run to confirm they fail**

```
python -m pytest tests/unit/test_exports.py -v
```

Expected: `ImportError` or `AttributeError` — `l_download_image` does not exist yet.

- [ ] **Step 3: Rewrite `exports.py` with `l_download_image`**

Replace all content of `src/geets/utils/exports.py` with:

```python
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
```

- [ ] **Step 4: Run tests to confirm they pass**

```
python -m pytest tests/unit/test_exports.py -v
```

Expected: 2 PASSED.

- [ ] **Step 5: Commit**

```
git add src/geets/utils/exports.py tests/unit/test_exports.py
git commit -m "feat: add l_download_image"
```

---

### Task 2: `l_download_imagecollection`

**Files:**
- Modify: `src/geets/utils/exports.py`
- Modify: `tests/unit/test_exports.py`

- [ ] **Step 1: Add failing test**

Append to `tests/unit/test_exports.py`:

```python
def test_l_download_imagecollection_names_files_by_date(tmp_path):
    from geets.utils.exports import l_download_imagecollection

    mock_img1 = MagicMock()
    mock_img1.date.return_value.format.return_value.getInfo.return_value = "20220601"
    mock_img2 = MagicMock()
    mock_img2.date.return_value.format.return_value.getInfo.return_value = "20220615"

    mock_col = MagicMock()
    mock_col.size.return_value.getInfo.return_value = 2
    mock_col.toList.return_value.get.side_effect = [mock_img1, mock_img2]

    with patch("geets.utils.exports.geemap.ee_export_image"), \
         patch("geets.utils.exports.ee.Image", side_effect=lambda x: x):
        paths = l_download_imagecollection(mock_col, tmp_path, "sentinel2")

    assert paths == [
        tmp_path / "sentinel2_20220601.tif",
        tmp_path / "sentinel2_20220615.tif",
    ]


def test_l_download_imagecollection_returns_empty_list_for_empty_collection(tmp_path):
    from geets.utils.exports import l_download_imagecollection

    mock_col = MagicMock()
    mock_col.size.return_value.getInfo.return_value = 0

    with patch("geets.utils.exports.geemap.ee_export_image"):
        paths = l_download_imagecollection(mock_col, tmp_path, "prefix")

    assert paths == []
```

- [ ] **Step 2: Run to confirm they fail**

```
python -m pytest tests/unit/test_exports.py::test_l_download_imagecollection_names_files_by_date tests/unit/test_exports.py::test_l_download_imagecollection_returns_empty_list_for_empty_collection -v
```

Expected: `ImportError` — `l_download_imagecollection` not defined.

- [ ] **Step 3: Add `l_download_imagecollection` to `exports.py`**

Append after `l_download_image`:

```python
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
```

- [ ] **Step 4: Run all tests**

```
python -m pytest tests/unit/test_exports.py -v
```

Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```
git add src/geets/utils/exports.py tests/unit/test_exports.py
git commit -m "feat: add l_download_imagecollection"
```

---

### Task 3: `export_image_to_drive`

**Files:**
- Modify: `src/geets/utils/exports.py`
- Modify: `tests/unit/test_exports.py`

- [ ] **Step 1: Add failing test**

Append to `tests/unit/test_exports.py`:

```python
def test_export_image_to_drive_starts_task_and_returns_it():
    from geets.utils.exports import export_image_to_drive

    mock_image = MagicMock()
    mock_task = MagicMock()

    with patch("geets.utils.exports.ee.batch.Export.image.toDrive", return_value=mock_task) as mock_drive:
        result = export_image_to_drive(
            mock_image, "my_desc", "MyFolder", "my_prefix", scale=30.0
        )

    mock_drive.assert_called_once_with(
        image=mock_image,
        description="my_desc",
        folder="MyFolder",
        fileNamePrefix="my_prefix",
        region=None,
        scale=30.0,
        crs="EPSG:4326",
        maxPixels=int(1e13),
        skipEmptyTiles=False,
    )
    mock_task.start.assert_called_once()
    assert result is mock_task
```

- [ ] **Step 2: Run to confirm it fails**

```
python -m pytest tests/unit/test_exports.py::test_export_image_to_drive_starts_task_and_returns_it -v
```

Expected: `ImportError` — `export_image_to_drive` not defined.

- [ ] **Step 3: Add `export_image_to_drive` to `exports.py`**

Append after `l_download_imagecollection`:

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
```

- [ ] **Step 4: Run all tests**

```
python -m pytest tests/unit/test_exports.py -v
```

Expected: 5 PASSED.

- [ ] **Step 5: Commit**

```
git add src/geets/utils/exports.py tests/unit/test_exports.py
git commit -m "feat: add export_image_to_drive"
```

---

### Task 4: `export_imagecollection_to_drive`

**Files:**
- Modify: `src/geets/utils/exports.py`
- Modify: `tests/unit/test_exports.py`

- [ ] **Step 1: Add failing test**

Append to `tests/unit/test_exports.py`:

```python
def test_export_imagecollection_to_drive_starts_one_task_per_image():
    from geets.utils.exports import export_imagecollection_to_drive

    mock_img1 = MagicMock()
    mock_img1.date.return_value.format.return_value.getInfo.return_value = "20220601"
    mock_img2 = MagicMock()
    mock_img2.date.return_value.format.return_value.getInfo.return_value = "20220615"

    mock_col = MagicMock()
    mock_col.size.return_value.getInfo.return_value = 2
    mock_col.toList.return_value.get.side_effect = [mock_img1, mock_img2]

    mock_task1, mock_task2 = MagicMock(), MagicMock()

    with patch("geets.utils.exports.ee.batch.Export.image.toDrive", side_effect=[mock_task1, mock_task2]), \
         patch("geets.utils.exports.ee.Image", side_effect=lambda x: x):
        tasks = export_imagecollection_to_drive(mock_col, "desc", "Folder", "pfx")

    assert tasks == [mock_task1, mock_task2]
    mock_task1.start.assert_called_once()
    mock_task2.start.assert_called_once()


def test_export_imagecollection_to_drive_suffixes_description_and_prefix():
    from geets.utils.exports import export_imagecollection_to_drive

    mock_img = MagicMock()
    mock_img.date.return_value.format.return_value.getInfo.return_value = "20230101"

    mock_col = MagicMock()
    mock_col.size.return_value.getInfo.return_value = 1
    mock_col.toList.return_value.get.return_value = mock_img

    mock_task = MagicMock()

    with patch("geets.utils.exports.ee.batch.Export.image.toDrive", return_value=mock_task) as mock_drive, \
         patch("geets.utils.exports.ee.Image", side_effect=lambda x: x):
        export_imagecollection_to_drive(mock_col, "my_desc", "Folder", "my_pfx")

    mock_drive.assert_called_once_with(
        image=mock_img,
        description="my_desc_20230101",
        folder="Folder",
        fileNamePrefix="my_pfx_20230101",
        region=None,
        scale=30.0,
        crs="EPSG:4326",
        maxPixels=int(1e13),
        skipEmptyTiles=False,
    )
```

- [ ] **Step 2: Run to confirm they fail**

```
python -m pytest tests/unit/test_exports.py::test_export_imagecollection_to_drive_starts_one_task_per_image tests/unit/test_exports.py::test_export_imagecollection_to_drive_suffixes_description_and_prefix -v
```

Expected: `ImportError` — `export_imagecollection_to_drive` not defined.

- [ ] **Step 3: Add `export_imagecollection_to_drive` to `exports.py`**

Append after `export_image_to_drive`:

```python
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
```

- [ ] **Step 4: Run all tests**

```
python -m pytest tests/unit/test_exports.py -v
```

Expected: 7 PASSED.

- [ ] **Step 5: Commit**

```
git add src/geets/utils/exports.py tests/unit/test_exports.py
git commit -m "feat: add export_imagecollection_to_drive"
```

---

### Task 5: Wire up `__init__.py`

**Files:**
- Modify: `src/geets/__init__.py`

- [ ] **Step 1: Add import line**

In `src/geets/__init__.py`, add after the `from .utils.output` import line:

```python
from .utils.exports        import (
    l_download_image,
    l_download_imagecollection,
    export_image_to_drive,
    export_imagecollection_to_drive,
)
```

- [ ] **Step 2: Add entries to `__all__`**

In the `__all__` list, append:

```python
    "l_download_image",
    "l_download_imagecollection",
    "export_image_to_drive",
    "export_imagecollection_to_drive",
```

- [ ] **Step 3: Verify imports work**

```
python -c "from geets import l_download_image, l_download_imagecollection, export_image_to_drive, export_imagecollection_to_drive; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Run full test suite**

```
python -m pytest tests/ -v
```

Expected: all tests PASSED (including pre-existing `test_image_utils.py` and `test_s2l8.py`).

- [ ] **Step 5: Commit**

```
git add src/geets/__init__.py
git commit -m "feat: export download and drive-export functions from package root"
```
