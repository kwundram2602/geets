"""DEM collection metadata and loaders for Google Earth Engine."""

from __future__ import annotations

from typing import Literal

DemProduct = Literal["elevation", "slope", "aspect", "hillshade"]

DEM_COLLECTIONS: dict[str, str] = {
    "GLO30":   "COPERNICUS/DEM/GLO30",
    "SRTM":    "USGS/SRTMGL1_003",
    "ASTER":   "NASA/ASTER_GED/AG100_003",
    "NASADEM": "NASA/NASADEM_HGT/001",
}
