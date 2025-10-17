import asyncio
import pylast
import os
from dotenv import load_dotenv
from dbus_next.aio import MessageBus
from dbus import MPrisPlayer
from lastfm import Scrobbler

load_dotenv()
BUS_NAME = "org.mpris.MediaPlayer2.audacious"
OBJECT_PATH = "/org/mpris/MediaPlayer2"
API_KEY = os.getenv("LASTFM_API_KEY")
API_SECRET = os.getenv("LASTFM_API_SECRET")
USERNAME = os.getenv("LASTFM_USERNAME")
PASSWORD = os.getenv("LASTFM_PASSWORD")
PASSWORD_HASH = pylast.md5(PASSWORD)


async def main():
    player = MPrisPlayer(BUS_NAME, OBJECT_PATH)
    scrobbler = Scrobbler(API_KEY, API_SECRET, USERNAME, PASSWORD_HASH)
    await player.connect()
    await asyncio.to_thread(scrobbler.connect)

    meta = await player.get_metadata()
    print(meta)

    artist = "Iron Maiden"
    title = "The Nomad"
    # Delay .scrobble call instead of invoking the function and passing that value
    await asyncio.to_thread(lambda: scrobbler.scrobble(artist, title))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting")
