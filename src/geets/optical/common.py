"""Shared constants and cross-sensor utilities for optical loaders."""
from __future__ import annotations

import ee

_BANDS_HARMONIZED = ["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2"]

_S2_BANDS_SRC = ["B2",    "B3",    "B4",    "B8",    "B11",   "B12"  ]
_S2_SCALE     = 1e-4

_L8_BANDS_SRC = ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"]
_L8_BANDS_ALL = _L8_BANDS_SRC + ["QA_PIXEL", "ST_B10"]
_L8_SCALE     = 2.75e-5
_L8_OFFSET    = -0.2


def to_surface_reflection(img: ee.Image, sensor: str) -> ee.Image:
    """Scale a single image to physical surface reflectance [0, 1].

    Parameters
    ----------
    img    : ee.Image with original DN bands for the given sensor.
    sensor : "S2" scales by ÷ 10 000; "L8" scales by × 0.0000275 − 0.2.

    Raises
    ------
    ValueError for unknown sensor strings.
    """
    if sensor == "S2":
        scaled = img.select(_S2_BANDS_SRC).multiply(_S2_SCALE)
        return scaled.copyProperties(img, img.propertyNames())
    if sensor == "L8":
        scaled = img.select(_L8_BANDS_SRC).multiply(_L8_SCALE).add(_L8_OFFSET)
        return scaled.copyProperties(img, img.propertyNames())
    raise ValueError(f"Unknown sensor '{sensor}'. Choose 'S2' or 'L8'.")
