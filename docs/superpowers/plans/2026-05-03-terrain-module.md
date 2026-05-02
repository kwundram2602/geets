# Terrain Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `terrain/` subpackage to `geets` that loads DEM/DSM images from four GEE sources and optionally computes derived terrain products (slope, aspect, hillshade) server-side with harmonized band names.

**Architecture:** Four public loaders (`load_copernicus_dem`, `load_srtm`, `load_aster`, `load_nasadem`) all delegate to a shared private `_load_dem` helper, following the same layered pattern as `optical/s2l8.py`. The `terrain/__init__.py` re-exports all public symbols, and the root `geets/__init__.py` is updated to include them.

**Tech Stack:** Python 3.13, `earthengine-api` (`ee`), `unittest.mock` for tests, `pytest`

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `src/geets/terrain/__init__.py` | re-export public API |
| Create | `src/geets/terrain/dem.py` | all DEM loading logic |
| Create | `tests/unit/terrain/__init__.py` | test package marker |
| Create | `tests/unit/terrain/test_dem.py` | unit tests (mocked ee) |
| Modify | `src/geets/__init__.py` | add terrain imports + `__all__` entries |

---

## Task 1: Package skeleton + constants

**Files:**
- Create: `src/geets/terrain/__init__.py`
- Create: `src/geets/terrain/dem.py`
- Create: `tests/unit/terrain/__init__.py`
- Create: `tests/unit/terrain/test_dem.py`

- [ ] **Step 1: Write failing tests for constants**

Create `tests/unit/terrain/__init__.py` (empty) and `tests/unit/terrain/test_dem.py`:

```python
from geets.terrain import dem


def test_dem_collections_has_four_sources():
    assert set(dem.DEM_COLLECTIONS.keys()) == {"GLO30", "SRTM", "ASTER", "NASADEM"}


def test_dem_collections_glo30():
    assert dem.DEM_COLLECTIONS["GLO30"] == "COPERNICUS/DEM/GLO30"


def test_dem_collections_srtm():
    assert dem.DEM_COLLECTIONS["SRTM"] == "USGS/SRTMGL1_003"


def test_dem_collections_aster():
    assert dem.DEM_COLLECTIONS["ASTER"] == "NASA/ASTER_GED/AG100_003"


def test_dem_collections_nasadem():
    assert dem.DEM_COLLECTIONS["NASADEM"] == "NASA/NASADEM_HGT/001"
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/unit/terrain/test_dem.py -v
```
Expected: `ModuleNotFoundError` — `geets.terrain` does not exist yet.

- [ ] **Step 3: Create the package skeleton**

Create `src/geets/terrain/__init__.py` (empty for now):
```python
```

Create `src/geets/terrain/dem.py`:
```python
from __future__ import annotations

from typing import Literal

import ee

DemProduct = Literal["elevation", "slope", "aspect", "hillshade"]

_VALID_PRODUCTS: frozenset[str] = frozenset({"elevation", "slope", "aspect", "hillshade"})

DEM_COLLECTIONS: dict[str, str] = {
    "GLO30":   "COPERNICUS/DEM/GLO30",
    "SRTM":    "USGS/SRTMGL1_003",
    "ASTER":   "NASA/ASTER_GED/AG100_003",
    "NASADEM": "NASA/NASADEM_HGT/001",
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```
pytest tests/unit/terrain/test_dem.py -v
```
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```
git add src/geets/terrain/ tests/unit/terrain/
git commit -m "feat: add terrain package skeleton with DEM_COLLECTIONS"
```

---

## Task 2: Implement `_load_dem` helper

**Files:**
- Modify: `src/geets/terrain/dem.py`
- Modify: `tests/unit/terrain/test_dem.py`

- [ ] **Step 1: Write failing tests for `_load_dem`**

Append to `tests/unit/terrain/test_dem.py`:

```python
import pytest
from unittest.mock import MagicMock, patch


def test_load_dem_raises_on_invalid_product():
    with pytest.raises(ValueError, match="Unknown product"):
        dem._load_dem("COPERNICUS/DEM/GLO30", "DEM", True, None, True, ["invalid"])


