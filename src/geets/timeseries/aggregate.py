"""
Temporal aggregation helpers for ee.ImageCollection.

Typical use-case:
  Daily collections (ERA5/ERA5-LAND) -> weekly/monthly/x-week aggregates.
"""

from __future__ import annotations

import ee


_FREQUENCIES = {"day", "week", "month", "year"}
_REDUCERS = {"mean", "sum", "min", "max", "median"}


def _aggregate_window(window: ee.ImageCollection, reducer: str) -> ee.Image:
    if reducer == "mean":
        return window.mean()
    if reducer == "sum":
        return window.sum()
    if reducer == "min":
        return window.min()
    if reducer == "max":
        return window.max()
    if reducer == "median":
        return window.median()
    raise ValueError(f"Unsupported reducer '{reducer}'. Choose from: {_REDUCERS}")


def aggregate_temporal(
    image_collection: ee.ImageCollection,
    start_date: str,
    end_date: str,
    *,
    frequency: str = "week",
    every: int = 1,
    reducer: str = "mean",
    aoi: ee.Geometry | None = None,
    clip: bool = False,
) -> ee.ImageCollection:
    """
    Aggregate an ImageCollection into fixed temporal windows.

    Parameters
    ----------
    image_collection : ee.ImageCollection
        Input collection (typically daily).
    start_date, end_date : str
        ISO date strings defining the aggregation horizon.
    frequency : str
        "day", "week", or "month".
    every : int
        Window size in units of ``frequency`` (e.g. 2 weeks, 3 months).
    reducer : str
        One of "mean", "sum", "min", "max", "median".
    aoi : ee.Geometry | None
        Optional AOI for bounds filtering and optional clipping.
    clip : bool
        Clip aggregated images to AOI.

    Returns
    -------
    ee.ImageCollection
        One image per aggregation window. ``system:time_start`` equals
        the window start.
    """
    if frequency not in _FREQUENCIES:
        raise ValueError(f"Unsupported frequency '{frequency}'. Choose from: {_FREQUENCIES}")
    if every < 1:
        raise ValueError("every must be >= 1")
    if reducer not in _REDUCERS:
        raise ValueError(f"Unsupported reducer '{reducer}'. Choose from: {_REDUCERS}")

    # Schritt 1: Kollektion auf den gewünschten Zeitraum und (optional) die AOI einschränken.
    # filterDate(a, b) schließt b aus (halboffenes Intervall [a, b)).
    col = image_collection.filterDate(start_date, end_date)
    if aoi is not None:
        col = col.filterBounds(aoi)  # nur Bilder, deren Footprint die AOI schneidet

    # GEE-seitige Datumsobjekte – alle folgenden Berechnungen laufen auf dem GEE-Server.
    start = ee.Date(start_date)
    end   = ee.Date(end_date)

    # Schritt 2: Anzahl der Fenster berechnen.
    # ee.Date.difference(other, unit) gibt die Zeitspanne in der gewählten Einheit als
    # Dezimalzahl zurück, z.B. "2019-01-01" bis "2021-12-31" in "year" → ~2.997.
    # ceil().int() rundet auf, damit das letzte unvollständige Fenster nicht verloren geht.
    n_windows = end.difference(start, frequency).divide(every).ceil().int()

    # Schritt 3: Server-seitige Indexliste [0, 1, 2, ..., n_windows-1].
    # Diese Liste wird später mit .map() über die Fensterfunktion iteriert.
    # Wichtig: GEE führt .map() lazy/parallel auf seinen Servern aus – kein Python-Loop.
    indices = ee.List.sequence(0, n_windows.subtract(1))

    def _make_window(i: ee.Number) -> ee.Image:
        """Erzeugt für Fenster i ein einzelnes aggregiertes Bild."""
        i = ee.Number(i)

        # Fenstergrenzen: Fenster i beginnt i * every Einheiten nach start_date.
        # Beispiel (monthly, every=1): i=0 → Jan, i=1 → Feb, i=2 → Mär, …
        window_start = start.advance(i.multiply(every), frequency)
        window_end   = window_start.advance(every, frequency)

        # Alle Bilder, die in dieses Zeitfenster fallen, herausfiltern.
        window = col.filterDate(window_start, window_end)

        # Schritt 4: Pixel-weiser Reducer über alle Bilder im Fenster.
        # Jeder Pixel im Ausgabebild erhält den Wert, der sich aus allen
        # Tageswerten an dieser Pixelposition in diesem Fenster ergibt:
        #   mean   → Durchschnitt aller Tageswerte  (z.B. mittlere Monatstemperatur)
        #   sum    → Summe aller Tageswerte          (z.B. monatlicher Niederschlag)
        #   min/max/median → entsprechend extremster oder mittlerer Tageswert
        # Das Ergebnis ist ein einzelnes Bild mit denselben Bändern wie die Eingabe.
        #
        # WICHTIG: Bei lückenhaften Kollektionen (z.B. MODIS 16-Tage-Komposit) kann
        # ein Fenster komplett leer sein. .mean()/.sum() auf einer leeren Kollektion
        # liefert ein Bild ohne Bänder → img.select(band) würde fehlschlagen.
        # ee.Algorithms.If gibt None zurück; dropNulls=True im map()-Aufruf entfernt
        # diese Fenster aus der Ausgabe-Kollektion.
        def _make_agg():
            agg = _aggregate_window(window, reducer)
            if aoi is not None and clip:
                agg = agg.clip(aoi)
            return agg.set(
                {
                    "system:time_start": window_start.millis(),
                    "window_start":      window_start.format("YYYY-MM-dd"),
                    "window_end":        window_end.format("YYYY-MM-dd"),
                    "window_frequency":  frequency,
                    "window_every":      every,
                    "window_reducer":    reducer,
                }
            )

        # Schritt 5: Zeitstempel und Metadaten am Ausgabebild setzen.
        # system:time_start ist GEEs Standard-Zeitstempel; er wird von
        # reduce_region_stats genutzt, um die 'date'-Spalte im DataFrame zu befüllen.
        return ee.Algorithms.If(window.size().gt(0), _make_agg(), None)

    # Schritt 6: Alle Fensterfunktionen server-seitig ausführen und zu einer
    # neuen ImageCollection zusammenfassen (ein Bild pro Aggregationsfenster).
    # dropNulls=True entfernt leere Fenster (None-Einträge) aus der Liste.
    result = ee.ImageCollection.fromImages(indices.map(_make_window, dropNulls=True))

    # Schritt 7: Warnung ausgeben wenn Fenster übersprungen wurden.
    # ee.List([n_windows, result.size()]).getInfo() fasst beide Server-Werte in
    # einem einzigen API-Round-trip zusammen.
    n_expected, n_actual = ee.List([n_windows, result.size()]).getInfo()
    if n_actual < n_expected:
        n_skipped = n_expected - n_actual
        print(
            f"[geets.aggregate_temporal] WARNING: {n_skipped} of {n_expected} "
            f"{frequency}-window(s) were empty and skipped "
            f"(date range: {start_date} – {end_date}, every={every}, reducer={reducer}). "
            f"The source collection has gaps in this period."
        )

    return result


