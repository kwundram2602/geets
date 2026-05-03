# MODIS Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote MODIS from `optical/modis.py` into a top-level `geets/modis/` subpackage with four product-family loaders (VI, LST, SR, Fire) and a unified `MODIS_SETS` metadata dict.

**Architecture:** One focused file per product family (`vi.py`, `lst.py`, `sr.py`, `fire.py`) plus a standalone `sets.py` for collection metadata. Each loader imports `MODIS_SETS` from `sets.py` to validate the `collection` argument by product family tag. No GEE calls in unit tests — all tests mock `ee.ImageCollection`.

**Tech Stack:** Python 3.12+, `ee` (Google Earth Engine Python API), `unittest.mock`, `pytest`

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `src/geets/modis/__init__.py` | Re-export all public symbols |
| Create | `src/geets/modis/sets.py` | `MODIS_SETS` dict — all collection metadata |
| Create | `src/geets/modis/vi.py` | `load_modis_vi`, `load_modis_ndvi` |
| Create | `src/geets/modis/lst.py` | `load_modis_lst` |
| Create | `src/geets/modis/sr.py` | `load_modis_sr` |
| Create | `src/geets/modis/fire.py` | `load_modis_fire` |
| Delete | `src/geets/optical/modis.py` | Replaced by `modis/vi.py` |
| Modify | `src/geets/optical/__init__.py` | Remove MODIS imports |
| Modify | `src/geets/__init__.py` | Swap optical.modis → modis imports |
| Create | `tests/unit/modis/__init__.py` | Test package marker |
| Create | `tests/unit/modis/test_sets.py` | Tests for MODIS_SETS structure |
| Create | `tests/unit/modis/test_vi.py` | Tests for VI loader |
| Create | `tests/unit/modis/test_lst.py` | Tests for LST loader |
| Create | `tests/unit/modis/test_sr.py` | Tests for SR loader |
| Create | `tests/unit/modis/test_fire.py` | Tests for fire loader |

---

## Task 1: `sets.py` — MODIS_SETS metadata

**Files:**
- Create: `src/geets/modis/sets.py`
- Create: `tests/unit/modis/__init__.py`
- Create: `tests/unit/modis/test_sets.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/modis/__init__.py` (empty file), then create `tests/unit/modis/test_sets.py`:

```python
def test_modis_sets_is_dict():
    from geets.modis import sets
    assert isinstance(sets.MODIS_SETS, dict)


def test_modis_sets_has_vi_collections():
    from geets.modis import sets
    vi_keys = {k for k, v in sets.MODIS_SETS.items() if v["product"] == "vi"}
    assert {"MOD13Q1", "MOD13A1", "MOD13A3", "MYD13Q1"}.issubset(vi_keys)


def test_modis_sets_has_lst_collections():
    from geets.modis import sets
    lst_keys = {k for k, v in sets.MODIS_SETS.items() if v["product"] == "lst"}
    assert {"MOD11A1", "MOD11A2", "MYD11A1", "MYD11A2"}.issubset(lst_keys)


def test_modis_sets_has_sr_collections():
    from geets.modis import sets
    sr_keys = {k for k, v in sets.MODIS_SETS.items() if v["product"] == "sr"}
    assert {"MOD09GQ", "MOD09GA", "MOD09A1", "MOD09Q1", "MYD09GQ", "MYD09GA"}.issubset(sr_keys)


def test_modis_sets_has_fire_collections():
    from geets.modis import sets
    fire_keys = {k for k, v in sets.MODIS_SETS.items() if v["product"] == "fire"}
    assert {"MCD64A1", "MOD14A1", "MOD14A2"}.issubset(fire_keys)


def test_modis_sets_entry_shape():
    from geets.modis import sets
    required = {"id", "product", "description", "start", "end", "resolution_m", "cadence"}
    for key, entry in sets.MODIS_SETS.items():
        missing = required - entry.keys()
        assert not missing, f"{key} missing fields: {missing}"


def test_modis_sets_ids_start_with_modis():
    from geets.modis import sets
    for key, entry in sets.MODIS_SETS.items():
        assert entry["id"].startswith("MODIS/"), f"{key} id should start with MODIS/"


def test_modis_sets_resolution_m_is_int():
    from geets.modis import sets
    for key, entry in sets.MODIS_SETS.items():
        assert isinstance(entry["resolution_m"], int), f"{key} resolution_m must be int"
```

- [ ] **Step 2: Run tests to confirm they fail**

```
python -m pytest tests/unit/modis/test_sets.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` — `geets.modis` does not exist yet.

- [ ] **Step 3: Create `src/geets/modis/sets.py`**

