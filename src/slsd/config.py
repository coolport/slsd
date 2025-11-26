import tomllib
import os
import hashlib
from pathlib import Path

CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
CONFIG_FILE = CONFIG_HOME / "slsd" / "config.toml"

try:
    with open(CONFIG_FILE, "rb") as user_config:
        config_data = tomllib.load(user_config)
    if config_data:
        USERNAME = config_data.get("credentials").get("username")
        PASSWORD = config_data.get("credentials").get("password")
        API_KEY = config_data.get("credentials").get("api_key")
        API_SECRET = config_data.get("credentials").get("api_secret")
        PASSWORD_HASH = hashlib.md5(PASSWORD.encode("utf-8")).hexdigest()
        BLACKLIST = config_data.get("options").get("blacklist")
        THRESHOLD = config_data.get("options").get("threshold")
except Exception as e:
    print("Failed: ", e)
