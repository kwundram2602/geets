def test_l8_collection_id():
    from geets.optical.landsat import _L8_COLLECTION_ID
    assert _L8_COLLECTION_ID == "LANDSAT/LC08/C02/T1_L2"


def test_l8_cloud_property():
    from geets.optical.landsat import _L8_CLOUD_PROPERTY
    assert _L8_CLOUD_PROPERTY == "CLOUD_COVER"



def test_get_l8_importable_from_optical():
    from geets.optical import get_l8
    assert callable(get_l8)
