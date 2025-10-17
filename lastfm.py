import pylast
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("LASTFM_API_KEY")
API_SECRET = os.getenv("LASTFM_API_SECRET")
USERNAME = os.getenv("LASTFM_USERNAME")
PASSWORD = os.getenv("LASTFM_PASSWORD")
PASSWORD_HASH = pylast.md5(PASSWORD)


class Scrobbler:
    def __init__(self, api_key, api_secret, username, password_hash):
        self.api_key = api_key
        self.api_secret = api_secret
        self.username = username
        self.password_hash = password_hash
        self.network = None

    def connect(self):
        self.network = pylast.LastFMNetwork(
            api_key=self.api_key,
            api_secret=self.api_secret,
            username=self.username,
            password_hash=self.password_hash,
        )
        return self


def main():
    scrobbler = Scrobbler(API_KEY, API_SECRET, USERNAME, PASSWORD_HASH).connect()

    track = scrobbler.network.get_track("Iron Maiden", "The Nomad")
    track.love()

    # artist = "Iron Maiden"
    # title = "The Nomad"
    # base_timestamp = int(time.time())
    # print(base_timestamp)
    # # print(pylast.__file__)
    #
    # for x in range(1):
    #     ts = base_timestamp - x
    #     network.scrobble(artist=artist, title=title, timestamp=ts)


if __name__ == "__main__":
    main()
