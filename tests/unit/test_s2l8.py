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


def test_to_surface_reflection_raises_on_unknown_sensor():
    from unittest.mock import MagicMock
    from geets.optical.s2l8 import to_surface_reflection
    import pytest

    with pytest.raises(ValueError, match="Unknown sensor"):
        to_surface_reflection(MagicMock(), "MODIS")


def test_to_surface_reflection_dispatches_s2():
    from unittest.mock import MagicMock, patch
    from geets.optical import s2l8

    img = MagicMock()
    with patch.object(s2l8, "_scale_s2", return_value=MagicMock()) as mock_scale:
        s2l8.to_surface_reflection(img, "S2")
        mock_scale.assert_called_once_with(img)


def test_to_surface_reflection_dispatches_l8():
    from unittest.mock import MagicMock, patch
    from geets.optical import s2l8

    img = MagicMock()
    with patch.object(s2l8, "_scale_l8", return_value=MagicMock()) as mock_scale:
        s2l8.to_surface_reflection(img, "L8")
        mock_scale.assert_called_once_with(img)