def aggregate_weekly(
    image_collection: ee.ImageCollection,
    start_date: str,
    end_date: str,
    *,
    weeks: int = 1,
    reducer: str = "mean",
    aoi: ee.Geometry | None = None,
    clip: bool = False,
) -> ee.ImageCollection:
    """Aggregate to weekly or x-week windows."""
    return aggregate_temporal(
        image_collection,
        start_date,
        end_date,
        frequency="week",
        every=weeks,
        reducer=reducer,
        aoi=aoi,
        clip=clip,
    )


def aggregate_monthly(
    image_collection: ee.ImageCollection,
    start_date: str,
    end_date: str,
    *,
    months: int = 1,
    reducer: str = "mean",
    aoi: ee.Geometry | None = None,
    clip: bool = False,
) -> ee.ImageCollection:
    """Aggregate to monthly or x-month windows."""
    return aggregate_temporal(
        image_collection,
        start_date,
        end_date,
        frequency="month",
        every=months,
        reducer=reducer,
        aoi=aoi,
        clip=clip,
    )


def aggregate_yearly(
    image_collection: ee.ImageCollection,
    start_date: str,
    end_date: str,
    *,
    reducer: str = "mean",
    aoi: ee.Geometry | None = None,
    clip: bool = False,
) -> ee.ImageCollection:
    """
    Aggregate a daily ImageCollection to one image per calendar year.

    Parameters
    ----------
    image_collection : ee.ImageCollection
        Input collection (typically daily).
    start_date, end_date : str
        ISO date strings defining the aggregation horizon.
    reducer : str
        One of "mean", "sum", "min", "max", "median".
        Use "mean" for temperature/rates, "sum" for precipitation totals.
    aoi : ee.Geometry | None
        Optional AOI for bounds filtering and optional clipping.
    clip : bool
        Clip aggregated images to AOI.

    Returns
    -------
    ee.ImageCollection
        One image per year. ``system:time_start`` equals January 1 of that year.
    """
    return aggregate_temporal(
        image_collection,
        start_date,
        end_date,
        frequency="year",
        every=1,
        reducer=reducer,
        aoi=aoi,
        clip=clip,
    )