```python
"""MODIS collection metadata for Google Earth Engine.

Keys follow the GEE short product name (e.g. "MOD13Q1").
Where multiple Collection versions exist for the same product
(e.g. 061 and 062), each version has its own entry using the
convention "<PRODUCT>.<VERSION>" for non-baseline entries
(e.g. "MOD13Q1.062"). Loaders default to the highest-numbered
version available in GEE.

Only official MODIS collections (MODIS/06x/ namespace) are included.
"""

MODIS_SETS: dict[str, dict] = {
    # ------------------------------------------------------------------ VI
    "MOD13Q1": {
        "id": "MODIS/061/MOD13Q1",
        "product": "vi",
        "description": "Terra Vegetation Indices (NDVI/EVI), 250 m, 16-day composite",
        "start": "2000-02-18",
        "end": "present",
        "resolution_m": 250,
        "cadence": "16-day",
    },
    "MOD13A1": {
        "id": "MODIS/061/MOD13A1",
        "product": "vi",
        "description": "Terra Vegetation Indices (NDVI/EVI), 500 m, 16-day composite",
        "start": "2000-02-18",
        "end": "present",
        "resolution_m": 500,
        "cadence": "16-day",
    },
    "MOD13A3": {
        "id": "MODIS/061/MOD13A3",
        "product": "vi",
        "description": "Terra Vegetation Indices (NDVI/EVI), 1 km, monthly composite",
        "start": "2000-03-01",
        "end": "present",
        "resolution_m": 1000,
        "cadence": "monthly",
    },
    "MYD13Q1": {
        "id": "MODIS/061/MYD13Q1",
        "product": "vi",
        "description": "Aqua Vegetation Indices (NDVI/EVI), 250 m, 16-day composite",
        "start": "2002-07-04",
        "end": "present",
        "resolution_m": 250,
        "cadence": "16-day",
    },
    # ------------------------------------------------------------------ LST
    "MOD11A1": {
        "id": "MODIS/061/MOD11A1",
        "product": "lst",
        "description": "Terra Land Surface Temperature and Emissivity, 1 km, daily",
        "start": "2000-03-05",
        "end": "present",
        "resolution_m": 1000,
        "cadence": "daily",
    },
    "MOD11A2": {
        "id": "MODIS/061/MOD11A2",
        "product": "lst",
        "description": "Terra Land Surface Temperature and Emissivity, 1 km, 8-day composite",
        "start": "2000-03-05",
        "end": "present",
        "resolution_m": 1000,
        "cadence": "8-day",
    },
    "MYD11A1": {
        "id": "MODIS/061/MYD11A1",
        "product": "lst",
        "description": "Aqua Land Surface Temperature and Emissivity, 1 km, daily",
        "start": "2002-07-04",
        "end": "present",
        "resolution_m": 1000,
        "cadence": "daily",
    },
    "MYD11A2": {
        "id": "MODIS/061/MYD11A2",
        "product": "lst",
        "description": "Aqua Land Surface Temperature and Emissivity, 1 km, 8-day composite",
        "start": "2002-07-04",
        "end": "present",
        "resolution_m": 1000,
        "cadence": "8-day",
    },
    # ------------------------------------------------------------------ SR
    "MOD09GQ": {
        "id": "MODIS/061/MOD09GQ",
        "product": "sr",
        "description": "Terra Surface Reflectance, 250 m, daily (bands 1-2)",
        "start": "2000-02-24",
        "end": "present",
        "resolution_m": 250,
        "cadence": "daily",
    },
    "MOD09GA": {
        "id": "MODIS/061/MOD09GA",
        "product": "sr",
        "description": "Terra Surface Reflectance, 500 m, daily (bands 1-7 + state)",
        "start": "2000-02-24",
        "end": "present",
        "resolution_m": 500,
        "cadence": "daily",
    },
    "MOD09A1": {
        "id": "MODIS/061/MOD09A1",
        "product": "sr",
        "description": "Terra Surface Reflectance, 500 m, 8-day composite (bands 1-7)",
        "start": "2000-02-18",
        "end": "present",
        "resolution_m": 500,
        "cadence": "8-day",
    },
    "MOD09Q1": {
        "id": "MODIS/061/MOD09Q1",
        "product": "sr",
        "description": "Terra Surface Reflectance, 250 m, 8-day composite (bands 1-2)",
        "start": "2000-02-18",
        "end": "present",
        "resolution_m": 250,
        "cadence": "8-day",
    },
    "MYD09GQ": {
        "id": "MODIS/061/MYD09GQ",
        "product": "sr",
        "description": "Aqua Surface Reflectance, 250 m, daily (bands 1-2)",
        "start": "2002-07-04",
        "end": "present",
        "resolution_m": 250,
        "cadence": "daily",
    },
    "MYD09GA": {
        "id": "MODIS/061/MYD09GA",
        "product": "sr",
        "description": "Aqua Surface Reflectance, 500 m, daily (bands 1-7 + state)",
        "start": "2002-07-04",
        "end": "present",
        "resolution_m": 500,
        "cadence": "daily",
    },
    # ------------------------------------------------------------------ Fire
    "MCD64A1": {
        "id": "MODIS/061/MCD64A1",
        "product": "fire",
        "description": "Terra+Aqua Burned Area, 500 m, monthly",
        "start": "2000-11-01",
        "end": "present",
        "resolution_m": 500,
        "cadence": "monthly",
    },
    "MOD14A1": {
        "id": "MODIS/061/MOD14A1",
        "product": "fire",
        "description": "Terra Thermal Anomalies and Fire, 1 km, daily",
        "start": "2000-02-24",
        "end": "present",
        "resolution_m": 1000,
        "cadence": "daily",
    },
    "MOD14A2": {
        "id": "MODIS/061/MOD14A2",
        "product": "fire",
        "description": "Terra Thermal Anomalies and Fire, 1 km, 8-day composite",
        "start": "2000-02-24",
        "end": "present",
        "resolution_m": 1000,
        "cadence": "8-day",
    },
}
```

- [ ] **Step 4: Create `src/geets/modis/__init__.py`** (minimal — will be filled in Task 6)

```python
from .sets import MODIS_SETS
```

- [ ] **Step 5: Run tests and confirm they pass**

```
python -m pytest tests/unit/modis/test_sets.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 6: Commit**

```
git add src/geets/modis/sets.py src/geets/modis/__init__.py tests/unit/modis/__init__.py tests/unit/modis/test_sets.py
git commit -m "feat: add geets.modis package with MODIS_SETS metadata"
```

---

## Task 2: `vi.py` — Vegetation Index loader (migrated from `optical/modis.py`)

**Files:**
- Create: `src/geets/modis/vi.py`
- Create: `tests/unit/modis/test_vi.py`
- Delete: `src/geets/optical/modis.py`
- Modify: `src/geets/optical/__init__.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/modis/test_vi.py`:

```python
def test_load_modis_vi_raises_on_invalid_collection():
    import pytest
    from geets.modis import vi

    with pytest.raises(ValueError, match="Unknown collection"):
        vi.load_modis_vi("2023-01-01", "2024-01-01", collection="BOGUS")


