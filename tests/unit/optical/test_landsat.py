def test_l8_collection_id():
    from geets.optical.landsat import _L8_COLLECTION_ID
    assert _L8_COLLECTION_ID == "LANDSAT/LC08/C02/T1_L2"


def test_l8_cloud_property():
    from geets.optical.landsat import _L8_CLOUD_PROPERTY
    assert _L8_CLOUD_PROPERTY == "CLOUD_COVER"


def test_get_l8_raises_on_invalid_band():
    from unittest.mock import MagicMock

    import pytest

    from geets.optical.landsat import get_l8

    with pytest.raises(ValueError, match="Unknown band"):
        get_l8("2022-01-01", "2022-03-01", MagicMock(), bands=["INVALID_BAND"])


def test_get_l8_importable_from_optical():
    from geets.optical import get_l8
    assert callable(get_l8)
