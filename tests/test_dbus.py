"""Tests for MPrisPlayer scrobble state machine and ServiceManager lifecycle."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from slsd.dbus import MPrisPlayer, ServiceManager

LONG_TRACK_US = 200_000_000  # 200s -> standard delay 100s


def variant(value):
    return SimpleNamespace(value=value)


def metadata(artist="Artist", title="Title", length=LONG_TRACK_US):
    return {
        "Metadata": variant(
            {
                "xesam:artist": variant([artist]),
                "xesam:title": variant(title),
                "mpris:length": variant(length),
            }
        )
    }


def status(value):
    return {"PlaybackStatus": variant(value)}


def merged(*prop_dicts):
    out = {}
    for d in prop_dicts:
        out.update(d)
    return out


def make_player(**kwargs):
    kwargs.setdefault("threshold", 0)
    return MPrisPlayer(
        "org.mpris.MediaPlayer2.test", "/org/mpris/MediaPlayer2", **kwargs
    )


class HangingDelay:
    """Replaces _scrobble_after_delay; records the requested delay and hangs."""

    def __init__(self, player):
        self.player = player
        self.delay = None
        self.started = 0

    async def __call__(self, delay_sec):
        self.delay = delay_sec
        self.started += 1
        await asyncio.sleep(3600)


def attach_hanging_spy(player):
    spy = HangingDelay(player)
    player._scrobble_after_delay = spy
    return spy


async def feed(player, *prop_dicts):
    await player.property_change_callback("iface", merged(*prop_dicts), [])
    await asyncio.sleep(0)


async def cancel_pending_timer(player):
    if player.scrobble_task:
        player.scrobble_task.cancel()
        try:
            await player.scrobble_task
        except asyncio.CancelledError:
            pass
        player.scrobble_task = None


class TestScheduling:
    def test_playing_long_track_schedules_half_length(self):
        player = make_player(callback=AsyncMock())

        async def scenario():
            spy = attach_hanging_spy(player)
            await feed(player, metadata(), status("Playing"))
            assert player.scrobble_task is not None
            assert spy.delay == pytest.approx(100.0)
            await cancel_pending_timer(player)

        asyncio.run(scenario())

    def test_four_minute_cap_applied(self):
        player = make_player(callback=AsyncMock())

        async def scenario():
            spy = attach_hanging_spy(player)
            await feed(player, metadata(length=1200_000_000), status("Playing"))
            assert spy.delay == pytest.approx(240.0)
            await cancel_pending_timer(player)

        asyncio.run(scenario())

    def test_user_threshold_caps_delay(self):
        player = make_player(callback=AsyncMock(), threshold=30)

        async def scenario():
            spy = attach_hanging_spy(player)
            await feed(player, metadata(), status("Playing"))
            assert spy.delay == pytest.approx(30.0)
            await cancel_pending_timer(player)

        asyncio.run(scenario())

    def test_short_track_never_scheduled(self):
        player = make_player(callback=AsyncMock())

        async def scenario():
            spy = attach_hanging_spy(player)
            await feed(player, metadata(length=20_000_000), status("Playing"))
            assert player.scrobble_task is None
            assert spy.started == 0

        asyncio.run(scenario())

    def test_missing_title_never_scheduled(self):
        player = make_player(callback=AsyncMock())

        async def scenario():
            attach_hanging_spy(player)
            no_title = {
                "Metadata": variant(
                    {
                        "xesam:artist": variant(["Artist"]),
                        "mpris:length": variant(LONG_TRACK_US),
                    }
                )
            }
            await feed(player, no_title, status("Playing"))
            assert player.current_artist == "Artist"
            assert player.current_title is None
            assert not player.has_valid_track()
            assert player.scrobble_task is None

        asyncio.run(scenario())

    def test_missing_artist_never_scheduled(self):
        player = make_player(callback=AsyncMock())

        async def scenario():
            attach_hanging_spy(player)
            no_artist = {
                "Metadata": variant(
                    {
                        "xesam:title": variant("Song"),
                        "mpris:length": variant(LONG_TRACK_US),
                    }
                )
            }
            await feed(player, no_artist, status("Playing"))
            assert not player.has_valid_track()
            assert player.scrobble_task is None

        asyncio.run(scenario())

    def test_paused_track_not_scheduled(self):
        player = make_player(callback=AsyncMock())

        async def scenario():
            spy = attach_hanging_spy(player)
            await feed(player, metadata(), status("Paused"))
            assert player.playback_status == "Paused"
            assert spy.started == 0

        asyncio.run(scenario())


class TestDuplicatePrevention:
    def test_repeated_metadata_keeps_same_timer(self):
        player = make_player(callback=AsyncMock())

        async def scenario():
            attach_hanging_spy(player)
            await feed(player, metadata(), status("Playing"))
            first_task = player.scrobble_task

            await feed(player, metadata())
            await feed(player, metadata())

            assert player.scrobble_task is first_task
            await cancel_pending_timer(player)

        asyncio.run(scenario())

    def test_repeated_metadata_does_not_rescrobble(self):
        recorded = []

        async def cb(artist, title):
            recorded.append((artist, title))

        player = make_player(callback=cb, delay_scale=0.001)

        async def scenario():
            await feed(player, metadata(), status("Playing"))
            for _ in range(5):
                await asyncio.sleep(0.02)
                await feed(player, metadata())
            await asyncio.sleep(0.15)
            await feed(player, metadata())

        asyncio.run(scenario())

        assert recorded == [("Artist", "Title")]
        assert player.scrobbled is True

    def test_new_track_cancels_pending_timer(self):
        player = make_player(callback=AsyncMock())

        async def scenario():
            attach_hanging_spy(player)
            await feed(player, metadata(artist="First", title="Song"), status("Playing"))
            old_task = player.scrobble_task
            assert old_task is not None

            await feed(player, metadata(artist="Second", title="Other"))

            await asyncio.sleep(0)
            assert old_task.cancelled()
            assert player.scrobble_task is not None
            assert player.scrobble_task is not old_task
            assert player.played_sec == 0.0
            assert player.scrobbled is False
            assert player.current_title == "Other"
            await cancel_pending_timer(player)

        asyncio.run(scenario())

    def test_duration_correction_is_not_a_track_change(self):
        player = make_player(callback=AsyncMock())

        async def scenario():
            attach_hanging_spy(player)
            await feed(player, metadata(), status("Playing"))
            first_task = player.scrobble_task

            await feed(player, metadata(length=210_000_000))

            assert player.scrobble_task is first_task
            assert player.track_length == 210_000_000
            await cancel_pending_timer(player)

        asyncio.run(scenario())

    def test_pause_cancels_and_resume_schedules_remaining_time(self):
        player = make_player(callback=AsyncMock())

        async def scenario():
            spy = attach_hanging_spy(player)
            await feed(player, metadata(), status("Playing"))
            await cancel_pending_timer(player)
            player.played_sec = 40.0

            await feed(player, status("Paused"))
            spy.started = 0

            await feed(player, status("Playing"))

            assert spy.started == 1
            assert spy.delay == pytest.approx(60.0, abs=1.0)
            await cancel_pending_timer(player)

        asyncio.run(scenario())

    def test_stopped_resets_so_replay_scrobbles_again(self):
        player = make_player(callback=AsyncMock())

        async def scenario():
            spy = attach_hanging_spy(player)
            await feed(player, metadata(), status("Playing"))
            player.scrobbled = True
            await cancel_pending_timer(player)

            await feed(player, status("Stopped"))
            assert player.scrobbled is False
            assert player.played_sec == 0.0

            spy.started = 0
            await feed(player, status("Playing"))
            assert spy.started == 1
            assert spy.delay == pytest.approx(100.0)
            await cancel_pending_timer(player)

        asyncio.run(scenario())

    def test_pause_does_not_reset_scrobbled_flag(self):
        player = make_player(callback=AsyncMock())

        async def scenario():
            attach_hanging_spy(player)
            await feed(player, metadata(), status("Playing"))
            player.scrobbled = True
            await cancel_pending_timer(player)

            await feed(player, status("Paused"))
            await feed(player, status("Playing"))

            assert player.scrobbled is True
            assert player.scrobble_task is None

        asyncio.run(scenario())


class TestScrobbleFires:
    def test_callback_receives_artist_title_once(self):
        recorded = []

        async def cb(artist, title):
            recorded.append((artist, title))

        player = make_player(callback=cb, delay_scale=0.001)

        async def scenario():
            await feed(player, metadata(), status("Playing"))
            await asyncio.sleep(0.15)

        asyncio.run(scenario())

        assert recorded == [("Artist", "Title")]
        assert player.scrobbled is True
        assert player.scrobble_task is None


class StubPlayer(MPrisPlayer):
    instances = []

    def __init__(
        self,
        service_name,
        object_path,
        callback=None,
        bus=None,
        threshold=0,
        delay_scale=1.0,
    ):
        super().__init__(
            service_name, object_path, callback, bus, threshold, delay_scale
        )
        StubPlayer.instances.append(self)

    async def connect(self):
        self.properties = MagicMock()
        self.current_artist = "Artist"
        self.current_title = "Title"
        return self


@pytest.fixture(autouse=True)
def reset_stub_instances():
    StubPlayer.instances.clear()
    yield


def make_manager(blacklist=None, **kwargs):
    return ServiceManager(
        "org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        AsyncMock(),
        blacklist if blacklist is not None else [],
        **kwargs,
    )


class TestServiceManager:
    def test_blacklisted_player_is_ignored(self):
        manager = make_manager(blacklist=["firefox"])

        async def scenario():
            manager.owner_change_callback(
                "org.mpris.MediaPlayer2.firefox-esr", "", ":1.1"
            )
            await asyncio.sleep(0.05)

        asyncio.run(scenario())

        assert manager.players == {}
        assert StubPlayer.instances == []

    def test_non_mpris_names_ignored(self):
        manager = make_manager()

        manager.owner_change_callback("org.freedesktop.Notifications", "", ":1.1")
        manager.owner_change_callback(":1.55", "", ":1.55")

        assert manager.players == {}
        assert manager._pending_players == set()

    def test_player_removal_unregisters_and_snapshots(self):
        manager = make_manager()
        player = MagicMock()
        player.track_id = ("A", "T")
        player.scrobbled = True
        manager.players["org.mpris.MediaPlayer2.vlc"] = player

        manager.owner_change_callback("org.mpris.MediaPlayer2.vlc", ":1.1", "")

        assert "org.mpris.MediaPlayer2.vlc" not in manager.players
        assert manager._previous_sessions["org.mpris.MediaPlayer2.vlc"] == (
            ("A", "T"),
            True,
        )
        player.properties.off_properties_changed.assert_called_once_with(
            player.property_change_callback
        )

    def test_new_player_gets_added(self):
        manager = make_manager()

        with patch("slsd.dbus.MPrisPlayer", StubPlayer):

            async def scenario():
                manager.owner_change_callback(
                    "org.mpris.MediaPlayer2.vlc", "", ":1.1"
                )
                await asyncio.sleep(0.05)

            asyncio.run(scenario())

        assert list(manager.players) == ["org.mpris.MediaPlayer2.vlc"]

    def test_reconnecting_player_inherits_scrobbled_state(self):
        manager = make_manager()

        with patch("slsd.dbus.MPrisPlayer", StubPlayer):
            manager._previous_sessions["org.mpris.MediaPlayer2.vlc"] = (
                ("Artist", "Title"),
                True,
            )

            async def scenario():
                await manager.create_player("org.mpris.MediaPlayer2.vlc")

            asyncio.run(scenario())

        assert StubPlayer.instances[-1].scrobbled is True

    def test_reconnecting_player_with_different_track_starts_fresh(self):
        manager = make_manager()

        with patch("slsd.dbus.MPrisPlayer", StubPlayer):
            manager._previous_sessions["org.mpris.MediaPlayer2.vlc"] = (
                ("Old", "Track"),
                True,
            )

            async def scenario():
                await manager.create_player("org.mpris.MediaPlayer2.vlc")

            asyncio.run(scenario())

        assert StubPlayer.instances[-1].scrobbled is False

    def test_rapid_duplicate_events_create_single_player(self):
        manager = make_manager()
        original_connect = StubPlayer.connect

        async def slow_connect(self):
            await asyncio.sleep(0.02)
            return await original_connect(self)

        StubPlayer.connect = slow_connect
        try:
            with patch("slsd.dbus.MPrisPlayer", StubPlayer):

                async def scenario():
                    manager.owner_change_callback(
                        "org.mpris.MediaPlayer2.vlc", "", ":1.1"
                    )
                    manager.owner_change_callback(
                        "org.mpris.MediaPlayer2.vlc", "", ":1.1"
                    )
                    await asyncio.sleep(0.1)

                asyncio.run(scenario())
        finally:
            StubPlayer.connect = original_connect

        assert len(StubPlayer.instances) == 1
        assert list(manager.players) == ["org.mpris.MediaPlayer2.vlc"]
