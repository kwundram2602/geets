# geets

Google Earth Engine Tools for Earth Science.

A thin Python layer over `earthengine-api` that wraps the recurring steps:
load collections, mask, scale and harmonize band names; aggregate over time;
reduce over regions; export as CSV, plot or GeoTIFF.

Every loader returns an `ee.ImageCollection` or `ee.Image` — evaluation stays
lazy and server-side.

## Installation

```bash
uv add geets          # or: uv pip install -e .
```

Requires Python ≥ 3.13 and an Earth Engine project.

```python
import geets

geets.authenticate_and_initialize_ee(project="my-ee-project")
```

## Layout

| Module | Contents |
|---|---|
| `geets.optical` | Sentinel-2, Landsat 8/9 — cloud masking, scaling, band harmonization |
| `geets.modis` | MODIS VI, LST, surface reflectance, fire — QA masking and scaling |
| `geets.climate` | ERA5 / ERA5-Land, CHIRPS |
| `geets.terrain` | DEM products |
| `geets.timeseries` | Temporal aggregation, region statistics, CSV export, plots |
| `geets.utils` | EE init, image helpers, local downloads / Drive exports, output directory |
| `geets.pairs` | Find and export image pairs from two collections by spatial overlap |

The full public API is also importable directly from `geets.*`.

## Currently supported

**Optical** — `get_s2`, `get_l8`, `get_l9`, `get_l8l9`, `to_surface_reflection`

- Sentinel-2 `COPERNICUS/S2_SR_HARMONIZED`: QA60 or s2cloudless cloud and
  shadow masking, optional water masking (SCL or MNDWI), scaling to
  reflectance [0, 1], harmonized band names.
- Landsat 8/9 Collection 2 Level 2 (`LC08/LC09 C02/T1_L2`): QA_PIXEL masking
  (cloud, shadow, cirrus, dilated, snow, water, …), optional scaling;
  `get_l8l9` returns the merged collection with `SPACECRAFT_ID` preserved.

**MODIS** — `load_modis_vi`, `load_modis_ndvi`, `load_modis_lst`, `load_modis_sr`,
`load_modis_fire`; product catalogue in `MODIS_SETS`

- VI: MOD13Q1, MOD13A1, MOD13A3, MYD13Q1
- LST: MOD11A1, MOD11A2, MYD11A1, MYD11A2
- SR: MOD09GQ, MOD09GA, MOD09A1, MOD09Q1, MYD09GQ, MYD09GA
- Fire: MCD64A1, MOD14A1, MOD14A2

**Climate** — `load_era5_daily` (ERA5, ERA5-Land), `load_chirps_daily`
(CHIRPS v2 and v3, daily precipitation)

**Terrain** — `load_copernicus_dem` (GLO-30), `load_srtm`, `load_aster`,
`load_nasadem`, `load_fabdem`

**Time series**

- `aggregate_temporal`, with the shorthands `aggregate_weekly`,
  `aggregate_monthly`, `aggregate_yearly`
- `reduce_region_stats` for per-image, per-region statistics
- `l_export_csv`, `l_load_band_csvs`, `l_aggregate_csv`
- `l_plot_timeseries`, `l_plot_boxplot`, `l_plot_combined`, `l_stack_plots`

**Export** — `l_download_image`, `l_download_imagecollection` (local),
`export_image_to_drive`, `export_imagecollection_to_drive`

**Image pairs** — `find_pairs`, `export_pairs`, `ImagePair`

**Configuration & authentication** — `config_path`, `load_config`, `save_config`,
`init_from_config`, `authenticate_from_config`, `ee_status`

- Per-device settings in `~/.config/geets/.env` (override: `GEETS_ENV_FILE`), e.g.
  `EE_PROJECT=<cloud project id>`; written with mode 600, outside every repo.
- `authenticate_from_config()` runs the browser login (localhost redirect) and checks
  the connection; `ee_status()` reports config, stored token and a live round trip.

**File-based API** (AOI vector file in, GeoTIFF/CSV out; initializes EE from the .env)

- `l_composite` — temporal composite (median/mean/min/max/sum/least_cloudy) of
  Sentinel-2, Landsat 8/9, MODIS NDVI/EVI/LST, ERA5 / ERA5-Land or CHIRPS
- `l_image_series` — one GeoTIFF per date (optionally one mosaic per day), skipping
  images whose valid pixels cover too little of the AOI; refuses more than
  `max_images` downloads
- `l_dem` — DEM plus optional slope/aspect/hillshade (Copernicus, SRTM, ASTER,
  NASADEM, FABDEM)
- `l_region_timeseries_csv` — per-image region statistics of one band as CSV
- Masking is configurable per dataset (`MASK_OPTIONS`): Sentinel-2 QA60
  (+cirrus), s2cloudless with all thresholds, any SCL classes (`scl_classes`);
  Landsat QA_PIXEL flags
  by name (`qa_bits`) and saturation; MODIS VI `max_qa`, LST QC mask. Options
  that do not apply to a dataset raise instead of being ignored.
- Downloads are checked: a request over the ~32 MB limit raises instead of
  returning a missing file.

Radar (Sentinel-1 GRD) is currently not included.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check src tests
uv run ty check src
```
