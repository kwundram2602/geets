import pytest

from geets import config


@pytest.fixture
def env_file(tmp_path, monkeypatch):
    path = tmp_path / "geets" / ".env"
    monkeypatch.setenv(config.ENV_VAR, str(path))
    return path


def test_config_path_override(env_file):
    assert config.config_path() == env_file


def test_load_config_missing_file_returns_known_keys_empty(env_file):
    assert config.load_config() == {"EE_PROJECT": ""}


def test_save_config_creates_file_with_mode_600(env_file):
    config.save_config({"EE_PROJECT": "my-proj"})
    assert env_file.read_text() == "EE_PROJECT=my-proj\n"
    assert env_file.stat().st_mode & 0o777 == 0o600
    assert config.load_config()["EE_PROJECT"] == "my-proj"


def test_save_config_keeps_comments_and_unknown_keys(env_file):
    env_file.parent.mkdir(parents=True)
    env_file.write_text('# note\nOTHER="x y"\nEE_PROJECT=old\n')
    config.save_config({"EE_PROJECT": "new"})
    assert env_file.read_text() == '# note\nOTHER="x y"\nEE_PROJECT=new\n'
    assert config.load_config() == {"EE_PROJECT": "new", "OTHER": "x y"}


def test_save_config_empty_value_removes_key(env_file):
    config.save_config({"EE_PROJECT": "p"})
    config.save_config({"EE_PROJECT": ""})
    assert "EE_PROJECT" not in env_file.read_text()


def test_init_without_project_names_the_file(env_file, monkeypatch):
    monkeypatch.delenv("EE_PROJECT", raising=False)
    with pytest.raises(ValueError, match=str(env_file)):
        config.init_from_config()


def test_ee_status_without_credentials(env_file, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "EE_CREDENTIALS", tmp_path / "missing")
    status = config.ee_status()
    assert status["ok"] is False and status["credentials"] is False
