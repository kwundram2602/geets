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


def test_select_series_skips_empty_and_below_threshold():
    dates = ["2024-06-01", "2024-06-04", "2024-06-06", "2024-06-09"]
    fractions = [0.0, 0.05, 0.6, None]
    assert files.select_series(dates, fractions, min_valid_fraction=0.0) == [1, 2]
    assert files.select_series(dates, fractions, min_valid_fraction=0.5) == [2]


def test_series_filenames_are_unique_per_date():
    names = files.series_filenames("s2", ["2024-06-01", "2024-06-01", "2024-06-04"])
    assert names == ["s2_20240601", "s2_20240601_2", "s2_20240604"]


def test_series_filenames_add_time_only_on_days_with_several_overpasses():
    # 2026-06-11: Sentinel-2B (00:27) and Sentinel-2A (00:37) over the same AOI
    times = ["2026-06-11T00:27", "2026-06-11T00:37", "2026-06-14T00:30"]
    names = files.series_filenames("s2", times)
    assert names == ["s2_20260611T0027", "s2_20260611T0037", "s2_20260614"]


def test_series_filenames_unique_for_identical_times():
    names = files.series_filenames("s2", ["2026-06-11T00:37", "2026-06-11T00:37"])
    assert names == ["s2_20260611T0037", "s2_20260611T0037_2"]


@pytest.mark.parametrize(
    "dataset, keys",
    [
        ("s2", ["SPACECRAFT_NAME", "SENSING_ORBIT_NUMBER"]),
        ("l8l9", ["SPACECRAFT_ID", "WRS_PATH"]),
        ("l9", ["SPACECRAFT_ID", "WRS_PATH"]),
        ("modis_ndvi", []),
        ("era5:ERA5_LAND", []),
    ],
)
def test_overpass_keys_separate_satellites_and_orbits(dataset, keys):
    assert files.overpass_keys(dataset) == keys


def test_l_image_series_refuses_too_many_images(tmp_path):
    col = MagicMock()
    col.size.return_value.getInfo.return_value = 40
    with (
        patch("geets.files.ensure_initialized"),
        patch("geets.files.aoi_from_file"),
        patch("geets.files.load_collection", return_value=col),
        patch("geets.files.mosaic_per_overpass", return_value=col),
    ):
        with pytest.raises(ValueError, match="40 images.*max_images=30"):
            files.l_image_series(
                tmp_path / "a.gpkg", "2024-01-01", "2024-12-31", tmp_path / "out"
            )