def test_load_modis_vi_raises_on_lst_collection():
    import pytest
    from geets.modis import vi

    with pytest.raises(ValueError, match="Unknown collection"):
        vi.load_modis_vi("2023-01-01", "2024-01-01", collection="MOD11A1")


def test_load_modis_vi_filters_date():
    from unittest.mock import MagicMock, patch
    from geets.modis import vi

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.filterBounds.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 5

    with patch.object(vi.ee, "ImageCollection", return_value=mock_col):
        vi.load_modis_vi("2023-01-01", "2024-01-01", mask_clouds=False, apply_scale=False)
        mock_col.filterDate.assert_called_once_with("2023-01-01", "2024-01-01")


def test_load_modis_vi_applies_aoi_filter():
    from unittest.mock import MagicMock, patch
    from geets.modis import vi

    aoi = MagicMock()
    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.filterBounds.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 3

    with patch.object(vi.ee, "ImageCollection", return_value=mock_col):
        vi.load_modis_vi("2023-01-01", "2024-01-01", aoi=aoi, mask_clouds=False, apply_scale=False)
        mock_col.filterBounds.assert_called_once_with(aoi)


def test_load_modis_vi_skips_aoi_filter_when_none():
    from unittest.mock import MagicMock, patch
    from geets.modis import vi

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 3

    with patch.object(vi.ee, "ImageCollection", return_value=mock_col):
        vi.load_modis_vi("2023-01-01", "2024-01-01", mask_clouds=False, apply_scale=False)
        mock_col.filterBounds.assert_not_called()


def test_load_modis_vi_applies_cloud_mask():
    from unittest.mock import MagicMock, patch
    from geets.modis import vi

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 5

    with patch.object(vi.ee, "ImageCollection", return_value=mock_col):
        vi.load_modis_vi("2023-01-01", "2024-01-01", mask_clouds=True, apply_scale=False)
        assert mock_col.map.called


def test_load_modis_ndvi_is_alias():
    from unittest.mock import patch
    from geets.modis import vi

    with patch.object(vi, "load_modis_vi") as mock_vi:
        vi.load_modis_ndvi("2023-01-01", "2024-01-01", collection="MOD13Q1")
        mock_vi.assert_called_once()
```

- [ ] **Step 2: Run tests to confirm they fail**

```
python -m pytest tests/unit/modis/test_vi.py -v
```

Expected: `ImportError` — `geets.modis.vi` does not exist yet.

- [ ] **Step 3: Create `src/geets/modis/vi.py`**

```python
"""MODIS Vegetation Index loader for Google Earth Engine.

Supported collections (product family: "vi"):
  MOD13Q1  – Terra NDVI/EVI, 250 m, 16-day
  MOD13A1  – Terra NDVI/EVI, 500 m, 16-day
  MOD13A3  – Terra NDVI/EVI, 1 km, monthly
  MYD13Q1  – Aqua  NDVI/EVI, 250 m, 16-day
"""

from __future__ import annotations

import ee

from .sets import MODIS_SETS

_VI_COLLECTIONS: dict[str, dict] = {
    k: v for k, v in MODIS_SETS.items() if v["product"] == "vi"
}

_VI_META: dict[str, dict] = {
    "MOD13Q1": {"ndvi": "NDVI", "evi": "EVI", "qa": "SummaryQA", "scale_factor": 0.0001},
    "MOD13A1": {"ndvi": "NDVI", "evi": "EVI", "qa": "SummaryQA", "scale_factor": 0.0001},
    "MOD13A3": {"ndvi": "NDVI", "evi": "EVI", "qa": "SummaryQA", "scale_factor": 0.0001},
    "MYD13Q1": {"ndvi": "NDVI", "evi": "EVI", "qa": "SummaryQA", "scale_factor": 0.0001},
}

# SummaryQA: 0=good, 1=marginal, 2=snow/ice, 3=cloudy
_QA_MARGINAL = 1


def _mask_qa(img: ee.Image, max_qa: int) -> ee.Image:
    qa = img.select("SummaryQA")
    return img.updateMask(qa.lte(max_qa))


def _scale_vi(img: ee.Image, scale_factor: float, qa_band: str) -> ee.Image:
    scaled = img.select(["NDVI", "EVI"]).multiply(scale_factor)
    qa = img.select(qa_band)
    return scaled.addBands(qa).copyProperties(img, img.propertyNames())


