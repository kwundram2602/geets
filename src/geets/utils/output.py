from __future__ import annotations

from pathlib import Path

import pandas as pd


_OUTDIR: Path | None = None


def l_set_outdir(outdir: str | Path) -> Path:
    """Set global output directory and create it if missing."""
    global _OUTDIR
    _OUTDIR = Path(outdir).expanduser().resolve()
    _OUTDIR.mkdir(parents=True, exist_ok=True)
    return _OUTDIR


def l_get_outdir() -> Path | None:
    """Return configured global output directory or None."""
    return _OUTDIR


def _slug(text: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in text).strip("-")


def _dates_from_df_index(df: pd.DataFrame | None) -> tuple[str | None, str | None]:
    if df is None or df.empty:
        return None, None
    if not isinstance(df.index, pd.DatetimeIndex):
        return None, None
    start = pd.Timestamp(df.index.min()).strftime("%Y%m%d")
    end = pd.Timestamp(df.index.max()).strftime("%Y%m%d")
    return start, end


def build_output_path(
    kind: str,
    band: str,
    *,
    outdir: str | Path | None = None,
    group: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    df: pd.DataFrame | None = None,
    stem: str | None = None,
    ext: str = "png",
) -> Path:
    """
    Build an output path and create subdirectory automatically.

    Filename format (default):
        <kind>[/<group>]/<kind>_<band>_<start>_<end>.<ext>
    Example (no group):
        plot/boxplot_ndvi_20230101_20260101.png
    Example (group=band):
        csv/temperature_2m/timeseries_temperature_2m_20230101_20260101.csv
    """
    root = Path(outdir).expanduser().resolve() if outdir is not None else l_get_outdir()
    if root is None:
        raise ValueError("No outdir configured. Use l_set_outdir(...) or pass outdir=...")

    subdir = root / _slug(kind)
    if group is not None:
        subdir = subdir / group   # keep as-is: band names are already filesystem-safe
    subdir.mkdir(parents=True, exist_ok=True)

    idx_start, idx_end = _dates_from_df_index(df)
    start = (start_date or idx_start or "na").replace("-", "")
    end = (end_date or idx_end or "na").replace("-", "")

    if stem is None:
        stem = f"{_slug(kind)}_{_slug(band)}_{start}_{end}"

    normalized_ext = ext if ext.startswith(".") else f".{ext}"
    return subdir / f"{stem}{normalized_ext}"
