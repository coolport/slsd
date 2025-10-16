import asyncio
from dbus_next.aio import MessageBus

# loop = asyncio.get_event_loop()
# busctl --user list | grep mpris
# org.mpris.MediaPlayer2.playerctld                                                           2317 playerctld      aidan :1.1          session-c1.scope c1      -
# org.mpris.MediaPlayer2.spotify                                                           2300185 spotify         aidan :1.85211      session-c1.scope c1      -
# peek
# busctl --user introspect org.mpris.MediaPlayer2.spotify /org/mpris/MediaPlayer2

# TODO: exception handling, typing etc

# Establish connection to interfaces


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

    # async def get_metadata(self):
    #     self.propret
    async def play_pause(self):
        await self.player.call_play_pause()


async def main():
    player = MPrisPlayer(BUS_NAME, OBJECT_PATH)
    await player.connect()
    await player.play_pause()


# loop.run_until_complete(main())
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exiting")
