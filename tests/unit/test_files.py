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


def test_l_region_timeseries_csv_reduces_one_mosaic_per_overpass(tmp_path):
    import pandas as pd

    col = MagicMock()
    df = pd.DataFrame({"NIR_mean": [0.1]}, index=pd.Index(["2026-06-11"], name="date"))
    with (
        patch("geets.files.ensure_initialized"),
        patch("geets.files.aoi_from_file", return_value="aoi"),
        patch("geets.files.load_collection", return_value=col),
        patch("geets.files.native_scale", return_value=10.0),
        patch("geets.files.mosaic_per_overpass", return_value="mosaics") as mosaic,
        patch("geets.files.reduce_region_stats", return_value=df) as reduce,
    ):
        files.l_region_timeseries_csv(
            tmp_path / "a.gpkg",
            "2026-06-01",
            "2026-07-01",
            tmp_path / "s.csv",
            dataset="s2",
            band="NIR",
        )
    mosaic.assert_called_once_with(col, ["SPACECRAFT_NAME", "SENSING_ORBIT_NUMBER"])
    assert reduce.call_args.args[:3] == ("mosaics", "aoi", "NIR")
    assert reduce.call_args.kwargs["date_format"] == "YYYY-MM-dd'T'HH:mm"
    assert reduce.call_args.kwargs["scale"] == 10


def test_composite_least_cloudy_needs_aoi():
    col = MagicMock()
    col.size.return_value.getInfo.return_value = 3
    with pytest.raises(ValueError, match="AOI"):
        files.composite(col, "least_cloudy", "s2")


def test_composite_least_cloudy_picks_overpass_with_most_valid_aoi_share():
    col = MagicMock()
    col.size.return_value.getInfo.return_value = 3
    ranked = MagicMock()
    with (
        patch("geets.files.mosaic_per_overpass") as mosaic,
        patch("geets.files.with_valid_fraction", return_value=ranked) as valid,
        patch("geets.files.ee.Image", side_effect=lambda x: x),
    ):
        result = files.composite(col, "least_cloudy", "l8l9", aoi="aoi")
    mosaic.assert_called_once_with(col, ["SPACECRAFT_ID", "WRS_PATH"])
    assert valid.call_args.args[1] == "aoi"
    ranked.sort.assert_called_once_with("valid_fraction", False)
    assert result is ranked.sort.return_value.first.return_value


def test_l_image_series_via_drive_exports_all_kept_images(tmp_path):
    series = MagicMock()
    series.size.return_value.getInfo.return_value = 3
    agg = series.aggregate_array.return_value
    agg.map.return_value.getInfo.return_value = [
        "2026-06-09T00:37",
        "2026-06-11T00:27",
        "2026-06-11T00:37",
    ]
    agg.getInfo.return_value = [0.9, 0.0, 0.4]
    imgs = [MagicMock(name=f"img{i}") for i in range(3)]
    series.toList.return_value.get.side_effect = lambda i: imgs[i]
    with (
        patch("geets.files.ensure_initialized"),
        patch("geets.files.aoi_from_file", return_value="aoi"),
        patch("geets.files.load_collection"),
        patch("geets.files.mosaic_per_overpass", return_value=series),
        patch("geets.files.with_valid_fraction", return_value=series),
        patch("geets.files.native_scale", return_value=10.0),
        patch("geets.files.ee.Image", side_effect=lambda x: x),
        patch("geets.files.download_checked") as download,
        patch("geets.files.l_export_and_pull_many", return_value=["p0", "p2"]) as many,
    ):
        paths = files.l_image_series(
            tmp_path / "a.gpkg",
            "2026-06-01",
            "2026-07-01",
            tmp_path / "out",
            via_drive=True,
            drive_folder="f",
        )
    assert paths == ["p0", "p2"]
    download.assert_not_called()
    items = many.call_args.args[0]
    # one dtype for all bands, as for direct downloads (Drive exports require it)
    assert [i[0] for i in items] == [
        imgs[0].toFloat.return_value,
        imgs[2].toFloat.return_value,
    ]
    assert [i[1].name for i in items] == ["s2_20260609.tif", "s2_20260611T0037.tif"]
    assert many.call_args.kwargs == {"folder": "f"}