def load_modis_vi(
    start_date: str,
    end_date: str,
    aoi: ee.Geometry | None = None,
    collection: str = "MOD13Q1",
    band: str = "NDVI",
    apply_scale: bool = True,
    mask_clouds: bool = True,
    max_qa: int = _QA_MARGINAL,
) -> ee.ImageCollection:
    """Load a MODIS NDVI/EVI ImageCollection from GEE.

    Args:
        start_date: ISO date string, e.g. "2023-01-01".
        end_date: ISO date string, e.g. "2024-01-01".
        aoi: Optional AOI geometry for filtering and clipping.
        collection: One of MOD13Q1, MOD13A1, MOD13A3, MYD13Q1.
        band: "NDVI", "EVI", or None to keep both.
        apply_scale: Multiply raw int values by 0.0001.
        mask_clouds: Apply SummaryQA mask.
        max_qa: Max accepted QA value (0=good only, 1=good+marginal).

    Returns:
        ee.ImageCollection
    """
    if collection not in _VI_COLLECTIONS:
        raise ValueError(
            f"Unknown collection '{collection}'. "
            f"Choose from: {sorted(_VI_COLLECTIONS)}"
        )

    meta = _VI_META[collection]
    collection_id = _VI_COLLECTIONS[collection]["id"]
    print(f"[geets.modis.vi] Loading: {collection_id}")
    print(f"[geets.modis.vi] Date range: {start_date} -> {end_date}")

    col = (
        ee.ImageCollection(collection_id)
        .filterDate(start_date, end_date)
        .select(["NDVI", "EVI", meta["qa"]])
    )

    if aoi is not None:
        col = col.filterBounds(aoi)

    if mask_clouds:
        col = col.map(lambda img: _mask_qa(img, max_qa))

    if apply_scale:
        sf = meta["scale_factor"]
        col = col.map(lambda img: _scale_vi(img, sf, meta["qa"]))

    if band is not None:
        col = col.select([band, meta["qa"]])

    if aoi is not None:
        col = col.map(lambda img: img.clip(aoi))

    n = col.size().getInfo()
    if n == 0:
        print(f"[geets.modis.vi] WARNING: collection is EMPTY.")
    else:
        print(f"[geets.modis.vi] Collection ready: {n} images")

    return col


def load_modis_ndvi(
    start_date: str,
    end_date: str,
    aoi: ee.Geometry | None = None,
    collection: str = "MOD13Q1",
    band: str = "NDVI",
    apply_scale: bool = True,
    mask_clouds: bool = True,
    max_qa: int = _QA_MARGINAL,
) -> ee.ImageCollection:
    """Backward-compatible alias for `load_modis_vi`."""
    return load_modis_vi(
        start_date=start_date,
        end_date=end_date,
        aoi=aoi,
        collection=collection,
        band=band,
        apply_scale=apply_scale,
        mask_clouds=mask_clouds,
        max_qa=max_qa,
    )
```

- [ ] **Step 4: Run tests and confirm they pass**

```
python -m pytest tests/unit/modis/test_vi.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Delete `src/geets/optical/modis.py`**

```
git rm src/geets/optical/modis.py
```

- [ ] **Step 6: Update `src/geets/optical/__init__.py`**

Remove the MODIS lines. File should become:

```python
from .s2l8 import get_s2, get_l8, to_surface_reflection
```

- [ ] **Step 7: Run full test suite to confirm nothing broke**

```
python -m pytest -v
```

Expected: all existing tests PASS (no references to `optical.modis` remain).

- [ ] **Step 8: Commit**

```
git add src/geets/modis/vi.py src/geets/optical/__init__.py tests/unit/modis/test_vi.py
git commit -m "feat: migrate MODIS VI loader to geets.modis.vi"
```

---

## Task 3: `lst.py` — Land Surface Temperature loader

**Files:**
- Create: `src/geets/modis/lst.py`
- Create: `tests/unit/modis/test_lst.py`

**GEE band reference for MOD11A1/A2, MYD11A1/A2:**
- `LST_Day_1km` — daytime LST, raw uint16, scale 0.02 → Kelvin
- `LST_Night_1km` — nighttime LST, raw uint16, scale 0.02 → Kelvin
- `QC_Day` / `QC_Night` — 8-bit QA. Bits 0-1: `00`=good, `01`=other quality, `11`=not produced. Mask where bits 0-1 ≠ 0.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/modis/test_lst.py`:

```python
def test_load_modis_lst_raises_on_invalid_collection():
    import pytest
    from geets.modis import lst

    with pytest.raises(ValueError, match="Unknown collection"):
        lst.load_modis_lst("2023-01-01", "2024-01-01", collection="MOD13Q1")


def test_load_modis_lst_raises_on_invalid_time_of_day():
    import pytest
    from geets.modis import lst

    with pytest.raises(ValueError, match="time_of_day"):
        lst.load_modis_lst("2023-01-01", "2024-01-01", time_of_day="noon")


def test_load_modis_lst_filters_date():
    from unittest.mock import MagicMock, patch
    from geets.modis import lst

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 4

    with patch.object(lst.ee, "ImageCollection", return_value=mock_col):
        lst.load_modis_lst("2023-01-01", "2024-01-01", mask_clouds=False, apply_scale=False)
        mock_col.filterDate.assert_called_once_with("2023-01-01", "2024-01-01")


def test_load_modis_lst_applies_aoi_filter():
    from unittest.mock import MagicMock, patch
    from geets.modis import lst

    aoi = MagicMock()
    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.filterBounds.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 4

    with patch.object(lst.ee, "ImageCollection", return_value=mock_col):
        lst.load_modis_lst("2023-01-01", "2024-01-01", aoi=aoi, mask_clouds=False, apply_scale=False)
        mock_col.filterBounds.assert_called_once_with(aoi)


def test_load_modis_lst_selects_day_band():
    from unittest.mock import MagicMock, patch, call
    from geets.modis import lst

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 4

    with patch.object(lst.ee, "ImageCollection", return_value=mock_col):
        lst.load_modis_lst("2023-01-01", "2024-01-01", time_of_day="day",
                           mask_clouds=False, apply_scale=False)
        mock_col.select.assert_any_call(["LST_Day_1km", "QC_Day"])


def test_load_modis_lst_selects_night_band():
    from unittest.mock import MagicMock, patch
    from geets.modis import lst

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 4

    with patch.object(lst.ee, "ImageCollection", return_value=mock_col):
        lst.load_modis_lst("2023-01-01", "2024-01-01", time_of_day="night",
                           mask_clouds=False, apply_scale=False)
        mock_col.select.assert_any_call(["LST_Night_1km", "QC_Night"])
