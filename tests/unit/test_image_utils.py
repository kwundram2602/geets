from unittest.mock import MagicMock
import pytest


def test_get_image_with_least_cc_sorts_by_property():
    from geets.utils.image_utils import get_image_with_least_cc

    mock_img = MagicMock()
    mock_sorted = MagicMock()
    mock_sorted.first.return_value = mock_img

    mock_col = MagicMock()
    mock_col.size.return_value.getInfo.return_value = 3
    mock_col.sort.return_value = mock_sorted

    result = get_image_with_least_cc(mock_col, "CLOUDY_PIXEL_PERCENTAGE")

    mock_col.sort.assert_called_once_with("CLOUDY_PIXEL_PERCENTAGE")
    assert result is mock_img


def test_get_image_with_least_cc_default_property():
    from geets.utils.image_utils import get_image_with_least_cc

    mock_col = MagicMock()
    mock_col.size.return_value.getInfo.return_value = 1
    mock_col.sort.return_value.first.return_value = MagicMock()

    get_image_with_least_cc(mock_col)

    mock_col.sort.assert_called_once_with("CLOUDY_PIXEL_PERCENTAGE")


def test_get_image_with_least_cc_raises_on_empty_collection():
    from geets.utils.image_utils import get_image_with_least_cc

    mock_col = MagicMock()
    mock_col.size.return_value.getInfo.return_value = 0

    with pytest.raises(ValueError, match="empty"):
        get_image_with_least_cc(mock_col)
