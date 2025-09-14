from dbus_next.aio import MessageBus
import asyncio

# loop = asyncio.get_event_loop()


async def main():
    bus = await MessageBus().connect()
    # the introspection xml would normally be included in your project, but
    # this is convenient for development
    bus_name = "org.mpris.MediaPlayer2.spotify"
    object_path = "/org/mpris/MediaPlayer2"

    obj = bus.get_proxy_object(
        "org.mpris.MediaPlayer2.vlc", "/org/mpris/MediaPlayer2", introspection
    )
    player = obj.get_interface("org.mpris.MediaPlayer2.Player")
    properties = obj.get_interface("org.freedesktop.DBus.Properties")

    # call methods on the interface (this causes the media player to play)
    await player.call_play()

    volume = await player.get_volume()
    print(f"current volume: {volume}, setting to 0.5")

    introspection = await bus.introspect(bus_name, object_path)
    print(introspection)


# loop.run_until_complete(main())
asyncio.run(main())
