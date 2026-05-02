# Terrain Module Design

**Date:** 2026-05-03
**Status:** Approved

## Overview

Add a `terrain/` subpackage to `geets` that loads static DEM/DSM images from four GEE sources and optionally computes derived terrain products (slope, aspect, hillshade) server-side. Output bands are always renamed to harmonized names regardless of source.

## Supported Sources

| Public function | GEE Collection ID | Native elev band | Resolution |
|---|---|---|---|
| `load_copernicus_dem` | `COPERNICUS/DEM/GLO30` | `"DEM"` | 30 m |
| `load_srtm` | `USGS/SRTMGL1_003` | `"elevation"` | 30 m |
| `load_aster` | `NASA/ASTER_GED/AG100_003` | `"b1"` | 30 m |
| `load_nasadem` | `NASA/NASADEM_HGT/001` | `"elevation"` | 30 m |

## File Layout

```
src/geets/terrain/
    __init__.py   # re-exports all public symbols
    dem.py        # all DEM logic
```

## Public API

```python
DEM_COLLECTIONS: dict[str, str]   # source name → GEE collection ID
DemProduct = Literal["elevation", "slope", "aspect", "hillshade"]

load_copernicus_dem(aoi, *, products, clip) -> ee.Image
load_srtm(aoi, *, products, clip) -> ee.Image
load_aster(aoi, *, products, clip) -> ee.Image
load_nasadem(aoi, *, products, clip) -> ee.Image
```

All four share the same signature and are added to the root `geets/__init__.py`.

## Shared Signature

```python
def load_<source>(
    aoi: ee.Geometry | None = None,
    *,
    products: list[DemProduct] | None = None,  # default: ["elevation"]
    clip: bool = True,
) -> ee.Image:
```

## Private Helper

```python
def _load_dem(
    collection_id: str,
    elev_band: str,
    aoi: ee.Geometry | None,
    clip: bool,
    products: list[DemProduct],
) -> ee.Image:
```

All four public loaders delegate to `_load_dem` with their specific `collection_id` and `elev_band`.

## Behavior

1. Load the DEM image from GEE (`ee.ImageCollection(...).mosaic()` for tiled sources like GLO-30; `.first()` for single-image sources)
2. Rename the elevation band to `"elevation"`
3. If any of `["slope", "aspect", "hillshade"]` are in `products`: compute `ee.Terrain.products(img)` server-side (adds all four bands), then select only the requested subset
4. If `aoi` is provided: clip to AOI when `clip=True`
5. Print a `[geets.terrain]` progress line

## Band Naming

| Product | Output band name | Source |
|---|---|---|
| Elevation | `"elevation"` | renamed from source-specific band |
| Slope | `"slope"` | from `ee.Terrain.products` |
| Aspect | `"aspect"` | from `ee.Terrain.products` |
| Hillshade | `"hillshade"` | from `ee.Terrain.products` |

## Error Handling

- Invalid value in `products` → `ValueError` raised immediately, before any GEE call
- `aoi=None` with `clip=True` → clipping silently skipped (consistent with optical loaders)
- No empty-collection guard needed (DEMs are global, always present)

## Testing

File: `tests/unit/terrain/test_dem.py`

- All tests mock `ee` — no real GEE round-trips
- Each public loader passes correct `collection_id` and `elev_band` to `_load_dem`
- `products=["slope", "hillshade"]` triggers `ee.Terrain.products` and selects correct bands
- `products=["invalid"]` raises `ValueError`
- `clip=True` with `aoi=None` does not raise
