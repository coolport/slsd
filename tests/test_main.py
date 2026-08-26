"""Tests for CLI wiring and the `slsd setup` command."""

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

import slsd.main as main
from slsd.config import Config, load_config, save_session

runner = CliRunner()


class TestBuildScrobbler:
    def test_maps_session_config(self):
        cfg = Config(api_key="k", api_secret="s", session_key="sk", username="u")
        scrobbler = main.build_scrobbler(cfg)
        assert scrobbler.session_key == "sk"
        assert scrobbler.username == "u"
        assert scrobbler.password_hash is None

    def test_maps_password_config(self):
        cfg = Config(api_key="k", api_secret="s", username="u", password_hash="h")
        scrobbler = main.build_scrobbler(cfg)
        assert scrobbler.password_hash == "h"
        assert scrobbler.session_key is None


class TestHandleScrobble:
    def test_success_does_not_raise(self):
        scrobbler = MagicMock()
        scrobbler.scrobble.return_value = None
        main.asyncio.run(main.handle_scrobble(scrobbler, "A", "T"))
        scrobbler.scrobble.assert_called_once_with("A", "T")

    def test_auth_error_is_logged_not_raised(self):
        import slsd.lastfm as lastfm_mod

        scrobbler = MagicMock()
        scrobbler.scrobble.side_effect = lastfm_mod.AuthError("run slsd setup")
        main.asyncio.run(main.handle_scrobble(scrobbler, "A", "T"))

    def test_generic_error_is_logged_not_raised(self):
        scrobbler = MagicMock()
        scrobbler.scrobble.side_effect = RuntimeError("boom")
        main.asyncio.run(main.handle_scrobble(scrobbler, "A", "T"))


class TestSetupCommand:
    def _patch_auth_flow(self, monkeypatch, session=("sk_new", "alice")):
        generator = MagicMock()
        generator.get_web_auth_session_key_username.return_value = session
        monkeypatch.setattr(
            main, "create_web_auth_url", lambda k, s: (generator, "https://last.fm/auth")
        )
        monkeypatch.setattr(main, "open_browser", lambda url: True)
        return generator

    def test_setup_saves_session(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        save_dir = tmp_path / "slsd"
        save_dir.mkdir()
        (save_dir / "config.toml").write_text(
            '[credentials]\napi_key = "key123"\napi_secret = "secret456"\n'
        )
        self._patch_auth_flow(monkeypatch)

        result = runner.invoke(main.app, ["setup"])

        assert result.exit_code == 0
        assert "Successfully authenticated as alice" in result.output

        cfg = load_config()
        assert cfg.session_key == "sk_new"
        assert cfg.username == "alice"
        assert cfg.auth_mode == "session"

    def test_setup_without_api_credentials_fails_cleanly(self, tmp_path, monkeypatch, caplog):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

        with caplog.at_level("ERROR", logger="slsd"):
            result = runner.invoke(main.app, ["setup"])

        assert result.exit_code == 1
        assert any("api_key" in record.message for record in caplog.records)


class TestRunCommand:
    def test_run_without_config_exits_cleanly(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

        result = runner.invoke(main.app, ["run"])

        assert result.exit_code == 1
