import pylast
import os
import time


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

    def scrobble(self, artist, title):
        artist = artist
        title = title
        timestamp = int(time.time())
        self.network.scrobble(artist=artist, title=title, timestamp=timestamp)
