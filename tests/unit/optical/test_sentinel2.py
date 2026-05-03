def test_s2_collection_id():
    from geets.optical.sentinel2 import _S2_COLLECTION_ID
    assert _S2_COLLECTION_ID == "COPERNICUS/S2_SR_HARMONIZED"


def test_s2_cloud_property():
    from geets.optical.sentinel2 import _S2_CLOUD_PROPERTY
    assert _S2_CLOUD_PROPERTY == "CLOUDY_PIXEL_PERCENTAGE"



def test_get_s2_importable_from_optical():
    from geets.optical import get_s2
    assert callable(get_s2)
