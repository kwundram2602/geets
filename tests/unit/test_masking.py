"""Masking options: every mask and its parameters reach the loaders."""

import inspect
from unittest.mock import MagicMock, patch

import pytest

from geets import files
from geets.optical import landsat, sentinel2


def test_resolve_qa_bits_by_name_and_number():
    assert landsat.resolve_qa_bits(["cloud", "cloud_shadow"]) == [3, 4]
    assert landsat.resolve_qa_bits([1, "snow"]) == [1, 5]
    assert landsat.resolve_qa_bits(None) == [1, 2, 3, 4]
    assert landsat.resolve_qa_bits([]) == []


def test_resolve_qa_bits_rejects_unknown():
    with pytest.raises(ValueError, match="clouds"):
        landsat.resolve_qa_bits(["clouds"])


@pytest.mark.parametrize("func", [landsat.get_l8, landsat.get_l9, landsat.get_l8l9])
def test_landsat_loaders_expose_qa_options(func):
    params = inspect.signature(func).parameters
    assert {"mask_clouds", "qa_bits", "mask_saturated"} <= set(params)


def test_get_s2_exposes_all_mask_parameters():
    params = inspect.signature(sentinel2.get_s2).parameters
    expected = {
        "mask_clouds",
        "mask_cirrus",
        "mask_water",
        "use_s2cloudless",
        "cld_prb_thresh",
        "nir_drk_thresh",
        "cld_prj_dist",
        "buffer",
    }
    assert expected <= set(params)


def _call(dataset, loader_name, **options):
    loader = MagicMock()
    with patch(f"geets.files.{loader_name}", loader):
        files.load_collection(dataset, "2024-01-01", "2024-02-01", "AOI", **options)
    return loader.call_args.kwargs


def test_s2_options_are_forwarded():
    kwargs = _call(
        "s2",
        "get_s2",
        use_s2cloudless=True,
        cld_prb_thresh=30,
        buffer=100,
        mask_clouds=False,
    )
    assert kwargs["use_s2cloudless"] is True and kwargs["cld_prb_thresh"] == 30
    assert kwargs["buffer"] == 100 and kwargs["mask_clouds"] is False


def test_landsat_masking_on_by_default_but_switchable():
    assert _call("l8l9", "get_l8l9")["mask_clouds"] is True
    kwargs = _call("l8l9", "get_l8l9", mask_clouds=False)
    assert kwargs["mask_clouds"] is False and kwargs["scale"] is True
    kwargs = _call("l9", "get_l9", qa_bits=["cloud"], mask_saturated=False)
    assert kwargs["qa_bits"] == ["cloud"] and kwargs["mask_saturated"] is False


def test_modis_options_are_forwarded():
    assert _call("modis_ndvi", "load_modis_vi", max_qa=0)["max_qa"] == 0
    assert (
        _call("modis_lst_day", "load_modis_lst", mask_clouds=False)["mask_clouds"]
        is False
    )


@pytest.mark.parametrize(
    ("dataset", "option"),
    [
        ("modis_lst_day", "max_qa"),
        ("era5:ERA5_LAND", "max_cloud_cover"),
        ("s2", "qa_bits"),
    ],
)
def test_options_not_applicable_to_dataset_are_rejected(dataset, option):
    with pytest.raises(ValueError, match=f"{option}.*not available"):
        files.load_collection(dataset, "2024-01-01", "2024-02-01", "AOI", **{option: 1})
