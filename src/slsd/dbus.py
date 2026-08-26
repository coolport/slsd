import asyncio
import logging

from dbus_next.aio import MessageBus
from dbus_next.errors import DBusError

log = logging.getLogger(__name__)

DBUS_SERVICE_NAME = "org.freedesktop.DBus"
DBUS_OBJECT_PATH = "/org/freedesktop/DBus"

MP2_OBJECT_PATH = "/org/mpris/MediaPlayer2"
PLAYER_INTERFACE_NAME = "org.mpris.MediaPlayer2.Player"
PROPERTY_NAME = "org.freedesktop.DBus.Properties"

MIN_TRACK_LENGTH_US = 30_000_000
MAX_SCROBBLE_DELAY_US = 240 * 1_000_000


class ServiceManager:
    def __init__(
        self,
        dbus_service_name,
        dbus_object_path,
        property_signal_callback,
        blacklist,
        threshold=0,
        delay_scale=1.0,
    ):
        self.players: dict[str, "MPrisPlayer"] = {}
        self._pending_players: set[str] = set()
        self._previous_sessions: dict[str, tuple[tuple, bool]] = {}
        self.bus = None
        self.object = None
        self.introspection = None
        self.properties = None
        self.interface = None
        self.service_name = dbus_service_name
        self.object_path = dbus_object_path
        self.property_signal_callback = property_signal_callback
        self.blacklist = blacklist or []
        self.threshold = threshold
        self.delay_scale = delay_scale

    def is_blacklisted(self, name: str) -> bool:
        return any(item in name for item in self.blacklist)

    async def connect(self):
        try:
            self.bus = await MessageBus().connect()
        except Exception as e:
            log.error(
                "Failed to connect to the DBus session bus: %s\n"
                "Is a desktop session running?",
                e,
            )
            return None

        log.info("DBus connection successful")
        self.introspection = await self.bus.introspect(
            self.service_name,
            self.object_path,
        )
        self.object = self.bus.get_proxy_object(
            self.service_name,
            self.object_path,
            self.introspection,
        )
        self.interface = self.object.get_interface(self.service_name)

        self.interface.on_name_owner_changed(self.owner_change_callback)

        service_names = await self.interface.call_list_names()
        found = []
        for name in service_names:
            if name.startswith("org.mpris.MediaPlayer2."):
                if self.is_blacklisted(name):
                    log.info("Skipping blacklisted player: %s", name)
                    continue
                if name not in self.players and name not in self._pending_players:
                    self._schedule_player_creation(name)
                found.append(name)

        if found:
            log.info("Active MPRIS players:\n%s", "\n".join(f"- {n}" for n in found))
        else:
            log.info("No MPRIS players running yet; waiting for one to appear.")

        return self

    def _schedule_player_creation(self, name: str):
        self._pending_players.add(name)
        asyncio.create_task(self._create_player_task(name))

    async def _create_player_task(self, name: str):
        try:
            await self.create_player(name)
        except Exception as e:
            log.error("Failed to attach to player %s: %s", name, e)
        finally:
            self._pending_players.discard(name)

    async def create_player(self, player_name: str):
        if player_name in self.players:
            return None

        try:
            player = MPrisPlayer(
                player_name,
                MP2_OBJECT_PATH,
                self.property_signal_callback,
                self.bus,
                self.threshold,
                self.delay_scale,
            )
            await player.connect()
        except DBusError as e:
            log.error("Can't connect to player %s: %s", player_name, e)
            return None

        snapshot = self._previous_sessions.get(player_name)
        if snapshot is not None:
            previous_identity, was_scrobbled = snapshot
            if was_scrobbled and player.track_id == previous_identity:
                player.scrobbled = True
                log.debug(
                    "%s reconnected mid-track; suppressing duplicate scrobble",
                    player_name,
                )

        self.players[player_name] = player
        log.info("Player added: %s", player_name)
        return player

    def owner_change_callback(self, name, old_owner, new_owner):
        if not name.startswith("org.mpris.MediaPlayer2."):
            return

        log.debug("Player change: %s, old: %s, new: %s", name, old_owner, new_owner)

        if new_owner and not old_owner:
            if self.is_blacklisted(name):
                log.info("Ignoring blacklisted player: %s", name)
                return
            if name in self.players or name in self._pending_players:
                return
            self._schedule_player_creation(name)

        elif old_owner and not new_owner:
            player = self.players.pop(name, None)
            self._pending_players.discard(name)
            if player:
                self._previous_sessions[name] = (player.track_id, player.scrobbled)
                if player.properties:
                    try:
                        player.properties.off_properties_changed(
                            player.property_change_callback
                        )
                    except Exception as e:
                        log.error("Error detaching from player %s: %s", name, e)
                log.info("Player removed: %s", name)


