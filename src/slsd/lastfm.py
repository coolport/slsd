import logging
import time
import webbrowser

import pylast

log = logging.getLogger(__name__)

DEFAULT_AUTH_TIMEOUT = 300
POLL_INTERVAL = 2


class AuthError(Exception):
    """Last.fm authentication failed; message tells the user what to do."""


AUTH_ERROR_IDS = {"4", "9", "10", "26"}
PENDING_TOKEN_ERROR_IDS = {"14"}


def _translate(e: Exception) -> Exception:
    if isinstance(e, pylast.WSError):
        if e.get_id() in AUTH_ERROR_IDS:
            return AuthError(
                "Last.fm rejected our credentials.\n"
                "If you use `slsd setup`, run it again to get a new session; "
                "otherwise check username/password/api keys in your config."
            )
        return e
    return e


class Scrobbler:
    def __init__(
        self,
        api_key,
        api_secret,
        username=None,
        password_hash=None,
        session_key=None,
    ):
        if not (session_key or (username and password_hash)):
            raise ValueError(
                "Either session_key or username+password_hash is required."
            )
        self.api_key = api_key
        self.api_secret = api_secret
        self.username = username
        self.password_hash = password_hash
        self.session_key = session_key
        self.network = None

    def connect(self) -> pylast.LastFMNetwork:
        if self.network is not None:
            return self.network

        kwargs = {
            "api_key": self.api_key,
            "api_secret": self.api_secret,
        }
        if self.session_key:
            kwargs["session_key"] = self.session_key
        else:
            kwargs["username"] = self.username
            kwargs["password_hash"] = self.password_hash

        self.network = pylast.LastFMNetwork(**kwargs)
        return self.network

    def scrobble(self, artist, title):
        network = self.connect()
        timestamp = int(time.time())
        try:
            network.scrobble(artist=artist, title=title, timestamp=timestamp)
        except Exception as e:
            translated = _translate(e)
            if isinstance(translated, AuthError):
                self.network = None
            raise translated from e


def create_web_auth_url(api_key: str, api_secret: str) -> tuple[pylast.SessionKeyGenerator, str]:
    network = pylast.LastFMNetwork(api_key=api_key, api_secret=api_secret)
    generator = pylast.SessionKeyGenerator(network)
    return generator, generator.get_web_auth_url()


def wait_for_authorization(
    generator: pylast.SessionKeyGenerator,
    url: str,
    timeout: float = DEFAULT_AUTH_TIMEOUT,
    poll_interval: float = POLL_INTERVAL,
) -> tuple[str, str]:
    """Poll Last.fm until the token is authorized. Returns (session_key, username)."""
    deadline = time.monotonic() + timeout
    next_progress_log = time.monotonic() + 15

    while True:
        try:
            return generator.get_web_auth_session_key_username(url)
        except pylast.WSError as e:
            if e.get_id() in PENDING_TOKEN_ERROR_IDS:
                pass
            elif e.get_id() in AUTH_ERROR_IDS:
                raise AuthError(
                    f"Last.fm refused to create a session for token: {e}"
                ) from e
            else:
                raise _translate(e) from e
        except pylast.NetworkError as e:
            log.debug("Network error while polling for authorization: %s", e)

        now = time.monotonic()
        if now >= deadline:
            raise AuthError(
                f"Timed out after {int(timeout)}s waiting for authorization on "
                "last.fm.\nRun `slsd setup` and make sure to click 'Allow access' "
                "in the browser."
            )
        if now >= next_progress_log:
            log.info("Still waiting for authorization... (Ctrl+C to cancel)")
            next_progress_log = now + 15
        time.sleep(poll_interval)


def open_browser(url: str, opener=webbrowser.open) -> bool:
    try:
        if opener(url):
            return True
    except Exception as e:
        log.debug("Browser launch failed: %s", e)
    log.warning(
        "Could not launch a browser automatically; "
        "please open the URL shown above manually."
    )
    return False
