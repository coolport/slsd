from pprint import pprint
from dbus_next.aio import MessageBus

# Session Bus
#  └─Service (bus name): org.mpris.MediaPlayer2.spotify
#       └── Object path: /org/mpris/MediaPlayer2
#            ├── Interface: org.mpris.MediaPlayer2
#            ├── Interface: org.mpris.MediaPlayer2.Player
#            └── Interface: org.freedesktop.DBus.Properties
# ── org.freedesktop.DBus
#     ├── /org/freedesktop/DBus
#     └── interface: org.freedesktop.DBus
#          ├── method: ListNames()
#          └── method: NameHasOwner()

# TODO: exception handling, typing etc

DBUS_SERVICE_NAME = "org.freedesktop.DBus"
DBUS_OBJECT_PATH = "/org/freedesktop/DBus"

# PLAYER_SERVICE_NAME = "org.mpris.MediaPlayer2.spotify"
PLAYER_SERVICE_NAME = "org.mpris.MediaPlayer2.audacious"
MP2_OBJECT_PATH = "/org/mpris/MediaPlayer2"
PLAYER_INTERFACE_NAME = "org.mpris.MediaPlayer2.Player"

PROPERTY_NAME = "org.freedesktop.DBus.Properties"


class ServiceManager:
    def __init__(self, dbus_service_name, dbus_object_path, callback=None):
        self.players = {}
        self.service_name = dbus_service_name
        self.object_path = dbus_object_path
        self.bus = None
        self.object = None
        self.introspection = None
        self.properties = None
        self.interface = None
        self.callback = callback

    def owner_change_callback(self, name, old_owner, new_owner):
        if self.callback is not None:
            self.callback(name, old_owner, new_owner)

    async def connect(self):
        self.bus = await MessageBus().connect()
        self.introspection = await self.bus.introspect(
            self.service_name, self.object_path
        )
        self.object = self.bus.get_proxy_object(
            self.service_name, self.object_path, self.introspection
        )
        self.interface = self.object.get_interface(self.service_name)

        self.interface.on_name_owner_changed(self.owner_change_callback)

        names = await self.interface.call_list_names()
        for x in names:
            if x.startswith("org.mpris.MediaPlayer2."):
                print(x)

        return self


class MPrisPlayer:
    def __init__(
        self,
        service_name,
        object_path,
        change_callback_function=None,
    ):
        self.service_name = service_name
        self.object_path = object_path
        self.player = None
        self.bus = None
        self.introspection = None
        self.object = None
        self.properties = None
        self.metadata = None
        self.change_callback_function = change_callback_function

    async def signal_change_callback(
        self, interface_name, changed_properties, invalidated_properties
    ):
        if "Metadata" in changed_properties:
            metadata_variant = changed_properties["Metadata"]
            metadata = metadata_variant.value

            artist = metadata["xesam:artist"].value[0]
            track = metadata["xesam:title"].value

            if self.change_callback_function is not None:
                await self.change_callback_function(artist, track)

    async def connect(self):
        self.bus = await MessageBus().connect()
        self.introspection = await self.bus.introspect(
            self.service_name, self.object_path
        )
        self.object = self.bus.get_proxy_object(
            self.service_name, self.object_path, self.introspection
        )
        self.player = self.object.get_interface(PLAYER_INTERFACE_NAME)
        self.properties = self.object.get_interface(PROPERTY_NAME)
        print("DBus Connection Success\nProxyInterface: ", type(self.player))

        self.properties.on_properties_changed(self.signal_change_callback)

        return self

    async def get_metadata(self):
        metadata = await self.player.get_metadata()
        self.metadata = metadata

        return metadata
