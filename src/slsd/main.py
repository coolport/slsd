import asyncio
import logging
from slsd import config

from dbus import ServiceManager
from lastfm import Scrobbler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

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
    log.error("Failed to instantiate scrobbler object: %s", e)


async def catch_property_change(artist, track):
    try:
        await asyncio.to_thread(scrobbler.connect)
    except Exception as e:
        log.error("Failed to connect to Last.fm, incorrect credentials?: %s", e)
        return

    try:
        await asyncio.to_thread(lambda: scrobbler.scrobble(artist, track))
        log.info("Successfully scrobbled: %s - %s", track, artist)
    except Exception as e:
        log.error("Failed to scrobble '%s - %s': %s", track, artist, e)


async def main():
    threshold = getattr(config, "THRESHOLD", 0)

    service_manager = ServiceManager(
        DBUS_SERVICE_NAME,
        DBUS_OBJECT_PATH,
        catch_property_change,
        config.BLACKLIST,
        threshold,
    )
    await service_manager.connect()

    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        log.info("Main task cancelled, shutting down.")
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Shutting down")
