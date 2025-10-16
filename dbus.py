import asyncio
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

    async def change_callback(self, i, c, n):
        print("\nSomething Changed...")

    async def subscribe_signal(self):
        self.properties.on_properties_changed(self.change_callback)

    async def connect(self):
        self.bus = await MessageBus().connect()
        self.introspection = await self.bus.introspect(self.bus_name, self.object_path)
        self.obj = self.bus.get_proxy_object(
            self.bus_name, self.object_path, self.introspection
        )
        self.player = self.obj.get_interface(PLAYER_PATH)
        self.properties = self.obj.get_interface(PROPERTY_PATH)
        print("ProxyInterface: ", type(self.player))

        return self

    async def get_metadata(self):
        metadata = await self.player.get_metadata()
        self.metadata = metadata
        return metadata


async def main():
    await asyncio.sleep(1)
    player = MPrisPlayer(BUS_NAME, OBJECT_PATH)
    await player.connect()

    # await player.play_pause()
    # await player.player.set_volume(0.1)
    volume = await player.player.get_volume()
    print(volume)
    hello = await player.get_metadata()
    print("hi: ", hello)
    print("FROMMM: ", player.metadata)

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
