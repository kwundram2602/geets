"""Pull finished Earth Engine Drive exports into a local folder via the Drive API.

Direct downloads (``l_download_image``) stop at ~32 MB per request. Larger images go
through ``Export.image.toDrive``; once that task is done, the functions here find its
files on Drive and download them. No mount and no second login: the Earth Engine
credentials already carry the Drive scope (``ee.oauth.SCOPES``).

Large exports are split by Earth Engine into tiles named
``<prefix>-<row offset>-<col offset>.tif``; those are merged locally into one GeoTIFF.
"""

from __future__ import annotations

import re
import shutil
import time
import warnings
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import ee
import rasterio
from affine import Affine
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from rasterio.windows import Window

from .config import ensure_initialized
from .utils.exports import export_image_to_drive

CHUNK = 64 * 1024 * 1024
_FOLDER_URI = re.compile(r"folders/([\w-]+)")
_INVALID_DESCRIPTION = re.compile(r"[^\w.,:;-]")


def drive_service():
    """Drive v3 client authorized with the stored Earth Engine credentials."""
    credentials = ee.data.get_persistent_credentials()
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def drive_status() -> dict:
    """Check that the Drive API is reachable with the Earth Engine credentials."""
    try:
        about = drive_service().about().get(fields="user(emailAddress)").execute()
    except Exception as exc:  # noqa: BLE001 - reported to the caller as text
        return {"ok": False, "message": str(exc)}
    return {"ok": True, "message": f"Drive access as {about['user']['emailAddress']}."}


def export_name(name: str) -> str:
    """``name`` reduced to what Earth Engine accepts as a task description."""
    return _INVALID_DESCRIPTION.sub("_", name)[:99]


def task_status(task_id: str) -> dict:
    """Legacy task dict (``id``, ``state``, ``destination_uris``, ...) of one task."""
    ensure_initialized()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return ee.data.getTaskStatus(task_id)[0]


def _summary(task: dict) -> dict:
    uris = task.get("destination_uris") or []
    created = task.get("creation_timestamp_ms")
    return {
        "id": task["id"],
        "description": task.get("description", ""),
        "type": task.get("task_type", ""),
        "state": task.get("state", ""),
        "created": (
            datetime.fromtimestamp(created / 1000, UTC).isoformat(timespec="seconds")
            if created
            else ""
        ),
        "destination_uris": uris,
        "to_drive": any(_FOLDER_URI.search(u) for u in uris),
        "error_message": task.get("error_message", ""),
    }


def export_tasks(limit: int = 50) -> list[dict]:
    """Recent Earth Engine tasks of the current project, newest first (JSON-able)."""
    ensure_initialized()
    tasks = ee.data.getTaskList()
    tasks.sort(key=lambda t: t.get("creation_timestamp_ms", 0), reverse=True)
    return [_summary(t) for t in tasks[:limit]]


def wait_for_task(task_id: str, poll: float = 30, timeout: float | None = None) -> dict:
    """Poll a task until it is done; raise unless it COMPLETED."""
    start = time.monotonic()
    last = None
    while True:
        task = task_status(task_id)
        state = task.get("state")
        if state != last:
            print(f"[geets.drive] task {task_id}: {state}", flush=True)
            last = state
        if state == "COMPLETED":
            return task
        if state in ("FAILED", "CANCELLED", "UNKNOWN"):
            raise RuntimeError(
                f"Earth Engine task {task_id} {state}: {task.get('error_message', '')}"
            )
        if timeout is not None and time.monotonic() - start > timeout:
            raise TimeoutError(
                f"Earth Engine task {task_id} still {state} after {timeout:.0f} s; "
                "pull it later with l_pull_export."
            )
        time.sleep(poll)


def _part_pattern(prefix: str) -> re.Pattern:
    return re.compile(rf"^{re.escape(prefix)}(-\d+-\d+)?\.tif$")


