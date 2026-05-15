"""
Reduce an ee.ImageCollection over an AOI to a pandas DataFrame of statistics.

For each image the following are computed per pixel sample:
  p0  (min), p25, p50 (median), p75, p100 (max), mean

Usage example:
    import ee
    from geets import initialize_ee
    from geets.optical   import load_modis_vi
    from geets.timeseries import reduce_region_stats

    initialize_ee()
    aoi = ee.Geometry.Rectangle([32.0, 34.5, 34.5, 35.7])
    col = load_modis_vi("2023-01-01", "2026-01-01", aoi=aoi)
    stats = reduce_region_stats(
        col,
        aoi,
        band=["NDVI", "EVI"],
        scale=250,
        export_csv=True,
        outdir="outputs",
    )
    print(stats["NDVI"].head())
"""

from __future__ import annotations

import ee
import pandas as pd

from pathlib import Path

from geets.utils import build_output_path, l_get_outdir


# Default percentile breaks
_DEFAULT_PERCENTILES = [0, 25, 50, 75, 100]


def reduce_region_stats(
    image_collection: ee.ImageCollection,
    geometry:         ee.Geometry,
    band:             str | list[str],
    scale:            int   = 250,
    percentiles:      list[int] = _DEFAULT_PERCENTILES,
    include_mean:     bool  = True,
    date_format:      str   = "YYYY-MM-dd",
    max_pixels:       float = 1e13,
    best_effort:      bool  = True,
    outdir:           str | None = None,
    export_csv:       bool | None = None,
) -> pd.DataFrame | dict[str, pd.DataFrame]:
    """
    Reduce each image in a collection over a geometry to percentile statistics.

    For every image a single call to ``reduceRegion`` is made with a combined
    percentile + mean reducer.  All results are fetched in one ``getInfo()``
    call via a FeatureCollection → minimal round-trips to the GEE API.

    Parameters
    ----------
    image_collection : ee.ImageCollection
        Collection to reduce (should already be filtered / masked).
    geometry         : ee.Geometry
        Region over which to reduce (Polygon, Rectangle, …).
    band             : str | list[str]
        Band name or list of bands to extract.
    scale            : int
        Pixel scale in metres (match the native resolution of the collection).
    percentiles      : list[int]
        Percentile breaks, default [0, 25, 50, 75, 100].
    include_mean     : bool
        Also compute the mean value.
    date_format      : str
        GEE date format string for the 'date' column.
    max_pixels       : float
        Passed to reduceRegion – increase if you get "too many pixels" errors.
    best_effort      : bool
        If True, GEE scales up the pixel size automatically when max_pixels is
        exceeded instead of throwing an error.
    outdir           : str | None
        Optional output directory used when CSV export is enabled.
    export_csv       : bool | None
        Write CSV files via ``l_export_csv``.
        - None (default): always export (enables l_load_band_csvs workflow)
        - True: always export
        - False: never export

    Returns
    -------
    pd.DataFrame | dict[str, pd.DataFrame]
        - Single band: DataFrame (same behavior as before)
        - Multiple bands: dict keyed by band name, one DataFrame per band
    """
    bands = [band] if isinstance(band, str) else list(band)
    if not bands:
        raise ValueError("band list is empty")

    print(f"[geets.reduce] Starting reduce_region_stats")
    print(f"[geets.reduce] Band selection: {bands}")
    print(f"[geets.reduce] Scale={scale}, include_mean={include_mean}, best_effort={best_effort}")

    if export_csv is None:
        export_csv = True  # always export by default (enables l_load_band_csvs workflow)
    print(f"[geets.reduce] export_csv={export_csv}")

    # Normalize geometry:
    #   ee.FeatureCollection / ee.Feature → ee.Geometry (reduceRegion needs Geometry)
    if isinstance(geometry, (ee.FeatureCollection, ee.Feature)):
        print("[geets.reduce] Converting Feature/FeatureCollection to Geometry")
        geometry = geometry.geometry()

    # Pre-fetch the GeoJSON dict with one client-side call.
    # Reason: GEE's CustomFunction serializer calls the map-function body once
    # with dummy variables to inspect the return type.  At that point it tries
    # to re-wrap every captured ee.Geometry via Geometry(arg), which fails if
    # the geometry is a ComputedObject (e.g. from .geometry() on a FC).
    # Passing a plain Python dict avoids the serialization issue entirely.
    geom_dict = geometry.getInfo()
    print("[geets.reduce] Geometry prepared")

    # Build combined reducer: percentile + optionally mean
    reducer = ee.Reducer.percentile(percentiles)
    if include_mean:
        reducer = reducer.combine(
            reducer2=ee.Reducer.mean(),
            sharedInputs=True,
        )
    print(f"[geets.reduce] Reducer prepared with percentiles={percentiles}")

    def _reduce_image(img: ee.Image) -> ee.Feature:
        """Map function: reduce one image → Feature with stats as properties."""
        # Reconstruct ee.Geometry from the pre-fetched GeoJSON dict.
        # Using a plain dict avoids CustomFunction serialization issues.
        geom  = ee.Geometry(geom_dict)
        stats = (
            img.select(bands)
            .reduceRegion(
                reducer=reducer,
                geometry=geom,
                scale=scale,
                maxPixels=max_pixels,
                bestEffort=best_effort,
            )
        )
        date = img.date().format(date_format)
        return ee.Feature(None, stats.set("date", date))

    # Map over collection → FeatureCollection → single getInfo() call
    print("[geets.reduce] Mapping reduceRegion over image collection")
    fc   = image_collection.map(_reduce_image)
    print("[geets.reduce] Fetching results from Earth Engine")
    data = fc.getInfo()["features"]

    # Parse results into a list of dicts
    rows = []
    for feat in data:
        props = feat["properties"]
        row   = {"date": props.get("date")}

        for one_band in bands:
            # GEE names percentile outputs as "<band>_p<N>"
            for p in percentiles:
                key = f"{one_band}_p{p}"
                row[key] = props.get(key)          # None if all pixels masked

            if include_mean:
                mean_key = f"{one_band}_mean"
                row[mean_key] = props.get(mean_key)

        rows.append(row)

    if not rows:
        # GEE returned no features – collection is empty or no pixels in AOI
        print("[geets.reduce] WARNING: no features returned by GEE (empty collection or AOI mismatch)")
        all_cols = (
            [f"{b}_p{p}" for b in bands for p in percentiles]
            + ([f"{b}_mean" for b in bands] if include_mean else [])
        )
        empty = pd.DataFrame(columns=all_cols)
        empty.index = pd.DatetimeIndex([], name="date")
        return empty if len(bands) == 1 else {b: empty[[c for c in all_cols if c.startswith(b)]] for b in bands}

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()

    if len(bands) == 1:
        if export_csv:
            csv_path = l_export_csv(df, band=bands[0], outdir=outdir)
            print(f"[geets.reduce] CSV exported for {bands[0]}: {csv_path}")
        print("[geets.reduce] Finished (single-band)")
        return df

    by_band: dict[str, pd.DataFrame] = {}
    for one_band in bands:
        cols = [f"{one_band}_p{p}" for p in percentiles]
        if include_mean:
            cols.append(f"{one_band}_mean")
        band_df = df[cols].copy()
        by_band[one_band] = band_df
        if export_csv:
            csv_path = l_export_csv(band_df, band=one_band, outdir=outdir)
            print(f"[geets.reduce] CSV exported for {one_band}: {csv_path}")

    print("[geets.reduce] Finished (multi-band)")

    return by_band


