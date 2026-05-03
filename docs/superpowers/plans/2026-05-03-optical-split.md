# Optical Module Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `optical/s2l8.py` into `sentinel2.py` and `landsat.py` with shared constants in `common.py`, mirroring the `modis/` pattern.

**Architecture:** `common.py` holds all constants needed by `to_surface_reflection` (`_BANDS_HARMONIZED`, `_S2_BANDS_SRC`, `_S2_SCALE`, `_L8_BANDS_SRC`, `_L8_SCALE`, `_L8_OFFSET`) plus the function itself — this avoids circular imports since `sentinel2.py` and `landsat.py` import from `common.py` but `common.py` never imports from them. Each sensor module holds only its collection ID, cloud property name, private helpers, and the public loader.

**Tech Stack:** Python 3.13, Google Earth Engine Python API (`ee`), `pytest`, `unittest.mock`

---

## File Map

| Action | Path |
|--------|------|
| Create | `src/geets/optical/common.py` |
| Create | `src/geets/optical/sentinel2.py` |
| Create | `src/geets/optical/landsat.py` |
| Modify | `src/geets/optical/__init__.py` |
| Modify | `src/geets/__init__.py` |
| Delete | `src/geets/optical/s2l8.py` |
| Create | `tests/unit/optical/__init__.py` |
| Create | `tests/unit/optical/test_common.py` |
| Create | `tests/unit/optical/test_sentinel2.py` |
| Create | `tests/unit/optical/test_landsat.py` |
| Delete | `tests/unit/test_s2l8.py` |

---

## Task 1: Create `optical/common.py`

**Files:**
- Create: `src/geets/optical/common.py`
- Create: `tests/unit/optical/__init__.py`
- Create: `tests/unit/optical/test_common.py`

- [ ] **Step 1: Create the test directory and `__init__.py`**

Create `tests/unit/optical/__init__.py` as an empty file.

- [ ] **Step 2: Write failing tests for `common.py`**

Create `tests/unit/optical/test_common.py`:

```python
def test_bands_harmonized_values():
    from geets.optical.common import _BANDS_HARMONIZED
    assert _BANDS_HARMONIZED == ["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2"]


def test_s2_bands_src_values():
    from geets.optical.common import _S2_BANDS_SRC
    assert _S2_BANDS_SRC == ["B2", "B3", "B4", "B8", "B11", "B12"]


def test_l8_bands_src_values():
    from geets.optical.common import _L8_BANDS_SRC
    assert _L8_BANDS_SRC == ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"]


def test_band_lists_same_length():
    from geets.optical.common import _BANDS_HARMONIZED, _S2_BANDS_SRC, _L8_BANDS_SRC
    assert len(_S2_BANDS_SRC) == len(_BANDS_HARMONIZED)
    assert len(_L8_BANDS_SRC) == len(_BANDS_HARMONIZED)


def test_to_surface_reflection_raises_on_unknown_sensor():
    from unittest.mock import MagicMock
    from geets.optical.common import to_surface_reflection
    import pytest

    with pytest.raises(ValueError, match="Unknown sensor"):
        to_surface_reflection(MagicMock(), "MODIS")


def test_to_surface_reflection_s2_selects_s2_bands():
    from unittest.mock import MagicMock
    from geets.optical.common import to_surface_reflection, _S2_BANDS_SRC

    img = MagicMock()
    to_surface_reflection(img, "S2")
    img.select.assert_called_once_with(_S2_BANDS_SRC)


def test_to_surface_reflection_l8_selects_l8_bands():
    from unittest.mock import MagicMock
    from geets.optical.common import to_surface_reflection, _L8_BANDS_SRC

    img = MagicMock()
    to_surface_reflection(img, "L8")
    img.select.assert_called_once_with(_L8_BANDS_SRC)
```

- [ ] **Step 3: Run tests to confirm they fail**

```
python -m pytest tests/unit/optical/test_common.py -v
```

Expected: `ModuleNotFoundError` — `geets.optical.common` does not exist yet.

- [ ] **Step 4: Create `src/geets/optical/common.py`**