def drive_files_for_task(task: dict | str, prefix: str | None = None) -> list[dict]:
    """Drive files (``id``, ``name``, ``size``) a finished image export wrote.

    The folder comes from the task's destination URI; the file name prefix defaults
    to the task description (geets' own exports use the same string for both).
    Files older than the task are ignored, and for duplicate names the newest wins.
    """
    if isinstance(task, str):
        task = task_status(task)
    folders = [
        m.group(1)
        for u in task.get("destination_uris") or []
        if (m := _FOLDER_URI.search(u))
    ]
    if not folders:
        raise ValueError(
            f"Task {task['id']} has no Google Drive destination "
            f"(state {task.get('state')}, URIs {task.get('destination_uris')})."
        )
    prefix = prefix or task.get("description", "")
    created = task.get("creation_timestamp_ms", 0)
    since = datetime.fromtimestamp(created / 1000, UTC).strftime("%Y-%m-%dT%H:%M:%S")
    query = (
        f"'{folders[0]}' in parents and name contains '{prefix.replace(chr(39), '')}'"
        f" and trashed = false and createdTime >= '{since}'"
    )
    service = drive_service()
    found, token = [], None
    while True:
        response = (
            service.files()
            .list(
                q=query,
                fields="nextPageToken, files(id, name, size, createdTime)",
                pageToken=token,
            )
            .execute()
        )
        found += response.get("files", [])
        token = response.get("nextPageToken")
        if not token:
            break
    pattern = _part_pattern(prefix)
    newest: dict[str, dict] = {}
    for f in sorted(found, key=lambda f: f["createdTime"]):
        if pattern.match(f["name"]):
            newest[f["name"]] = f
    return [newest[name] for name in sorted(newest)]


