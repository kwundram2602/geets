"""MODIS collection metadata for Google Earth Engine.

Keys follow the GEE short product name (e.g. "MOD13Q1").
Where multiple Collection versions exist for the same product
(e.g. 061 and 062), each version has its own entry using the
convention "<PRODUCT>.<VERSION>" for non-baseline entries
(e.g. "MOD13Q1.062"). Loaders default to the highest-numbered
version available in GEE.

Only official MODIS collections (MODIS/06x/ namespace) are included.
"""

MODIS_SETS: dict[str, dict] = {
    # ------------------------------------------------------------------ VI
    "MOD13Q1": {
        "id": "MODIS/061/MOD13Q1",
        "product": "vi",
        "description": "Terra Vegetation Indices (NDVI/EVI), 250 m, 16-day composite",
        "start": "2000-02-18",
        "end": "present",
        "resolution_m": 250,
        "cadence": "16-day",
    },
    "MOD13A1": {
        "id": "MODIS/061/MOD13A1",
        "product": "vi",
        "description": "Terra Vegetation Indices (NDVI/EVI), 500 m, 16-day composite",
        "start": "2000-02-18",
        "end": "present",
        "resolution_m": 500,
        "cadence": "16-day",
    },
    "MOD13A3": {
        "id": "MODIS/061/MOD13A3",
        "product": "vi",
        "description": "Terra Vegetation Indices (NDVI/EVI), 1 km, monthly composite",
        "start": "2000-03-01",
        "end": "present",
        "resolution_m": 1000,
        "cadence": "monthly",
    },
    "MYD13Q1": {
        "id": "MODIS/061/MYD13Q1",
        "product": "vi",
        "description": "Aqua Vegetation Indices (NDVI/EVI), 250 m, 16-day composite",
        "start": "2002-07-04",
        "end": "present",
        "resolution_m": 250,
        "cadence": "16-day",
    },
    # ------------------------------------------------------------------ LST
    "MOD11A1": {
        "id": "MODIS/061/MOD11A1",
        "product": "lst",
        "description": "Terra Land Surface Temperature and Emissivity, 1 km, daily",
        "start": "2000-03-05",
        "end": "present",
        "resolution_m": 1000,
        "cadence": "daily",
    },
    "MOD11A2": {
        "id": "MODIS/061/MOD11A2",
        "product": "lst",
        "description": "Terra Land Surface Temperature and Emissivity, 1 km, 8-day composite",
        "start": "2000-03-05",
        "end": "present",
        "resolution_m": 1000,
        "cadence": "8-day",
    },
    "MYD11A1": {
        "id": "MODIS/061/MYD11A1",
        "product": "lst",
        "description": "Aqua Land Surface Temperature and Emissivity, 1 km, daily",
        "start": "2002-07-04",
        "end": "present",
        "resolution_m": 1000,
        "cadence": "daily",
    },
    "MYD11A2": {
        "id": "MODIS/061/MYD11A2",
        "product": "lst",
        "description": "Aqua Land Surface Temperature and Emissivity, 1 km, 8-day composite",
        "start": "2002-07-04",
        "end": "present",
        "resolution_m": 1000,
        "cadence": "8-day",
    },
    # ------------------------------------------------------------------ SR
    "MOD09GQ": {
        "id": "MODIS/061/MOD09GQ",
        "product": "sr",
        "description": "Terra Surface Reflectance, 250 m, daily (bands 1-2)",
        "start": "2000-02-24",
        "end": "present",
        "resolution_m": 250,
        "cadence": "daily",
    },
    "MOD09GA": {
        "id": "MODIS/061/MOD09GA",
        "product": "sr",
        "description": "Terra Surface Reflectance, 500 m, daily (bands 1-7 + state)",
        "start": "2000-02-24",
        "end": "present",
        "resolution_m": 500,
        "cadence": "daily",
    },
    "MOD09A1": {
        "id": "MODIS/061/MOD09A1",
        "product": "sr",
        "description": "Terra Surface Reflectance, 500 m, 8-day composite (bands 1-7)",
        "start": "2000-02-18",
        "end": "present",
        "resolution_m": 500,
        "cadence": "8-day",
    },
    "MOD09Q1": {
        "id": "MODIS/061/MOD09Q1",
        "product": "sr",
        "description": "Terra Surface Reflectance, 250 m, 8-day composite (bands 1-2)",
        "start": "2000-02-18",
        "end": "present",
        "resolution_m": 250,
        "cadence": "8-day",
    },
    "MYD09GQ": {
        "id": "MODIS/061/MYD09GQ",
        "product": "sr",
        "description": "Aqua Surface Reflectance, 250 m, daily (bands 1-2)",
        "start": "2002-07-04",
        "end": "present",
        "resolution_m": 250,
        "cadence": "daily",
    },
    "MYD09GA": {
        "id": "MODIS/061/MYD09GA",
        "product": "sr",
        "description": "Aqua Surface Reflectance, 500 m, daily (bands 1-7 + state)",
        "start": "2002-07-04",
        "end": "present",
        "resolution_m": 500,
        "cadence": "daily",
    },
    # ------------------------------------------------------------------ Fire
    "MCD64A1": {
        "id": "MODIS/061/MCD64A1",
        "product": "fire",
        "description": "Terra+Aqua Burned Area, 500 m, monthly",
        "start": "2000-11-01",
        "end": "present",
        "resolution_m": 500,
        "cadence": "monthly",
    },
    "MOD14A1": {
        "id": "MODIS/061/MOD14A1",
        "product": "fire",
        "description": "Terra Thermal Anomalies and Fire, 1 km, daily",
        "start": "2000-02-24",
        "end": "present",
        "resolution_m": 1000,
        "cadence": "daily",
    },
    "MOD14A2": {
        "id": "MODIS/061/MOD14A2",
        "product": "fire",
        "description": "Terra Thermal Anomalies and Fire, 1 km, 8-day composite",
        "start": "2000-02-24",
        "end": "present",
        "resolution_m": 1000,
        "cadence": "8-day",
    },
}
