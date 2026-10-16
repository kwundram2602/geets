from unittest.mock import MagicMock, patch

import geopandas as gpd
import pytest
from shapely.geometry import box

from geets import files


def test_aoi_from_file_dissolves_and_reprojects(tmp_path):
    path = tmp_path / "aoi.gpkg"
    gpd.GeoDataFrame(
        geometry=[
            box(500000, 5600000, 501000, 5601000),
            box(501000, 5600000, 502000, 5601000),
        ],
        crs="EPSG:25832",
    ).to_file(path)
    with patch("geets.files.shapely_to_ee", side_effect=lambda g: g):
        geom = files.aoi_from_file(path)
    assert geom.geom_type == "Polygon"
    assert 8 < geom.bounds[0] < 10  # lon in degrees, UTM 32N


def test_aoi_from_file_rejects_empty(tmp_path):
    path = tmp_path / "empty.gpkg"
    gpd.GeoDataFrame(geometry=[], crs="EPSG:4326").to_file(path)
    with pytest.raises(ValueError, match="no features"):
        files.aoi_from_file(path)


def test_load_collection_unknown_dataset():
    with pytest.raises(ValueError, match="Unknown dataset"):
        files.load_collection("nope", "2024-01-01", "2024-02-01", MagicMock())


def test_composite_unknown_reducer():
    with pytest.raises(ValueError, match="Unknown reducer"):
        files.composite(MagicMock(), "mode")


def test_composite_empty_collection():
    col = MagicMock()
    col.size.return_value.getInfo.return_value = 0
    with pytest.raises(ValueError, match="No images"):
        files.composite(col, "median")


def test_download_checked_raises_when_geemap_wrote_nothing(tmp_path):
    with patch("geets.files.l_download_image", return_value=tmp_path / "x.tif"):
        with pytest.raises(RuntimeError, match="32 MB"):
            files.download_checked(MagicMock(), tmp_path / "x.tif", MagicMock(), 30)


def test_l_dem_unknown_source(tmp_path):
    with pytest.raises(ValueError, match="Unknown DEM source"):
        files.l_dem(tmp_path / "a.gpkg", tmp_path / "d.tif", source="nope")


def test_aoi_from_file_rejects_point_aoi(tmp_path):
    from shapely.geometry import Point

    path = tmp_path / "point.gpkg"
    gpd.GeoDataFrame(geometry=[Point(149.0, -3.1)], crs="EPSG:4326").to_file(path)
    with pytest.raises(ValueError, match="polygon"):
        files.aoi_from_file(path)


def test_require_valid_pixels_raises_when_aoi_has_no_data():
    image = MagicMock()
    counts = image.select.return_value.reduceRegion.return_value.values.return_value
    counts.getInfo.return_value = [0]
    with patch("geets.files.ee.Reducer.count"):
        with pytest.raises(ValueError, match="No valid pixels.*over water"):
            files.require_valid_pixels(image, MagicMock(), 250, "modis_ndvi")


def test_require_valid_pixels_passes_with_data():
    image = MagicMock()
    counts = image.select.return_value.reduceRegion.return_value.values.return_value
    counts.getInfo.return_value = [42]
    with patch("geets.files.ee.Reducer.count"):
        files.require_valid_pixels(image, MagicMock(), 250, "modis_ndvi")
