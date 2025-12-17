# slsd - simple last.fm scrobbling daemon

![PyPI - Version](https://img.shields.io/pypi/v/slsd?style=flat)
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/coolport/slsd/.github%2Fworkflows%2Fpublish.yml)

This project was a personal tool of mine turned into a more full (yet minimalistic) program/daemon. It is used for background scrobbling of music to last.fm and is compatible with any music player (and browsers, or other apps) as long as they expose an MPRIS interface to DBus (which most players do).
The difference between this program and others is in the daemonization, where compatability is maximized since systemd can be odd sometimes, and with the setup -- installing the program is easy with pipx, and the program itself provides a cli for setting up the systemd service file. 

## Installation
```BASH
pipx install slsd
slsd install-service (or 'slsd run' to run it in the foreground)
```
After install, simply follow the steps that will be displayed in your terminal:
```BASH
Systemd user service file created successfully!
Path: /home/aidan/.config/systemd/user/slsd.service

Please set up the config file in $XDG_CONFIG_HOME/slsd/config.toml
template can be found in the README

To enable the service::
  systemctl --user daemon-reload
  systemctl --user enable --now slsd.service

To check its status and logs:
  systemctl --user status slsd.service
  journalctl --user -u slsd.service -f
```

## Configuration
This project looks for `$XDG_CONFIG_HOME/slsd/config.toml`

Template:
```toml
[credentials]
username = "lastfm_username"
password = "lastfm_password"
api_key = "7abd4278b39f061fc108bdf148c67db4" # Get these from your account page
api_secret = "4281fcb749ba1ec9c1e32121d85c0192c"

[options]
blacklist = ["firefox-esr", "playerctl", "spotify"]
threshold = 30 
```
Given that this is a universal scrobbler for all programs that expose an MPRIS interface, here are some things that you might want to blacklist:
1. Browsers - unless you want to scrobble your youtube watch history
2. Programs that may cause conflict. Example: `playerctl` which proxies over other mpris programs, resulting in duplicate scrobbles and other race conditions
3. Programs which you prefer to use the native scrobbling implementation (ex. last.fm's official spotify scrobbler)
   
The `threshold` key defines your hard scrobble threshold in seconds. The program will scrobble depending on what comes first between: the threshold defined above, half of the song length (if song =>30s), and 4 minutes. With the last two being official last.fm scrobbling spec.

## Development
This project uses uv, please ensure that it is installed.
```BASH
git clone https://github.com/coolport/slsd
cd slsd
uv sync
uv run src/slsd/main.py
```
to run tests do 
```BASH
uv run pytest
