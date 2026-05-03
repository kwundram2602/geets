def test_load_modis_lst_raises_on_invalid_collection():
    import pytest
    from geets.modis import lst

    with pytest.raises(ValueError, match="Unknown collection"):
        lst.load_modis_lst("2023-01-01", "2024-01-01", collection="MOD13Q1")


def test_load_modis_lst_raises_on_invalid_time_of_day():
    import pytest
    from geets.modis import lst

    with pytest.raises(ValueError, match="time_of_day"):
        lst.load_modis_lst("2023-01-01", "2024-01-01", time_of_day="noon")


def test_load_modis_lst_filters_date():
    from unittest.mock import MagicMock, patch
    from geets.modis import lst

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 4

    with patch.object(lst.ee, "ImageCollection", return_value=mock_col):
        lst.load_modis_lst("2023-01-01", "2024-01-01", mask_clouds=False, apply_scale=False)
        mock_col.filterDate.assert_called_once_with("2023-01-01", "2024-01-01")


def test_load_modis_lst_applies_aoi_filter():
    from unittest.mock import MagicMock, patch
    from geets.modis import lst

    aoi = MagicMock()
    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.filterBounds.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 4

    with patch.object(lst.ee, "ImageCollection", return_value=mock_col):
        lst.load_modis_lst("2023-01-01", "2024-01-01", aoi=aoi, mask_clouds=False, apply_scale=False)
        mock_col.filterBounds.assert_called_once_with(aoi)


def test_load_modis_lst_selects_day_band():
    from unittest.mock import MagicMock, patch, call
    from geets.modis import lst

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 4

    with patch.object(lst.ee, "ImageCollection", return_value=mock_col):
        lst.load_modis_lst("2023-01-01", "2024-01-01", time_of_day="day",
                           mask_clouds=False, apply_scale=False)
        mock_col.select.assert_any_call(["LST_Day_1km", "QC_Day"])


def test_load_modis_lst_selects_night_band():
    from unittest.mock import MagicMock, patch
    from geets.modis import lst

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 4

    with patch.object(lst.ee, "ImageCollection", return_value=mock_col):
        lst.load_modis_lst("2023-01-01", "2024-01-01", time_of_day="night",
                           mask_clouds=False, apply_scale=False)
        mock_col.select.assert_any_call(["LST_Night_1km", "QC_Night"])
