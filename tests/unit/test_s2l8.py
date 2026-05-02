def test_band_lists_have_equal_length():
    from geets.optical.s2l8 import _S2_BANDS_SRC, _L8_BANDS_SRC, _BANDS_HARMONIZED
    assert len(_S2_BANDS_SRC) == len(_BANDS_HARMONIZED)
    assert len(_L8_BANDS_SRC) == len(_BANDS_HARMONIZED)


def test_s2_band_src_contains_expected_bands():
    from geets.optical.s2l8 import _S2_BANDS_SRC
    assert _S2_BANDS_SRC == ["B2", "B3", "B4", "B8", "B11", "B12"]


def test_l8_band_src_contains_expected_bands():
    from geets.optical.s2l8 import _L8_BANDS_SRC
    assert _L8_BANDS_SRC == ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"]


def test_harmonized_bands():
    from geets.optical.s2l8 import _BANDS_HARMONIZED
    assert _BANDS_HARMONIZED == ["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2"]


def test_collection_ids_are_defined():
    from geets.optical.s2l8 import _S2_COLLECTION_ID, _L8_COLLECTION_ID
    assert _S2_COLLECTION_ID == "COPERNICUS/S2_SR_HARMONIZED"
    assert _L8_COLLECTION_ID == "LANDSAT/LC08/C02/T1_L2"
