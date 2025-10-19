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

# BUS_NAME = "org.mpris.MediaPlayer2.spotify"
DBUS_SERVICE_NAME = "org.freedesktop.DBus"
DBUS_OBJECT_PATH = "/org/freedesktop/DBus"

PLAYER_SERVICE_NAME = "org.mpris.MediaPlayer2.audacious"
MP2_OBJECT_PATH = "/org/mpris/MediaPlayer2"
PLAYER_INTERFACE_NAME = "org.mpris.MediaPlayer2.Player"

PROPERTY_NAME = "org.freedesktop.DBus.Properties"


class MPrisPlayer:
    def __init__(
        self,
        service_name,
        object_path,
        change_callback_function=None,
        owner_change_callback_function=None,
    ):
        self.bus_name = service_name
        self.object_path = object_path
        self.player = None
        self.bus = None
        self.introspection = None
        self.obj = None
        self.properties = None
        self.metadata = None
        self.change_callback_function = change_callback_function
        self.owner_change_callback_function = owner_change_callback_function

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

    async def myfunc(self, name, old_owner, new_owner):
        if self.owner_change_callback_function is not None:
            await self.owner_change_callback_function(name, old_owner, new_owner)

    # Connect to dbus service to listen and list/attach all mpris players
    async def get_dbus_service(self):
        dbus_introspection = await self.bus.introspect(
            DBUS_SERVICE_NAME, DBUS_OBJECT_PATH
        )
        dbus_object = self.bus.get_proxy_object(
            DBUS_SERVICE_NAME, DBUS_OBJECT_PATH, dbus_introspection
        )
        dbus_interface = dbus_object.get_interface(
            DBUS_SERVICE_NAME
        )  # Interface has same name as the service itself

        names = await dbus_interface.call_list_names()
        for x in names:
            if x.startswith("org.mpris.MediaPlayer2."):
                print(x)

        dbus_interface.on_name_owner_changed(self.myfunc)

    async def connect(self):
        self.bus = await MessageBus().connect()
        self.introspection = await self.bus.introspect(self.bus_name, self.object_path)
        self.obj = self.bus.get_proxy_object(
            self.bus_name, self.object_path, self.introspection
        )
        self.player = self.obj.get_interface(PLAYER_INTERFACE_NAME)
        self.properties = self.obj.get_interface(PROPERTY_NAME)
        print("DBus Connection Success\nProxyInterface: ", type(self.player))

        # Subscribe to the on properties changed signal
        self.properties.on_properties_changed(self.signal_change_callback)

        await self.get_dbus_service()

        return self

    async def get_metadata(self):
        metadata = await self.player.get_metadata()
        self.metadata = metadata

        return metadata


# async def main():
#     player = MPrisPlayer(BUS_NAME, OBJECT_PATH)
#     await player.connect()
#
#     volume = await player.player.get_volume()
#     print("Volume: ", volume)
#     # hello = await player.get_metadata()
#     # print("\nMetadata1: ", hello)
#     # print("\nMetadata2: ", player.metadata["xesam:album"])
#     # print("\nMetadata2: ", player.metadata.get("xesam:album", None))
#
#     try:
#         while True:
#             await asyncio.sleep(3600)
#     except asyncio.CancelledError:
#         pass
#
# if __name__ == "__main__":
#     try:
#         asyncio.run(main())
#     except KeyboardInterrupt:
#         print("\nExiting")
