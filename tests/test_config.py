"""Tests for configuration loading, validation, and session persistence."""

import pytest

from slsd import config
from slsd.config import ConfigError, load_api_credentials, load_config, save_session

VALID = """
[credentials]
api_key = "key123"
api_secret = "secret456"
session_key = "sess789"
username = "alice"

[options]
blacklist = ["spotify"]
threshold = 30
"""

LEGACY = """
[credentials]
username = "bob"
password = "hunter2"
api_key = "key123"
api_secret = "secret456"
"""

MINIMAL_API_ONLY = """
[credentials]
api_key = "key123"
api_secret = "secret456"
"""


def write_config(tmp_path, content):
    cfg_dir = tmp_path / "slsd"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = cfg_dir / "config.toml"
    cfg_file.write_text(content)
    return cfg_file


def test_missing_config_falls_back_to_bundled_keys(tmp_path):
    api_key, api_secret = load_api_credentials(tmp_path / "nonexistent.toml")
    assert api_key == config.BUNDLED_API_KEY
    assert api_secret == config.BUNDLED_API_SECRET


def test_blank_user_keys_fall_back_to_bundled(tmp_path):
    path = write_config(tmp_path, '[credentials]\napi_key = ""\napi_secret = ""\n')
    assert load_api_credentials(path) == (
        config.BUNDLED_API_KEY,
        config.BUNDLED_API_SECRET,
    )


def test_user_keys_override_bundled(tmp_path):
    path = write_config(
        tmp_path, '[credentials]\napi_key = "mine"\napi_secret = "also_mine"\n'
    )
    assert load_api_credentials(path) == ("mine", "also_mine")


def test_load_config_with_no_file_reports_missing_auth(tmp_path):
    with pytest.raises(ConfigError) as exc:
        load_config(tmp_path / "nonexistent.toml")
    assert "slsd setup" in str(exc.value)


def test_malformed_toml(tmp_path):
    path = write_config(tmp_path, "[credentials\napi_key = ")
    with pytest.raises(ConfigError, match="parse"):
        load_config(path)


def test_missing_credentials_section(tmp_path):
    path = write_config(tmp_path, '[options]\nthreshold = 5\n')
    with pytest.raises(ConfigError, match="credentials"):
        load_config(path)


def test_no_auth_method(tmp_path):
    path = write_config(tmp_path, MINIMAL_API_ONLY)
    with pytest.raises(ConfigError) as exc:
        load_config(path)
    assert "slsd setup" in str(exc.value)


def test_session_mode_loads(tmp_path):
    path = write_config(tmp_path, VALID)
    cfg = load_config(path)
    assert cfg.auth_mode == "session"
    assert cfg.session_key == "sess789"
    assert cfg.username == "alice"
    assert cfg.password_hash is None


def test_legacy_password_mode_loads(tmp_path):
    path = write_config(tmp_path, LEGACY)
    cfg = load_config(path)
    assert cfg.auth_mode == "password"
    assert cfg.session_key is None
    assert cfg.password_hash == config.hash_password("hunter2")
    assert len(cfg.password_hash) == 32


def test_options_defaults_and_values(tmp_path):
    path = write_config(
        tmp_path,
        MINIMAL_API_ONLY + 'session_key = "s"\nusername = "u"\n',
    )
    cfg = load_config(path)
    assert cfg.blacklist == []
    assert cfg.threshold == 0.0


def config_with_options(options_body: str) -> str:
    return (
        MINIMAL_API_ONLY
        + 'session_key = "s"\nusername = "u"\n\n[options]\n'
        + options_body
    )


def test_invalid_blacklist(tmp_path):
    path = write_config(tmp_path, config_with_options('blacklist = "spotify"\n'))
    with pytest.raises(ConfigError, match="blacklist"):
        load_config(path)


def test_invalid_threshold(tmp_path):
    path = write_config(tmp_path, config_with_options("threshold = -5\n"))
    with pytest.raises(ConfigError, match="threshold"):
        load_config(path)


def test_save_session_creates_new_config(tmp_path):
    path = tmp_path / "new" / "config.toml"
    save_session("sk1", "alice", path=path)
    text = path.read_text()
    assert 'session_key = "sk1"' in text
    assert 'username = "alice"' in text


def test_save_session_preserves_comments_and_options(tmp_path):
    original = """# my personal slsd config
[credentials]
api_key = "key123"
api_secret = "secret456"

[options]
# browsers leak everything
blacklist = ["firefox"]
threshold = 10
"""
    path = write_config(tmp_path, original)
    save_session("sk_new", "carol", path=path)
    result = path.read_text()

    assert "# my personal slsd config" in result
    assert "# browsers leak everything" in result
    assert 'blacklist = ["firefox"]' in result
    assert 'threshold = 10' in result
    assert 'session_key = "sk_new"' in result
    assert 'username = "carol"' in result

    cfg = load_config(path)
    assert cfg.session_key == "sk_new"
    assert cfg.username == "carol"
    assert cfg.threshold == 10.0
    assert cfg.blacklist == ["firefox"]


def test_save_session_replaces_existing_session(tmp_path):
    path = write_config(tmp_path, VALID)
    save_session("fresh", "dave", path=path)

    cfg = load_config(path)
    assert cfg.session_key == "fresh"
    assert cfg.username == "dave"


def test_xdg_config_home_respected(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config.config_file() == tmp_path / "slsd" / "config.toml"


def test_hash_password_is_md5():
    assert config.hash_password("hunter2") == "2ab96390c7dbe3439de74d0c9b0b1767"
