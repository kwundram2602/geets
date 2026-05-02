from __future__ import annotations

from typing import Literal

import ee

DemProduct = Literal["elevation", "slope", "aspect", "hillshade"]

_VALID_PRODUCTS: frozenset[str] = frozenset({"elevation", "slope", "aspect", "hillshade"})

DEM_COLLECTIONS: dict[str, str] = {
    "GLO30":   "COPERNICUS/DEM/GLO30",
    "SRTM":    "USGS/SRTMGL1_003",
    "ASTER":   "NASA/ASTER_GED/AG100_003",
    "NASADEM": "NASA/NASADEM_HGT/001",
}
