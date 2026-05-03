def test_load_modis_sr_raises_on_invalid_collection():
    import pytest
    from geets.modis import sr

    with pytest.raises(ValueError, match="Unknown collection"):
        sr.load_modis_sr("2023-01-01", "2024-01-01", collection="MOD13Q1")


def test_load_modis_sr_filters_date():
    from unittest.mock import MagicMock, patch
    from geets.modis import sr

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 10

    with patch.object(sr.ee, "ImageCollection", return_value=mock_col):
        sr.load_modis_sr("2023-01-01", "2024-01-01", mask_clouds=False, apply_scale=False)
        mock_col.filterDate.assert_called_once_with("2023-01-01", "2024-01-01")


def test_load_modis_sr_applies_aoi_filter():
    from unittest.mock import MagicMock, patch
    from geets.modis import sr

    aoi = MagicMock()
    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.filterBounds.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 10

    with patch.object(sr.ee, "ImageCollection", return_value=mock_col):
        sr.load_modis_sr("2023-01-01", "2024-01-01", aoi=aoi, mask_clouds=False, apply_scale=False)
        mock_col.filterBounds.assert_called_once_with(aoi)


def test_load_modis_sr_skips_aoi_when_none():
    from unittest.mock import MagicMock, patch
    from geets.modis import sr

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 10

    with patch.object(sr.ee, "ImageCollection", return_value=mock_col):
        sr.load_modis_sr("2023-01-01", "2024-01-01", mask_clouds=False, apply_scale=False)
        mock_col.filterBounds.assert_not_called()


def test_load_modis_sr_applies_scale():
    from unittest.mock import MagicMock, patch
    from geets.modis import sr

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 10

    with patch.object(sr.ee, "ImageCollection", return_value=mock_col):
        sr.load_modis_sr("2023-01-01", "2024-01-01", mask_clouds=False, apply_scale=True)
        # Only the scale map should fire (mask_clouds=False skips QA map).
        assert mock_col.map.call_count == 1


def test_load_modis_sr_accepts_band_subset():
    from unittest.mock import MagicMock, patch
    from geets.modis import sr

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 10

    with patch.object(sr.ee, "ImageCollection", return_value=mock_col):
        sr.load_modis_sr("2023-01-01", "2024-01-01",
                         bands=["sur_refl_b01", "sur_refl_b02"],
                         mask_clouds=False, apply_scale=False)
        mock_col.select.assert_any_call(["sur_refl_b01", "sur_refl_b02"])
