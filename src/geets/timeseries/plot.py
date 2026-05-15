"""
Plot functions for NDVI (or other band) time series DataFrames.

Expected DataFrame format: output of ``reduce_region_stats()``.
  Index  : pd.DatetimeIndex
  Columns: <band>_p0, <band>_p25, <band>_p50, <band>_p75, <band>_p100
           (optionally <band>_mean)

Usage example:
    from geets.timeseries import reduce_region_stats, l_plot_boxplot, l_plot_timeseries

    df = reduce_region_stats(col, aoi, band="NDVI", scale=250)
    l_plot_boxplot(df, band="NDVI", title="MODIS NDVI – Cyprus 2023-2026")
    l_plot_timeseries(df, band="NDVI", stats=["iqr", "median", "mean"])
    l_plot_timeseries(df, band="NDVI", stats=["min", "max", "median"])
    l_plot_timeseries(df, band="NDVI", stats=["mean"])
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

from geets.utils import build_output_path, l_get_outdir


# ---------------------------------------------------------------------------
# Stat aliases and styling
# ---------------------------------------------------------------------------

# Human-friendly aliases → internal stat key
_STAT_ALIAS: dict[str, str] = {
    "min":    "p0",
    "max":    "p100",
    "median": "p50",
}

# All stat keys that map to a single column (as opposed to fill ranges)
_LINE_STATS = ("p0", "p25", "p50", "p75", "p100", "mean")

# Per-stat line styles for l_plot_timeseries
_LINE_STYLE: dict[str, dict] = {
    "p0":   dict(linestyle="--", alpha=0.55, linewidth=1.0),
    "p25":  dict(linestyle="-.", alpha=0.70, linewidth=1.2),
    "p50":  dict(linestyle="-",  alpha=1.00, linewidth=2.0),
    "p75":  dict(linestyle="-.", alpha=0.70, linewidth=1.2),
    "p100": dict(linestyle="--", alpha=0.55, linewidth=1.0),
    "mean": dict(linestyle="--", alpha=1.00, linewidth=1.2, color="tomato"),
}

_LINE_LABEL: dict[str, str] = {
    "p0":   "Min (p0)",
    "p25":  "p25",
    "p50":  "Median (p50)",
    "p75":  "p75",
    "p100": "Max (p100)",
    "mean": "Mean",
}


def _normalize_stats(stats: list[str]) -> list[str]:
    """Resolve aliases to canonical keys, e.g. 'median' → 'p50'."""
    return [_STAT_ALIAS.get(s, s) for s in stats]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _col(band: str, suffix: str) -> str:
    """Build column name, e.g. _col('NDVI', 'p50') → 'NDVI_p50'."""
    return f"{band}_{suffix}"


def _require_cols(df: pd.DataFrame, band: str, cols: list[str]) -> None:
    if df.empty:
        raise KeyError(
            f"DataFrame is empty (band='{band}'). "
            "Use reduce_region_stats() or l_load_band_csvs() to populate it first."
        )
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(
            f"DataFrame is missing columns: {missing}. "
            f"Available: {list(df.columns)}"
        )


def _span_from_index(df: pd.DataFrame) -> tuple[str, str]:
    if df.empty or not isinstance(df.index, pd.DatetimeIndex):
        return "na", "na"
    return df.index.min().strftime("%Y%m%d"), df.index.max().strftime("%Y%m%d")


def _needed_cols_for_stats(band: str, norm_stats: list[str]) -> list[str]:
    """Return the DataFrame columns required by a given normalized stats list."""
    needed: list[str] = []
    if "range" in norm_stats:
        needed += [_col(band, "p0"), _col(band, "p100")]
    if "iqr" in norm_stats:
        needed += [_col(band, "p25"), _col(band, "p75")]
    for s in _LINE_STATS:
        if s in norm_stats:
            needed.append(_col(band, s))
    return list(dict.fromkeys(needed))   # deduplicate, preserve order


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def l_plot_boxplot(
    df:       pd.DataFrame,
    band:     str        = "NDVI",
    title:    str        = "",
    figsize:  tuple      = (16, 5),
    color:    str        = "steelblue",
    stats:    list[str]  = (),
    ax:       plt.Axes | None = None,
    save_path: str | None = None,
    outdir: str | None = None,
) -> plt.Axes:
    """
    Boxplot time series using pre-computed percentiles.

    Each date is one box:
      - box      : p25 – p75 (IQR)
      - line     : p50 (median)
      - whiskers : p0 (min) – p100 (max)

    Parameters
    ----------
    df        : DataFrame from reduce_region_stats()
    band      : band name prefix, e.g. "NDVI"
    title     : plot title (auto-generated if empty)
    figsize   : figure size
    color     : box fill colour
    stats     : optional list of overlay elements to add on top of the boxes.
                Supported: ``"mean"`` – draws a mean marker (◆) on each box.
                Example: ``stats=["mean"]``
    ax        : existing Axes to draw into (creates new figure if None)
    save_path : optional file path to save the figure
    outdir    : optional root output dir; if save_path is None, auto-saves to
                <outdir>/plot/<span>/ with logical filename

    Returns
    -------
    matplotlib Axes
    """
    norm = _normalize_stats(list(stats))
    if df.empty:
        print(f"[geets.l_plot_boxplot] Skipping '{band}': DataFrame is empty.")
        return None
    needed = [_col(band, s) for s in ("p0", "p25", "p50", "p75", "p100")]
    _require_cols(df, band, needed)

    df_clean = df.dropna(subset=needed)

    if df_clean.empty:
        own_figure = ax is None
        if own_figure:
            fig, ax = plt.subplots(figsize=figsize)
        ax.set_title((title or f"{band} Time Series – Boxplot") + "  [no data]")
        ax.text(0.5, 0.5, "No valid data", transform=ax.transAxes,
                ha="center", va="center", color="gray", fontsize=12)
        return ax

    # Build bxp stats list (matplotlib accepts pre-computed stats via ax.bxp)
    bxp_stats = [
        {
            "med":    row[_col(band, "p50")],
            "q1":     row[_col(band, "p25")],
            "q3":     row[_col(band, "p75")],
            "whislo": row[_col(band, "p0")],
            "whishi": row[_col(band, "p100")],
            "fliers": [],
            "label":  date.strftime("%Y-%m-%d"),
        }
        for date, row in df_clean.iterrows()
    ]

    own_figure = ax is None   # only auto-save when we created the figure
    if own_figure:
        fig, ax = plt.subplots(figsize=figsize)

    ax.bxp(
        bxp_stats,
        showfliers=False,
        patch_artist=True,
        boxprops     =dict(facecolor=color, alpha=0.6),
        medianprops  =dict(color="black", linewidth=1.5),
        whiskerprops =dict(color=color),
        capprops     =dict(color=color),
    )

    # Optional overlay: mean markers
    mean_col = _col(band, "mean")
    if "mean" in norm and mean_col in df_clean.columns:
        ax.plot(
            range(1, len(df_clean) + 1),
            df_clean[mean_col],
            marker="D", linestyle="none", color="tomato",
            markersize=3, zorder=5, label="Mean",
        )
        ax.legend(loc="upper right", fontsize=9)

    # X-axis: use date strings rotated
    n = len(df_clean)
    step = max(1, n // 12)                      # show at most ~12 labels
    ax.set_xticks(range(1, n + 1, step))
    ax.set_xticklabels(
        [bxp_stats[i]["label"] for i in range(0, n, step)],
        rotation=45, ha="right", fontsize=8,
    )

    ax.set_ylabel(band)
    ax.set_title(title or f"{band} Time Series – Boxplot")
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    if own_figure and save_path is None and (outdir is not None or l_get_outdir() is not None):
        start, end = _span_from_index(df_clean)
        save_path = str(
            build_output_path(
                "plot",
                band,
                group=f"{start}_{end}",
                outdir=outdir,
                df=df_clean,
                stem=f"boxplot_{band.lower()}_{start}_{end}",
                ext="png",
            )
        )

    if save_path:
        ax.figure.savefig(save_path, dpi=150, bbox_inches="tight")

    return ax


def l_plot_timeseries(
    df:        pd.DataFrame,
    band:      str        = "NDVI",
    title:     str        = "",
    figsize:   tuple      = (16, 5),
    color:     str        = "steelblue",
    stats:     list[str]  = ("range", "iqr", "median"),
    x_ticks:   str | int | None = None,
    ax:        plt.Axes | None = None,
    save_path: str | None = None,
    outdir: str | None = None,
) -> plt.Axes:
    """
    Flexible time series line/area plot driven by the ``stats`` parameter.

    Parameters
    ----------
    df    : DataFrame from reduce_region_stats() or l_load_band_csvs().
    band  : band name prefix, e.g. ``"NDVI"``.
    stats : list of elements to draw. Aliases accepted.

        Fill layers (drawn first, bottom to top):
          ``"range"``          – shaded area between p0 and p100
          ``"iqr"``            – shaded area between p25 and p75

        Line layers:
          ``"p0"`` / ``"min"`` – minimum line
          ``"p25"``            – 25th percentile line
          ``"p50"`` / ``"median"`` – median line  (default prominent style)
          ``"p75"``            – 75th percentile line
          ``"p100"`` / ``"max"`` – maximum line
          ``"mean"``           – mean line (tomato colour)

        Default: ``["range", "iqr", "median"]``

        Examples::

            stats=["mean"]                    # only mean line
            stats=["min", "max", "median"]    # three lines, no fills
            stats=["p0", "p25"]              # two lines
            stats=["iqr", "p50", "mean"]     # IQR fill + median + mean

    x_ticks : controls x-axis tick density.
        ``None``        – auto: every 3 months  (default)
        ``"yearly"``    – one tick per year, label format "%Y"
        ``int N``       – one tick every N months, label format "%Y-%m"

    color     : base colour used for fills and percentile lines.
    ax        : existing Axes to draw into (creates new figure if None).
    save_path : optional file path to save the figure.
    outdir    : optional root output dir; auto-saves to
                ``<outdir>/plot/<span>/`` when set.

    Returns
    -------
    matplotlib Axes
    """
    norm = _normalize_stats(list(stats))
    if df.empty:
        print(f"[geets.l_plot_timeseries] Skipping '{band}': DataFrame is empty.")
        return None
    needed = _needed_cols_for_stats(band, norm)

    if not needed:
        raise ValueError(f"stats={stats!r} produced no drawable elements.")

    _require_cols(df, band, needed)
    df_clean = df.dropna(subset=needed)

    if df_clean.empty:
        own_figure = ax is None
        if own_figure:
            fig, ax = plt.subplots(figsize=figsize)
        ax.set_title((title or f"{band} Time Series") + "  [no data]")
        ax.text(0.5, 0.5, "No valid data", transform=ax.transAxes,
                ha="center", va="center", color="gray", fontsize=12)
        return ax

    dates = df_clean.index

    own_figure = ax is None   # only auto-save when we created the figure
    if own_figure:
        fig, ax = plt.subplots(figsize=figsize)

    # Fill: p0–p100 range
    if "range" in norm:
        ax.fill_between(
            dates,
            df_clean[_col(band, "p0")],
            df_clean[_col(band, "p100")],
            alpha=0.15, color=color, label="Min–Max (p0–p100)",
        )

    # Fill: IQR p25–p75
    if "iqr" in norm:
        ax.fill_between(
            dates,
            df_clean[_col(band, "p25")],
            df_clean[_col(band, "p75")],
            alpha=0.35, color=color, label="IQR (p25–p75)",
        )

    # Individual lines
    for stat in _LINE_STATS:
        if stat not in norm:
            continue
        col = _col(band, stat)
        if col not in df_clean.columns:
            continue
        style = _LINE_STYLE[stat].copy()
        if "color" not in style:
            style["color"] = color
        ax.plot(dates, df_clean[col], label=_LINE_LABEL[stat], **style)

    if x_ticks == "yearly":
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    else:
        interval = int(x_ticks) if isinstance(x_ticks, int) else 3
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=interval))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

    ax.set_ylabel(band)
    ax.set_title(title or f"{band} Time Series")
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(axis="both", linestyle="--", alpha=0.3)

    if own_figure and save_path is None and (outdir is not None or l_get_outdir() is not None):
        start, end = _span_from_index(df_clean)
        save_path = str(
            build_output_path(
                "plot",
                band,
                group=f"{start}_{end}",
                outdir=outdir,
                df=df_clean,
                stem=f"timeseries_{band.lower()}_{start}_{end}",
                ext="png",
            )
        )

    if save_path:
        ax.figure.savefig(save_path, dpi=150, bbox_inches="tight")

    return ax


def l_plot_combined(
    df:        pd.DataFrame,
    band:      str        = "NDVI",
    title:     str        = "",
    figsize:   tuple      = (16, 9),
    color:     str        = "steelblue",
    stats:     list[str]  = ("range", "iqr", "median"),
    save_path: str | None = None,
    outdir: str | None = None,
) -> tuple[plt.Axes, plt.Axes]:
    """
    Convenience: boxplot (top) and timeseries line plot (bottom) stacked.

    ``stats`` is forwarded to ``l_plot_timeseries``.

    Returns
    -------
    (ax_box, ax_line)
    """
    fig, (ax_top, ax_bot) = plt.subplots(2, 1, figsize=figsize)
    l_plot_boxplot(df,    band=band, color=color, ax=ax_top)
    l_plot_timeseries(df, band=band, color=color, stats=stats, ax=ax_bot)

    fig.suptitle(title or f"{band} Time Series", fontsize=13, y=1.01)
    plt.tight_layout()

    if save_path is None and (outdir is not None or l_get_outdir() is not None):
        start, end = _span_from_index(df)
        save_path = str(
            build_output_path(
                "plot",
                band,
                outdir=outdir,
                df=df,
                stem=f"combined_{band.lower()}_{start}_{end}",
                ext="png",
            )
        )

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")

    return ax_top, ax_bot


def l_stack_plots(
    dirs:           list,
    *,
    stats:          list[str]      = ("iqr", "median"),
    x_ticks:        str | int | None = None,
    subplot_height: int            = 3,
    width:          int            = 16,
    color:          str | list[str] = "steelblue",
    titles:         list[str] | None = None,
    save_path:      str | None     = None,
    outdir:         str | None     = None,
) -> plt.Figure | None:
    """
    Stack multiple band time series vertically with a shared, synchronised x-axis.

    Each entry in ``dirs`` is a folder that contains CSV files written by
    ``reduce_region_stats`` (the ``csv/<band>/`` subfolder pattern).
    The band name is inferred from the folder name (last path component).

    Parameters
    ----------
    dirs           : list of folder paths, one per subplot.
                     e.g. [".../csv/temperature_2m", ".../csv/precipitation"]
    stats          : stat layers drawn in every subplot (same as l_plot_timeseries).
    x_ticks        : x-axis tick density (same as l_plot_timeseries).
                     ``None`` → every 3 months · ``"yearly"`` → per year · ``int N`` → every N months
    subplot_height : height in inches per subplot (default 3).
    width          : total figure width in inches (default 16).
    color          : base colour for fills and lines.
                     A single string applies to all subplots; a list assigns
                     one colour per subplot (falls back to "steelblue" for
                     missing entries).
    titles         : optional list of subplot titles (one per dir).
                     Falls back to the band name (folder name) when not provided.
    save_path      : explicit file path to save the figure.
    outdir         : root output directory; auto-saves to ``<outdir>/plot/<span>/``
                     when set (falls back to l_get_outdir()).

    Returns
    -------
    matplotlib Figure, or None if all DataFrames are empty.
    """
    from pathlib import Path as _Path

    dirs = [_Path(d) for d in dirs]
    n = len(dirs)
    if n == 0:
        print("[geets.l_stack_plots] No directories provided.")
        return None

    # ── Load CSVs for each dir ──────────────────────────────────────────────
    band_names: list[str] = [d.name for d in dirs]
    dfs: list[pd.DataFrame] = []
    for d, band in zip(dirs, band_names):
        csv_files = sorted(d.glob("*.csv")) if d.exists() else []
        if not csv_files:
            print(f"[geets.l_stack_plots] No CSV files in {d} (band='{band}') – subplot will be empty.")
            dfs.append(pd.DataFrame())
        else:
            parts = [pd.read_csv(f, index_col=0, parse_dates=True) for f in csv_files]
            merged = pd.concat(parts).sort_index()
            merged = merged[~merged.index.duplicated(keep="last")]
            dfs.append(merged)

    non_empty = [df for df in dfs if not df.empty]
    if not non_empty:
        print("[geets.l_stack_plots] All DataFrames are empty – nothing to plot.")
        return None

    # ── Build figure with shared x-axis ─────────────────────────────────────
    fig, axes = plt.subplots(
        n, 1,
        figsize=(width, subplot_height * n),
        sharex=True,
    )
    if n == 1:
        axes = [axes]

    colors = color if isinstance(color, list) else [color] * n

    for i, (ax, df, band) in enumerate(zip(axes, dfs, band_names)):
        title      = titles[i] if (titles and i < len(titles)) else band
        subplot_color = colors[i] if i < len(colors) else "steelblue"
        # Pass ax= so l_plot_timeseries draws into our pre-created axes without
        # auto-saving individual subplots (own_figure=False when ax is given).
        l_plot_timeseries(
            df, band=band, title=title, stats=stats,
            color=subplot_color, x_ticks=x_ticks, ax=ax,
        )

    # ── Shared x-axis: hide tick labels on every subplot except the bottom ──
    for ax in axes[:-1]:
        plt.setp(ax.get_xticklabels(), visible=False)
        ax.set_xlabel("")

    fig.tight_layout()

    # ── Save ────────────────────────────────────────────────────────────────
    if save_path is None:
        root = _Path(outdir).expanduser().resolve() if outdir is not None else l_get_outdir()
        if root is not None:
            span_start = min(df.index.min() for df in non_empty if isinstance(df.index, pd.DatetimeIndex)).strftime("%Y%m%d")
            span_end   = max(df.index.max() for df in non_empty if isinstance(df.index, pd.DatetimeIndex)).strftime("%Y%m%d")
            stem       = "stack_" + "_".join(band_names)
            plot_dir   = root / "plot" / f"{span_start}_{span_end}"
            plot_dir.mkdir(parents=True, exist_ok=True)
            save_path  = str(plot_dir / f"{stem}.png")

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"[geets.l_stack_plots] Saved: {save_path}")

    return fig
