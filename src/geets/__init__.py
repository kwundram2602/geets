"""
geets – Google Earth Engine Tools for Earth Science
"""

from .climate.chirps import (
    CHIRPS_BAND,
    CHIRPS_COLLECTION_ID,
    CHIRPS_COLLECTIONS,
    load_chirps_daily,
)
from .climate.era5 import ERA5_COLLECTIONS, load_era5_daily
from .modis import MODIS_SETS, load_modis_ndvi, load_modis_vi
from .optical.s2l8 import get_l8, get_s2, to_surface_reflection
from .pairs import ImagePair, export_pairs, find_pairs
from .terrain.dem import (
    DEM_COLLECTIONS,
    DemProduct,
    load_aster,
    load_copernicus_dem,
    load_nasadem,
    load_srtm,
)
from .timeseries.aggregate import (
    aggregate_monthly,
    aggregate_temporal,
    aggregate_weekly,
    aggregate_yearly,
)
from .timeseries.plot import (
    l_plot_boxplot,
    l_plot_combined,
    l_plot_timeseries,
    l_stack_plots,
)
from .timeseries.reduce import (
    l_aggregate_csv,
    l_export_csv,
    l_load_band_csvs,
    reduce_region_stats,
)
from .utils.exports import (
    export_image_to_drive,
    export_imagecollection_to_drive,
    l_download_image,
    l_download_imagecollection,
)
from .utils.gee import (
    DEFAULT_EE_PROJECT,
    authenticate_and_initialize_ee,
    authenticate_ee,
    initialize_ee,
)
from .utils.image_utils import get_image_with_least_cc
from .utils.output import l_get_outdir, l_set_outdir

__all__ = [
    "find_pairs",
    "export_pairs",
    "ImagePair",
    "load_modis_vi",
    "load_modis_ndvi",
    "MODIS_SETS",
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
    "l_download_image",
    "l_download_imagecollection",
    "export_image_to_drive",
    "export_imagecollection_to_drive",
    "DEM_COLLECTIONS",
    "DemProduct",
    "load_copernicus_dem",
    "load_srtm",
    "load_aster",
    "load_nasadem",
]
