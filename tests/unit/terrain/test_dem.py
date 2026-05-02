def test_dem_collections_has_four_sources():
    from geets.terrain import dem

    assert set(dem.DEM_COLLECTIONS.keys()) == {"GLO30", "SRTM", "ASTER", "NASADEM"}


def test_dem_collections_glo30():
    from geets.terrain import dem

    assert dem.DEM_COLLECTIONS["GLO30"] == "COPERNICUS/DEM/GLO30"


def test_dem_collections_srtm():
    from geets.terrain import dem

    assert dem.DEM_COLLECTIONS["SRTM"] == "USGS/SRTMGL1_003"


def test_dem_collections_aster():
    from geets.terrain import dem

    assert dem.DEM_COLLECTIONS["ASTER"] == "NASA/ASTER_GED/AG100_003"


def test_dem_collections_nasadem():
    from geets.terrain import dem

    assert dem.DEM_COLLECTIONS["NASADEM"] == "NASA/NASADEM_HGT/001"


def test_load_dem_raises_on_invalid_product():
    import pytest

    from geets.terrain import dem

    with pytest.raises(ValueError, match="Unknown product"):
        dem._load_dem(
            "COPERNICUS/DEM/GLO30", "DEM", True, None, True, ["invalid"]
        )


def test_load_dem_uses_mosaic_for_tiled():
    from unittest.mock import MagicMock, patch

    from geets.terrain import dem

    mock_col = MagicMock()
    mock_img = MagicMock()
    mock_col.mosaic.return_value = mock_img
    mock_img.select.return_value = mock_img
    mock_img.rename.return_value = mock_img

    with patch.object(dem.ee, "ImageCollection", return_value=mock_col):
        dem._load_dem(
            "COPERNICUS/DEM/GLO30", "DEM", True, None, True, ["elevation"]
        )
        mock_col.mosaic.assert_called_once()
        mock_col.first.assert_not_called()


def test_load_dem_uses_first_for_non_tiled():
    from unittest.mock import MagicMock, patch

    from geets.terrain import dem

    mock_col = MagicMock()
    mock_img = MagicMock()
    mock_col.first.return_value = mock_img
    mock_img.select.return_value = mock_img
    mock_img.rename.return_value = mock_img

    with patch.object(dem.ee, "ImageCollection", return_value=mock_col):
        dem._load_dem(
            "USGS/SRTMGL1_003", "elevation", False, None, True, ["elevation"]
        )
        mock_col.first.assert_called_once()
        mock_col.mosaic.assert_not_called()


def test_load_dem_calls_terrain_products_for_slope():
    from unittest.mock import MagicMock, patch

    from geets.terrain import dem

    mock_col = MagicMock()
    mock_img = MagicMock()
    mock_col.first.return_value = mock_img
    mock_img.select.return_value = mock_img
    mock_img.rename.return_value = mock_img
    mock_terrain_img = MagicMock()
    mock_terrain_img.select.return_value = mock_terrain_img

    with patch.object(
        dem.ee, "ImageCollection", return_value=mock_col
    ), patch.object(
        dem.ee.Terrain, "products", return_value=mock_terrain_img
    ) as mock_terrain:
        dem._load_dem(
            "USGS/SRTMGL1_003",
            "elevation",
            False,
            None,
            True,
            ["elevation", "slope"],
        )
        mock_terrain.assert_called_once()


def test_load_dem_skips_terrain_products_for_elevation_only():
    from unittest.mock import MagicMock, patch

    from geets.terrain import dem

    mock_col = MagicMock()
    mock_img = MagicMock()
    mock_col.first.return_value = mock_img
    mock_img.select.return_value = mock_img
    mock_img.rename.return_value = mock_img

    with patch.object(
        dem.ee, "ImageCollection", return_value=mock_col
    ), patch.object(dem.ee.Terrain, "products") as mock_terrain:
        dem._load_dem(
            "USGS/SRTMGL1_003", "elevation", False, None, True, ["elevation"]
        )
        mock_terrain.assert_not_called()


def test_load_dem_clips_when_aoi_provided():
    from unittest.mock import MagicMock, patch

    from geets.terrain import dem

    aoi = MagicMock()
    mock_col = MagicMock()
    mock_img = MagicMock()
    mock_col.filterBounds.return_value = mock_col
    mock_col.first.return_value = mock_img
    mock_img.select.return_value = mock_img
    mock_img.rename.return_value = mock_img
    mock_img.clip.return_value = mock_img

    with patch.object(dem.ee, "ImageCollection", return_value=mock_col):
        dem._load_dem(
            "USGS/SRTMGL1_003", "elevation", False, aoi, True, ["elevation"]
        )
        mock_img.clip.assert_called_once_with(aoi)


def test_load_dem_no_clip_when_aoi_none():
    from unittest.mock import MagicMock, patch

    from geets.terrain import dem

    mock_col = MagicMock()
    mock_img = MagicMock()
    mock_col.first.return_value = mock_img
    mock_img.select.return_value = mock_img
    mock_img.rename.return_value = mock_img

    with patch.object(dem.ee, "ImageCollection", return_value=mock_col):
        dem._load_dem(
            "USGS/SRTMGL1_003", "elevation", False, None, True, ["elevation"]
        )
        mock_img.clip.assert_not_called()


def test_load_dem_no_clip_when_clip_false():
    from unittest.mock import MagicMock, patch

    from geets.terrain import dem

    aoi = MagicMock()
    mock_col = MagicMock()
    mock_img = MagicMock()
    mock_col.filterBounds.return_value = mock_col
    mock_col.first.return_value = mock_img
    mock_img.select.return_value = mock_img
    mock_img.rename.return_value = mock_img

    with patch.object(dem.ee, "ImageCollection", return_value=mock_col):
        dem._load_dem(
            "USGS/SRTMGL1_003", "elevation", False, aoi, False, ["elevation"]
        )
        mock_img.clip.assert_not_called()
