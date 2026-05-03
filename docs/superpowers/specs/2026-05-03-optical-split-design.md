# Optical Module Split: sentinel2 + landsat

**Date:** 2026-05-03
**Status:** Approved

## Goal

Split `optical/s2l8.py` into two focused sensor modules (`sentinel2.py`, `landsat.py`) with shared constants/utilities in `optical/common.py`. Mirrors the pattern used in `modis/`.

## File Structure

```
src/geets/optical/
  common.py       ← _BANDS_HARMONIZED, to_surface_reflection
  sentinel2.py    ← S2 constants, private helpers, get_s2
  landsat.py      ← L8 constants, private helpers, get_l8
  __init__.py     ← re-exports: get_s2, get_l8, to_surface_reflection
  s2l8.py         ← deleted
```

## Module Responsibilities

### `common.py`

- `_BANDS_HARMONIZED`: shared harmonized band name list `["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2"]`
- `to_surface_reflection(img, sensor)`: applies scale inline (no imports from sensor modules — avoids circular import). S2: `× 1e-4`; L8: `× 2.75e-5 − 0.2`. Raises `ValueError` for unknown sensor.

`sentinel2.py` and `landsat.py` each import `_BANDS_HARMONIZED` from `common.py`; `common.py` does not import from them.

### `sentinel2.py`

Extracted from `s2l8.py` — no behaviour changes:

- Constants: `_S2_COLLECTION_ID`, `_S2_CLOUD_PROPERTY`, `_S2_BANDS_SRC`, `_S2_SCALE`
- Private helpers: `_mask_s2_qa60`, `_scale_s2`, `_rename_s2`
- Public loader: `get_s2`
- Log prefix updated: `[geets.s2l8]` → `[geets.sentinel2]`

### `landsat.py`

Extracted from `s2l8.py` — no behaviour changes:

- Constants: `_L8_COLLECTION_ID`, `_L8_CLOUD_PROPERTY`, `_L8_BANDS_SRC`, `_L8_SCALE`, `_L8_OFFSET`
- Private helpers: `_mask_l8_qa_pixel`, `_scale_l8`, `_rename_l8`
- Public loader: `get_l8`
- Log prefix updated: `[geets.s2l8]` → `[geets.landsat]`
- Landsat 9 support deferred to a future iteration

### `optical/__init__.py`

```python
from .common import to_surface_reflection
from .sentinel2 import get_s2
from .landsat import get_l8
```

### Root `geets/__init__.py`

Import line updated from:
```python
from .optical.s2l8 import get_l8, get_s2, to_surface_reflection
```
to:
```python
from .optical import get_l8, get_s2, to_surface_reflection
```

## Public API

No changes. `get_s2`, `get_l8`, `to_surface_reflection` remain importable from `geets` directly.

## Out of Scope

- Landsat 9 (`LC09`) support
- Any behaviour changes to existing loaders
