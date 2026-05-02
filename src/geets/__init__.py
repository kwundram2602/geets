"""
geets – Google Earth Engine Tools for Earth Science
"""

from .climate.era5         import ERA5_COLLECTIONS, load_era5_daily
from .climate.chirps       import CHIRPS_COLLECTIONS, CHIRPS_COLLECTION_ID, CHIRPS_BAND, load_chirps_daily
from .optical.modis        import load_modis_vi, load_modis_ndvi, MODIS_COLLECTIONS
from .optical.s2l8         import get_s2, get_l8, to_surface_reflection
from .timeseries.aggregate import aggregate_monthly, aggregate_temporal, aggregate_weekly, aggregate_yearly
from .timeseries.reduce    import l_aggregate_csv, l_export_csv, l_load_band_csvs, reduce_region_stats
from .timeseries.plot      import l_plot_boxplot, l_plot_timeseries, l_plot_combined, l_stack_plots
from .utils.gee            import (
    DEFAULT_EE_PROJECT,
    authenticate_and_initialize_ee,
    authenticate_ee,
    initialize_ee,
)
from .utils.output         import l_get_outdir, l_set_outdir
from .utils.image_utils    import get_image_with_least_cc
from .pairs                import find_pairs, export_pairs, ImagePair

__all__ = [
    "find_pairs",
    "export_pairs",
    "ImagePair",
    "load_modis_vi",
    "load_modis_ndvi",
    "MODIS_COLLECTIONS",
    "get_s2",
    "get_l8",
    "to_surface_reflection",
    "load_era5_daily",
    "ERA5_COLLECTIONS",
    "load_chirps_daily",
    "CHIRPS_COLLECTIONS",
    "CHIRPS_COLLECTION_ID",
    "CHIRPS_BAND",
    "aggregate_temporal",
    "aggregate_weekly",
    "aggregate_monthly",
    "aggregate_yearly",
    "reduce_region_stats",
    "l_export_csv",
    "l_load_band_csvs",
    "l_aggregate_csv",
    "l_plot_boxplot",
    "l_plot_timeseries",
    "l_plot_combined",
    "l_stack_plots",
    "DEFAULT_EE_PROJECT",
    "authenticate_ee",
    "initialize_ee",
    "authenticate_and_initialize_ee",
    "l_set_outdir",
    "l_get_outdir",
    "get_image_with_least_cc",
]
