import asyncio
from dbus_next.aio import MessageBus

# loop = asyncio.get_event_loop()

# busctl --user list | grep mpris
# org.mpris.MediaPlayer2.playerctld                                                           2317 playerctld      aidan :1.1          session-c1.scope c1      -
# org.mpris.MediaPlayer2.spotify                                                           2300185 spotify         aidan :1.85211      session-c1.scope c1      -

# peek
# busctl --user introspect org.mpris.MediaPlayer2.spotify /org/mpris/MediaPlayer2


async def main():
    bus = await MessageBus().connect()
    # the introspection xml would normally be included in your project, but
    # this is convenient for development
    bus_name = "org.mpris.MediaPlayer2.spotify"
    object_path = "/org/mpris/MediaPlayer2"

    introspection = await bus.introspect(bus_name, object_path)
    print(introspection)  # <dbus_next.introspection.Node object at 0x7f664196b2d0>

    obj = bus.get_proxy_object(
        "org.mpris.MediaPlayer2.spotify", "/org/mpris/MediaPlayer2", introspection
    )

    player = obj.get_interface("org.mpris.MediaPlayer2.Player")
    properties = obj.get_interface("org.freedesktop.DBus.Properties")

    # call methods on the interface (this causes the media player to play)
    # await player.call_play()
    await player.call_play_pause()

    volume = await player.get_volume()
    print(f"current volume: {volume}, setting to 0.5")


# loop.run_until_complete(main())
asyncio.run(main())