def test_load_dem_uses_mosaic_for_tiled():
    mock_col = MagicMock()
    mock_img = MagicMock()
    mock_col.mosaic.return_value = mock_img
    mock_img.select.return_value = mock_img
    mock_img.rename.return_value = mock_img

    with patch.object(dem.ee, "ImageCollection", return_value=mock_col):
        dem._load_dem("COPERNICUS/DEM/GLO30", "DEM", True, None, True, ["elevation"])
        mock_col.mosaic.assert_called_once()
        mock_col.first.assert_not_called()


def test_load_dem_uses_first_for_non_tiled():
    mock_col = MagicMock()
    mock_img = MagicMock()
    mock_col.first.return_value = mock_img
    mock_img.select.return_value = mock_img
    mock_img.rename.return_value = mock_img

    with patch.object(dem.ee, "ImageCollection", return_value=mock_col):
        dem._load_dem("USGS/SRTMGL1_003", "elevation", False, None, True, ["elevation"])
        mock_col.first.assert_called_once()
        mock_col.mosaic.assert_not_called()


def test_load_dem_calls_terrain_products_for_slope():
    mock_col = MagicMock()
    mock_img = MagicMock()
    mock_col.first.return_value = mock_img
    mock_img.select.return_value = mock_img
    mock_img.rename.return_value = mock_img
    mock_terrain_img = MagicMock()
    mock_terrain_img.select.return_value = mock_terrain_img

    with patch.object(dem.ee, "ImageCollection", return_value=mock_col), \
         patch.object(dem.ee.Terrain, "products", return_value=mock_terrain_img) as mock_terrain:
        dem._load_dem("USGS/SRTMGL1_003", "elevation", False, None, True, ["elevation", "slope"])
        mock_terrain.assert_called_once()


def test_load_dem_skips_terrain_products_for_elevation_only():
    mock_col = MagicMock()
    mock_img = MagicMock()
    mock_col.first.return_value = mock_img
    mock_img.select.return_value = mock_img
    mock_img.rename.return_value = mock_img

    with patch.object(dem.ee, "ImageCollection", return_value=mock_col), \
         patch.object(dem.ee.Terrain, "products") as mock_terrain:
        dem._load_dem("USGS/SRTMGL1_003", "elevation", False, None, True, ["elevation"])
        mock_terrain.assert_not_called()


def test_load_dem_clips_when_aoi_provided():
    aoi = MagicMock()
    mock_col = MagicMock()
    mock_img = MagicMock()
    mock_col.filterBounds.return_value = mock_col
    mock_col.first.return_value = mock_img
    mock_img.select.return_value = mock_img
    mock_img.rename.return_value = mock_img
    mock_img.clip.return_value = mock_img

    with patch.object(dem.ee, "ImageCollection", return_value=mock_col):
        dem._load_dem("USGS/SRTMGL1_003", "elevation", False, aoi, True, ["elevation"])
        mock_img.clip.assert_called_once_with(aoi)


def test_load_dem_no_clip_when_aoi_none():
    mock_col = MagicMock()
    mock_img = MagicMock()
    mock_col.first.return_value = mock_img
    mock_img.select.return_value = mock_img
    mock_img.rename.return_value = mock_img

    with patch.object(dem.ee, "ImageCollection", return_value=mock_col):
        dem._load_dem("USGS/SRTMGL1_003", "elevation", False, None, True, ["elevation"])
        mock_img.clip.assert_not_called()