class MPrisPlayer:
    def __init__(
        self,
        service_name,
        object_path,
        callback=None,
        bus=None,
        threshold=0,
        delay_scale=1.0,
    ):
        self.service_name = service_name
        self.object_path = object_path
        self.callback = callback
        self.bus = bus

        self.player = None
        self.introspection = None
        self.object = None
        self.properties = None
        self.metadata = None

        self.playback_status = None
        self.current_artist = None
        self.current_title = None
        self.track_length = 0

        self.scrobble_task = None
        self.scrobbled = False
        self.user_threshold = threshold
        self.delay_scale = delay_scale

        self.played_sec = 0.0
        self.timer_started_at = None

    @property
    def track_id(self) -> tuple | None:
        if not self.current_artist or not self.current_title:
            return None
        return (self.current_artist, self.current_title)

    def has_valid_track(self) -> bool:
        return self.current_title is not None and self.current_artist is not None

    def required_delay_sec(self) -> float | None:
        if self.track_length <= MIN_TRACK_LENGTH_US:
            return None
        delay_us = min(self.track_length / 2, MAX_SCROBBLE_DELAY_US)
        if self.user_threshold > 0:
            delay_us = min(delay_us, self.user_threshold * 1_000_000)
        return delay_us / 1_000_000

    async def _scrobble_after_delay(self, delay_sec):
        title = self.current_title
        artist = self.current_artist
        if delay_sec > 0:
            log.info("Scrobbling '%s' in %.1f seconds...", title, delay_sec)
            await asyncio.sleep(delay_sec * self.delay_scale)
        else:
            log.info("Scrobbling '%s' now...", title)

        self.timer_started_at = None
        await self.callback(artist, title)
        self.scrobbled = True
        self.scrobble_task = None

    def _cancel_pending_timer(self, accumulate: bool):
        if self.scrobble_task is None:
            return
        if accumulate and self.timer_started_at is not None:
            self.played_sec += asyncio.get_running_loop().time() - self.timer_started_at
        self.scrobble_task.cancel()
        log.debug("Scrobble timer cancelled for '%s'", self.current_title)
        self.scrobble_task = None
        self.timer_started_at = None

    def _maybe_start_timer(self):
        if (
            self.playback_status != "Playing"
            or self.scrobbled
            or self.scrobble_task is not None
            or not self.has_valid_track()
        ):
            return

        required = self.required_delay_sec()
        if required is None:
            if self.track_length > 0:
                log.info("Track '%s' is too short to scrobble.", self.current_title)
            return

        remaining = max(required - self.played_sec, 0.0)
        self.timer_started_at = asyncio.get_running_loop().time()
        self.scrobble_task = asyncio.create_task(
            self._scrobble_after_delay(remaining)
        )

    def _parse_metadata(self, metadata_variant) -> bool:
        if not metadata_variant or not metadata_variant.value:
            return False

        metadata = metadata_variant.value
        self.metadata = metadata

        artist_variant = metadata.get("xesam:artist")
        title_variant = metadata.get("xesam:title")
        length_variant = metadata.get("mpris:length")

        artist = None
        if artist_variant and artist_variant.value:
            artists = artist_variant.value
            if isinstance(artists, (list, tuple)) and artists:
                artist = str(artists[0]) if artists[0] else None
            elif isinstance(artists, str):
                artist = artists or None

        title = None
        if title_variant and title_variant.value:
            title = str(title_variant.value)

        length = length_variant.value if length_variant else 0

        new_id = (artist, title) if artist and title else None

        if new_id is not None and new_id == self.track_id:
            if length != self.track_length:
                self.track_length = length
            return True

        self._cancel_pending_timer(accumulate=True)
        self.played_sec = 0.0
        self.scrobbled = False

        self.current_artist = artist
        self.current_title = title
        self.track_length = length

        if artist and title:
            log.info(
                "Track changed: %s - %s (%.0fs)",
                title,
                artist,
                length / 1_000_000,
            )
        elif title or artist:
            log.info(
                "Incomplete metadata from %s (%s); will not scrobble.",
                self.service_name,
                title or artist,
            )

        return True

    async def property_change_callback(
        self,
        interface_name,
        changed_properties,
        invalidated_properties,
    ):
        if not changed_properties:
            return

        if "Metadata" in changed_properties:
            self._parse_metadata(changed_properties.get("Metadata"))

        if "PlaybackStatus" in changed_properties:
            status_variant = changed_properties.get("PlaybackStatus")
            if status_variant:
                new_status = status_variant.value
                if new_status != self.playback_status:
                    if new_status == "Paused":
                        self._cancel_pending_timer(accumulate=True)
                    elif new_status == "Stopped":
                        self._cancel_pending_timer(accumulate=False)
                        self.played_sec = 0.0
                        self.scrobbled = False
                    self.playback_status = new_status
                    log.info("Playback status: %s", new_status)

        self._maybe_start_timer()

    async def connect(self):
        self.introspection = await self.bus.introspect(
            self.service_name,
            self.object_path,
        )
        self.object = self.bus.get_proxy_object(
            self.service_name,
            self.object_path,
            self.introspection,
        )

        self.player = self.object.get_interface(PLAYER_INTERFACE_NAME)
        self.properties = self.object.get_interface(PROPERTY_NAME)

        self.properties.on_properties_changed(self.property_change_callback)

        try:
            initial_properties = await self.properties.call_get_all(
                PLAYER_INTERFACE_NAME
            )
            await self.property_change_callback(
                PLAYER_INTERFACE_NAME, initial_properties, []
            )
        except DBusError as e:
            log.error(
                "Can't get initial properties for %s. Error: %s",
                self.service_name,
                e,
            )

        return self
