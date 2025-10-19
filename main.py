import asyncio
import pylast
import os
from dotenv import load_dotenv
from dbus_next.aio import MessageBus
from dbus import MPrisPlayer, ServiceManager
from lastfm import Scrobbler

load_dotenv()
SERVICE_NAME = "org.mpris.MediaPlayer2.spotify"
# SERVICE_NAME = "org.mpris.MediaPlayer2.audacious"
OBJECT_PATH = "/org/mpris/MediaPlayer2"
API_KEY = os.getenv("LASTFM_API_KEY")
API_SECRET = os.getenv("LASTFM_API_SECRET")
USERNAME = os.getenv("LASTFM_USERNAME")
PASSWORD = os.getenv("LASTFM_PASSWORD")
PASSWORD_HASH = pylast.md5(PASSWORD)

DBUS_SERVICE_NAME = "org.freedesktop.DBus"
DBUS_OBJECT_PATH = "/org/freedesktop/DBus"


async def catch_change(artist, track):
    print(f"\nTracked Changed To:\n{track} - {artist}")
    scrobbler = Scrobbler(
        API_KEY,
        API_SECRET,
        USERNAME,
        PASSWORD_HASH,
    )

    await asyncio.to_thread(scrobbler.connect)
    # Delay .scrobble call instead of invoking the function and passing that value
    await asyncio.to_thread(lambda: scrobbler.scrobble(artist, track))
    print(f"Scrobbled: {track} - {artist}")

    return artist, track


async def main():
    service_manager = ServiceManager(DBUS_SERVICE_NAME, DBUS_OBJECT_PATH)
    await service_manager.connect()
    player = MPrisPlayer(
        SERVICE_NAME,
        OBJECT_PATH,
        catch_change,
        service_manager.bus,
    )
    await player.connect()

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
