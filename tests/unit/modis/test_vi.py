def test_load_modis_vi_raises_on_invalid_collection():
    import pytest
    from geets.modis import vi

    with pytest.raises(ValueError, match="Unknown collection"):
        vi.load_modis_vi("2023-01-01", "2024-01-01", collection="BOGUS")


def test_load_modis_vi_raises_on_lst_collection():
    import pytest
    from geets.modis import vi

    with pytest.raises(ValueError, match="Unknown collection"):
        vi.load_modis_vi("2023-01-01", "2024-01-01", collection="MOD11A1")


def test_load_modis_vi_filters_date():
    from unittest.mock import MagicMock, patch
    from geets.modis import vi

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.filterBounds.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 5

    with patch.object(vi.ee, "ImageCollection", return_value=mock_col):
        vi.load_modis_vi("2023-01-01", "2024-01-01", mask_clouds=False, apply_scale=False)
        mock_col.filterDate.assert_called_once_with("2023-01-01", "2024-01-01")


def test_load_modis_vi_applies_aoi_filter():
    from unittest.mock import MagicMock, patch
    from geets.modis import vi

    aoi = MagicMock()
    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.filterBounds.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 3

    with patch.object(vi.ee, "ImageCollection", return_value=mock_col):
        vi.load_modis_vi("2023-01-01", "2024-01-01", aoi=aoi, mask_clouds=False, apply_scale=False)
        mock_col.filterBounds.assert_called_once_with(aoi)


def test_load_modis_vi_skips_aoi_filter_when_none():
    from unittest.mock import MagicMock, patch
    from geets.modis import vi

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 3

    with patch.object(vi.ee, "ImageCollection", return_value=mock_col):
        vi.load_modis_vi("2023-01-01", "2024-01-01", mask_clouds=False, apply_scale=False)
        mock_col.filterBounds.assert_not_called()


def test_load_modis_vi_applies_cloud_mask():
    from unittest.mock import MagicMock, patch
    from geets.modis import vi

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 5

    with patch.object(vi.ee, "ImageCollection", return_value=mock_col):
        vi.load_modis_vi("2023-01-01", "2024-01-01", mask_clouds=True, apply_scale=False)
        assert mock_col.map.called


def test_load_modis_ndvi_is_alias():
    from unittest.mock import patch
    from geets.modis import vi

    with patch.object(vi, "load_modis_vi") as mock_vi:
        vi.load_modis_ndvi("2023-01-01", "2024-01-01", collection="MOD13Q1")
        mock_vi.assert_called_once_with(
            start_date="2023-01-01",
            end_date="2024-01-01",
            aoi=None,
            collection="MOD13Q1",
            band="NDVI",
            apply_scale=True,
            mask_clouds=True,
            max_qa=vi._QA_MARGINAL,
        )


def test_load_modis_vi_keeps_both_bands_when_band_is_none():
    from unittest.mock import MagicMock, patch
    from geets.modis import vi

    mock_col = MagicMock()
    mock_col.filterDate.return_value = mock_col
    mock_col.select.return_value = mock_col
    mock_col.map.return_value = mock_col
    mock_col.size.return_value.getInfo.return_value = 5

    with patch.object(vi.ee, "ImageCollection", return_value=mock_col):
        vi.load_modis_vi("2023-01-01", "2024-01-01", band=None, mask_clouds=False, apply_scale=False)
        # Only the initial select(["NDVI", "EVI", "SummaryQA"]) should be called;
        # the second select([band, qa]) must be skipped when band is None.
        assert mock_col.select.call_count == 1
