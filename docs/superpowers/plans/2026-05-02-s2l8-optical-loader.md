# S2/L8 Optical Loader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `optical/s2l8.py` and `utils/image_utils.py` providing a layered pipeline for loading cloud-masked, scaled, and band-harmonized Sentinel-2 and Landsat-8 ImageCollections from GEE.

**Architecture:** Four pipeline levels — private per-image transforms (mask, scale, rename), a public single-image dispatcher (`to_surface_reflection`), a sensor-agnostic collection helper (`get_image_with_least_cc` in utils), and full-pipeline loaders (`get_s2`, `get_l8`). GEE calls are lazy; `size().getInfo()` at the end of each loader triggers a single round-trip to validate the result.

**Tech Stack:** Python 3.13, earthengine-api (`ee`), pytest, unittest.mock

---

### Task 1: Test Infrastructure

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/conftest.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add pytest to dev dependencies and configure in `pyproject.toml`**

Update `[project.optional-dependencies]` and add `[tool.pytest.ini_options]`:

```toml
[project.optional-dependencies]
dev = ["ruff", "ty", "pytest"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create test directory structure**

Create the following empty files:
- `tests/__init__.py`
- `tests/conftest.py`
- `tests/unit/__init__.py`

All three files are empty.

- [ ] **Step 3: Verify pytest runs**

```powershell
uv sync
python -m pytest --collect-only
```

Expected output: `no tests ran`, exit 0.

- [ ] **Step 4: Commit**

```powershell
git add pyproject.toml tests/
git commit -m "test: add pytest infrastructure"
```

---

### Task 2: `utils/image_utils.py` — `get_image_with_least_cc`

**Files:**
- Create: `src/geets/utils/image_utils.py`
- Create: `tests/unit/test_image_utils.py`
- Modify: `src/geets/utils/__init__.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_image_utils.py`:

```python
from unittest.mock import MagicMock
import pytest


def test_get_image_with_least_cc_sorts_by_property():
    from geets.utils.image_utils import get_image_with_least_cc

    mock_img = MagicMock()
    mock_sorted = MagicMock()
    mock_sorted.first.return_value = mock_img

    mock_col = MagicMock()
    mock_col.size.return_value.getInfo.return_value = 3
    mock_col.sort.return_value = mock_sorted

    result = get_image_with_least_cc(mock_col, "CLOUDY_PIXEL_PERCENTAGE")

    mock_col.sort.assert_called_once_with("CLOUDY_PIXEL_PERCENTAGE")
    assert result is mock_img


def test_get_image_with_least_cc_default_property():
    from geets.utils.image_utils import get_image_with_least_cc

    mock_col = MagicMock()
    mock_col.size.return_value.getInfo.return_value = 1
    mock_col.sort.return_value.first.return_value = MagicMock()

    get_image_with_least_cc(mock_col)

    mock_col.sort.assert_called_once_with("CLOUDY_PIXEL_PERCENTAGE")


def test_get_image_with_least_cc_raises_on_empty_collection():
    from geets.utils.image_utils import get_image_with_least_cc

    mock_col = MagicMock()
    mock_col.size.return_value.getInfo.return_value = 0

    with pytest.raises(ValueError, match="empty"):
        get_image_with_least_cc(mock_col)
```

- [ ] **Step 2: Run to verify failure**

```powershell
python -m pytest tests/unit/test_image_utils.py -v
```

Expected: `ImportError` — `geets.utils.image_utils` does not exist yet.

- [ ] **Step 3: Implement `src/geets/utils/image_utils.py`**

```python
from __future__ import annotations

import ee


def get_image_with_least_cc(
    collection: ee.ImageCollection,
    cloud_property: str = "CLOUDY_PIXEL_PERCENTAGE",
) -> ee.Image:
    """Return the image with the lowest cloud cover from a collection.

    Parameters
    ----------
    collection     : pre-filtered ee.ImageCollection
    cloud_property : image property to sort by (default "CLOUDY_PIXEL_PERCENTAGE")

    Raises
    ------
    ValueError if the collection is empty.
    """
    n = collection.size().getInfo()
    if n == 0:
        raise ValueError(
            "[geets.image_utils] Collection is empty – "
            "cannot select least-cloudy image. Check your filters."
        )
    print(
        f"[geets.image_utils] Selecting least-cloudy image from {n} candidates "
        f"(property: '{cloud_property}')"
    )
    return collection.sort(cloud_property).first()