```

- [ ] **Step 2: Run tests to confirm they fail**

```
python -m pytest tests/unit/modis/test_lst.py -v
```

Expected: `ImportError` — `geets.modis.lst` does not exist yet.

- [ ] **Step 3: Create `src/geets/modis/lst.py`**

```python
"""MODIS Land Surface Temperature loader for Google Earth Engine.

Supported collections (product family: "lst"):
  MOD11A1  – Terra LST, 1 km, daily
  MOD11A2  – Terra LST, 1 km, 8-day composite
  MYD11A1  – Aqua  LST, 1 km, daily
  MYD11A2  – Aqua  LST, 1 km, 8-day composite

LST raw values are uint16; multiply by 0.02 to get Kelvin.
To convert to Celsius: (raw * 0.02) - 273.15.
QA bits 0-1: 00=good, 01=other quality, 10=TBD, 11=not produced.
"""

from __future__ import annotations

import ee

from .sets import MODIS_SETS

_LST_COLLECTIONS: dict[str, dict] = {
    k: v for k, v in MODIS_SETS.items() if v["product"] == "lst"
}

_LST_SCALE = 0.02  # raw → Kelvin

_LST_BANDS = {
    "day":   ("LST_Day_1km",   "QC_Day"),
    "night": ("LST_Night_1km", "QC_Night"),
}


def _mask_lst_qa(img: ee.Image, qc_band: str) -> ee.Image:
    # Keep only pixels where QC bits 0-1 == 0b00 (good quality).
    qc = img.select(qc_band)
    good = qc.bitwiseAnd(0b11).eq(0)
    return img.updateMask(good)


def _scale_lst(img: ee.Image, lst_band: str, qc_band: str) -> ee.Image:
    scaled = img.select(lst_band).multiply(_LST_SCALE)
    qc = img.select(qc_band)
    return scaled.addBands(qc).copyProperties(img, img.propertyNames())


def load_modis_lst(
    start_date: str,
    end_date: str,
    aoi: ee.Geometry | None = None,
    collection: str = "MOD11A2",
    time_of_day: str = "day",
    apply_scale: bool = True,
    mask_clouds: bool = True,
) -> ee.ImageCollection:
    """Load a MODIS Land Surface Temperature ImageCollection from GEE.

    Args:
        start_date: ISO date string, e.g. "2023-01-01".
        end_date: ISO date string, e.g. "2024-01-01".
        aoi: Optional AOI geometry for filtering and clipping.
        collection: One of MOD11A1, MOD11A2, MYD11A1, MYD11A2.
        time_of_day: "day" or "night".
        apply_scale: Multiply raw values by 0.02 to get Kelvin.
        mask_clouds: Apply QC bitmask (bits 0-1 must equal 00).

    Returns:
        ee.ImageCollection with LST band and QC band.
    """
    if collection not in _LST_COLLECTIONS:
        raise ValueError(
            f"Unknown collection '{collection}'. "
            f"Choose from: {sorted(_LST_COLLECTIONS)}"
        )
    if time_of_day not in _LST_BANDS:
        raise ValueError(
            f"Invalid time_of_day '{time_of_day}'. Choose 'day' or 'night'."
        )

    lst_band, qc_band = _LST_BANDS[time_of_day]
    collection_id = _LST_COLLECTIONS[collection]["id"]
    print(f"[geets.modis.lst] Loading: {collection_id}")
    print(f"[geets.modis.lst] Date range: {start_date} -> {end_date}")
    print(f"[geets.modis.lst] time_of_day={time_of_day}, band={lst_band}")

    col = (
        ee.ImageCollection(collection_id)
        .filterDate(start_date, end_date)
        .select([lst_band, qc_band])
    )

    if aoi is not None:
        col = col.filterBounds(aoi)

    if mask_clouds:
        col = col.map(lambda img: _mask_lst_qa(img, qc_band))

    if apply_scale:
        col = col.map(lambda img: _scale_lst(img, lst_band, qc_band))

    if aoi is not None:
        col = col.map(lambda img: img.clip(aoi))

    n = col.size().getInfo()
    if n == 0:
        print(f"[geets.modis.lst] WARNING: collection is EMPTY.")
    else:
        print(f"[geets.modis.lst] Collection ready: {n} images")

    return col
```

- [ ] **Step 4: Run tests and confirm they pass**

```
python -m pytest tests/unit/modis/test_lst.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```
git add src/geets/modis/lst.py tests/unit/modis/test_lst.py
git commit -m "feat: add MODIS LST loader (load_modis_lst)"
```

---

## Task 4: `sr.py` — Surface Reflectance loader

**Files:**
- Create: `src/geets/modis/sr.py`
- Create: `tests/unit/modis/test_sr.py`

**GEE band reference:**
- MOD09GQ / MYD09GQ (250 m daily): `sur_refl_b01_1` (red), `sur_refl_b02_1` (NIR), QA: `QC_250m`
- MOD09Q1 (250 m 8-day): `sur_refl_b01`, `sur_refl_b02`, QA: `QC_250m`
- MOD09GA / MYD09GA (500 m daily): `sur_refl_b01`–`sur_refl_b07`, QA: `state_1km`
- MOD09A1 (500 m 8-day): `sur_refl_b01`–`sur_refl_b07`, QA: `StateQA`
- Scale factor: 0.0001 for all SR bands.
- StateQA / state_1km: bit 10 = internal cloud flag. Mask where bit 10 is set.
- QC_250m: bits 2-5 = band 1 data quality. Mask where bits 2-3 ≠ 00 (not ideal).

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/modis/test_sr.py`:

```python
def test_load_modis_sr_raises_on_invalid_collection():
    import pytest
    from geets.modis import sr

    with pytest.raises(ValueError, match="Unknown collection"):
        sr.load_modis_sr("2023-01-01", "2024-01-01", collection="MOD13Q1")


