# Design: S2/L8 Optical Loader (`s2l8.py`)

**Date:** 2026-05-02
**Status:** Approved

## Summary

Add `src/geets/optical/s2l8.py` for loading Sentinel-2 and Landsat-8 as individually processed `ee.ImageCollection` objects. Functions are structured as a layered pipeline — each level builds on the one below. A sensor-agnostic helper (`get_image_with_least_cc`) goes to `utils/image_utils.py`.

## New Files

```text
src/geets/
  optical/
    s2l8.py              ← main loader file
  utils/
    image_utils.py       ← get_image_with_least_cc
```

`optical/__init__.py`, `utils/__init__.py`, and `src/geets/__init__.py` are updated to re-export the new public symbols.

## GEE Collections

| Sensor | Collection ID | Cloud Property |
|--------|--------------|----------------|
| S2     | `COPERNICUS/S2_SR_HARMONIZED` | `CLOUDY_PIXEL_PERCENTAGE` |
| L8     | `LANDSAT/LC08/C02/T1_L2`      | `CLOUD_COVER` |

## Band Harmonization

Both loaders rename bands to a common scheme after scaling:

| Harmonized | S2 original | L8 original |
|------------|-------------|-------------|
| `Blue`     | B2          | SR_B2       |
| `Green`    | B3          | SR_B3       |
| `Red`      | B4          | SR_B4       |
| `NIR`      | B8          | SR_B5       |
| `SWIR1`    | B11         | SR_B6       |
| `SWIR2`    | B12         | SR_B7       |

## Pipeline Levels

```text
Level 1 — private per-image transforms (_-prefix, used in .map())
  _mask_s2_qa60(img)       QA60 bits 10+11 → mask opaque clouds + cirrus
  _mask_l8_qa_pixel(img)   QA_PIXEL bits 3+4 → mask clouds + cloud shadow
  _scale_s2(img)           optical bands ÷ 10 000  → [0, 1]
  _scale_l8(img)           SR_B* × 0.0000275 − 0.2 → [0, 1]
  _rename_s2(img)          rename to harmonized band names
  _rename_l8(img)          rename to harmonized band names

Level 2 — public per-image transform
  to_surface_reflection(img, sensor)
    Dispatches to _scale_s2 or _scale_l8 based on sensor ("S2" | "L8").
    Usable standalone or via .map() on a pre-filtered collection.

Level 3 — collection → single image  [utils/image_utils.py]
  get_image_with_least_cc(col, cloud_property)
    Sorts collection by cloud_property ascending, returns first image.
    Sensor-agnostic: works on any ImageCollection with a numeric cloud property.

Level 4 — full pipeline
  get_s2(start_date, end_date, aoi, *, bands, max_cloud_cover, mask_clouds, clip)
  get_l8(start_date, end_date, aoi, *, bands, max_cloud_cover, mask_clouds, clip)
    Both return ee.ImageCollection.
    Internal order: filterDate → filterBounds → filter(cloud_cover)
                    → map(mask) → map(scale) → map(rename)
                    → select(bands) → map(clip) → size().getInfo()
```

## Public API

```python
# utils/image_utils.py
def get_image_with_least_cc(
    collection: ee.ImageCollection,
    cloud_property: str = "CLOUDY_PIXEL_PERCENTAGE",
) -> ee.Image: ...

# optical/s2l8.py
def to_surface_reflection(img: ee.Image, sensor: str) -> ee.Image: ...

def get_s2(
    start_date: str,
    end_date: str,
    aoi: ee.Geometry | None = None,
    *,
    bands: list[str] | None = None,
    max_cloud_cover: float = 20.0,
    mask_clouds: bool = True,
    clip: bool = True,
) -> ee.ImageCollection: ...

def get_l8(
    start_date: str,
    end_date: str,
    aoi: ee.Geometry | None = None,
    *,
    bands: list[str] | None = None,
    max_cloud_cover: float = 20.0,
    mask_clouds: bool = True,
    clip: bool = True,
) -> ee.ImageCollection: ...
```

## Typical Workflow

```python
from geets import initialize_ee, get_s2, get_l8, get_image_with_least_cc
import ee

initialize_ee()
aoi = ee.Geometry.Rectangle([10.5, 47.2, 11.2, 47.8])

# Full filtered collection
col = get_s2("2022-06-01", "2022-09-01", aoi, max_cloud_cover=20)

# Single best image
img = get_image_with_least_cc(col, "CLOUDY_PIXEL_PERCENTAGE")

# Standalone scaling (e.g. on a pre-loaded image)
from geets.optical.s2l8 import to_surface_reflection
scaled = to_surface_reflection(raw_img, sensor="S2")
```

## Consistency with Existing Patterns

- Cloud masking and scaling helpers use `_`-prefix (same as `_mask_qa` in `modis.py`)
- Print log prefix: `[geets.s2l8]` and `[geets.image_utils]`
- Empty-collection warning via `size().getInfo()` at end of loader (same as `era5.py`, `modis.py`)
- `copyProperties(img, img.propertyNames())` after scaling to preserve `system:time_start`

## Out of Scope

- TOA → SR atmospheric correction
- SCL-based cloud masking (can be added later as `mask_clouds_scl` parameter)
- Landsat-9 (same band structure as L8, easy to add later as `get_l9`)
