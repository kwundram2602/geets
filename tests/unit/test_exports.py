from unittest.mock import MagicMock, patch
from pathlib import Path


def test_l_download_image_creates_outdir_and_calls_geemap(tmp_path):
    from geets.utils.exports import l_download_image

    mock_image = MagicMock()
    outdir = tmp_path / "downloads"

    with patch("geets.utils.exports.geemap.ee_export_image") as mock_export:
        result = l_download_image(mock_image, outdir, "test_img", scale=10.0, crs="EPSG:32636")

    assert outdir.exists()
    assert result == outdir / "test_img.tif"
    mock_export.assert_called_once_with(
        mock_image,
        filename=str(outdir / "test_img.tif"),
        scale=10.0,
        region=None,
        crs="EPSG:32636",
        file_per_band=False,
    )


def test_l_download_image_appends_tif_extension(tmp_path):
    from geets.utils.exports import l_download_image

    with patch("geets.utils.exports.geemap.ee_export_image"):
        result = l_download_image(MagicMock(), tmp_path, "myfile")

    assert result == tmp_path / "myfile.tif"


def test_l_download_imagecollection_names_files_by_date(tmp_path):
    from geets.utils.exports import l_download_imagecollection

    mock_img1 = MagicMock()
    mock_img1.date.return_value.format.return_value.getInfo.return_value = "20220601"
    mock_img2 = MagicMock()
    mock_img2.date.return_value.format.return_value.getInfo.return_value = "20220615"

    mock_col = MagicMock()
    mock_col.size.return_value.getInfo.return_value = 2
    mock_col.toList.return_value.get.side_effect = [mock_img1, mock_img2]

    with patch("geets.utils.exports.geemap.ee_export_image"), \
         patch("geets.utils.exports.ee.Image", side_effect=lambda x: x):
        paths = l_download_imagecollection(mock_col, tmp_path, "sentinel2")

    assert paths == [
        tmp_path / "sentinel2_20220601.tif",
        tmp_path / "sentinel2_20220615.tif",
    ]


def test_l_download_imagecollection_returns_empty_list_for_empty_collection(tmp_path):
    from geets.utils.exports import l_download_imagecollection

    mock_col = MagicMock()
    mock_col.size.return_value.getInfo.return_value = 0

    with patch("geets.utils.exports.geemap.ee_export_image"):
        paths = l_download_imagecollection(mock_col, tmp_path, "prefix")

    assert paths == []


def test_export_image_to_drive_starts_task_and_returns_it():
    from geets.utils.exports import export_image_to_drive

    mock_image = MagicMock()
    mock_task = MagicMock()

    with patch("geets.utils.exports.ee.batch.Export.image.toDrive", return_value=mock_task) as mock_drive:
        result = export_image_to_drive(
            mock_image, "my_desc", "MyFolder", "my_prefix", scale=30.0
        )

    mock_drive.assert_called_once_with(
        image=mock_image,
        description="my_desc",
        folder="MyFolder",
        fileNamePrefix="my_prefix",
        region=None,
        scale=30.0,
        crs="EPSG:4326",
        maxPixels=int(1e13),
        skipEmptyTiles=False,
    )
    mock_task.start.assert_called_once()
    assert result is mock_task


def test_export_imagecollection_to_drive_starts_one_task_per_image():
    from geets.utils.exports import export_imagecollection_to_drive

    mock_img1 = MagicMock()
    mock_img1.date.return_value.format.return_value.getInfo.return_value = "20220601"
    mock_img2 = MagicMock()
    mock_img2.date.return_value.format.return_value.getInfo.return_value = "20220615"

    mock_col = MagicMock()
    mock_col.size.return_value.getInfo.return_value = 2
    mock_col.toList.return_value.get.side_effect = [mock_img1, mock_img2]

    mock_task1, mock_task2 = MagicMock(), MagicMock()

    with patch("geets.utils.exports.ee.batch.Export.image.toDrive", side_effect=[mock_task1, mock_task2]), \
         patch("geets.utils.exports.ee.Image", side_effect=lambda x: x):
        tasks = export_imagecollection_to_drive(mock_col, "desc", "Folder", "pfx")

    assert tasks == [mock_task1, mock_task2]
    mock_task1.start.assert_called_once()
    mock_task2.start.assert_called_once()


def test_export_imagecollection_to_drive_suffixes_description_and_prefix():
    from geets.utils.exports import export_imagecollection_to_drive

    mock_img = MagicMock()
    mock_img.date.return_value.format.return_value.getInfo.return_value = "20230101"

    mock_col = MagicMock()
    mock_col.size.return_value.getInfo.return_value = 1
    mock_col.toList.return_value.get.return_value = mock_img

    mock_task = MagicMock()

    with patch("geets.utils.exports.ee.batch.Export.image.toDrive", return_value=mock_task) as mock_drive, \
         patch("geets.utils.exports.ee.Image", side_effect=lambda x: x):
        export_imagecollection_to_drive(mock_col, "my_desc", "Folder", "my_pfx")

    mock_drive.assert_called_once_with(
        image=mock_img,
        description="my_desc_20230101",
        folder="Folder",
        fileNamePrefix="my_pfx_20230101",
        region=None,
        scale=30.0,
        crs="EPSG:4326",
        maxPixels=int(1e13),
        skipEmptyTiles=False,
    )