```

- [ ] **Step 4: Run tests — expect pass**

```powershell
python -m pytest tests/unit/test_image_utils.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Update `src/geets/utils/__init__.py`**

Replace the full file contents:

```python
from .gee import (
    DEFAULT_EE_PROJECT,
    authenticate_and_initialize_ee,
    authenticate_ee,
    initialize_ee,
)
from .output import build_output_path, l_get_outdir, l_set_outdir
from .image_utils import get_image_with_least_cc

__all__ = [
    "DEFAULT_EE_PROJECT",
    "authenticate_ee",
    "initialize_ee",
    "authenticate_and_initialize_ee",
    "l_set_outdir",
    "l_get_outdir",
    "build_output_path",
    "get_image_with_least_cc",
]
```

- [ ] **Step 6: Commit**

```powershell
git add src/geets/utils/image_utils.py src/geets/utils/__init__.py tests/unit/test_image_utils.py
git commit -m "feat: add get_image_with_least_cc to utils"
```

---

### Task 3: `optical/s2l8.py` — Constants and private level-1 helpers

**Files:**
- Create: `src/geets/optical/s2l8.py`
- Create: `tests/unit/test_s2l8.py`

- [ ] **Step 1: Write failing tests for constants**

Create `tests/unit/test_s2l8.py`:

```python
def test_band_lists_have_equal_length():
    from geets.optical.s2l8 import _S2_BANDS_SRC, _L8_BANDS_SRC, _BANDS_HARMONIZED
    assert len(_S2_BANDS_SRC) == len(_BANDS_HARMONIZED)
    assert len(_L8_BANDS_SRC) == len(_BANDS_HARMONIZED)


def test_s2_band_src_contains_expected_bands():
    from geets.optical.s2l8 import _S2_BANDS_SRC
    assert _S2_BANDS_SRC == ["B2", "B3", "B4", "B8", "B11", "B12"]


def test_l8_band_src_contains_expected_bands():
    from geets.optical.s2l8 import _L8_BANDS_SRC
    assert _L8_BANDS_SRC == ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"]


def test_harmonized_bands():
    from geets.optical.s2l8 import _BANDS_HARMONIZED
    assert _BANDS_HARMONIZED == ["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2"]


def test_collection_ids_are_defined():
    from geets.optical.s2l8 import _S2_COLLECTION_ID, _L8_COLLECTION_ID
    assert _S2_COLLECTION_ID == "COPERNICUS/S2_SR_HARMONIZED"
    assert _L8_COLLECTION_ID == "LANDSAT/LC08/C02/T1_L2"
```

- [ ] **Step 2: Run to verify failure**

```powershell
python -m pytest tests/unit/test_s2l8.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Create `src/geets/optical/s2l8.py` with constants and level-1 helpers**

```python
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
```

- [ ] **Step 4: Run tests — expect pass**

```powershell
python -m pytest tests/unit/test_s2l8.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/geets/optical/s2l8.py tests/unit/test_s2l8.py
git commit -m "feat: add s2l8 constants and private level-1 helpers"
```

---

### Task 4: `to_surface_reflection` — Level-2 public dispatcher

**Files:**
- Modify: `src/geets/optical/s2l8.py` (append after level-1 helpers)
- Modify: `tests/unit/test_s2l8.py` (append tests)

- [ ] **Step 1: Append failing tests to `tests/unit/test_s2l8.py`**

```python
def test_to_surface_reflection_raises_on_unknown_sensor():
    from unittest.mock import MagicMock
    from geets.optical.s2l8 import to_surface_reflection
    import pytest

    with pytest.raises(ValueError, match="Unknown sensor"):
        to_surface_reflection(MagicMock(), "MODIS")


def test_to_surface_reflection_dispatches_s2():
    from unittest.mock import MagicMock, patch
    from geets.optical import s2l8

    img = MagicMock()
    with patch.object(s2l8, "_scale_s2", return_value=MagicMock()) as mock_scale:
        s2l8.to_surface_reflection(img, "S2")
        mock_scale.assert_called_once_with(img)


