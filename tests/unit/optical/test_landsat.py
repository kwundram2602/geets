def test_l8_collection_id():
    from geets.optical.landsat import _L8_COLLECTION_ID
    assert _L8_COLLECTION_ID == "LANDSAT/LC08/C02/T1_L2"


def test_lc_cloud_property():
    from geets.optical.landsat import _LC_CLOUD_PROPERTY
    assert _LC_CLOUD_PROPERTY == "CLOUD_COVER"


def test_lc_helpers_importable():
    from geets.optical.landsat import (
        _mask_lc_qa_pixel,
        _scale_lc_sr,
        _rename_lc_sr,
        _ndvi_lc,
        _emissivity_lc,
        thermal_scaling_lc,
        land_surface_temperature_lc,
        add_lst_lc,
    )
    assert all(callable(f) for f in [
        _mask_lc_qa_pixel, _scale_lc_sr, _rename_lc_sr, _ndvi_lc,
        _emissivity_lc, thermal_scaling_lc, land_surface_temperature_lc, add_lst_lc,
    ])


def test_get_l8_importable_from_optical():
    from geets.optical import get_l8
    assert callable(get_l8)


def test_l9_collection_id():
    from geets.optical.landsat import _L9_COLLECTION_ID
    assert _L9_COLLECTION_ID == "LANDSAT/LC09/C02/T1_L2"


def test_get_l9_importable_from_optical():
    from geets.optical import get_l9
    assert callable(get_l9)


def test_get_l8l9_importable_from_optical():
    from geets.optical import get_l8l9
    assert callable(get_l8l9)
