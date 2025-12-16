import asyncio
import logging
import shutil
import os
from pathlib import Path
import getpass
import typer

from slsd import config
from slsd.dbus import ServiceManager
from slsd.lastfm import Scrobbler

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

DBUS_SERVICE_NAME = "org.freedesktop.DBus"
DBUS_OBJECT_PATH = "/org/freedesktop/DBus"

app = typer.Typer()

try:
    scrobbler = Scrobbler(
        config.API_KEY,
        config.API_SECRET,
        config.USERNAME,
        config.PASSWORD_HASH,
    )
except Exception as e:
    log.error("Failed to instantiate scrobbler object: %s", e)


def ensure_dbus_environment():
    if os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        log.info("Using existing DBus address from environment")
        return

    log.info("DBus address not set, attempting auto-detection...")

    # Case 1: Standard location
    uid = os.getuid()
    standard_path = Path(f"/run/user/{uid}/bus")

    if standard_path.exists() and standard_path.is_socket():
        dbus_addr = f"unix:path={standard_path}"
        os.environ["DBUS_SESSION_BUS_ADDRESS"] = dbus_addr
        log.info("Found DBus socket at: %s", dbus_addr)
        return

    # Case 2: tmp (like mine)
    log.info("Standard location not found, searching /tmp...")
    tmp_dir = Path("/tmp")

    for item in tmp_dir.glob("dbus-*"):
        if item.is_socket():
            dbus_addr = f"unix:path={item}"
            os.environ["DBUS_SESSION_BUS_ADDRESS"] = dbus_addr
            log.info("✓ Found DBus socket at: %s", dbus_addr)
            return

    # If we get here, no socket was found
    log.error("Could not find any DBus session socket!")
    log.error("Service may not detect MPRIS players.")
    log.error("Checked: %s and /tmp/dbus-*", standard_path)

    # Set fallback
    fallback = f"unix:path=/run/user/{uid}/bus"
    os.environ["DBUS_SESSION_BUS_ADDRESS"] = fallback
    log.warning("Using fallback address: %s", fallback)


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


async def _run_async_daemon():
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
        log.info("Daemon started. Monitoring MPRIS players...")
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        log.info("Daemon main task cancelled, shutting down")


@app.command()
def run():
    ensure_dbus_environment()

    try:
        asyncio.run(_run_async_daemon())
    except KeyboardInterrupt:
        log.info("Shutdown requested by user (Ctrl+C)")
    except Exception as e:
        log.error("An unexpected error occurred in the daemon: %s", e)


@app.command("install-service")
def install_service_command():
    log.info("Attempting to install systemd user service for slsd...")

    executable_path = shutil.which("slsd")
    if not executable_path:
        log.error(
            "Could not find 'slsd' executable in PATH. "
            "Please ensure the package is installed via 'pipx install slsd' or 'pip install slsd'."
        )
        raise typer.Exit(code=1)

    log.info("Found slsd executable at: %s", executable_path)

    current_user = getpass.getuser()
    service_content = f"""[Unit]
Description=Last.fm Scrobbler Daemon for {current_user}
PartOf=graphical-session.target
After=graphical-session.target

[Service]
Type=simple
ExecStart={executable_path} run
Restart=always
RestartSec=10
TimeoutStopSec=5
SyslogIdentifier=slsd

[Install]
WantedBy=graphical-session.target
"""

    systemd_dir = Path.home() / ".config" / "systemd" / "user"
    try:
        systemd_dir.mkdir(parents=True, exist_ok=True)
        log.info("Ensured systemd user directory exists at: %s", systemd_dir)
    except OSError as e:
        log.error("Failed to create systemd user directory '%s': %s", systemd_dir, e)
        raise typer.Exit(code=1)

    service_file_path = systemd_dir / "slsd.service"

    try:
        service_file_path.write_text(service_content)
        log.info("Service file written to: %s", service_file_path)
    except OSError as e:
        log.error("Failed to write service file to '%s': %s", service_file_path, e)
        raise typer.Exit(code=1)

    print("\nSystemd user service file created successfully!")
    print(f" Path: {service_file_path}")
    print(f"\nPlease set up the config file in $XDG_CONFIG_HOME/slsd/config.toml")
    print(f"template can be found in the README")
    print("\nNext steps: enable the service. Example:")
    print("\n  systemctl --user daemon-reload")
    print("  systemctl --user enable --now slsd.service")
    print("\nTo check its status and logs:")
    print("  systemctl --user status slsd.service")
    print("  journalctl --user -u slsd.service -f")


def cli():
    app()


if __name__ == "__main__":
    cli()
