from pprint import pprint
from dbus_next.aio import MessageBus

# busctl --user list | grep mpris
# busctl --user introspect org.mpris.MediaPlayer2.spotify /org/mpris/MediaPlayer2
# GENERAL STRUCTURE OF DBUS - SERVICE - OBJECTS(typically 1, yung mprismp2 lang) - INTERFACES
# Session Bus
#  └── Service (bus name): org.mpris.MediaPlayer2.spotify
#       └── Object path: /org/mpris/MediaPlayer2
#            ├── Interface: org.mpris.MediaPlayer2
#            ├── Interface: org.mpris.MediaPlayer2.Player
#            └── Interface: org.freedesktop.DBus.Properties

# TODO: exception handling, typing etc

# BUS_NAME = "org.mpris.MediaPlayer2.spotify"
DBUS_SERVICE_ADDRESS = "org.freedesktop.DBus"

SERVICE_NAME = "org.mpris.MediaPlayer2.audacious"
OBJECT_PATH = "/org/mpris/MediaPlayer2"
PLAYER_NAME = "org.mpris.MediaPlayer2.Player"

PROPERTY_NAME = "org.freedesktop.DBus.Properties"


class MPrisPlayer:
    def __init__(self, service_name, object_path, change_callback_function=None):
        self.bus_name = service_name
        self.object_path = object_path
        self.player = None
        self.bus = None
        self.introspection = None
        self.obj = None
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

    # async def get_mpris_services(self):
    # self.dbusinterface = self.bus.get_interface(DBUS_ADDRESS)
    # print(self.dbusinterface)

    async def connect(self):
        self.bus = await MessageBus().connect()
        self.introspection = await self.bus.introspect(self.bus_name, self.object_path)
        self.obj = self.bus.get_proxy_object(
            self.bus_name, self.object_path, self.introspection
        )
        self.player = self.obj.get_interface(PLAYER_NAME)
        self.properties = self.obj.get_interface(PROPERTY_NAME)
        print("DBus Connection Success\nProxyInterface: ", type(self.player))

        # Subscribe to the on properties changed signal
        self.properties.on_properties_changed(self.signal_change_callback)

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
