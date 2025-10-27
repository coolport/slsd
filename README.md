### Configuration
This project looks for `$XDG_CONFIG_HOME/slsd/config.toml`

Sample:
```toml
[credentials]
username = "username"
password = "password"
api_key = "7abd4278b39f061fc108bdf148c67db4"
api_secret = "4281fcb749ba1ec9c1e32121d85c0192c"

[options]
blacklist = ["firefox-esr", "playerctl", "spotify"]
```
Given that this is a universal scrobbler for all programs that expose an MPRIS interface, I advise that you blacklist these things:
1. Browsers - unless you want all of last.fm to see your watch history across all sites
2. Programs like `playerctl` that proxy over other mpris programs, resulting in multiple scrobbles and other race conditions
3. Programs which you prefer to use the native scrobbling implementation (ex. last.fm's official spotify scrobbler)
