import asyncio
from pprint import pprint
from dbus_next.aio import MessageBus

DBUS_SERVICE_NAME = "org.freedesktop.DBus"
DBUS_OBJECT_PATH = "/org/freedesktop/DBus"

MP2_OBJECT_PATH = "/org/mpris/MediaPlayer2"
PLAYER_INTERFACE_NAME = "org.mpris.MediaPlayer2.Player"
PROPERTY_NAME = "org.freedesktop.DBus.Properties"


class ServiceManager:
    def __init__(self, dbus_service_name, dbus_object_path, property_signal_callback):
        self.players = {}
        self.service_name = dbus_service_name
        self.object_path = dbus_object_path
        self.bus = None
        self.object = None
        self.introspection = None
        self.properties = None
        self.interface = None
        self.property_signal_callback = property_signal_callback

    async def connect(self):
        try:
            self.bus = await MessageBus().connect()
        except e:
            print("Failed: ", e)

        print("DBus Connection Succesful")
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

        names = await self.interface.call_list_names()
        print("Found MPRIS Players on connect: \n")
        for x in names:
            if x.startswith("org.mpris.MediaPlayer2."):
                asyncio.create_task(
                    self.create_player(x, self.property_signal_callback)
                )
                print(x)

        return self

    def owner_change_callback(self, name, old_owner, new_owner):
        if name.startswith("org.mpris.MediaPlayer2."):
            print(f"\nPlayer change: {name}, Old: {old_owner}, New: {new_owner}")
            if new_owner and not old_owner:
                asyncio.create_task(
                    self.create_player(name, self.property_signal_callback)
                )
                print(f"\nPlayer {name} found, adding to players[]")
                print("Current: ", self.players)
            elif old_owner and not new_owner:
                print(f"\n{name} was closed. Removing from players[]")
                self.players.pop(f"{name}")
                print("Current: ", self.players)
        return self

    async def create_player(self, player_name, property_signal_callback):
        player = MPrisPlayer(
            player_name,
            MP2_OBJECT_PATH,
            property_signal_callback,
            self.bus,
        )
        await player.connect()
        self.players.update({f"{player_name}": player})
        print("\nUpdated players{}")
        print(self.players)

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
        self.current_track = None

        self.callback = callback

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
                self.current_track = meta_track_variant.value

        if "PlaybackStatus" in changed_properties:
            playback_status_variant = changed_properties["PlaybackStatus"]
            self.playback_status = playback_status_variant.value
            print("Playback: ", self.playback_status)

        if self.playback_status == "Playing":
            if self.callback and self.current_artist and self.current_track:
                await self.callback(self.current_artist, self.current_track)

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

        # TODO: Refactor, duplicate logic with prop change callback - static method? idk
        initial_properties = await self.properties.call_get_all(PLAYER_INTERFACE_NAME)
        self.metadata = initial_properties.get("Metadata").value
        self.playback_status = initial_properties.get("PlaybackStatus").value
        self.current_track = self.metadata.get("xesam:title").value
        self.current_artist = self.metadata.get("xesam:artist").value[0]
        self.properties.on_properties_changed(self.property_change_callback)

        if self.playback_status == "Playing":
            if self.callback and self.current_artist and self.current_track:
                await self.callback(self.current_artist, self.current_track)

        return self
