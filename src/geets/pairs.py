"""
pairs – Find and export spatially overlapping image pairs from two GEE collections.

Typical workflow::

    pairs = find_pairs(
        "LANDSAT/LC08/C02/T1_L2",
        "COPERNICUS/S2_SR_HARMONIZED",
        start_date="2022-06-01",
        end_date="2022-09-01",
        aoi=ee.Geometry.Rectangle([10.5, 47.2, 11.2, 47.8]),
        max_cloud_cover=20,
        min_overlap=0.7,
        bands_a=["SR_B4", "SR_B3", "SR_B2"],
        bands_b=["B4", "B3", "B2"],
        max_time_delta_days=3,
        cloud_property_a="CLOUD_COVER",
        cloud_property_b="CLOUDY_PIXEL_PERCENTAGE",
    )

    export_pairs(pairs, "export", name_a="Landsat8", name_b="S2",
                 scale_a=30, scale_b=10, aoi=aoi)
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, TypedDict

import ee
import geemap
from shapely.geometry import shape as _shape


# ── Types ─────────────────────────────────────────────────────────────────


class ImagePair(TypedDict):
    """One matched pair of GEE images with acquisition metadata."""

    image_a: ee.Image
    image_b: ee.Image
    date_a: str          # "YYYY-MM-DD"
    date_b: str
    overlap_ratio: float  # intersection / min(area_a, area_b)


# ── Internal helpers ───────────────────────────────────────────────────────


def _load_and_filter(
    collection: str | ee.ImageCollection,
    start_date: str,
    end_date: str,
    aoi: ee.Geometry,
    bands: list[str] | None,
    cloud_property: str | None,
    max_cloud: float,
) -> ee.ImageCollection:
    col = ee.ImageCollection(collection) if isinstance(collection, str) else collection
    col = col.filterDate(start_date, end_date).filterBounds(aoi)
    if cloud_property is not None:
        col = col.filter(ee.Filter.lte(cloud_property, max_cloud))
    if bands:
        col = col.select(bands)
    return col


def _get_image_metadata(col: ee.ImageCollection) -> list[dict[str, Any]]:
    """Fetch image IDs, dates, and footprints from GEE in one round-trip.

    Converts the ImageCollection to a lightweight FeatureCollection that carries
    only the timestamp and asset ID as properties plus a simplified footprint
    geometry (~1 km precision).  This avoids serialising all image band data and
    the full set of metadata properties, which would be extremely slow for large
    Sentinel-2 or Landsat collections.
    """
    n = col.size().getInfo()
    if n == 0:
        return []
    print(f"[geets.pairs]   → {n} images after filtering, fetching footprints …")

    def _to_feature(img: ee.Image) -> ee.Feature:
        return ee.Feature(
            img.geometry().simplify(maxError=1000),  # ~1 km, sufficient for overlap check
            {
                "_ts": img.date().millis(),
                "_id": img.get("system:id"),
            },
        )

    info = ee.FeatureCollection(col.map(_to_feature)).getInfo()
    results: list[dict[str, Any]] = []
    for feat in info.get("features", []):
        props = feat.get("properties", {})
        ts_ms = props.get("_ts")
        img_id = props.get("_id")
        if ts_ms is None or img_id is None:
            continue
        results.append({
            "id": img_id,
            "date": datetime.utcfromtimestamp(ts_ms / 1000),
            "geometry": feat.get("geometry"),
        })
    return results


def _overlap(
    geom_a: dict,
    geom_b: dict,
    aoi_geom: dict | None,
) -> float:
    """Return intersection / min(area_a, area_b).  Both polygons are clipped to the
    AOI first so only the region of interest is considered."""
    poly_a = _shape(geom_a)
    poly_b = _shape(geom_b)
    if aoi_geom is not None:
        aoi = _shape(aoi_geom)
        poly_a = poly_a.intersection(aoi)
        poly_b = poly_b.intersection(aoi)
    inter = poly_a.intersection(poly_b)
    min_area = min(poly_a.area, poly_b.area)
    return inter.area / min_area if min_area > 0 else 0.0


# ── Public API ─────────────────────────────────────────────────────────────


def find_pairs(
    collection_a: str | ee.ImageCollection,
    collection_b: str | ee.ImageCollection,
    start_date: str,
    end_date: str,
    aoi: ee.Geometry,
    *,
    max_cloud_cover: float = 20.0,
    min_overlap: float = 0.5,
    bands_a: list[str] | None = None,
    bands_b: list[str] | None = None,
    max_time_delta_days: int = 5,
    cloud_property_a: str | None = "CLOUD_COVER",
    cloud_property_b: str | None = "CLOUDY_PIXEL_PERCENTAGE",
) -> list[ImagePair]:
    """Find pairs of images from two GEE collections with sufficient spatial overlap.

    Both collections are filtered by date range, AOI, and cloud cover before
    matching.  A pair is accepted when:

    * The acquisition dates differ by at most *max_time_delta_days*, **and**
    * The spatial overlap ratio ``intersection / min(area_a, area_b) ≥ min_overlap``
      (computed within the AOI).

    Parameters
    ----------
    collection_a, collection_b:
        GEE asset ID string **or** a pre-processed ``ee.ImageCollection``
        (e.g. with cloud masking and scaling already applied).
        Date / bounds / cloud filters are always applied on top.
    start_date, end_date:
        ISO date strings ``"YYYY-MM-DD"``.  Interval is half-open ``[a, b)``.
    aoi:
        Area of interest – used for spatial filtering **and** overlap computation.
    max_cloud_cover:
        Maximum cloud cover in percent (default ``20``).
    min_overlap:
        Minimum overlap ratio in ``[0, 1]`` (default ``0.5``).
    bands_a, bands_b:
        Optional band selection applied to each collection.
    max_time_delta_days:
        Maximum allowed days between the two acquisition dates (default ``5``).
    cloud_property_a, cloud_property_b:
        GEE image property for cloud cover.  Pass ``None`` to skip cloud
        filtering for that collection (e.g. for SAR data).

    Returns
    -------
    list[ImagePair]
        Matched pairs sorted by *date_a*.
    """
    label_a = collection_a if isinstance(collection_a, str) else "collection_a"
    label_b = collection_b if isinstance(collection_b, str) else "collection_b"

    # ── Filter collection A ────────────────────────────────────────────────
    print(f"[geets.pairs] (1/5) Applying filters to A: {label_a}")
    print(f"              date={start_date}–{end_date}  "
          f"cloud≤{max_cloud_cover}%  bands={bands_a or 'all'}")
    col_a = _load_and_filter(
        collection_a, start_date, end_date, aoi,
        bands_a, cloud_property_a, max_cloud_cover,
    )

    # ── Filter collection B ────────────────────────────────────────────────
    print(f"[geets.pairs] (2/5) Applying filters to B: {label_b}")
    print(f"              date={start_date}–{end_date}  "
          f"cloud≤{max_cloud_cover}%  bands={bands_b or 'all'}")
    col_b = _load_and_filter(
        collection_b, start_date, end_date, aoi,
        bands_b, cloud_property_b, max_cloud_cover,
    )

    # ── Fetch AOI geometry (one round-trip) ────────────────────────────────
    print("[geets.pairs] (3/5) Fetching AOI geometry …")
    aoi_geom = aoi.getInfo()

    # ── Fetch image metadata ───────────────────────────────────────────────
    print("[geets.pairs] (4/5) Fetching image metadata …")
    print(f"              Collection A ({label_a}):")
    meta_a = _get_image_metadata(col_a)
    print(f"              Collection B ({label_b}):")
    meta_b = _get_image_metadata(col_b)

    if not meta_a or not meta_b:
        print("[geets.pairs] ✗ One or both collections returned 0 images – check filters.")
        return []

    # ── Match pairs ────────────────────────────────────────────────────────
    max_delta = timedelta(days=max_time_delta_days)
    n_candidates = len(meta_a) * len(meta_b)
    print(
        f"[geets.pairs] (5/5) Matching {len(meta_a)} × {len(meta_b)} = "
        f"{n_candidates} candidate pairs …"
    )
    print(f"              criteria: Δt≤{max_time_delta_days}d  overlap≥{min_overlap:.0%}")

    pairs: list[ImagePair] = []
    skipped_time = 0
    skipped_overlap = 0

    for ma in meta_a:
        for mb in meta_b:
            if abs(ma["date"] - mb["date"]) > max_delta:
                skipped_time += 1
                continue
            if ma["geometry"] is None or mb["geometry"] is None:
                skipped_overlap += 1
                continue
            ratio = _overlap(ma["geometry"], mb["geometry"], aoi_geom)
            if ratio < min_overlap:
                skipped_overlap += 1
                continue

            img_a = ee.Image(ma["id"])
            img_b = ee.Image(mb["id"])
            if bands_a:
                img_a = img_a.select(bands_a)
            if bands_b:
                img_b = img_b.select(bands_b)

            pairs.append(ImagePair(
                image_a=img_a,
                image_b=img_b,
                date_a=ma["date"].strftime("%Y-%m-%d"),
                date_b=mb["date"].strftime("%Y-%m-%d"),
                overlap_ratio=round(ratio, 4),
            ))
            print(
                f"  ✓ pair found  A={ma['date'].date()}  B={mb['date'].date()}"
                f"  overlap={ratio:.1%}"
            )

    print(
        f"[geets.pairs] Done.  {len(pairs)} pair(s) found  "
        f"(skipped: {skipped_time} Δt, {skipped_overlap} overlap)"
    )
    pairs.sort(key=lambda p: p["date_a"])
    return pairs


def export_pairs(
    pairs: list[ImagePair],
    outdir: str | Path,
    name_a: str = "collection_a",
    name_b: str = "collection_b",
    *,
    scale_a: float = 30.0,
    scale_b: float = 10.0,
    aoi: ee.Geometry | None = None,
    clip_to_intersection: bool = True,
    crs: str = "EPSG:4326",
) -> None:
    """Export matched image pairs as GeoTIFF files on local disk.

    Directory layout::

        <outdir>/
            pair_01/
                <name_a>_<date_a>.tif
                <name_b>_<date_b>.tif
            pair_02/
                ...

    When *clip_to_intersection* is ``True`` (default), both images are clipped
    to the intersection of their footprints (and the AOI if provided) so both
    TIFs share the same spatial extent.

    .. note::
        Uses the GEE download API (via :func:`geemap.ee_export_image`), which is
        limited to roughly 32 MB per file.  For large extents or fine resolutions
        use :func:`ee.batch.Export.image.toDrive` instead.

    Parameters
    ----------
    pairs:
        Output from :func:`find_pairs`.
    outdir:
        Root directory; created automatically if it does not exist.
    name_a, name_b:
        Filename stems for the two collections (no extension).
    scale_a, scale_b:
        Export pixel size in metres.
    aoi:
        Export region.  When *clip_to_intersection* is ``False`` and *aoi* is
        ``None``, geemap falls back to each image's own footprint.
    clip_to_intersection:
        Clip both images to the intersection of their footprints (and *aoi*).
    crs:
        Coordinate reference system for the export (default ``"EPSG:4326"``).
    """
    outdir = Path(outdir)
    n = len(pairs)
    if n == 0:
        print("[geets.pairs] No pairs to export.")
        return

    for i, pair in enumerate(pairs, start=1):
        pair_dir = outdir / f"pair_{i:02d}"
        pair_dir.mkdir(parents=True, exist_ok=True)

        # Determine export region
        if clip_to_intersection:
            region: ee.Geometry = pair["image_a"].geometry().intersection(
                pair["image_b"].geometry(), maxError=10
            )
            if aoi is not None:
                region = region.intersection(aoi, maxError=10)
        else:
            region = aoi  # type: ignore[assignment]  # may be None

        date_a_str = pair["date_a"].replace("-", "")
        date_b_str = pair["date_b"].replace("-", "")
        path_a = pair_dir / f"{name_a}_{date_a_str}.tif"
        path_b = pair_dir / f"{name_b}_{date_b_str}.tif"

        print(
            f"[geets.pairs] Pair {i}/{n}  "
            f"({pair['date_a']} | {pair['date_b']})  "
            f"overlap={pair['overlap_ratio']:.2%}"
        )
        geemap.ee_export_image(
            pair["image_a"],
            filename=str(path_a),
            scale=scale_a,
            region=region,
            crs=crs,
            file_per_band=False,
        )
        print(f"  → {path_a}")

        geemap.ee_export_image(
            pair["image_b"],
            filename=str(path_b),
            scale=scale_b,
            region=region,
            crs=crs,
            file_per_band=False,
        )
        print(f"  → {path_b}")

    print(f"[geets.pairs] Done.  {n} pair(s) exported to {outdir}/")
