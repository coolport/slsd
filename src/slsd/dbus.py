import asyncio
from dbus_next.aio import MessageBus
from dbus_next.errors import DBusError

from slsd import config

DBUS_SERVICE_NAME = "org.freedesktop.DBus"
DBUS_OBJECT_PATH = "/org/freedesktop/DBus"

MP2_OBJECT_PATH = "/org/mpris/MediaPlayer2"
PLAYER_INTERFACE_NAME = "org.mpris.MediaPlayer2.Player"
PROPERTY_NAME = "org.freedesktop.DBus.Properties"


# TODO: actual proper logging
class ServiceManager:
    def __init__(
        self, dbus_service_name, dbus_object_path, property_signal_callback, blacklist
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

    async def connect(self):
        try:
            self.bus = await MessageBus().connect()
        except Exception as e:
            print("Failed: ", e)

        print("DBus Connection Succesful!")
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
        print("Active MPRIS Players on connect: \n")
        for name in service_names:
            if name.startswith("org.mpris.MediaPlayer2."):
                if self.blacklist and any(item in name for item in self.blacklist):
                    continue

                if name not in self.players:
                    asyncio.create_task(
                        self.create_player(name, self.property_signal_callback)
                    )
                else:
                    print("Skipping: ", name, " already in dict.")
                print(name)

        return self

    def owner_change_callback(self, name, old_owner, new_owner):
        if name.startswith("org.mpris.MediaPlayer2."):
            print(f"\nPlayer change: {name}, Old: {old_owner}, New: {new_owner}")

            if new_owner and not old_owner:
                if self.blacklist and any(item in name for item in self.blacklist):
                    return
                if name not in self.players:
                    asyncio.create_task(
                        self.create_player(name, self.property_signal_callback)
                    )
                else:
                    print("Skipping: ", name, " already in dict.")
                print(f"\nPlayer {name} found, adding to players[]")

            elif old_owner and not new_owner:
                print(f"\n{name} was closed. Removing from players[]")
                player = self.players.pop(name, None)
                if player and player.properties:
                    try:
                        player.properties.off_properties_changed(
                            player.property_change_callback
                        )
                    except Exception as e:
                        print(f"Error disconnecting player {player.service_name}: {e}")

                print("Current: ", self.players)
        return self

    async def create_player(self, player_name, property_signal_callback):
        if player_name not in self.players:
            try:
                player = MPrisPlayer(
                    player_name,
                    MP2_OBJECT_PATH,
                    property_signal_callback,
                    self.bus,
                )
                await player.connect()
                self.players.update({f"{player_name}": player})
                print("\nUpdated players: ")
                print(self.players)
            except DBusError as e:
                print(f"Cant connect to player {player_name}: {e}")

        return self


class MPrisPlayer:
    def __init__(self, service_name, object_path, callback=None, bus=None):
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

    def update_current_track(self):
        self.current_track = {
            "artist": self.current_artist,
            "title": self.current_title,
        }
        return self

    async def _scrobble_after_delay(self, delay):
        try:
            print(f"Scrobbling '{self.current_title}' in {delay:.2f} seconds...")
            await asyncio.sleep(delay)

            print(f"Scrobbled: {self.current_title} - {self.current_artist}")
            await self.callback(self.current_artist, self.current_title)
            self.scrobbled = True
            self.scrobble_task = None
        except asyncio.CancelledError:
            print(f"Scrobble for '{self.current_title}' was cancelled.")

    # TODO: handle repeating songs
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
                print(
                    f"\nTrack Changed: {self.current_title} - {self.current_artist} ({self.track_length / 1_000_000:.0f}s)"
                )

        if "PlaybackStatus" in changed_properties:
            status_variant = changed_properties.get("PlaybackStatus")
            if status_variant:
                self.playback_status = status_variant.value
                print(f"# Playback Status: {self.playback_status}")

        if (
            self.playback_status == "Playing"
            and not self.scrobbled
            and not self.scrobble_task
        ):
            if self.track_length > 30_000_000:
                scrobble_point_us = min(self.track_length / 2, 240 * 1_000_000)
                delay_sec = scrobble_point_us / 1_000_000
                self.scrobble_task = asyncio.create_task(
                    self._scrobble_after_delay(delay_sec)
                )
            else:
                if self.track_length > 0:
                    print(f"Track '{self.current_title}' is too short to scrobble.")

        elif self.playback_status in ["Paused", "Stopped"]:
            if self.scrobble_task:
                self.scrobble_task.cancel()
                self.scrobble_task = None

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
            print(f"Can't get initial properties for {self.service_name}. Error: {e}")

        return self
