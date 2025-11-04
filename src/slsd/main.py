import asyncio
import hashlib
import tomllib
import os
from pathlib import Path
from dbus import ServiceManager
from lastfm import Scrobbler

DBUS_SERVICE_NAME = "org.freedesktop.DBus"
DBUS_OBJECT_PATH = "/org/freedesktop/DBus"

CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
CONFIG_FILE = CONFIG_HOME / "slsd" / "config.toml"

# TODO: exception handlingzz
try:
    with open(CONFIG_FILE, "rb") as config:
        config_data = tomllib.load(config)
    if config_data:
        USERNAME = config_data.get("credentials").get("username")
        PASSWORD = config_data.get("credentials").get("password")
        API_KEY = config_data.get("credentials").get("api_key")
        API_SECRET = config_data.get("credentials").get("api_secret")
        PASSWORD_HASH = hashlib.md5(PASSWORD.encode("utf-8")).hexdigest()
        BLACKLIST = config_data.get("options").get("blacklist")
except Exception as e:
    print("Failed: ", e)

try:
    scrobbler = Scrobbler(
        API_KEY,
        API_SECRET,
        USERNAME,
        PASSWORD_HASH,
    )
except Exception as e:
    print("Failed to instantiate scrobbler object", e)


async def catch_property_change(artist, track):
    try:
        await asyncio.to_thread(scrobbler.connect)
    except Exception as e:
        print("Failed to connect to scrobbler, incorrect credentials?: ", e)

    # Delay .scrobble call instead of invoking the function and passing that value
    # await asyncio.to_thread(lambda: scrobbler.scrobble(artist, track))
    print(f"Scrobbled: {track} - {artist}")
    return artist, track


async def main():
    service_manager = ServiceManager(
        DBUS_SERVICE_NAME,
        DBUS_OBJECT_PATH,
        catch_property_change,
        BLACKLIST,
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
