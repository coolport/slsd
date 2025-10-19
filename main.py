import asyncio
import pylast
import os
from dotenv import load_dotenv
from dbus_next.aio import MessageBus
from dbus import MPrisPlayer
from lastfm import Scrobbler

load_dotenv()
# SERVICE_NAME = "org.mpris.MediaPlayer2.spotify"
SERVICE_NAME = "org.mpris.MediaPlayer2.audacious"
OBJECT_PATH = "/org/mpris/MediaPlayer2"
API_KEY = os.getenv("LASTFM_API_KEY")
API_SECRET = os.getenv("LASTFM_API_SECRET")
USERNAME = os.getenv("LASTFM_USERNAME")
PASSWORD = os.getenv("LASTFM_PASSWORD")
PASSWORD_HASH = pylast.md5(PASSWORD)


# class ScrobbleQueue:
#     def __init__(self):


async def catch_change(artist, track):
    print(f"\nTracked Changed To:\n{track} - {artist}")
    scrobbler = Scrobbler(API_KEY, API_SECRET, USERNAME, PASSWORD_HASH)

    # await asyncio.to_thread(scrobbler.connect)
    # Delay .scrobble call instead of invoking the function and passing that value
    # await asyncio.to_thread(lambda: scrobbler.scrobble(artist, track))

    return artist, track


async def catch_owner_change(name, old_owner, new_owner):
    # print("Name: ", name)
    # print("Old Owner: ", old_owner)
    # print("New Owner: ", new_owner)
    if name.startswith("org.mpris.MediaPlayer2."):
        print(f"Player change: {name}, Old: {old_owner}, New: {new_owner}")


async def main():
    player = MPrisPlayer(SERVICE_NAME, OBJECT_PATH, catch_change, catch_owner_change)
    await player.connect()

    meta = await player.get_metadata()
    print("\nPlayer Metadata: ", meta)

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
