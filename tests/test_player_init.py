from slsd.dbus import MPrisPlayer


def test_mpris_player_initialization():

    player = MPrisPlayer(
        service_name="org.mpris.MediaPlayer2.mockplayer",
        object_path="/org/mpris/MediaPlayer2",
        callback=None,
        bus=None,
    )

    assert player.service_name == "org.mpris.MediaPlayer2.mockplayer"
    assert player.object_path == "/org/mpris/MediaPlayer2"
    assert player.player is None
    assert player.bus is None
    assert player.introspection is None
    assert player.object is None
    assert player.properties is None
    assert player.metadata is None
    assert player.playback_status is None
    assert player.current_artist is None
    assert player.current_track is None
    assert player.previous_track is None
    assert player.callback is None
