from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from geets import drive, files

FOLDER_URI = "https://drive.google.com/#folders/abc123"
TASK = {
    "id": "T1",
    "state": "COMPLETED",
    "description": "s2_20260101T000000",
    "creation_timestamp_ms": 1_767_225_600_000,  # 2026-01-01T00:00:00Z
    "destination_uris": [FOLDER_URI],
}


def _service(files_pages):
    service = MagicMock()
    service.files.return_value.list.return_value.execute.side_effect = files_pages
    return service


def test_export_name_replaces_invalid_characters():
    assert drive.export_name("my file/ä?.tif") == "my_file_ä_.tif"
    assert len(drive.export_name("x" * 200)) == 99


def test_export_tasks_newest_first_with_drive_flag():
    tasks = [
        {"id": "a", "state": "COMPLETED", "creation_timestamp_ms": 1000},
        {
            "id": "b",
            "state": "RUNNING",
            "creation_timestamp_ms": 2000,
            "destination_uris": [FOLDER_URI],
        },
    ]
    with (
        patch("geets.drive.ensure_initialized"),
        patch("geets.drive.ee.data.getTaskList", return_value=tasks),
    ):
        result = drive.export_tasks()
    assert [t["id"] for t in result] == ["b", "a"]
    assert result[0]["to_drive"] and not result[1]["to_drive"]
    assert result[0]["created"] == "1970-01-01T00:00:02+00:00"


def test_wait_for_task_returns_on_completed():
    states = [{"state": "READY"}, {"state": "RUNNING"}, {"state": "COMPLETED"}]
    with (
        patch("geets.drive.task_status", side_effect=states),
        patch("geets.drive.time.sleep") as sleep,
    ):
        assert drive.wait_for_task("T1", poll=5)["state"] == "COMPLETED"
    assert sleep.call_count == 2


@pytest.mark.parametrize("state", ["FAILED", "CANCELLED", "UNKNOWN"])
def test_wait_for_task_raises_on_failure(state):
    status = {"state": state, "error_message": "boom"}
    with patch("geets.drive.task_status", return_value=status):
        with pytest.raises(RuntimeError, match=state):
            drive.wait_for_task("T1")


def test_drive_files_for_task_filters_names_and_keeps_newest():
    page1 = {
        "files": [
            {
                "id": "old",
                "name": "s2_20260101T000000.tif",
                "createdTime": "2026-01-01",
            },
            {
                "id": "other",
                "name": "s2_20260101T000000_x.tif",
                "createdTime": "2026-01-02",
            },
        ],
        "nextPageToken": "p2",
    }
    page2 = {
        "files": [
            {
                "id": "new",
                "name": "s2_20260101T000000.tif",
                "createdTime": "2026-01-03",
            },
        ]
    }
    service = _service([page1, page2])
    with patch("geets.drive.drive_service", return_value=service):
        found = drive.drive_files_for_task(TASK)
    assert [f["id"] for f in found] == ["new"]
    query = service.files.return_value.list.call_args_list[0].kwargs["q"]
    assert "'abc123' in parents" in query
    assert "createdTime >= '2026-01-01T00:00:00'" in query


def test_drive_files_for_task_matches_tiles():
    tiles = [
        {"id": "t2", "name": "s2_20260101T000000-0000000000-0000000256.tif"},
        {"id": "t1", "name": "s2_20260101T000000-0000000000-0000000000.tif"},
    ]
    for t in tiles:
        t["createdTime"] = "2026-01-02"
    with patch("geets.drive.drive_service", return_value=_service([{"files": tiles}])):
        found = drive.drive_files_for_task(TASK)
    assert [f["id"] for f in found] == ["t1", "t2"]


def test_drive_files_for_task_without_drive_destination():
    with pytest.raises(ValueError, match="no Google Drive destination"):
        drive.drive_files_for_task({**TASK, "destination_uris": []})


def test_l_download_drive_file_streams_to_path(tmp_path):
    class FakeDownloader:
        def __init__(self, fh, request, chunksize):
            self.fh = fh
            self.chunks = [b"ab", b"cd"]

        def next_chunk(self):
            self.fh.write(self.chunks.pop(0))
            return MagicMock(progress=lambda: 0.5), not self.chunks

    with (
        patch("geets.drive.drive_service"),
        patch("geets.drive.MediaIoBaseDownload", FakeDownloader),
    ):
        out = drive.l_download_drive_file("F1", tmp_path / "sub" / "x.tif")
    assert out.read_bytes() == b"abcd"
    assert not (tmp_path / "sub" / "x.tif.part").exists()


