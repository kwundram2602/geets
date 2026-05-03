def test_bands_harmonized_values():
    from geets.optical.common import _BANDS_HARMONIZED
    assert _BANDS_HARMONIZED == ["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2"]


def test_s2_bands_src_values():
    from geets.optical.common import _S2_BANDS_SRC
    assert _S2_BANDS_SRC == ["B2", "B3", "B4", "B8", "B11", "B12"]


def test_l8_bands_src_values():
    from geets.optical.common import _L8_BANDS_SRC
    assert _L8_BANDS_SRC == ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"]


def test_band_lists_same_length():
    from geets.optical.common import _BANDS_HARMONIZED, _S2_BANDS_SRC, _L8_BANDS_SRC
    assert len(_S2_BANDS_SRC) == len(_BANDS_HARMONIZED)
    assert len(_L8_BANDS_SRC) == len(_BANDS_HARMONIZED)


def test_to_surface_reflection_raises_on_unknown_sensor():
    from unittest.mock import MagicMock
    from geets.optical.common import to_surface_reflection
    import pytest

    with pytest.raises(ValueError, match="Unknown sensor"):
        to_surface_reflection(MagicMock(), "MODIS")


def test_to_surface_reflection_s2_selects_s2_bands():
    from unittest.mock import MagicMock
    from geets.optical.common import to_surface_reflection, _S2_BANDS_SRC

    img = MagicMock()
    to_surface_reflection(img, "S2")
    img.select.assert_called_once_with(_S2_BANDS_SRC)


def test_to_surface_reflection_l8_selects_l8_bands():
    from unittest.mock import MagicMock
    from geets.optical.common import to_surface_reflection, _L8_BANDS_SRC

    img = MagicMock()
    to_surface_reflection(img, "L8")
    img.select.assert_called_once_with(_L8_BANDS_SRC)