def l_export_csv(
    df: pd.DataFrame,
    band: str = "NDVI",
    outdir: str | None = None,
    save_path: str | None = None,
) -> str:
    """
    Export reduced time-series statistics to CSV.

    CSVs are saved in a band-named subfolder so that multiple runs
    (covering different date ranges) accumulate without overwriting:
      <outdir>/csv/<band>/timeseries_<band>_<start>_<end>.csv

    Returns
    -------
    str
        Absolute path to the written CSV file.
    """
    if save_path is None and (outdir is not None or l_get_outdir() is not None):
        if df.empty or not isinstance(df.index, pd.DatetimeIndex):
            start, end = "na", "na"
        else:
            start = df.index.min().strftime("%Y%m%d")
            end = df.index.max().strftime("%Y%m%d")

        save_path = str(
            build_output_path(
                "csv",
                band,
                group=band,          # → csv/<band>/
                outdir=outdir,
                df=df,
                stem=f"timeseries_{band.lower()}_{start}_{end}",
                ext="csv",
            )
        )

    if save_path is None:
        raise ValueError("No output path configured. Use l_set_outdir(...), outdir=..., or save_path=...")

    df.to_csv(save_path)
    return save_path


def l_load_band_csvs(
    band: str,
    outdir: str | None = None,
) -> pd.DataFrame:
    """
    Load and concatenate all CSV files from the band subfolder.

    Looks in ``<outdir>/csv/<band>/`` for any ``*.csv`` files, reads them
    all, concatenates, removes duplicate dates, and returns a single
    sorted DataFrame – ready for plotting over a longer time span than
    a single API call could return.

    Parameters
    ----------
    band   : band name, e.g. ``"temperature_2m"``
    outdir : override for the global output directory

    Returns
    -------
    pd.DataFrame
        Merged DataFrame with a DatetimeIndex, or an empty DataFrame if
        the folder does not exist or contains no CSV files.
    """
    root = Path(outdir).expanduser().resolve() if outdir is not None else l_get_outdir()
    if root is None:
        raise ValueError("No outdir configured. Use l_set_outdir(...) or pass outdir=...")

    band_dir = root / "csv" / band
    csv_files = sorted(band_dir.glob("*.csv")) if band_dir.exists() else []

    if not csv_files:
        print(f"[geets.l_load_band_csvs] No CSV files found in {band_dir}")
        return pd.DataFrame()

    dfs = [pd.read_csv(f, index_col=0, parse_dates=True) for f in csv_files]
    merged = pd.concat(dfs).sort_index()
    merged = merged[~merged.index.duplicated(keep="last")]
    print(f"[geets.l_load_band_csvs] Loaded {len(csv_files)} CSV(s) for '{band}': {len(merged)} rows")
    return merged


