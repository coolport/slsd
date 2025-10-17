import asyncio
from pprint import pprint
from dbus_next.aio import MessageBus

# busctl --user list | grep mpris
# busctl --user introspect org.mpris.MediaPlayer2.spotify /org/mpris/MediaPlayer2

# TODO: exception handling, typing etc

BUS_NAME = "org.mpris.MediaPlayer2.spotify"
OBJECT_PATH = "/org/mpris/MediaPlayer2"
PLAYER_PATH = "org.mpris.MediaPlayer2.Player"
PROPERTY_PATH = "org.freedesktop.DBus.Properties"


class MPrisPlayer:
    def __init__(self, bus_name, object_path):
        self.bus_name = bus_name
        self.object_path = object_path
        self.player = None
        self.bus = None
        self.introspection = None
        self.obj = None
        self.properties = None
        self.metadata = None

        # TODO: exception handling, null handling, .get etc

    async def signal_change_callback(
        self, interface_name, changed_properties, invalidated_properties
    ):
        if "Metadata" in changed_properties:
            metadata_variant = changed_properties["Metadata"]
            metadata = metadata_variant.value
            print("\nMetadata Variant: ", metadata_variant)
            print("\nMetadata: ", metadata)

            artist = metadata["xesam:artist"].value[0]
            print("\nTrack Arist: ", artist)
            track = metadata["xesam:title"].value
            print("\nTrack Title: ", track)

            return artist, track

        print("\nInterface Name: ")
        pprint(interface_name)
        print("\nChanged Properties:")
        pprint(changed_properties)
        print("\nInvalidated Properties:")
        pprint(invalidated_properties)

    async def connect(self):
        self.bus = await MessageBus().connect()
        self.introspection = await self.bus.introspect(self.bus_name, self.object_path)
        self.obj = self.bus.get_proxy_object(
            self.bus_name, self.object_path, self.introspection
        )
        self.player = self.obj.get_interface(PLAYER_PATH)
        self.properties = self.obj.get_interface(PROPERTY_PATH)
        print("Connected! ProxyInterface: ", type(self.player))

        # Subscribe to the on properties changed signal
        self.properties.on_properties_changed(self.signal_change_callback)

        return self

    async def get_metadata(self):
        metadata = await self.player.get_metadata()
        self.metadata = metadata
        return metadata


async def main():
    player = MPrisPlayer(BUS_NAME, OBJECT_PATH)
    await player.connect()

    volume = await player.player.get_volume()
    print("Volume: ", volume)
    # hello = await player.get_metadata()
    # print("\nMetadata1: ", hello)
    # print("\nMetadata2: ", player.metadata["xesam:album"])
    # print("\nMetadata2: ", player.metadata.get("xesam:album", None))

    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting")