def test_load_dem_no_clip_when_clip_false():
    aoi = MagicMock()
    mock_col = MagicMock()
    mock_img = MagicMock()
    mock_col.filterBounds.return_value = mock_col
    mock_col.first.return_value = mock_img
    mock_img.select.return_value = mock_img
    mock_img.rename.return_value = mock_img

    with patch.object(dem.ee, "ImageCollection", return_value=mock_col):
        dem._load_dem("USGS/SRTMGL1_003", "elevation", False, aoi, False, ["elevation"])
        mock_img.clip.assert_not_called()
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/unit/terrain/test_dem.py -v
```
Expected: 8 new tests FAIL with `AttributeError: module 'geets.terrain.dem' has no attribute '_load_dem'`.

- [ ] **Step 3: Implement `_load_dem`**

Add to `src/geets/terrain/dem.py` after the constants:

```python
def _load_dem(
    collection_id: str,
    elev_band: str,
    is_tiled: bool,
    aoi: ee.Geometry | None,
    clip: bool,
    products: list[DemProduct],
) -> ee.Image:
    invalid = [p for p in products if p not in _VALID_PRODUCTS]
    if invalid:
        raise ValueError(
            f"[geets.terrain] Unknown product(s) {invalid}. "
            f"Choose from: {sorted(_VALID_PRODUCTS)}"
        )

    print(f"[geets.terrain] Loading DEM: {collection_id}")
    print(f"[geets.terrain] products={products}")

    col = ee.ImageCollection(collection_id)
    if aoi is not None:
        col = col.filterBounds(aoi)

    img = col.mosaic() if is_tiled else col.first()
    img = img.select(elev_band).rename("elevation")

    if any(p != "elevation" for p in products):
        img = ee.Terrain.products(img)

    img = img.select(products)

    if aoi is not None and clip:
        img = img.clip(aoi)

    return img
```

- [ ] **Step 4: Run tests to confirm they pass**

```
pytest tests/unit/terrain/test_dem.py -v
```
Expected: all 13 tests PASS.

- [ ] **Step 5: Commit**

```
git add src/geets/terrain/dem.py tests/unit/terrain/test_dem.py
git commit -m "feat: implement _load_dem helper with terrain products support"
```

---

## Task 3: Implement four public loaders

**Files:**
- Modify: `src/geets/terrain/dem.py`
- Modify: `src/geets/terrain/__init__.py`
- Modify: `tests/unit/terrain/test_dem.py`

- [ ] **Step 1: Write failing tests for public loaders**

Append to `tests/unit/terrain/test_dem.py`:

```python
def test_load_copernicus_dem_delegates_correctly():
    with patch.object(dem, "_load_dem") as mock_load:
        aoi = MagicMock()
        dem.load_copernicus_dem(aoi, products=["elevation", "slope"], clip=False)
        mock_load.assert_called_once_with(
            "COPERNICUS/DEM/GLO30", "DEM", True, aoi, False, ["elevation", "slope"]
        )


def test_load_copernicus_dem_defaults():
    with patch.object(dem, "_load_dem") as mock_load:
        dem.load_copernicus_dem()
        mock_load.assert_called_once_with(
            "COPERNICUS/DEM/GLO30", "DEM", True, None, True, ["elevation"]
        )


def test_load_srtm_delegates_correctly():
    with patch.object(dem, "_load_dem") as mock_load:
        dem.load_srtm()
        mock_load.assert_called_once_with(
            "USGS/SRTMGL1_003", "elevation", False, None, True, ["elevation"]
        )


def test_load_aster_delegates_correctly():
    with patch.object(dem, "_load_dem") as mock_load:
        dem.load_aster()
        mock_load.assert_called_once_with(
            "NASA/ASTER_GED/AG100_003", "elevation", False, None, True, ["elevation"]
        )


def test_load_nasadem_delegates_correctly():
    with patch.object(dem, "_load_dem") as mock_load:
        dem.load_nasadem()
        mock_load.assert_called_once_with(
            "NASA/NASADEM_HGT/001", "elevation", False, None, True, ["elevation"]
        )
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/unit/terrain/test_dem.py -v
```
Expected: 5 new tests FAIL with `AttributeError: module 'geets.terrain.dem' has no attribute 'load_copernicus_dem'`.

- [ ] **Step 3: Implement the four public loaders**

Append to `src/geets/terrain/dem.py`:

```python
def load_copernicus_dem(
    aoi: ee.Geometry | None = None,
    *,
    products: list[DemProduct] | None = None,
    clip: bool = True,
) -> ee.Image:
    """Load Copernicus DEM GLO-30 (30 m global DEM).

    Args:
        aoi: Optional AOI geometry for filtering and clipping.
        products: Terrain products to include. Defaults to ["elevation"].
            Valid values: "elevation", "slope", "aspect", "hillshade".
        clip: Clip to AOI when aoi is provided.

    Returns:
        ee.Image with requested bands.
    """
    return _load_dem(
        DEM_COLLECTIONS["GLO30"], "DEM", True, aoi, clip, products or ["elevation"]
    )