def test_load_modis_sr_filters_date():
    from unittest.mock import MagicMock, patch
    from geets.modis import sr

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 10

    with patch.object(sr.ee, "ImageCollection", return_value=mock_col):
        sr.load_modis_sr("2023-01-01", "2024-01-01", mask_clouds=False, apply_scale=False)
        mock_col.filterDate.assert_called_once_with("2023-01-01", "2024-01-01")


def test_load_modis_sr_applies_aoi_filter():
    from unittest.mock import MagicMock, patch
    from geets.modis import sr

    aoi = MagicMock()
    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.filterBounds.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 10

    with patch.object(sr.ee, "ImageCollection", return_value=mock_col):
        sr.load_modis_sr("2023-01-01", "2024-01-01", aoi=aoi, mask_clouds=False, apply_scale=False)
        mock_col.filterBounds.assert_called_once_with(aoi)


def test_load_modis_sr_skips_aoi_when_none():
    from unittest.mock import MagicMock, patch
    from geets.modis import sr

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 10

    with patch.object(sr.ee, "ImageCollection", return_value=mock_col):
        sr.load_modis_sr("2023-01-01", "2024-01-01", mask_clouds=False, apply_scale=False)
        mock_col.filterBounds.assert_not_called()


def test_load_modis_sr_applies_scale():
    from unittest.mock import MagicMock, patch
    from geets.modis import sr

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 10

    with patch.object(sr.ee, "ImageCollection", return_value=mock_col):
        sr.load_modis_sr("2023-01-01", "2024-01-01", mask_clouds=False, apply_scale=True)
        assert mock_col.map.called


def test_load_modis_sr_accepts_band_subset():
    from unittest.mock import MagicMock, patch
    from geets.modis import sr

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 10

    with patch.object(sr.ee, "ImageCollection", return_value=mock_col):
        sr.load_modis_sr("2023-01-01", "2024-01-01",
                         bands=["sur_refl_b01", "sur_refl_b02"],
                         mask_clouds=False, apply_scale=False)
        mock_col.select.assert_any_call(["sur_refl_b01", "sur_refl_b02"])
```

- [ ] **Step 2: Run tests to confirm they fail**

```
python -m pytest tests/unit/modis/test_sr.py -v
```

Expected: `ImportError` — `geets.modis.sr` does not exist yet.

- [ ] **Step 3: Create `src/geets/modis/sr.py`**

```python
"""MODIS Surface Reflectance loader for Google Earth Engine.

Supported collections (product family: "sr"):
  MOD09GQ  – Terra SR, 250 m, daily (bands 1-2)
  MOD09GA  – Terra SR, 500 m, daily (bands 1-7)
  MOD09A1  – Terra SR, 500 m, 8-day composite (bands 1-7)
  MOD09Q1  – Terra SR, 250 m, 8-day composite (bands 1-2)
  MYD09GQ  – Aqua  SR, 250 m, daily (bands 1-2)
  MYD09GA  – Aqua  SR, 500 m, daily (bands 1-7)

Scale factor 0.0001 for all reflectance bands.
"""

from __future__ import annotations

import ee

from .sets import MODIS_SETS

_SR_COLLECTIONS: dict[str, dict] = {
    k: v for k, v in MODIS_SETS.items() if v["product"] == "sr"
}

_SR_SCALE = 0.0001

# Reflectance band names per collection (excludes QA band).
_SR_REFL_BANDS: dict[str, list[str]] = {
    "MOD09GQ": ["sur_refl_b01_1", "sur_refl_b02_1"],
    "MYD09GQ": ["sur_refl_b01_1", "sur_refl_b02_1"],
    "MOD09Q1": ["sur_refl_b01", "sur_refl_b02"],
    "MOD09GA": [f"sur_refl_b0{i}" for i in range(1, 8)],
    "MYD09GA": [f"sur_refl_b0{i}" for i in range(1, 8)],
    "MOD09A1": [f"sur_refl_b0{i}" for i in range(1, 8)],
}

# QA band and cloud-bit mask per collection.
# StateQA/state_1km bit 10 = internal cloud algorithm flag.
# QC_250m bits 2-3 = band 1 quality (00=ideal).
_SR_QA: dict[str, tuple[str, int]] = {
    "MOD09GQ": ("QC_250m", 0b1100),      # bits 2-3 must be 0
    "MYD09GQ": ("QC_250m", 0b1100),
    "MOD09Q1": ("QC_250m", 0b1100),
    "MOD09GA": ("state_1km", 1 << 10),   # bit 10 = cloud
    "MYD09GA": ("state_1km", 1 << 10),
    "MOD09A1": ("StateQA", 1 << 10),
}


def _mask_sr_qa(img: ee.Image, qa_band: str, cloud_bit: int) -> ee.Image:
    qa = img.select(qa_band)
    clear = qa.bitwiseAnd(cloud_bit).eq(0)
    return img.updateMask(clear)


def _scale_sr(img: ee.Image, refl_bands: list[str]) -> ee.Image:
    scaled = img.select(refl_bands).multiply(_SR_SCALE)
    return scaled.copyProperties(img, img.propertyNames())


