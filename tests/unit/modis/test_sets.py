def test_modis_sets_is_dict():
    from geets.modis import sets
    assert isinstance(sets.MODIS_SETS, dict)


def test_modis_sets_has_vi_collections():
    from geets.modis import sets
    vi_keys = {k for k, v in sets.MODIS_SETS.items() if v["product"] == "vi"}
    assert {"MOD13Q1", "MOD13A1", "MOD13A3", "MYD13Q1"}.issubset(vi_keys)


def test_modis_sets_has_lst_collections():
    from geets.modis import sets
    lst_keys = {k for k, v in sets.MODIS_SETS.items() if v["product"] == "lst"}
    assert {"MOD11A1", "MOD11A2", "MYD11A1", "MYD11A2"}.issubset(lst_keys)


def test_modis_sets_has_sr_collections():
    from geets.modis import sets
    sr_keys = {k for k, v in sets.MODIS_SETS.items() if v["product"] == "sr"}
    assert {"MOD09GQ", "MOD09GA", "MOD09A1", "MOD09Q1", "MYD09GQ", "MYD09GA"}.issubset(sr_keys)


def test_modis_sets_has_fire_collections():
    from geets.modis import sets
    fire_keys = {k for k, v in sets.MODIS_SETS.items() if v["product"] == "fire"}
    assert {"MCD64A1", "MOD14A1", "MOD14A2"}.issubset(fire_keys)


def test_modis_sets_entry_shape():
    from geets.modis import sets
    required = {"id", "product", "description", "start", "end", "resolution_m", "cadence"}
    for key, entry in sets.MODIS_SETS.items():
        missing = required - entry.keys()
        assert not missing, f"{key} missing fields: {missing}"


def test_modis_sets_ids_start_with_modis():
    from geets.modis import sets
    for key, entry in sets.MODIS_SETS.items():
        assert entry["id"].startswith("MODIS/"), f"{key} id should start with MODIS/"


def test_modis_sets_resolution_m_is_int():
    from geets.modis import sets
    for key, entry in sets.MODIS_SETS.items():
        assert isinstance(entry["resolution_m"], int), f"{key} resolution_m must be int"


def test_modis_sets_ids_use_06x_namespace():
    import re
    from geets.modis import sets
    for key, entry in sets.MODIS_SETS.items():
        assert re.match(r"MODIS/06\d/", entry["id"]), (
            f"{key} id should be in MODIS/06x/ namespace, got: {entry['id']}"
        )