def _write_tile(path, data, left, top, res=10.0):
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=data.shape[2],
        height=data.shape[1],
        count=data.shape[0],
        dtype="float32",
        crs="EPSG:32632",
        transform=from_origin(left, top, res, res),
        nodata=-9999.0,
    ) as dst:
        dst.write(data)


def test_merge_tiles_places_tiles_by_georeference(tmp_path):
    # 2 x 2 grid of tiles, 4 x 3 px each, 2 bands; the bottom-right tile is narrower
    tiles = []
    for row, col, width in [(0, 0, 4), (0, 1, 2), (1, 0, 4), (1, 1, 2)]:
        data = np.full((2, 3, width), row * 10 + col, dtype="float32")
        data[1] += 100
        path = tmp_path / f"t-{row}-{col}.tif"
        _write_tile(path, data, 500000 + col * 40, 5600000 - row * 30)
        tiles.append(path)
    out = drive.merge_tiles(list(reversed(tiles)), tmp_path / "merged.tif")
    with rasterio.open(out) as src:
        assert (src.width, src.height, src.count) == (6, 6, 2)
        assert src.transform.c == 500000 and src.transform.f == 5600000
        assert src.nodata == -9999.0
        merged = src.read()
    assert merged[0, 0, 0] == 0 and merged[0, 0, 5] == 1
    assert merged[0, 5, 0] == 10 and merged[0, 5, 5] == 11
    assert merged[1, 5, 5] == 111


def test_l_pull_export_single_file(tmp_path):
    files_found = [{"id": "F1", "name": "s2_20260101T000000.tif"}]
    with (
        patch("geets.drive.task_status", return_value=TASK),
        patch("geets.drive.drive_files_for_task", return_value=files_found),
        patch("geets.drive.l_download_drive_file", side_effect=lambda i, p: p) as dl,
    ):
        out = drive.l_pull_export("T1", tmp_path, name="composite")
    assert out == tmp_path / "composite.tif"
    dl.assert_called_once_with("F1", tmp_path / "composite.tif")


def test_l_pull_export_merges_tiles_and_removes_them(tmp_path):
    names = ["s2-0000000000-0000000000.tif", "s2-0000000000-0000000004.tif"]

    def download(file_id, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        col = int(file_id)
        _write_tile(
            path, np.full((1, 2, 4), col, "float32"), 500000 + col * 40, 5600000
        )
        return path

    with (
        patch("geets.drive.task_status", return_value=TASK),
        patch(
            "geets.drive.drive_files_for_task",
            return_value=[{"id": str(i), "name": n} for i, n in enumerate(names)],
        ),
        patch("geets.drive.l_download_drive_file", side_effect=download),
    ):
        out = drive.l_pull_export("T1", tmp_path, name="big")
    assert out == tmp_path / "big.tif"
    assert not (tmp_path / "big_tiles").exists()
    with rasterio.open(out) as src:
        assert (src.width, src.height) == (8, 2)


def test_l_pull_export_rejects_unfinished_task(tmp_path):
    with patch("geets.drive.task_status", return_value={**TASK, "state": "RUNNING"}):
        with pytest.raises(RuntimeError, match="not COMPLETED"):
            drive.l_pull_export("T1", tmp_path)


def test_l_export_and_pull_uses_one_prefix_and_output_stem(tmp_path):
    task = MagicMock(id="T9")
    with (
        patch("geets.drive.export_image_to_drive", return_value=task) as export,
        patch("geets.drive.wait_for_task") as wait,
        patch("geets.drive.l_pull_export", return_value="done") as pull,
    ):
        result = drive.l_export_and_pull(
            "img", tmp_path / "OUTPUT.tif", "aoi", 20.0, folder="exports"
        )
    assert result == "done"
    args = export.call_args.args
    assert args[0] == "img" and args[2] == "exports"
    assert args[1] == args[3] and args[1].startswith("OUTPUT_")
    wait.assert_called_once_with("T9", poll=30)
    pull.assert_called_once_with("T9", tmp_path, name="OUTPUT")


def test_deliver_downloads_directly_by_default(tmp_path):
    with patch("geets.files.download_checked", return_value="local") as download:
        assert files.deliver("img", tmp_path / "x.tif", "aoi", 30) == "local"
    download.assert_called_once()


def test_deliver_via_drive(tmp_path):
    image = MagicMock()
    with patch("geets.files.l_export_and_pull", return_value="pulled") as pull:
        result = files.deliver(
            image, tmp_path / "x.tif", "aoi", 30, via_drive=True, drive_folder="f"
        )
    assert result == "pulled"
    pull.assert_called_once_with(
        image.toFloat.return_value,
        tmp_path / "x.tif",
        "aoi",
        30,
        "EPSG:4326",
        folder="f",
    )