def l_download_drive_file(file_id: str, output_path: str | Path) -> Path:
    """Stream one Drive file to ``output_path`` in chunks (no full copy in memory)."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_name(out.name + ".part")
    request = drive_service().files().get_media(fileId=file_id)
    with part.open("wb") as fh:
        downloader = MediaIoBaseDownload(fh, request, chunksize=CHUNK)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"[geets.drive] {out.name}: {status.progress():.0%}", flush=True)
    part.replace(out)
    return out


def merge_tiles(paths: Sequence[str | Path], output_path: str | Path) -> Path:
    """Merge north-up tiles of one export into a single GeoTIFF, block by block.

    The tiles share CRS, resolution, bands and dtype (Earth Engine splits one image),
    so no resampling is needed and memory use stays at one block per read.
    """
    out = Path(output_path)
    tiles = []
    for path in paths:
        with rasterio.open(path) as src:
            tiles.append((Path(path), src.transform, src.width, src.height))
            profile = src.profile
    res_x, res_y = tiles[0][1].a, tiles[0][1].e
    left = min(t.c for _, t, _, _ in tiles)
    top = max(t.f for _, t, _, _ in tiles)
    width = max(round((t.c - left) / res_x) + w for _, t, w, _ in tiles)
    height = max(round((t.f - top) / res_y) + h for _, t, _, h in tiles)
    profile.update(
        driver="GTiff",
        width=width,
        height=height,
        transform=Affine(res_x, 0.0, left, 0.0, res_y, top),
        tiled=True,
        blockxsize=512,
        blockysize=512,
        compress="deflate",
        BIGTIFF="IF_SAFER",
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_name(out.name + ".part")
    with rasterio.open(part, "w", **profile) as dst:
        for path, t, _, _ in tiles:
            x_off = round((t.c - left) / res_x)
            y_off = round((t.f - top) / res_y)
            with rasterio.open(path) as src:
                for _, window in src.block_windows(1):
                    row = window.row_off + y_off
                    col = window.col_off + x_off
                    target = Window.from_slices(
                        (row, row + window.height), (col, col + window.width)
                    )
                    dst.write(src.read(window=window), window=target)
    part.replace(out)
    return out


def l_pull_export(
    task_id: str,
    output_dir: str | Path,
    *,
    name: str | None = None,
    wait: bool = False,
    poll: float = 30,
) -> Path:
    """Download a finished Drive image export into ``output_dir``.

    Args:
        task_id: Earth Engine task id (see ``export_tasks``).
        output_dir: Local folder (created if missing), e.g. inside the QGIS project.
        name: Local file stem; default is the export's file name prefix.
        wait: Wait for a running task instead of failing.
        poll: Seconds between status checks while waiting.

    Returns:
        ``<output_dir>/<name>.tif``. Tiled exports are merged into that one file and
        the downloaded tiles are removed.
    """
    task = wait_for_task(task_id, poll=poll) if wait else task_status(task_id)
    if task.get("state") != "COMPLETED":
        raise RuntimeError(
            f"Earth Engine task {task_id} is {task.get('state')}, not COMPLETED yet."
        )
    prefix = task.get("description", "")
    files = drive_files_for_task(task, prefix)
    if not files:
        raise FileNotFoundError(
            f"No files named '{prefix}*.tif' from task {task_id} found on Google Drive "
            "(moved, renamed or deleted?)."
        )
    out = Path(output_dir) / f"{name or prefix}.tif"
    if len(files) == 1:
        return l_download_drive_file(files[0]["id"], out)
    tile_dir = out.with_name(f"{out.stem}_tiles")
    paths = [l_download_drive_file(f["id"], tile_dir / f["name"]) for f in files]
    print(f"[geets.drive] merging {len(paths)} tiles into {out.name}", flush=True)
    merge_tiles(paths, out)
    shutil.rmtree(tile_dir)
    return out


def l_export_and_pull_many(
    items: Sequence[tuple[ee.Image, str | Path]],
    region: ee.Geometry,
    scale: float,
    crs: str = "EPSG:4326",
    *,
    folder: str = "geets",
    poll: float = 30,
) -> list[Path]:
    """Export several images to Drive at once, then pull each as soon as it is done.

    ``items`` are ``(image, output_path)`` pairs. All export tasks are started first,
    so Earth Engine works on them in parallel. A failed task does not stop the
    others; after all are done a ``RuntimeError`` lists the failed ones. Drive files
    are named ``<output stem>_<UTC timestamp>``, which keeps repeated exports (e.g.
    QGIS temporary outputs, all called ``OUTPUT``) distinguishable there. If the
    caller is interrupted while waiting, the tasks keep running on Earth Engine and
    can be pulled later with ``l_pull_export`` (their ids are printed).
    """
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    pending: dict[str, tuple[int, Path]] = {}
    for i, (image, output_path) in enumerate(items):
        out = Path(output_path)
        prefix = f"{export_name(out.stem)[:80]}_{stamp}"
        task = export_image_to_drive(
            image, prefix, folder, prefix, region=region, scale=scale, crs=crs
        )
        if not task.id:
            raise RuntimeError("Earth Engine did not return a task id for the export.")
        pending[task.id] = (i, out)
        print(
            f"[geets.drive] export task {task.id} started for {out.name} "
            f"(Drive folder '{folder}')",
            flush=True,
        )
    print(
        "[geets.drive] if interrupted, pull finished tasks later with l_pull_export.",
        flush=True,
    )
    results: list[Path | None] = [None] * len(items)
    failed: list[str] = []
    while True:
        for task_id in list(pending):
            task = task_status(task_id)
            state = task.get("state")
            if state == "COMPLETED":
                i, out = pending.pop(task_id)
                results[i] = l_pull_export(task_id, out.parent, name=out.stem)
                done = len(items) - len(pending)
                print(f"[geets.drive] {done}/{len(items)} done: {out.name}", flush=True)
            elif state in ("FAILED", "CANCELLED", "UNKNOWN"):
                _, out = pending.pop(task_id)
                failed.append(
                    f"{out.name} (task {task_id} {state}: "
                    f"{task.get('error_message', '')})"
                )
        if not pending:
            break
        time.sleep(poll)
    if failed:
        raise RuntimeError(
            f"{len(failed)} of {len(items)} Drive exports failed: " + "; ".join(failed)
        )
    return [p for p in results if p is not None]


def l_export_and_pull(
    image: ee.Image,
    output_path: str | Path,
    region: ee.Geometry,
    scale: float,
    crs: str = "EPSG:4326",
    *,
    folder: str = "geets",
    poll: float = 30,
) -> Path:
    """Export one image to Drive, wait for it and download it to ``output_path``.

    See ``l_export_and_pull_many`` for naming and interruption.
    """
    return l_export_and_pull_many(
        [(image, output_path)], region, scale, crs, folder=folder, poll=poll
    )[0]
