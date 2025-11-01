import asyncio
from dbus_next.aio import MessageBus
from dbus_next.errors import DBusError

DBUS_SERVICE_NAME = "org.freedesktop.DBus"
DBUS_OBJECT_PATH = "/org/freedesktop/DBus"

MP2_OBJECT_PATH = "/org/mpris/MediaPlayer2"
PLAYER_INTERFACE_NAME = "org.mpris.MediaPlayer2.Player"
PROPERTY_NAME = "org.freedesktop.DBus.Properties"


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
                if player:
                    try:
                        if self.properties:
                            self.properties.off_properties_changed(
                                self.property_change_callback
                            )
                    except Exception as e:
                        print(f"Error disconnecting player {self.service_name}: {e}")
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
        self.player = None
        self.bus = bus
        self.introspection = None
        self.object = None
        self.properties = None
        self.metadata = None

        self.playback_status = None
        self.current_artist = None

        self.current_title = None

        self.current_track = {"artist": None, "title": None}
        self.previous_track = {"artist": None, "title": None}

        # self.previous_track = None

        self.callback = callback

    def update_current_track(self):
        self.current_track = {
            "artist": self.current_artist,
            "title": self.current_title,
        }
        return self

    # def update_previous_track(self):
    #     self.previous_track = {
    #         "artist": self.current_artist,
    #         "title": self.current_title,
    #     }
    #     return self

    async def property_change_callback(
        self,
        interface_name,
        changed_properties,
        invalidated_properties,
    ):
        if "Metadata" in changed_properties:
            metadata_variant = changed_properties["Metadata"]
            self.metadata = metadata_variant.value

            meta_artist_variant = self.metadata.get("xesam:artist")
            meta_track_variant = self.metadata.get("xesam:title")

            if meta_artist_variant and meta_artist_variant.value:
                self.current_artist = meta_artist_variant.value[0]

            if meta_track_variant:
                self.current_title = meta_track_variant.value

            if self.current_artist and self.current_title:
                self.update_current_track()

        if "PlaybackStatus" in changed_properties:
            playback_status_variant = changed_properties["PlaybackStatus"]
            self.playback_status = playback_status_variant.value
            print("# Playback: ", self.playback_status)

        await self._validate_scrobbler()

    async def _validate_scrobbler(self):
        if self.playback_status == "Playing":
            if self.callback and self.current_artist and self.current_title:
                if self.current_track != self.previous_track:
                    await self.callback(self.current_artist, self.current_title)
                    self.previous_track = self.current_track
                    print("New previous track: ", self.previous_track)

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

        initial_properties = await self.properties.call_get_all(PLAYER_INTERFACE_NAME)

        metadata_variant = initial_properties.get("Metadata")
        if metadata_variant:
            self.metadata = metadata_variant.value
            meta_artist_variant = self.metadata.get("xesam:artist")
            meta_track_variant = self.metadata.get("xesam:title")

            if meta_artist_variant and meta_artist_variant.value:
                self.current_artist = meta_artist_variant.value[0]
            if meta_track_variant:
                self.current_title = meta_track_variant.value
            if self.current_artist and self.current_title:
                self.update_current_track()
                self.previous_track = self.current_track

            print(
                f"current_track on connnect: {self.current_title} - {self.current_artist}"
            )
            print(f"prev: {self.previous_track}")

        status_variant = initial_properties.get("PlaybackStatus")
        if status_variant:
            self.playback_status = status_variant.value

        self.properties.on_properties_changed(self.property_change_callback)
        await self._validate_scrobbler()
        return self
