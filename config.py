from pathlib import Path
import os
import tomllib

with open("test.toml", "rb") as f:
    data = tomllib.load(f)

print("Data: ", data)
# {
#     "credentials": {"username": "aidan", "password": "123"},
#     "whitelist": {"name": ["player1", "player2"]},
# }
print("Username: ", (data.get("credentials")).get("username"))


config_home1 = os.environ.get("XDG_CONFIG_HOME")
config_home2 = Path.home()
config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
config_file = config_home / "slsd" / "config.toml"
print(config_file)


try:
    with open(config_file, "rb") as config:
        config_data = tomllib.load(config)
    if config_data:
        print(config_data)
except Exception as e:
    print("Failed: ", e)
