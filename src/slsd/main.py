import asyncio
from slsd import config

from dbus import ServiceManager
from lastfm import Scrobbler

DBUS_SERVICE_NAME = "org.freedesktop.DBus"
DBUS_OBJECT_PATH = "/org/freedesktop/DBus"

try:
    scrobbler = Scrobbler(
        config.API_KEY,
        config.API_SECRET,
        config.USERNAME,
        config.PASSWORD_HASH,
    )
except Exception as e:
    print("Failed to instantiate scrobbler object", e)


# TODO: exception handling etc
async def catch_property_change(artist, track):
    try:
        await asyncio.to_thread(scrobbler.connect)
    except Exception as e:
        print("Failed to connect to scrobbler, incorrect credentials?: ", e)

    await asyncio.to_thread(lambda: scrobbler.scrobble(artist, track))
    print(f"Scrobbled: {track} - {artist}")
    return artist, track


async def main():
    service_manager = ServiceManager(
        DBUS_SERVICE_NAME,
        DBUS_OBJECT_PATH,
        catch_property_change,
        config.BLACKLIST,
    )
    await service_manager.connect()

    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nPress again to exit.")