def l_aggregate_csv(
    df: pd.DataFrame,
    band: str,
    freq: str = "ME",
) -> pd.DataFrame:
    """
    Resample a daily stats DataFrame to a coarser time resolution (monthly or yearly).

    Parameters
    ----------
    df   : DataFrame from ``l_load_band_csvs`` or ``reduce_region_stats``.
           Must have a DatetimeIndex and columns named ``<band>_p0``,
           ``<band>_p25``, ``<band>_p50``, ``<band>_p75``, ``<band>_p100``,
           and optionally ``<band>_mean``.
    band : Band name prefix, e.g. ``"temperature_2m"``.
    freq : Pandas resample frequency string.
           ``"ME"``  – month-end  (default)
           ``"YE"``  – year-end
           Any other valid pandas offset alias is accepted.

    Returns
    -------
    pd.DataFrame
        Resampled DataFrame with the same column names and a DatetimeIndex
        at the requested frequency.

    Notes on statistical validity
    ------------------------------
    The aggregation method depends on the column:

    - ``_p0``   → ``min``   Exact: the period minimum equals the minimum of daily minima.
    - ``_p100`` → ``max``   Exact: the period maximum equals the maximum of daily maxima.
    - ``_mean`` → ``mean``  Exact: the period mean equals the mean of daily means
                            (assuming one observation per day).
    - ``_p25``, ``_p50``, ``_p75`` → ``mean``
                            Approximation: the mean of daily percentiles is NOT the
                            true period percentile, but a reasonable indicator for
                            trend analysis.
    """
    agg: dict[str, str] = {}
    for col in df.columns:
        if col == f"{band}_p0":
            agg[col] = "min"
        elif col == f"{band}_p100":
            agg[col] = "max"
        else:
            agg[col] = "mean"   # _p25, _p50, _p75, _mean → mean of daily values

    return df.resample(freq).agg(agg)