def test_to_surface_reflection_dispatches_l8():
    from unittest.mock import MagicMock, patch
    from geets.optical import s2l8

    img = MagicMock()
    with patch.object(s2l8, "_scale_l8", return_value=MagicMock()) as mock_scale:
        s2l8.to_surface_reflection(img, "L8")
        mock_scale.assert_called_once_with(img)
```

- [ ] **Step 2: Run to verify failure**

```powershell
python -m pytest tests/unit/test_s2l8.py::test_to_surface_reflection_raises_on_unknown_sensor -v
```

Expected: `AttributeError` — `to_surface_reflection` not defined.

- [ ] **Step 3: Append to `src/geets/optical/s2l8.py`**

Add after the level-1 helpers block:

```python
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
```

- [ ] **Step 4: Run all tests — expect pass**

```powershell
python -m pytest tests/unit/test_s2l8.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/geets/optical/s2l8.py tests/unit/test_s2l8.py
git commit -m "feat: add to_surface_reflection dispatcher"
```

---

### Task 5: `get_s2` — Level-4 full pipeline

**Files:**
- Modify: `src/geets/optical/s2l8.py` (append after level-2)
- Modify: `tests/unit/test_s2l8.py` (append test)

- [ ] **Step 1: Append failing test to `tests/unit/test_s2l8.py`**

```python
def test_get_s2_raises_on_invalid_band():
    from unittest.mock import MagicMock
    from geets.optical.s2l8 import get_s2
    import pytest

    with pytest.raises(ValueError, match="Unknown band"):
        get_s2("2022-01-01", "2022-03-01", MagicMock(), bands=["INVALID_BAND"])
```

- [ ] **Step 2: Run to verify failure**

```powershell
python -m pytest tests/unit/test_s2l8.py::test_get_s2_raises_on_invalid_band -v
```

Expected: `AttributeError` — `get_s2` not defined.

- [ ] **Step 3: Append `get_s2` to `src/geets/optical/s2l8.py`**

Add after the level-2 block:

```python
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
```

- [ ] **Step 4: Run all tests — expect pass**

```powershell
python -m pytest tests/unit/test_s2l8.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/geets/optical/s2l8.py tests/unit/test_s2l8.py
git commit -m "feat: add get_s2 pipeline"
```

---

### Task 6: `get_l8` — Level-4 full pipeline

**Files:**
- Modify: `src/geets/optical/s2l8.py` (append after `get_s2`)
- Modify: `tests/unit/test_s2l8.py` (append test)

- [ ] **Step 1: Append failing test to `tests/unit/test_s2l8.py`**

```python
def test_get_l8_raises_on_invalid_band():
    from unittest.mock import MagicMock
    from geets.optical.s2l8 import get_l8
    import pytest

    with pytest.raises(ValueError, match="Unknown band"):
        get_l8("2022-01-01", "2022-03-01", MagicMock(), bands=["INVALID_BAND"])
```

- [ ] **Step 2: Run to verify failure**

```powershell
python -m pytest tests/unit/test_s2l8.py::test_get_l8_raises_on_invalid_band -v
```

Expected: `AttributeError` — `get_l8` not defined.

- [ ] **Step 3: Append `get_l8` to `src/geets/optical/s2l8.py`**

Add immediately after `get_s2`:

```python
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

    print(f"[geets.s2l8] Loading L8: {_L8_COLLECTION_ID}")
    print(f"[geets.s2l8] Date range: {start_date} → {end_date}")
    print(f"[geets.s2l8] max_cloud_cover={max_cloud_cover}%  "
          f"mask_clouds={mask_clouds}  bands={bands or 'all'}")

    col = (
        ee.ImageCollection(_L8_COLLECTION_ID)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lte(_L8_CLOUD_PROPERTY, max_cloud_cover))
    )

    if aoi is not None:
        print("[geets.s2l8] Applying AOI filter")
        col = col.filterBounds(aoi)

    if mask_clouds:
        col = col.map(_mask_l8_qa_pixel)

    col = col.map(_scale_l8).map(_rename_l8)

    if bands is not None:
        col = col.select(bands)

    if aoi is not None and clip:
        print("[geets.s2l8] Clipping to AOI")
        col = col.map(lambda img: img.clip(aoi))

    n = col.size().getInfo()
    if n == 0:
        print(f"[geets.s2l8] WARNING: L8 collection is EMPTY (0 images).")
        print(f"[geets.s2l8]   → Check date range ({start_date} – {end_date}),")
        print(f"[geets.s2l8]      max_cloud_cover={max_cloud_cover}%, and AOI.")
    else:
        print(f"[geets.s2l8] L8 collection ready: {n} images")

    return col
