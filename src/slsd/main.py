import asyncio
import getpass
import logging
import os
import shutil
from pathlib import Path

import typer

from slsd import config
from slsd.config import Config, ConfigError, save_session
from slsd.dbus import DBUS_OBJECT_PATH, DBUS_SERVICE_NAME, ServiceManager
from slsd.lastfm import (
    AuthError,
    Scrobbler,
    create_web_auth_url,
    open_browser,
    wait_for_authorization,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
for noisy in ("pylast", "httpx", "httpcore"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
log = logging.getLogger("slsd")

app = typer.Typer(no_args_is_help=True)


def load_config_or_exit() -> Config:
    try:
        cfg = config.load_config()
    except ConfigError as e:
        log.error("%s", e)
        raise typer.Exit(code=1) from e
    return cfg


def build_scrobbler(cfg: Config) -> Scrobbler:
    return Scrobbler(
        api_key=cfg.api_key,
        api_secret=cfg.api_secret,
        username=cfg.username,
        password_hash=cfg.password_hash,
        session_key=cfg.session_key,
    )


def ensure_dbus_environment():
    if os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        return

    uid = os.getuid()
    standard_path = Path(f"/run/user/{uid}/bus")

    if standard_path.exists() and standard_path.is_socket():
        os.environ["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={standard_path}"
        log.info("Found DBus socket at %s", standard_path)
        return

    for item in Path("/tmp").glob("dbus-*"):
        if item.is_socket():
            os.environ["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={item}"
            log.info("Found DBus socket at %s", item)
            return

    fallback = f"unix:path={standard_path}"
    os.environ["DBUS_SESSION_BUS_ADDRESS"] = fallback
    log.warning(
        "No DBus session socket found (checked %s and /tmp/dbus-*). "
        "Falling back to %s; players may not be detected.",
        standard_path,
        fallback,
    )


async def handle_scrobble(scrobbler: Scrobbler, artist: str | None, title: str | None):
    try:
        await asyncio.to_thread(scrobbler.scrobble, artist, title)
        log.info("Scrobbled: %s - %s", title, artist)
    except AuthError as e:
        log.error("%s", e)
    except Exception as e:
        log.error("Failed to scrobble '%s - %s': %s", title, artist, e)


async def _run_async_daemon(scrobbler: Scrobbler, cfg: Config):
    service_manager = ServiceManager(
        DBUS_SERVICE_NAME,
        DBUS_OBJECT_PATH,
        lambda artist, title: handle_scrobble(scrobbler, artist, title),
        cfg.blacklist,
        cfg.threshold,
    )
    if await service_manager.connect() is None:
        log.error("Could not connect to DBus; exiting. "
                  "Run slsd inside an active desktop session.")
        return

    auth_desc = (
        f"session key for '{cfg.username}'"
        if cfg.auth_mode == "session"
        else f"password credentials for '{cfg.username}'"
    )
    log.info("Daemon started using %s. Monitoring MPRIS players...", auth_desc)

    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        log.info("Daemon main task cancelled, shutting down")


@app.command()
def run():
    """Run the scrobbler daemon in the foreground."""
    cfg = load_config_or_exit()
    scrobbler = build_scrobbler(cfg)

    ensure_dbus_environment()

    try:
        asyncio.run(_run_async_daemon(scrobbler, cfg))
    except KeyboardInterrupt:
        log.info("Shutdown requested by user (Ctrl+C)")
    except Exception as e:
        log.error("An unexpected error occurred in the daemon: %s", e)


@app.command()
def setup():
    """Authenticate with Last.fm via your browser and save the session."""
    print("\nLast.fm setup\n", flush=True)

    try:
        api_key, api_secret = config.load_api_credentials()
        existing = None
    except ConfigError:
        try:
            existing = config.load_config()
            api_key, api_secret = existing.api_key, existing.api_secret
        except ConfigError as e:
            log.error("%s", e)
            raise typer.Exit(code=1) from e

    if existing and existing.session_key:
        print(f"A session already exists for '{existing.username}'.", flush=True)
        print("Continuing will replace it with a fresh authorization.\n", flush=True)

    try:
        generator, url = create_web_auth_url(api_key, api_secret)
    except Exception as e:
        log.error(
            "Could not request an auth token from Last.fm (%s).\n"
            "Check that `api_key` and `api_secret` in your config are correct.",
            e,
        )
        raise typer.Exit(code=1) from e

    print("Opening your browser to authorize slsd on Last.fm...", flush=True)
    print(f"If it does not open, visit this URL manually:\n\n  {url}\n", flush=True)
    open_browser(url)

    print("Waiting for authorization... (Ctrl+C to cancel)", flush=True)

    try:
        session_key, username = wait_for_authorization(generator, url)
    except AuthError as e:
        log.error("%s", e)
        raise typer.Exit(code=1) from e
    except KeyboardInterrupt:
        print("\nSetup cancelled. Nothing was saved.", flush=True)
        raise typer.Exit(code=1) from None

    path = save_session(session_key, username)

    print(f"\nSuccessfully authenticated as {username}.", flush=True)
    print(f"Configuration saved to {path}.", flush=True)
    print("You can now run `slsd run` or install the systemd service.", flush=True)


@app.command("install-service")
def install_service_command():
    """Install the slsd systemd user service."""
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
    except OSError as e:
        log.error("Failed to create systemd user directory '%s': %s", systemd_dir, e)
        raise typer.Exit(code=1) from e

    service_file_path = systemd_dir / "slsd.service"

    try:
        service_file_path.write_text(service_content)
        log.info("Service file written to: %s", service_file_path)
    except OSError as e:
        log.error("Failed to write service file to '%s': %s", service_file_path, e)
        raise typer.Exit(code=1) from e

    print("\nSystemd user service file created successfully!", flush=True)
    print(f"  Path: {service_file_path}", flush=True)

    try:
        cfg = config.load_config()
        authenticated = bool(cfg.session_key or cfg.password_hash)
    except ConfigError as e:
        print(f"\nConfig problem: {e}", flush=True)
        authenticated = False

    if not authenticated:
        print("\nNext step: authenticate with Last.fm:", flush=True)
        print("  slsd setup", flush=True)

    print("\nThen enable the service:", flush=True)
    print("  systemctl --user daemon-reload", flush=True)
    print("  systemctl --user enable --now slsd.service", flush=True)
    print("\nTo check its status and logs:", flush=True)
    print("  systemctl --user status slsd.service", flush=True)
    print("  journalctl --user -u slsd.service -f", flush=True)


def cli():
    app()


if __name__ == "__main__":
    cli()