```python
"""Shared constants and cross-sensor utilities for optical loaders."""
from __future__ import annotations

import ee

_BANDS_HARMONIZED = ["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2"]

_S2_BANDS_SRC = ["B2",    "B3",    "B4",    "B8",    "B11",   "B12"  ]
_S2_SCALE     = 1e-4

_L8_BANDS_SRC = ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"]
_L8_SCALE     = 2.75e-5
_L8_OFFSET    = -0.2


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
        scaled = img.select(_S2_BANDS_SRC).multiply(_S2_SCALE)
        return scaled.copyProperties(img, img.propertyNames())
    if sensor == "L8":
        scaled = img.select(_L8_BANDS_SRC).multiply(_L8_SCALE).add(_L8_OFFSET)
        return scaled.copyProperties(img, img.propertyNames())
    raise ValueError(f"Unknown sensor '{sensor}'. Choose 'S2' or 'L8'.")
```

- [ ] **Step 5: Run tests to confirm they pass**

```
python -m pytest tests/unit/optical/test_common.py -v
```

Expected: 7 PASSED.

- [ ] **Step 6: Commit**

```
git add src/geets/optical/common.py tests/unit/optical/__init__.py tests/unit/optical/test_common.py
git commit -m "feat: add optical/common.py with shared band constants and to_surface_reflection"
```

---

## Task 2: Create `optical/sentinel2.py`

**Files:**
- Create: `src/geets/optical/sentinel2.py`
- Create: `tests/unit/optical/test_sentinel2.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/optical/test_sentinel2.py`:

```python
def test_s2_collection_id():
    from geets.optical.sentinel2 import _S2_COLLECTION_ID
    assert _S2_COLLECTION_ID == "COPERNICUS/S2_SR_HARMONIZED"


def test_s2_cloud_property():
    from geets.optical.sentinel2 import _S2_CLOUD_PROPERTY
    assert _S2_CLOUD_PROPERTY == "CLOUDY_PIXEL_PERCENTAGE"


def test_get_s2_raises_on_invalid_band():
    from unittest.mock import MagicMock
    from geets.optical.sentinel2 import get_s2
    import pytest

    with pytest.raises(ValueError, match="Unknown band"):
        get_s2("2022-01-01", "2022-03-01", MagicMock(), bands=["INVALID_BAND"])


def test_get_s2_importable_from_optical():
    from geets.optical import get_s2
    assert callable(get_s2)
```

- [ ] **Step 2: Run tests to confirm they fail**

```
python -m pytest tests/unit/optical/test_sentinel2.py -v
```

Expected: `ModuleNotFoundError` — `geets.optical.sentinel2` does not exist yet.

- [ ] **Step 3: Create `src/geets/optical/sentinel2.py`**

```python
"""Sentinel-2 SR optical loader for Google Earth Engine."""
from __future__ import annotations

import ee

from .common import _BANDS_HARMONIZED, _S2_BANDS_SRC, _S2_SCALE

_S2_COLLECTION_ID  = "COPERNICUS/S2_SR_HARMONIZED"
_S2_CLOUD_PROPERTY = "CLOUDY_PIXEL_PERCENTAGE"


def _mask_s2_qa60(img: ee.Image) -> ee.Image:
    """Mask opaque clouds (bit 10) and cirrus (bit 11) using QA60."""
    qa = img.select("QA60")
    mask = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
    return img.updateMask(mask)


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

    print(f"[geets.sentinel2] Loading S2: {_S2_COLLECTION_ID}")
    print(f"[geets.sentinel2] Date range: {start_date} → {end_date}")
    print(f"[geets.sentinel2] max_cloud_cover={max_cloud_cover}%  "
          f"mask_clouds={mask_clouds}  bands={bands or 'all'}")

    col = (
        ee.ImageCollection(_S2_COLLECTION_ID)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lte(_S2_CLOUD_PROPERTY, max_cloud_cover))
    )

    if aoi is not None:
        print("[geets.sentinel2] Applying AOI filter")
        col = col.filterBounds(aoi)

    if mask_clouds:
        col = col.map(_mask_s2_qa60)

    col = col.map(_scale_s2).map(_rename_s2)

    if bands is not None:
        col = col.select(bands)

    if aoi is not None and clip:
        print("[geets.sentinel2] Clipping to AOI")
        col = col.map(lambda img: img.clip(aoi))

    n = col.size().getInfo()
    if n == 0:
        print(f"[geets.sentinel2] WARNING: S2 collection is EMPTY (0 images).")
        print(f"[geets.sentinel2]   → Check date range ({start_date} – {end_date}),")
        print(f"[geets.sentinel2]      max_cloud_cover={max_cloud_cover}%, and AOI.")
    else:
        print(f"[geets.sentinel2] S2 collection ready: {n} images")

    return col
```