```

- [ ] **Step 4: Run all tests — expect pass**

```powershell
python -m pytest tests/unit/test_s2l8.py -v
```

Expected: 10 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/geets/optical/s2l8.py tests/unit/test_s2l8.py
git commit -m "feat: add get_l8 pipeline"
```

---

### Task 7: Wire up `__init__.py` files

**Files:**
- Modify: `src/geets/optical/__init__.py`
- Modify: `src/geets/__init__.py`

(`src/geets/utils/__init__.py` was already updated in Task 2.)

- [ ] **Step 1: Replace `src/geets/optical/__init__.py`**

```python
from .modis import load_modis_vi, load_modis_ndvi, MODIS_COLLECTIONS
from .s2l8 import get_s2, get_l8, to_surface_reflection
```

- [ ] **Step 2: Replace `src/geets/__init__.py`**

```python
"""
geets – Google Earth Engine Tools for Earth Science
"""

from .climate.era5         import ERA5_COLLECTIONS, load_era5_daily
from .climate.chirps       import CHIRPS_COLLECTIONS, CHIRPS_COLLECTION_ID, CHIRPS_BAND, load_chirps_daily
from .optical.modis        import load_modis_vi, load_modis_ndvi, MODIS_COLLECTIONS
from .optical.s2l8         import get_s2, get_l8, to_surface_reflection
from .timeseries.aggregate import aggregate_monthly, aggregate_temporal, aggregate_weekly, aggregate_yearly
from .timeseries.reduce    import l_aggregate_csv, l_export_csv, l_load_band_csvs, reduce_region_stats
from .timeseries.plot      import l_plot_boxplot, l_plot_timeseries, l_plot_combined, l_stack_plots
from .utils.gee            import (
    DEFAULT_EE_PROJECT,
    authenticate_and_initialize_ee,
    authenticate_ee,
    initialize_ee,
)
from .utils.output         import l_get_outdir, l_set_outdir
from .utils.image_utils    import get_image_with_least_cc
from .pairs                import find_pairs, export_pairs, ImagePair

__all__ = [
    "find_pairs",
    "export_pairs",
    "ImagePair",
    "load_modis_vi",
    "load_modis_ndvi",
    "MODIS_COLLECTIONS",
    "get_s2",
    "get_l8",
    "to_surface_reflection",
    "load_era5_daily",
    "ERA5_COLLECTIONS",
    "load_chirps_daily",
    "CHIRPS_COLLECTIONS",
    "CHIRPS_COLLECTION_ID",
    "CHIRPS_BAND",
    "aggregate_temporal",
    "aggregate_weekly",
    "aggregate_monthly",
    "aggregate_yearly",
    "reduce_region_stats",
    "l_export_csv",
    "l_load_band_csvs",
    "l_aggregate_csv",
    "l_plot_boxplot",
    "l_plot_timeseries",
    "l_plot_combined",
    "l_stack_plots",
    "DEFAULT_EE_PROJECT",
    "authenticate_ee",
    "initialize_ee",
    "authenticate_and_initialize_ee",
    "l_set_outdir",
    "l_get_outdir",
    "get_image_with_least_cc",
]
```

- [ ] **Step 3: Run full test suite**

```powershell
python -m pytest tests/ -v
```

Expected: all 13 tests pass.

- [ ] **Step 4: Verify package imports**

```powershell
python -c "from geets import get_s2, get_l8, to_surface_reflection, get_image_with_least_cc; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```powershell
git add src/geets/optical/__init__.py src/geets/__init__.py
git commit -m "feat: export s2l8 and image_utils from package root"
```
