from geets.terrain import dem


def test_dem_collections_has_four_sources():
    assert set(dem.DEM_COLLECTIONS.keys()) == {"GLO30", "SRTM", "ASTER", "NASADEM"}


def test_dem_collections_glo30():
    assert dem.DEM_COLLECTIONS["GLO30"] == "COPERNICUS/DEM/GLO30"


def test_dem_collections_srtm():
    assert dem.DEM_COLLECTIONS["SRTM"] == "USGS/SRTMGL1_003"


def test_dem_collections_aster():
    assert dem.DEM_COLLECTIONS["ASTER"] == "NASA/ASTER_GED/AG100_003"


def test_dem_collections_nasadem():
    assert dem.DEM_COLLECTIONS["NASADEM"] == "NASA/NASADEM_HGT/001"
