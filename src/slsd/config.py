import hashlib
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(Exception):
    """Raised when the configuration is missing or invalid."""


@dataclass
class Config:
    api_key: str
    api_secret: str
    username: str | None = None
    password_hash: str | None = None
    session_key: str | None = None
    blacklist: list[str] = field(default_factory=list)
    threshold: float = 0.0

    @property
    def auth_mode(self) -> str:
        return "session" if self.session_key else "password"


def config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def config_file() -> Path:
    return config_home() / "slsd" / "config.toml"


def hash_password(password: str) -> str:
    return hashlib.md5(password.encode("utf-8")).hexdigest()


BUNDLED_API_KEY = "486bef1b515d38e53978f1d36f84a1ae"
BUNDLED_API_SECRET = "96ecd98d751ca3643349c5becbc05c8a"


def _resolve_api_keys(credentials: dict) -> tuple[str, str]:
    api_key = credentials.get("api_key")
    api_secret = credentials.get("api_secret")
    if api_key and api_secret:
        return api_key, api_secret
    if BUNDLED_API_KEY and BUNDLED_API_SECRET:
        return BUNDLED_API_KEY, BUNDLED_API_SECRET
    raise ConfigError(
        "`api_key` and `api_secret` are required under [credentials].\n"
        "Get them from https://www.last.fm/api/account_creation\n"
        f"Then update {config_file()}."
    )


def load_api_credentials(path: Path | None = None) -> tuple[str, str]:
    """Load just api_key/api_secret; used by `slsd setup` before any auth exists.

    Falls back to the bundled app credentials when the user has none.
    """
    path = path or config_file()

    credentials: dict = {}
    if path.exists():
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ConfigError(f"Could not parse {path}: {e}") from e
        if isinstance(data.get("credentials"), dict):
            credentials = data["credentials"]

    return _resolve_api_keys(credentials)


def load_config(path: Path | None = None) -> Config:
    path = path or config_file()

    data: dict = {}
    if path.exists():
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ConfigError(f"Could not parse {path}: {e}") from e

    credentials = data.get("credentials", {})
    if not isinstance(credentials, dict):
        credentials = {}
    api_key, api_secret = _resolve_api_keys(credentials)

    session_key = credentials.get("session_key")
    username = credentials.get("username")
    password = credentials.get("password")

    if session_key:
        pass
    elif password and username:
        session_key = None
    else:
        raise ConfigError(
            "No Last.fm authentication found.\n"
            "Run `slsd setup` to authenticate via your browser, or add "
            "`username` and `password` under [credentials] for manual auth."
        )

    options = data.get("options", {})
    if options is None:
        options = {}
    if not isinstance(options, dict):
        raise ConfigError("[options] must be a table.")

    blacklist = options.get("blacklist", [])
    if blacklist is None:
        blacklist = []
    if not isinstance(blacklist, list) or not all(
        isinstance(item, str) for item in blacklist
    ):
        raise ConfigError("`blacklist` must be a list of strings, e.g. [\"spotify\"].")

    threshold = options.get("threshold", 0)
    if threshold is None:
        threshold = 0
    if not isinstance(threshold, (int, float)) or threshold < 0:
        raise ConfigError("`threshold` must be a non-negative number of seconds.")

    return Config(
        api_key=api_key,
        api_secret=api_secret,
        username=username,
        password_hash=hash_password(password) if password else None,
        session_key=session_key,
        blacklist=blacklist,
        threshold=float(threshold),
    )


def save_session(
    session_key: str,
    username: str,
    path: Path | None = None,
) -> Path:
    """Persist session_key and username into the [credentials] section,
    preserving the rest of the file."""
    path = path or config_file()

    if path.exists():
        text = path.read_text(encoding="utf-8")
    else:
        text = "[credentials]\n"

    updated = _update_credentials_section(
        text, {"session_key": session_key, "username": username}
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated, encoding="utf-8")
    return path


def _update_credentials_section(text: str, updates: dict[str, str]) -> str:
    lines = text.splitlines()
    out: list[str] = []
    in_credentials = False
    replaced: set[str] = set()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("["):
            in_credentials = stripped == "[credentials]"
            out.append(line)
            continue
        if not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip().strip('"').strip("'")
            if in_credentials and key in updates and key not in replaced:
                out.append(f'{key} = "{updates[key]}"')
                replaced.add(key)
                continue
        out.append(line)

    missing = [key for key in updates if key not in replaced]

    if "[credentials]" in [line.strip() for line in lines]:
        insert_at = None
        for i, line in enumerate(out):
            if line.strip() == "[credentials]":
                insert_at = i + 1
                for j in range(i + 1, len(out)):
                    if out[j].strip().startswith("["):
                        insert_at = j
                        break
                break
    else:
        out.append("")
        out.append("[credentials]")
        insert_at = len(out)

    for offset, key in enumerate(missing):
        out.insert(insert_at + offset, f'{key} = "{updates[key]}"')

    return "\n".join(out).rstrip("\n") + "\n"