def load_modis_sr(
    start_date: str,
    end_date: str,
    aoi: ee.Geometry | None = None,
    collection: str = "MOD09A1",
    bands: list[str] | None = None,
    apply_scale: bool = True,
    mask_clouds: bool = True,
) -> ee.ImageCollection:
    """Load a MODIS Surface Reflectance ImageCollection from GEE.

    Args:
        start_date: ISO date string, e.g. "2023-01-01".
        end_date: ISO date string, e.g. "2024-01-01".
        aoi: Optional AOI geometry for filtering and clipping.
        collection: One of MOD09GQ, MOD09GA, MOD09A1, MOD09Q1, MYD09GQ, MYD09GA.
        bands: Reflectance bands to select. None = all bands for collection.
        apply_scale: Multiply raw int values by 0.0001.
        mask_clouds: Apply QA cloud mask.

    Returns:
        ee.ImageCollection
    """
    if collection not in _SR_COLLECTIONS:
        raise ValueError(
            f"Unknown collection '{collection}'. "
            f"Choose from: {sorted(_SR_COLLECTIONS)}"
        )

    refl_bands = bands if bands is not None else _SR_REFL_BANDS[collection]
    qa_band, cloud_bit = _SR_QA[collection]
    collection_id = _SR_COLLECTIONS[collection]["id"]
    print(f"[geets.modis.sr] Loading: {collection_id}")
    print(f"[geets.modis.sr] Date range: {start_date} -> {end_date}")

    col = (
        ee.ImageCollection(collection_id)
        .filterDate(start_date, end_date)
    )

    if aoi is not None:
        col = col.filterBounds(aoi)

    if mask_clouds:
        col = col.map(lambda img: _mask_sr_qa(img, qa_band, cloud_bit))

    col = col.select(refl_bands)

    if apply_scale:
        col = col.map(lambda img: _scale_sr(img, refl_bands))

    if aoi is not None:
        col = col.map(lambda img: img.clip(aoi))

    n = col.size().getInfo()
    if n == 0:
        print(f"[geets.modis.sr] WARNING: collection is EMPTY.")
    else:
        print(f"[geets.modis.sr] Collection ready: {n} images")

    return col
```

- [ ] **Step 4: Run tests and confirm they pass**

```
python -m pytest tests/unit/modis/test_sr.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```
git add src/geets/modis/sr.py tests/unit/modis/test_sr.py
git commit -m "feat: add MODIS Surface Reflectance loader (load_modis_sr)"
```

---

## Task 5: `fire.py` — Fire and Burned Area loader

**Files:**
- Create: `src/geets/modis/fire.py`
- Create: `tests/unit/modis/test_fire.py`

**GEE band reference:**
- MCD64A1: `BurnDate` (day-of-year, 0=unburned, -1=unmapped), `QA` (pixel QA), `FirstDay`, `LastDay`
- MOD14A1: `FireMask` (0=missing,…,5=very low confidence,…,8=high confidence fire), `MaxFRP`
- MOD14A2: `FireMask` (same scale), `MaxFRP`
- No standard cloud QA for fire products; `mask_clouds=False` by default.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/modis/test_fire.py`:

```python
def test_load_modis_fire_raises_on_invalid_collection():
    import pytest
    from geets.modis import fire

    with pytest.raises(ValueError, match="Unknown collection"):
        fire.load_modis_fire("2023-01-01", "2024-01-01", collection="MOD13Q1")


def test_load_modis_fire_filters_date():
    from unittest.mock import MagicMock, patch
    from geets.modis import fire

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 6

    with patch.object(fire.ee, "ImageCollection", return_value=mock_col):
        fire.load_modis_fire("2023-01-01", "2024-01-01")
        mock_col.filterDate.assert_called_once_with("2023-01-01", "2024-01-01")


def test_load_modis_fire_applies_aoi_filter():
    from unittest.mock import MagicMock, patch
    from geets.modis import fire

    aoi = MagicMock()
    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.filterBounds.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 6

    with patch.object(fire.ee, "ImageCollection", return_value=mock_col):
        fire.load_modis_fire("2023-01-01", "2024-01-01", aoi=aoi)
        mock_col.filterBounds.assert_called_once_with(aoi)


def test_load_modis_fire_skips_aoi_when_none():
    from unittest.mock import MagicMock, patch
    from geets.modis import fire

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 6

    with patch.object(fire.ee, "ImageCollection", return_value=mock_col):
        fire.load_modis_fire("2023-01-01", "2024-01-01")
        mock_col.filterBounds.assert_not_called()


def test_load_modis_fire_defaults_to_mcd64a1():
    from unittest.mock import MagicMock, patch
    from geets.modis import fire

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 6

    with patch.object(fire.ee, "ImageCollection", return_value=mock_col) as mock_ic:
        fire.load_modis_fire("2023-01-01", "2024-01-01")
        args = mock_ic.call_args[0]
        assert "MCD64A1" in args[0]
```

- [ ] **Step 2: Run tests to confirm they fail**

```
python -m pytest tests/unit/modis/test_fire.py -v
```

Expected: `ImportError` — `geets.modis.fire` does not exist yet.

- [ ] **Step 3: Create `src/geets/modis/fire.py`**

```python
"""MODIS Fire and Burned Area loader for Google Earth Engine.

Supported collections (product family: "fire"):
  MCD64A1  – Terra+Aqua Burned Area, 500 m, monthly
  MOD14A1  – Terra Active Fire / FRP, 1 km, daily
  MOD14A2  – Terra Active Fire / FRP, 1 km, 8-day

Fire products have no standard cloud QA; mask_clouds=False by default.
"""

from __future__ import annotations

import ee

from .sets import MODIS_SETS

_FIRE_COLLECTIONS: dict[str, dict] = {
    k: v for k, v in MODIS_SETS.items() if v["product"] == "fire"
}


