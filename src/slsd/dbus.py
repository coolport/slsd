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


class ServiceManager:
    def __init__(
        self,
        dbus_service_name,
        dbus_object_path,
        property_signal_callback,
        blacklist,
        threshold=0,
    ):
        self.players = {}
        self.bus = None
        self.object = None
        self.introspection = None
        self.properties = None
        self.interface = None
        self.service_name = dbus_service_name
        self.object_path = dbus_object_path
        self.property_signal_callback = property_signal_callback
        self.blacklist = blacklist
        self.threshold = threshold

    async def connect(self):
        try:
            self.bus = await MessageBus().connect()
        except Exception as e:
            log.error("Failed to connect to system DBus: %s", e)
            return

        log.info("DBus Connection Succesful!")
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
        log.info("Active MPRIS Players on connect:")
        for name in service_names:
            if name.startswith("org.mpris.MediaPlayer2."):
                if self.blacklist and any(item in name for item in self.blacklist):
                    continue

                if name not in self.players:
                    asyncio.create_task(
                        self.create_player(name, self.property_signal_callback)
                    )
                else:
                    log.warning("Skipping %s, already in dict.", name)
                log.info("- %s", name)

        return self

    def owner_change_callback(self, name, old_owner, new_owner):
        if name.startswith("org.mpris.MediaPlayer2."):
            log.info("Player change: %s, Old: %s, New: %s", name, old_owner, new_owner)

            if new_owner and not old_owner:
                if self.blacklist and any(item in name for item in self.blacklist):
                    return
                if name not in self.players:
                    asyncio.create_task(
                        self.create_player(name, self.property_signal_callback)
                    )
                else:
                    log.warning("Skipping %s, already in dict.", name)
                log.info("Player %s found, adding to players dictionary.", name)

            elif old_owner and not new_owner:
                log.info("%s was closed. Removing from players dictionary.", name)
                player = self.players.pop(name, None)
                if player and player.properties:
                    try:
                        player.properties.off_properties_changed(
                            player.property_change_callback
                        )
                    except Exception as e:
                        log.error(
                            "Error disconnecting player %s: %s", player.service_name, e
                        )
                log.debug("Current players: %s", self.players)
        return self

    async def create_player(self, player_name, property_signal_callback):
        if player_name not in self.players:
            try:
                player = MPrisPlayer(
                    player_name,
                    MP2_OBJECT_PATH,
                    property_signal_callback,
                    self.bus,
                    self.threshold,
                )
                await player.connect()
                self.players.update({f"{player_name}": player})
                log.info("Updated players: %s", self.players)
            except DBusError as e:
                log.error("Cant connect to player %s: %s", player_name, e)

        return self


class MPrisPlayer:
    def __init__(self, service_name, object_path, callback=None, bus=None, threshold=0):
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

        self.current_track = {"artist": None, "title": None}

        self.track_length = 0
        self.scrobble_task = None
        self.scrobbled = False
        self.user_threshold = threshold

    def update_current_track(self):
        self.current_track = {
            "artist": self.current_artist,
            "title": self.current_title,
        }
        return self

    async def _scrobble_after_delay(self, delay):
        try:
            log.info("Scrobbling '%s' in %.2f seconds...", self.current_title, delay)
            await asyncio.sleep(delay)

            log.info(
                "Timer complete, sending scrobble request for '%s'", self.current_title
            )
            await self.callback(self.current_artist, self.current_title)
            self.scrobbled = True
            self.scrobble_task = None
        except asyncio.CancelledError:
            log.info("Scrobble for '%s' was cancelled.", self.current_title)

    async def property_change_callback(
        self,
        interface_name,
        changed_properties,
        invalidated_properties,
    ):
        if not changed_properties:
            return

        if "Metadata" in changed_properties:
            if self.scrobble_task:
                self.scrobble_task.cancel()
                self.scrobble_task = None

            self.scrobbled = False
            metadata_variant = changed_properties.get("Metadata")
            if not metadata_variant or not metadata_variant.value:
                return

            self.metadata = metadata_variant.value

            artist_variant = self.metadata.get("xesam:artist")
            title_variant = self.metadata.get("xesam:title")
            length_variant = self.metadata.get("mpris:length")

            self.current_artist = (
                artist_variant.value[0]
                if artist_variant and artist_variant.value
                else "Unknown Artist"
            )
            self.current_title = (
                title_variant.value if title_variant else "Unknown Title"
            )
            self.track_length = length_variant.value if length_variant else 0
            self.update_current_track()

            if self.current_title != "Unknown Title":
                log.info(
                    "Track Changed: %s - %s (%.0fs)",
                    self.current_title,
                    self.current_artist,
                    self.track_length / 1_000_000,
                )

        if "PlaybackStatus" in changed_properties:
            status_variant = changed_properties.get("PlaybackStatus")
            if status_variant:
                self.playback_status = status_variant.value
                log.info("Playback Status: %s", self.playback_status)

        if (
            self.playback_status == "Playing"
            and not self.scrobbled
            and not self.scrobble_task
        ):
            if self.track_length > 30_000_000:
                standard_scrobble_point_us = min(self.track_length / 2, 240 * 1_000_000)

                final_scrobble_point_us = standard_scrobble_point_us
                if self.user_threshold > 0:
                    hard_threshold_us = self.user_threshold * 1_000_000
                    final_scrobble_point_us = min(
                        standard_scrobble_point_us, hard_threshold_us
                    )

                delay_sec = final_scrobble_point_us / 1_000_000
                self.scrobble_task = asyncio.create_task(
                    self._scrobble_after_delay(delay_sec)
                )
            else:
                if self.track_length > 0:
                    log.info("Track '%s' is too short to scrobble.", self.current_title)

        elif self.playback_status in ["Paused", "Stopped"]:
            if self.scrobble_task:
                self.scrobble_task.cancel()
                self.scrobble_task = None

    # TODO: handle race condition where program is added to list before proper init (missing mp2 interface, etc)
    async def connect(self):
        bus = self.bus
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
