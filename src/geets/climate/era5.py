"""
ERA5 daily climate data loaders for Google Earth Engine.

Supported collections:
  ERA5       -> ECMWF/ERA5/DAILY
  ERA5_LAND  -> ECMWF/ERA5_LAND/DAILY_AGGR
"""

from __future__ import annotations

import ee


ERA5_COLLECTIONS: dict[str, dict[str, str]] = {
    "ERA5": {
        "id": "ECMWF/ERA5/DAILY",
        "cadence": "daily",
    },
    "ERA5_LAND": {
        "id": "ECMWF/ERA5_LAND/DAILY_AGGR",
        "cadence": "daily",
    },
}

# All band names in ERA5 / ERA5-Land that are in Kelvin
_KELVIN_BANDS: frozenset[str] = frozenset({
    "temperature_2m",
    "dewpoint_temperature_2m",
    "skin_temperature",
    "soil_temperature_level_1",
    "soil_temperature_level_2",
    "soil_temperature_level_3",
    "soil_temperature_level_4",
    "lake_bottom_temperature",
    "lake_mix_layer_temperature",
    "lake_surface_water_temperature",
    "sea_surface_temperature",
})

_KELVIN_OFFSET = 273.15


def load_era5_daily(
    start_date: str,
    end_date: str,
    aoi: ee.Geometry | None = None,
    dataset: str = "ERA5_LAND",
    bands: str | list[str] | None = None,
    clip: bool = True,
    kelvin_to_celsius: bool = True,
) -> ee.ImageCollection:
    """
    Load ERA5 or ERA5-LAND daily data from GEE.

    Parameters
    ----------
    start_date : str
        ISO date string, e.g. "2023-01-01".
    end_date : str
        ISO date string, e.g. "2023-12-31".
    aoi : ee.Geometry | None
        Optional AOI for bounds filtering and clipping.
    dataset : str
        One of "ERA5" or "ERA5_LAND".
    bands : str | list[str] | None
        Optional band or list of bands to keep.
    clip : bool
        Clip each image to AOI when AOI is given.
    kelvin_to_celsius : bool
        Convert temperature bands from Kelvin to °C (subtract 273.15).
        Default True. Only affects bands listed in ``_KELVIN_BANDS``.
    """
    if dataset not in ERA5_COLLECTIONS:
        raise ValueError(
            f"Unknown ERA5 dataset '{dataset}'. Choose from: {list(ERA5_COLLECTIONS)}"
        )

    collection_id = ERA5_COLLECTIONS[dataset]["id"]
    print(f"[geets.era5] Loading collection: {collection_id}")
    print(f"[geets.era5] Date range: {start_date} -> {end_date}")

    if bands is None:
        selected_bands = "ALL"
    elif isinstance(bands, str):
        selected_bands = [bands]
    else:
        selected_bands = list(bands)
    print(f"[geets.era5] Band selection: {selected_bands}")

    col = ee.ImageCollection(collection_id).filterDate(start_date, end_date)

    if aoi is not None:
        print("[geets.era5] Applying AOI filter")
        col = col.filterBounds(aoi)

    if bands is not None:
        if isinstance(bands, str):
            col = col.select([bands])
        else:
            col = col.select(bands)

    # K → °C conversion for temperature bands
    if kelvin_to_celsius:
        temp_bands = (
            [b for b in selected_bands if b in _KELVIN_BANDS]
            if selected_bands != "ALL"
            else list(_KELVIN_BANDS)   # when all bands are loaded
        )
        if temp_bands:
            print(f"[geets.era5] Converting K → °C for: {temp_bands}")
            col = col.map(
                lambda img: img.addBands(
                    img.select(temp_bands).subtract(_KELVIN_OFFSET),
                    overwrite=True,
                )
            )

    if aoi is not None and clip:
        print("[geets.era5] Clipping to AOI")
        col = col.map(lambda img: img.clip(aoi))

    # Client-side size check – triggers one API call but saves confusion later
    n = col.size().getInfo()
    if n == 0:
        print(f"[geets.era5] WARNING: collection is EMPTY (0 images).")
        print(f"[geets.era5]   -> Check date range ({start_date} – {end_date}),")
        print(f"[geets.era5]      band names, and whether '{collection_id}' is available in GEE.")
    else:
        print(f"[geets.era5] Collection ready: {n} images")

    return col