def load_modis_fire(
    start_date: str,
    end_date: str,
    aoi: ee.Geometry | None = None,
    collection: str = "MCD64A1",
    mask_clouds: bool = False,
) -> ee.ImageCollection:
    """Load a MODIS Fire or Burned Area ImageCollection from GEE.

    Args:
        start_date: ISO date string, e.g. "2023-01-01".
        end_date: ISO date string, e.g. "2024-01-01".
        aoi: Optional AOI geometry for filtering and clipping.
        collection: One of MCD64A1, MOD14A1, MOD14A2.
        mask_clouds: No standard cloud QA exists for fire products;
            this flag is accepted for API consistency but does nothing.

    Returns:
        ee.ImageCollection with all native bands.
    """
    if collection not in _FIRE_COLLECTIONS:
        raise ValueError(
            f"Unknown collection '{collection}'. "
            f"Choose from: {sorted(_FIRE_COLLECTIONS)}"
        )

    collection_id = _FIRE_COLLECTIONS[collection]["id"]
    print(f"[geets.modis.fire] Loading: {collection_id}")
    print(f"[geets.modis.fire] Date range: {start_date} -> {end_date}")

    col = ee.ImageCollection(collection_id).filterDate(start_date, end_date)

    if aoi is not None:
        col = col.filterBounds(aoi)
        col = col.map(lambda img: img.clip(aoi))

    n = col.size().getInfo()
    if n == 0:
        print(f"[geets.modis.fire] WARNING: collection is EMPTY.")
    else:
        print(f"[geets.modis.fire] Collection ready: {n} images")

    return col
```

- [ ] **Step 4: Run tests and confirm they pass**

```
python -m pytest tests/unit/modis/test_fire.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```
git add src/geets/modis/fire.py tests/unit/modis/test_fire.py
git commit -m "feat: add MODIS fire/burned area loader (load_modis_fire)"
```

---

## Task 6: Wire up package exports and root `__init__.py`

**Files:**
- Modify: `src/geets/modis/__init__.py`
- Modify: `src/geets/__init__.py`

- [ ] **Step 1: Update `src/geets/modis/__init__.py`**

Replace its current content with full re-exports:

```python
from .fire import load_modis_fire
from .lst import load_modis_lst
from .sets import MODIS_SETS
from .sr import load_modis_sr
from .vi import load_modis_ndvi, load_modis_vi

__all__ = [
    "MODIS_SETS",
    "load_modis_vi",
    "load_modis_ndvi",
    "load_modis_lst",
    "load_modis_sr",
    "load_modis_fire",
]
```

- [ ] **Step 2: Update `src/geets/__init__.py`**

Replace:
```python
from .optical.modis import MODIS_COLLECTIONS, load_modis_ndvi, load_modis_vi
```

With:
```python
from .modis import (
    MODIS_SETS,
    load_modis_fire,
    load_modis_lst,
    load_modis_ndvi,
    load_modis_sr,
    load_modis_vi,
)
```

In the `__all__` list, remove `"MODIS_COLLECTIONS"` and add:
```python
"MODIS_SETS",
"load_modis_lst",
"load_modis_sr",
"load_modis_fire",
```

The final `__all__` block (MODIS-relevant entries) should be:

```python
"load_modis_vi",
"load_modis_ndvi",
"load_modis_lst",
"load_modis_sr",
"load_modis_fire",
"MODIS_SETS",
```

- [ ] **Step 3: Run the full test suite**

```
python -m pytest -v
```

Expected: all tests PASS. Verify these specific imports work:

```
python -c "from geets import MODIS_SETS, load_modis_vi, load_modis_lst, load_modis_sr, load_modis_fire; print('OK')"
python -c "from geets.modis import MODIS_SETS; print(list(MODIS_SETS)[:3])"
```

- [ ] **Step 4: Verify `optical` no longer leaks MODIS symbols**

```
python -c "from geets.optical import load_modis_vi" 2>&1 | findstr ImportError
```

Expected: `ImportError` (the symbol no longer lives there).

- [ ] **Step 5: Run linter and type-checker**

```
ruff check src/geets/modis/
ty check src/
```

Fix any reported issues before committing.

- [ ] **Step 6: Commit**

```
git add src/geets/modis/__init__.py src/geets/__init__.py
git commit -m "feat: wire geets.modis into root package, expose MODIS_SETS and all loaders"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by |
|---|---|
| `modis/` subpackage with `__init__.py`, `sets.py`, `vi.py`, `lst.py`, `sr.py`, `fire.py` | Tasks 1–6 |
| Delete `optical/modis.py` | Task 2 step 5 |
| `MODIS_SETS` keyed by short name, fields: id/product/description/start/end/resolution_m/cadence | Task 1 |
| `MODIS/06x/` namespace only, no third-party | Task 1 data |
| Higher version = preferred default (noted in sets.py docstring) | Task 1 step 3 |
| `load_modis_vi` + `load_modis_ndvi` alias | Task 2 |
| `load_modis_lst` with `time_of_day` param | Task 3 |
| `load_modis_sr` with `bands` param | Task 4 |
| `load_modis_fire` with `mask_clouds=False` default | Task 5 |
| Each loader validates collection by product family tag | Tasks 2–5 (all raise ValueError) |
| Remove `MODIS_COLLECTIONS` from root `__all__` | Task 6 |
| Add `MODIS_SETS` + 3 new loaders to root `__all__` | Task 6 |
| `optical/__init__.py` MODIS imports removed | Task 2 step 6 |

**Placeholder scan:** No TBD, TODO, or vague steps found.

**Type consistency:** `MODIS_SETS` defined in Task 1, imported as `from .sets import MODIS_SETS` in Tasks 2–5 consistently. All loaders return `ee.ImageCollection`. `load_modis_ndvi` alias signature matches `load_modis_vi`.