- [ ] **Step 4: Update `optical/__init__.py`** (partial — sentinel2 only for now)

Edit `src/geets/optical/__init__.py` to read:

```python
from .common import to_surface_reflection
from .sentinel2 import get_s2
```

(Leave `get_l8` out until Task 3.)

- [ ] **Step 5: Run tests to confirm they pass**

```
python -m pytest tests/unit/optical/test_sentinel2.py -v
```

Expected: 4 PASSED.

- [ ] **Step 6: Commit**

```
git add src/geets/optical/sentinel2.py src/geets/optical/__init__.py tests/unit/optical/test_sentinel2.py
git commit -m "feat: add optical/sentinel2.py, extract get_s2 from s2l8"
```

---

## Task 3: Create `optical/landsat.py`

**Files:**
- Create: `src/geets/optical/landsat.py`
- Create: `tests/unit/optical/test_landsat.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/optical/test_landsat.py`:

```python
def test_l8_collection_id():
    from geets.optical.landsat import _L8_COLLECTION_ID
    assert _L8_COLLECTION_ID == "LANDSAT/LC08/C02/T1_L2"


def test_l8_cloud_property():
    from geets.optical.landsat import _L8_CLOUD_PROPERTY
    assert _L8_CLOUD_PROPERTY == "CLOUD_COVER"


def test_get_l8_raises_on_invalid_band():
    from unittest.mock import MagicMock
    from geets.optical.landsat import get_l8
    import pytest

    with pytest.raises(ValueError, match="Unknown band"):
        get_l8("2022-01-01", "2022-03-01", MagicMock(), bands=["INVALID_BAND"])


def test_get_l8_importable_from_optical():
    from geets.optical import get_l8
    assert callable(get_l8)
```

- [ ] **Step 2: Run tests to confirm they fail**

```
python -m pytest tests/unit/optical/test_landsat.py -v
```

Expected: `ModuleNotFoundError` — `geets.optical.landsat` does not exist yet.

- [ ] **Step 3: Create `src/geets/optical/landsat.py`**

