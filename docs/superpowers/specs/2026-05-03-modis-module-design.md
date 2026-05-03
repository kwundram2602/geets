# MODIS Module Design

**Date:** 2026-05-03
**Status:** Approved

## Overview

Promote MODIS from `optical/modis.py` into a dedicated top-level `geets/modis/` subpackage. Add loaders for Land Surface Temperature (LST), Surface Reflectance (SR), and Fire/Burned Area alongside the existing Vegetation Index (VI) loader. Introduce a `MODIS_SETS` Python dict covering all supported collections with human-readable metadata.

## File Layout

```
src/geets/modis/
  __init__.py     # re-exports all public symbols
  sets.py         # MODIS_SETS — metadata for every collection
  vi.py           # load_modis_vi, load_modis_ndvi (moved from optical/modis.py)
  lst.py          # load_modis_lst
  sr.py           # load_modis_sr
  fire.py         # load_modis_fire
```

Deleted: `src/geets/optical/modis.py`

## MODIS_SETS (`sets.py`)

A single `MODIS_SETS: dict[str, dict]` keyed by the GEE short name. Covers all official MODIS collections under the `MODIS/061/` or `MODIS/062/` namespace — no third-party alternatives (e.g. JRC GlobFire is excluded). Where both 061 and 062 exist for the same product, both are included; 062 is the preferred default.

Each entry shape:

```python
{
    "id":           str,   # GEE collection path, e.g. "MODIS/061/MOD13Q1"
    "product":      str,   # family tag: "vi" | "lst" | "sr" | "fire"
    "description":  str,   # human-readable one-liner
    "start":        str,   # ISO date, e.g. "2000-02-18"
    "end":          str,   # ISO date or "present"
    "resolution_m": int,   # native spatial resolution in metres
    "cadence":      str,   # e.g. "daily", "8-day", "16-day", "monthly"
}
```

Band names, scale factors, and QA band identifiers are **not** stored in `MODIS_SETS` — they live inside the relevant loader module as private constants. `MODIS_SETS` is a human-facing reference, not internal wiring.

### Collections included

The table below lists the 061 baseline. During implementation, check GEE for each product whether a `MODIS/062/` equivalent exists; if it does, add a second entry with key suffix `_062` (e.g. `"MOD13Q1_062"`) and mark it as the preferred default in the loader.

| Key | GEE ID | Family | Resolution | Cadence |
|-----|--------|--------|-----------|---------|
| MOD13Q1 | MODIS/061/MOD13Q1 | vi | 250 m | 16-day |
| MOD13A1 | MODIS/061/MOD13A1 | vi | 500 m | 16-day |
| MOD13A3 | MODIS/061/MOD13A3 | vi | 1 km | monthly |
| MYD13Q1 | MODIS/061/MYD13Q1 | vi | 250 m | 16-day |
| MOD11A1 | MODIS/061/MOD11A1 | lst | 1 km | daily |
| MOD11A2 | MODIS/061/MOD11A2 | lst | 1 km | 8-day |
| MYD11A1 | MODIS/061/MYD11A1 | lst | 1 km | daily |
| MYD11A2 | MODIS/061/MYD11A2 | lst | 1 km | 8-day |
| MOD09GQ | MODIS/061/MOD09GQ | sr | 250 m | daily |
| MOD09GA | MODIS/061/MOD09GA | sr | 500 m | daily |
| MOD09A1 | MODIS/061/MOD09A1 | sr | 500 m | 8-day |
| MOD09Q1 | MODIS/061/MOD09Q1 | sr | 250 m | 8-day |
| MYD09GQ | MODIS/061/MYD09GQ | sr | 250 m | daily |
| MYD09GA | MODIS/061/MYD09GA | sr | 500 m | daily |
| MCD64A1 | MODIS/061/MCD64A1 | fire | 500 m | monthly |
| MOD14A1 | MODIS/061/MOD14A1 | fire | 1 km | daily |
| MOD14A2 | MODIS/061/MOD14A2 | fire | 1 km | 8-day |

## Public API

All functions are exported from `geets.modis` and re-exported from the root `geets` package.

```python
# vi.py
def load_modis_vi(
    start_date: str,
    end_date: str,
    aoi: ee.Geometry | None = None,
    collection: str = "MOD13Q1",
    band: str = "NDVI",           # "NDVI", "EVI", or None (keep both)
    apply_scale: bool = True,
    mask_clouds: bool = True,
    max_qa: int = 1,
) -> ee.ImageCollection

def load_modis_ndvi(...)           # backward-compat alias for load_modis_vi

# lst.py
def load_modis_lst(
    start_date: str,
    end_date: str,
    aoi: ee.Geometry | None = None,
    collection: str = "MOD11A2",
    time_of_day: str = "day",     # "day" | "night"
    apply_scale: bool = True,
    mask_clouds: bool = True,
) -> ee.ImageCollection

# sr.py
def load_modis_sr(
    start_date: str,
    end_date: str,
    aoi: ee.Geometry | None = None,
    collection: str = "MOD09A1",
    bands: list[str] | None = None,  # None = all bands
    apply_scale: bool = True,
    mask_clouds: bool = True,
) -> ee.ImageCollection

# fire.py
def load_modis_fire(
    start_date: str,
    end_date: str,
    aoi: ee.Geometry | None = None,
    collection: str = "MCD64A1",
    mask_clouds: bool = False,
) -> ee.ImageCollection
```

Each loader validates `collection` against the collections it supports (by product family tag in `MODIS_SETS`), raises `ValueError` on unknown keys.

Internal `_load_*` helpers handle QA masking and scaling per file — helpers are **not** shared across product families because QA flag schemes differ significantly between VI (`SummaryQA`), LST (`QC_Day`/`QC_Night` bitmasks), SR (`StateQA` bitmask), and Fire (no standard pixel QA).

## Root Package Changes

```python
# geets/__init__.py — remove:
from .optical.modis import MODIS_COLLECTIONS, load_modis_ndvi, load_modis_vi

# geets/__init__.py — add:
from .modis import (
    MODIS_SETS,
    load_modis_vi,
    load_modis_ndvi,
    load_modis_lst,
    load_modis_sr,
    load_modis_fire,
)
```

`MODIS_COLLECTIONS` removed from `__all__`; `MODIS_SETS` and the three new loaders added.

`optical/__init__.py`: MODIS imports removed; `get_s2`, `get_l8`, `to_surface_reflection` unchanged.

## What Does Not Change

- All other modules (`climate/`, `terrain/`, `radar/`, `timeseries/`, `utils/`) are untouched.
- `load_modis_ndvi` is kept as an alias — existing call sites continue to work.
- The `l_*` naming convention and GEE lazy-evaluation pattern are unchanged.
