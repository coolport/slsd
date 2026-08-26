"""Tests for the Scrobbler and Last.fm web authentication flow."""

import asyncio

import pylast
import pytest
from unittest.mock import MagicMock, patch

from slsd import lastfm
from slsd.lastfm import (
    AuthError,
    Scrobbler,
    open_browser,
    wait_for_authorization,
)

API_KEY = "test_api_key"
API_SECRET = "test_api_secret"


def ws_error(status: str, details: str = "error") -> pylast.WSError:
    return pylast.WSError(MagicMock(), status, details)


def test_scrobbler_requires_credentials():
    with pytest.raises(ValueError):
        Scrobbler(api_key=API_KEY, api_secret=API_SECRET)


def test_session_mode_network_kwargs():
    with patch.object(pylast, "LastFMNetwork") as network_cls:
        scrobbler = Scrobbler(API_KEY, API_SECRET, session_key="sk123")
        network_cls.assert_not_called()

        scrobbler.connect()
        network_cls.assert_called_once_with(
            api_key=API_KEY, api_secret=API_SECRET, session_key="sk123"
        )

        scrobbler.connect()
        network_cls.assert_called_once()


def test_password_mode_network_kwargs():
    with patch.object(pylast, "LastFMNetwork") as network_cls:
        scrobbler = Scrobbler(
            API_KEY, API_SECRET, username="alice", password_hash="hash"
        )
        scrobbler.connect()
        network_cls.assert_called_once_with(
            api_key=API_KEY,
            api_secret=API_SECRET,
            username="alice",
            password_hash="hash",
        )


def test_scrobble_success():
    with patch.object(pylast, "LastFMNetwork") as network_cls:
        network = network_cls.return_value
        scrobbler = Scrobbler(API_KEY, API_SECRET, session_key="sk")
        scrobbler.scrobble("Artist", "Title")

        assert network.scrobble.call_count == 1
        kwargs = network.scrobble.call_args.kwargs
        assert kwargs["artist"] == "Artist"
        assert kwargs["title"] == "Title"
        assert isinstance(kwargs["timestamp"], int)


def test_auth_error_translated_and_network_reset():
    with patch.object(pylast, "LastFMNetwork") as network_cls:
        network = network_cls.return_value
        network.scrobble.side_effect = ws_error("9", "Invalid session key")

        scrobbler = Scrobbler(API_KEY, API_SECRET, session_key="bad")
        with pytest.raises(AuthError) as exc:
            scrobbler.scrobble("A", "T")
        assert "slsd setup" in str(exc.value)

        assert scrobbler.network is None


def test_other_errors_pass_through():
    with patch.object(pylast, "LastFMNetwork") as network_cls:
        network = network_cls.return_value
        original = ws_error("8", "Operation failed")
        network.scrobble.side_effect = original

        scrobbler = Scrobbler(API_KEY, API_SECRET, session_key="sk")
        with pytest.raises(pylast.WSError):
            scrobbler.scrobble("A", "T")


class FakeGenerator:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def get_web_auth_session_key_username(self, url):
        self.calls += 1
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def test_wait_for_authorization_polls_until_authorized():
    generator = FakeGenerator(
        [
            ws_error("14", "This token is not authorized"),
            ws_error("14", "This token is not authorized"),
            ("sessionkey1", "alice"),
        ]
    )

    key, username = wait_for_authorization(
        generator, "http://url", timeout=5, poll_interval=0.01
    )

    assert (key, username) == ("sessionkey1", "alice")
    assert generator.calls == 3


def test_wait_for_authorization_timeout_mentions_setup():
    generator = FakeGenerator([ws_error("14", "not authorized")] * 100)

    with pytest.raises(AuthError) as exc:
        wait_for_authorization(generator, "http://url", timeout=0.05, poll_interval=0.01)
    assert "slsd setup" in str(exc.value)


def test_wait_for_authorization_fatal_error_raises_immediately():
    generator = FakeGenerator([ws_error("4", "Authentication Failed")])

    with pytest.raises(AuthError):
        wait_for_authorization(generator, "http://url", timeout=5, poll_interval=0.01)


def test_open_browser_handles_failure():
    def boom(url):
        raise RuntimeError("no browser")

    assert open_browser("http://url", opener=boom) is False


def test_open_browser_success():
    assert open_browser("http://url", opener=lambda url: True) is True


def test_create_web_auth_url_builds_lastfm_url():
    fake_generator = MagicMock()
    fake_generator.get_web_auth_url.return_value = (
        "https://www.last.fm/api/auth/?api_key=k&token=t"
    )

    with (
        patch.object(pylast, "LastFMNetwork"),
        patch.object(
            pylast, "SessionKeyGenerator", return_value=fake_generator
        ) as skg_cls,
    ):
        generator, url = lastfm.create_web_auth_url(API_KEY, API_SECRET)

    skg_cls.assert_called_once()
    assert "last.fm/api/auth" in url