```python
"""Landsat-8 C2L2 SR optical loader for Google Earth Engine."""
from __future__ import annotations

import ee

from .common import _BANDS_HARMONIZED, _L8_BANDS_SRC, _L8_SCALE, _L8_OFFSET

_L8_COLLECTION_ID  = "LANDSAT/LC08/C02/T1_L2"
_L8_CLOUD_PROPERTY = "CLOUD_COVER"


def _mask_l8_qa_pixel(img: ee.Image) -> ee.Image:
    """Mask clouds (bit 3) and cloud shadow (bit 4) using QA_PIXEL."""
    qa = img.select("QA_PIXEL")
    mask = qa.bitwiseAnd(1 << 3).eq(0).And(qa.bitwiseAnd(1 << 4).eq(0))
    return img.updateMask(mask)


def _scale_l8(img: ee.Image) -> ee.Image:
    """Scale L8 C2L2 SR integer DNs to physical reflectance [0, 1] (× 0.0000275 − 0.2)."""
    scaled = img.select(_L8_BANDS_SRC).multiply(_L8_SCALE).add(_L8_OFFSET)
    return scaled.copyProperties(img, img.propertyNames())


def _rename_l8(img: ee.Image) -> ee.Image:
    """Rename scaled L8 bands to harmonized names."""
    return img.rename(_BANDS_HARMONIZED)


def get_l8(
    start_date: str,
    end_date: str,
    aoi: ee.Geometry | None = None,
    *,
    bands: list[str] | None = None,
    max_cloud_cover: float = 20.0,
    mask_clouds: bool = True,
    clip: bool = True,
) -> ee.ImageCollection:
    """Load a cloud-masked, scaled, band-harmonized Landsat-8 C2L2 SR collection.

    Parameters
    ----------
    start_date, end_date : ISO date strings "YYYY-MM-DD" (half-open [a, b))
    aoi                  : optional AOI for bounds filtering and clipping
    bands                : subset of harmonized names, e.g. ["Red", "NIR"].
                           None keeps all six: Blue Green Red NIR SWIR1 SWIR2
    max_cloud_cover      : maximum CLOUD_COVER (default 20)
    mask_clouds          : apply QA_PIXEL cloud/shadow mask (default True)
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

    print(f"[geets.landsat] Loading L8: {_L8_COLLECTION_ID}")
    print(f"[geets.landsat] Date range: {start_date} → {end_date}")
    print(f"[geets.landsat] max_cloud_cover={max_cloud_cover}%  "
          f"mask_clouds={mask_clouds}  bands={bands or 'all'}")

    col = (
        ee.ImageCollection(_L8_COLLECTION_ID)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lte(_L8_CLOUD_PROPERTY, max_cloud_cover))
    )

    if aoi is not None:
        print("[geets.landsat] Applying AOI filter")
        col = col.filterBounds(aoi)

    if mask_clouds:
        col = col.map(_mask_l8_qa_pixel)

    col = col.map(_scale_l8).map(_rename_l8)

    if bands is not None:
        col = col.select(bands)

    if aoi is not None and clip:
        print("[geets.landsat] Clipping to AOI")
        col = col.map(lambda img: img.clip(aoi))

    n = col.size().getInfo()
    if n == 0:
        print(f"[geets.landsat] WARNING: L8 collection is EMPTY (0 images).")
        print(f"[geets.landsat]   → Check date range ({start_date} – {end_date}),")
        print(f"[geets.landsat]      max_cloud_cover={max_cloud_cover}%, and AOI.")
    else:
        print(f"[geets.landsat] L8 collection ready: {n} images")

    return col
```

- [ ] **Step 4: Finalize `optical/__init__.py`**

Edit `src/geets/optical/__init__.py` to its final form:

```python
from .common import to_surface_reflection
from .landsat import get_l8
from .sentinel2 import get_s2
```

- [ ] **Step 5: Run tests to confirm they pass**

```
python -m pytest tests/unit/optical/test_landsat.py -v
```

Expected: 4 PASSED.

- [ ] **Step 6: Commit**

```
git add src/geets/optical/landsat.py src/geets/optical/__init__.py tests/unit/optical/test_landsat.py
git commit -m "feat: add optical/landsat.py, extract get_l8 from s2l8"
```

---

## Task 4: Update root `geets/__init__.py` and delete `s2l8.py`

**Files:**
- Modify: `src/geets/__init__.py` (line 20)
- Delete: `src/geets/optical/s2l8.py`
- Delete: `tests/unit/test_s2l8.py`

- [ ] **Step 1: Update the import in `src/geets/__init__.py`**

Change line 20 from:

```python
from .optical.s2l8 import get_l8, get_s2, to_surface_reflection
```

to:

```python
from .optical import get_l8, get_s2, to_surface_reflection
```

- [ ] **Step 2: Delete `s2l8.py` and the old test file**

```
git rm src/geets/optical/s2l8.py
git rm tests/unit/test_s2l8.py
```

- [ ] **Step 3: Run the full test suite**

```
python -m pytest tests/ -v
```

Expected: all tests PASS, no references to `s2l8` remain.

If any test imports from `geets.optical.s2l8`, fix them to import from `geets.optical.common`, `geets.optical.sentinel2`, or `geets.optical.landsat` as appropriate.

- [ ] **Step 4: Run ruff and ty**

```
ruff check src/
ty check src/
```

Expected: no errors.

- [ ] **Step 5: Commit**

```
git add src/geets/__init__.py
git commit -m "refactor: wire optical split into root package, delete s2l8.py"
```
