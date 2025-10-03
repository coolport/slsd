import pylast
import time
import asyncio
import os
from dotenv import load_dotenv


def main():
    load_dotenv()
    print("PyLast Test")
    API_KEY = os.getenv("LASTFM_API_KEY")
    API_SECRET = os.getenv("LASTFM_API_SECRET")

    username = os.getenv("LASTFM_USERNAME")
    password = os.getenv("LASTFM_PASSWORD")
    password_hash = pylast.md5(password)

    network = pylast.LastFMNetwork(
        api_key=API_KEY,
        api_secret=API_SECRET,
        username=username,
        password_hash=password_hash,
    )

    track = network.get_track("Iron Maiden", "The Nomad")
    track.love()

    artist = "Iron Maiden"
    title = "The Nomad"
    base_timestamp = int(time.time())
    print(base_timestamp)
    # print(pylast.__file__)

    for x in range(1):
        ts = base_timestamp - x
        network.scrobble(artist=artist, title=title, timestamp=ts)


if __name__ == "__main__":
    main()