def load_srtm(
    aoi: ee.Geometry | None = None,
    *,
    products: list[DemProduct] | None = None,
    clip: bool = True,
) -> ee.Image:
    """Load USGS SRTM 30m DEM.

    Args:
        aoi: Optional AOI geometry for filtering and clipping.
        products: Terrain products to include. Defaults to ["elevation"].
            Valid values: "elevation", "slope", "aspect", "hillshade".
        clip: Clip to AOI when aoi is provided.

    Returns:
        ee.Image with requested bands.
    """
    return _load_dem(
        DEM_COLLECTIONS["SRTM"], "elevation", False, aoi, clip, products or ["elevation"]
    )


def load_aster(
    aoi: ee.Geometry | None = None,
    *,
    products: list[DemProduct] | None = None,
    clip: bool = True,
) -> ee.Image:
    """Load ASTER GDEM (30 m global DEM, elevation band from AG100_003).

    Args:
        aoi: Optional AOI geometry for filtering and clipping.
        products: Terrain products to include. Defaults to ["elevation"].
            Valid values: "elevation", "slope", "aspect", "hillshade".
        clip: Clip to AOI when aoi is provided.

    Returns:
        ee.Image with requested bands.
    """
    return _load_dem(
        DEM_COLLECTIONS["ASTER"], "elevation", False, aoi, clip, products or ["elevation"]
    )


def load_nasadem(
    aoi: ee.Geometry | None = None,
    *,
    products: list[DemProduct] | None = None,
    clip: bool = True,
) -> ee.Image:
    """Load NASA NASADEM 30m DEM.

    Args:
        aoi: Optional AOI geometry for filtering and clipping.
        products: Terrain products to include. Defaults to ["elevation"].
            Valid values: "elevation", "slope", "aspect", "hillshade".
        clip: Clip to AOI when aoi is provided.

    Returns:
        ee.Image with requested bands.
    """
    return _load_dem(
        DEM_COLLECTIONS["NASADEM"], "elevation", False, aoi, clip, products or ["elevation"]
    )
```

- [ ] **Step 4: Update `src/geets/terrain/__init__.py`**

```python
from .dem import (
    DEM_COLLECTIONS,
    DemProduct,
    load_copernicus_dem,
    load_srtm,
    load_aster,
    load_nasadem,
)

__all__ = [
    "DEM_COLLECTIONS",
    "DemProduct",
    "load_copernicus_dem",
    "load_srtm",
    "load_aster",
    "load_nasadem",
]
```

- [ ] **Step 5: Run all terrain tests**

```
pytest tests/unit/terrain/test_dem.py -v
```
Expected: all 18 tests PASS.

- [ ] **Step 6: Commit**

```
git add src/geets/terrain/ tests/unit/terrain/test_dem.py
git commit -m "feat: add load_copernicus_dem, load_srtm, load_aster, load_nasadem"
```

---

## Task 4: Wire into root `__init__.py`

**Files:**
- Modify: `src/geets/__init__.py`

- [ ] **Step 1: Add terrain imports to `src/geets/__init__.py`**

After the existing `from .utils.image_utils` line, add:

```python
from .terrain.dem import (
    DEM_COLLECTIONS,
    DemProduct,
    load_copernicus_dem,
    load_srtm,
    load_aster,
    load_nasadem,
)
```

Add to `__all__`:

```python
    "DEM_COLLECTIONS",
    "DemProduct",
    "load_copernicus_dem",
    "load_srtm",
    "load_aster",
    "load_nasadem",
```

- [ ] **Step 2: Verify the full test suite still passes**

```
pytest tests/ -v
```
Expected: all existing tests PASS, no regressions.

- [ ] **Step 3: Smoke-check the public API is reachable**

```
python -c "from geets import load_copernicus_dem, load_srtm, load_aster, load_nasadem, DEM_COLLECTIONS; print(DEM_COLLECTIONS)"
```
Expected output:
```
{'GLO30': 'COPERNICUS/DEM/GLO30', 'SRTM': 'USGS/SRTMGL1_003', 'ASTER': 'NASA/ASTER_GED/AG100_003', 'NASADEM': 'NASA/NASADEM_HGT/001'}
```

- [ ] **Step 4: Commit**

```
git add src/geets/__init__.py
git commit -m "feat: export terrain loaders from geets root package"
```
