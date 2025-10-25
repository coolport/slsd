import asyncio
import hashlib
import os
from dotenv import load_dotenv
from dbus import ServiceManager
from lastfm import Scrobbler

load_dotenv()
API_KEY = os.getenv("LASTFM_API_KEY")
API_SECRET = os.getenv("LASTFM_API_SECRET")
USERNAME = os.getenv("LASTFM_USERNAME")
PASSWORD = os.getenv("LASTFM_PASSWORD")
PASSWORD_HASH = hashlib.md5(PASSWORD.encode("utf-8")).hexdigest()

DBUS_SERVICE_NAME = "org.freedesktop.DBus"
DBUS_OBJECT_PATH = "/org/freedesktop/DBus"


async def catch_property_change(artist, track):
    print(f"\nTracked Changed To:\n{track} - {artist}")
    scrobbler = Scrobbler(
        API_KEY,
        API_SECRET,
        USERNAME,
        PASSWORD_HASH,
    )

    await asyncio.to_thread(scrobbler.connect)
    # Delay .scrobble call instead of invoking the function and passing that value
    # await asyncio.to_thread(lambda: scrobbler.scrobble(artist, track))
    print(
        f"Scrobbled: {track} - {artist}"
    )  # just to show when the scrobble will fire, because i dont want it to actually reflect in my account as im debugging
    return artist, track


async def main():
    service_manager = ServiceManager(
        DBUS_SERVICE_NAME,
        DBUS_OBJECT_PATH,
        catch_property_change,
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
