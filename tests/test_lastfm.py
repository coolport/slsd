from lastfm import Scrobbler

DUMMY_API_KEY = "test_api_key"
DUMMY_API_SECRET = "test_api_secret"
DUMMY_USERNAME = "test_user"
DUMMY_PASSWORD_HASH = "test_password_hash"


# Test if scrobbler instance loads correct values
def test_scrobbler_initialization():
    scrobbler = Scrobbler(
        api_key=DUMMY_API_KEY,
        api_secret=DUMMY_API_SECRET,
        username=DUMMY_USERNAME,
        password_hash=DUMMY_PASSWORD_HASH,
    )

    assert scrobbler.api_key == DUMMY_API_KEY
    assert scrobbler.api_secret == DUMMY_API_SECRET
    assert scrobbler.username == DUMMY_USERNAME
    assert scrobbler.password_hash == DUMMY_PASSWORD_HASH
    assert scrobbler.network is None
