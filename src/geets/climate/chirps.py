"""
CHIRPS daily precipitation loaders for Google Earth Engine.

Supported collections:
  CHIRPS_V2  -> UCSB-CHG/CHIRPS/DAILY
               Classic CHIRPS 2.0, ~5.5 km (0.05°), 1981–present
  CHIRPS_V3  -> UCSB-CHC/CHIRPS/V3/DAILY_RNL
               CHIRPS 3.0 Reanalysis (ERA5-based), ~5.5 km (0.05°), 1983–present

Both expose a single band: ``precipitation`` (mm / day).
Coverage: 50°S – 50°N.
"""

from __future__ import annotations

import ee

CHIRPS_COLLECTIONS: dict[str, dict[str, str]] = {
    "CHIRPS_V2": {
        "id":      "UCSB-CHG/CHIRPS/DAILY",
        "band":    "precipitation",
        "cadence": "daily",
        "note":    "CHIRPS 2.0 Final, 1981-present",
    },
    "CHIRPS_V3": {
        "id":      "UCSB-CHC/CHIRPS/V3/DAILY_RNL",
        "band":    "precipitation",
        "cadence": "daily",
        "note":    "CHIRPS 3.0 Reanalysis (ERA5-based), 1983-present",
    },
}

# Kept for backwards compatibility
CHIRPS_COLLECTION_ID = CHIRPS_COLLECTIONS["CHIRPS_V2"]["id"]
CHIRPS_BAND          = "precipitation"


def load_chirps_daily(
    start_date: str,
    end_date:   str,
    aoi:        ee.Geometry | None = None,
    dataset:    str  = "CHIRPS_V2",
    clip:       bool = True,
) -> ee.ImageCollection:
    """
    Load CHIRPS daily precipitation from GEE.

    Parameters
    ----------
    start_date : ISO date string, e.g. ``"2019-01-01"``
    end_date   : ISO date string, e.g. ``"2023-01-01"``
    aoi        : Optional AOI for bounds filtering and clipping.
    dataset    : ``"CHIRPS_V2"`` (default) or ``"CHIRPS_V3"``
    clip       : Clip each image to AOI when AOI is given.

    Returns
    -------
    ee.ImageCollection
        Single-band collection (``"precipitation"``, mm/day).
    """
    if dataset not in CHIRPS_COLLECTIONS:
        raise ValueError(
            f"Unknown CHIRPS dataset '{dataset}'. "
            f"Choose from: {list(CHIRPS_COLLECTIONS)}"
        )

    meta = CHIRPS_COLLECTIONS[dataset]
    print(f"[geets.chirps] Loading collection: {meta['id']}  ({meta['note']})")
    print(f"[geets.chirps] Date range: {start_date} -> {end_date}")

    col = (
        ee.ImageCollection(meta["id"])
        .filterDate(start_date, end_date)
        .select([meta["band"]])
    )

    if aoi is not None:
        print("[geets.chirps] Applying AOI filter")
        col = col.filterBounds(aoi)

    if aoi is not None and clip:
        print("[geets.chirps] Clipping to AOI")
        col = col.map(lambda img: img.clip(aoi))

    n = col.size().getInfo()
    if n == 0:
        print(f"[geets.chirps] WARNING: collection is EMPTY (0 images).")
        print(f"[geets.chirps]   -> Check date range ({start_date} – {end_date})")
        print(f"[geets.chirps]      and that the AOI overlaps 50°S–50°N coverage.")
    else:
        print(f"[geets.chirps] Collection ready: {n} images")

    return col
