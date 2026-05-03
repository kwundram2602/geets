def test_load_modis_fire_raises_on_invalid_collection():
    import pytest
    from geets.modis import fire

    with pytest.raises(ValueError, match="Unknown collection"):
        fire.load_modis_fire("2023-01-01", "2024-01-01", collection="MOD13Q1")


def test_load_modis_fire_filters_date():
    from unittest.mock import MagicMock, patch
    from geets.modis import fire

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 6

    with patch.object(fire.ee, "ImageCollection", return_value=mock_col):
        fire.load_modis_fire("2023-01-01", "2024-01-01")
        mock_col.filterDate.assert_called_once_with("2023-01-01", "2024-01-01")


def test_load_modis_fire_applies_aoi_filter():
    from unittest.mock import MagicMock, patch
    from geets.modis import fire

    aoi = MagicMock()
    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.filterBounds.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 6

    with patch.object(fire.ee, "ImageCollection", return_value=mock_col):
        fire.load_modis_fire("2023-01-01", "2024-01-01", aoi=aoi)
        mock_col.filterBounds.assert_called_once_with(aoi)


def test_load_modis_fire_skips_aoi_when_none():
    from unittest.mock import MagicMock, patch
    from geets.modis import fire

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 6

    with patch.object(fire.ee, "ImageCollection", return_value=mock_col):
        fire.load_modis_fire("2023-01-01", "2024-01-01")
        mock_col.filterBounds.assert_not_called()


def test_load_modis_fire_defaults_to_mcd64a1():
    from unittest.mock import MagicMock, patch
    from geets.modis import fire

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 6

    with patch.object(fire.ee, "ImageCollection", return_value=mock_col) as mock_ic:
        fire.load_modis_fire("2023-01-01", "2024-01-01")
        args = mock_ic.call_args[0]
        assert "MCD64A1" in args[0]
