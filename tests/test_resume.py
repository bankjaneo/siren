"""Tests for automatic resume when the speaker briefly disconnects."""

import types
from unittest import mock

import stream_audio


class FakeStatus:
    """Minimal stand-in for the media controller status object."""

    def __init__(self, player_state="PLAYING"):
        self.player_state = player_state


class FakeMediaController:
    """Minimal stand-in for the Chromecast media controller."""

    def __init__(self, player_state="PLAYING"):
        self.status = FakeStatus(player_state)

    def play_media(self, *args, **kwargs):
        return True

    def stop(self):
        return None


class FakeConnectionStatus:
    """Minimal stand-in for the socket client connection status."""

    def __init__(self, status):
        self.status = status


def reset_state():
    """Reset module globals to a clean, known state between tests."""
    stream_audio.is_paused = True
    stream_audio.chromecast = None
    stream_audio.media_controller = None
    stream_audio.stream_active = False
    stream_audio.connection_lost = False
    stream_audio.reconnect_running = False
    stream_audio.current_file_index = 0


def test_listener_triggers_reconnect_while_playing(monkeypatch):
    reset_state()
    stream_audio.stream_active = True
    stream_audio.is_paused = False

    started = []
    monkeypatch.setattr(stream_audio, "start_reconnect", lambda: started.append(True))

    listener = stream_audio.ConnectionListener()
    listener.new_connection_status(FakeConnectionStatus("DISCONNECTED"))

    assert started == [True]


def test_listener_calls_start_reconnect_even_when_paused(monkeypatch):
    reset_state()
    stream_audio.stream_active = True
    stream_audio.is_paused = True

    started = []
    monkeypatch.setattr(stream_audio, "start_reconnect", lambda: started.append(True))

    listener = stream_audio.ConnectionListener()
    listener.new_connection_status(FakeConnectionStatus("FAILED"))

    assert started == [True]


def test_start_reconnect_noop_when_paused(monkeypatch):
    reset_state()
    stream_audio.stream_active = True
    stream_audio.is_paused = True

    thread_spawned = []
    monkeypatch.setattr(
        stream_audio.threading.Thread,
        "start",
        lambda self: thread_spawned.append(True),
    )

    stream_audio.start_reconnect()

    assert thread_spawned == []
    assert stream_audio.reconnect_running is False


def test_start_reconnect_noop_when_not_streaming(monkeypatch):
    reset_state()
    stream_audio.stream_active = False
    stream_audio.is_paused = False

    thread_spawned = []
    monkeypatch.setattr(
        stream_audio.threading.Thread,
        "start",
        lambda self: thread_spawned.append(True),
    )

    stream_audio.start_reconnect()

    assert thread_spawned == []
    assert stream_audio.reconnect_running is False


def test_start_reconnect_spawns_single_thread(monkeypatch):
    reset_state()
    stream_audio.stream_active = True
    stream_audio.is_paused = False

    thread_spawned = []
    monkeypatch.setattr(
        stream_audio.threading.Thread,
        "start",
        lambda self: thread_spawned.append(True),
    )

    stream_audio.start_reconnect()
    stream_audio.start_reconnect()

    assert stream_audio.connection_lost is True
    assert stream_audio.reconnect_running is True
    assert thread_spawned == [True]


def test_reconnect_loop_resumes_playback(monkeypatch):
    reset_state()
    stream_audio.stream_active = True
    stream_audio.is_paused = False
    stream_audio.connection_lost = True
    stream_audio.reconnect_running = True
    stream_audio.chromecast = mock.Mock()
    stream_audio.media_controller = FakeMediaController("PLAYING")
    stream_audio.current_file_index = 3

    calls = []
    monkeypatch.setattr(stream_audio, "RECONNECT_ATTEMPTS", 5)
    monkeypatch.setattr(stream_audio, "RECONNECT_DELAY", 0)
    monkeypatch.setattr(
        stream_audio,
        "time",
        types.SimpleNamespace(
            sleep=lambda _: None,
            time=lambda: 0,
        ),
    )
    monkeypatch.setattr(
        stream_audio,
        "find_chromecast",
        lambda device: calls.append(("find", device)) or True,
    )
    monkeypatch.setattr(
        stream_audio,
        "play_stream_on_chromecast",
        lambda: calls.append(("play",)) or True,
    )
    monkeypatch.setattr(
        stream_audio, "stop_media_controller", lambda: calls.append(("stop",))
    )

    stream_audio.reconnect_loop()

    assert calls[0] == ("find", stream_audio.DEFAULT_DEVICE)
    assert ("play",) in calls
    assert ("stop",) in calls
    assert stream_audio.connection_lost is False
    assert stream_audio.reconnect_running is False


def test_reconnect_loop_cancelled_on_stop(monkeypatch):
    reset_state()
    stream_audio.stream_active = True
    stream_audio.is_paused = False
    stream_audio.connection_lost = True
    stream_audio.reconnect_running = True

    monkeypatch.setattr(stream_audio, "RECONNECT_ATTEMPTS", 10)
    monkeypatch.setattr(stream_audio, "RECONNECT_DELAY", 0)
    monkeypatch.setattr(
        stream_audio,
        "time",
        types.SimpleNamespace(
            sleep=lambda _: setattr(stream_audio, "is_paused", True),
            time=lambda: 0,
        ),
    )
    monkeypatch.setattr(stream_audio, "find_chromecast", lambda d: True)

    stream_audio.reconnect_loop()

    assert stream_audio.connection_lost is False
    assert stream_audio.reconnect_running is False


def test_reconnect_loop_cancelled_when_paused_during_find(monkeypatch):
    reset_state()
    stream_audio.stream_active = True
    stream_audio.is_paused = False
    stream_audio.connection_lost = True
    stream_audio.reconnect_running = True

    played = []
    monkeypatch.setattr(stream_audio, "RECONNECT_ATTEMPTS", 5)
    monkeypatch.setattr(stream_audio, "RECONNECT_DELAY", 0)
    monkeypatch.setattr(
        stream_audio,
        "time",
        types.SimpleNamespace(
            sleep=lambda _: None,
            time=lambda: 0,
        ),
    )

    def fake_find(device):
        stream_audio.is_paused = True
        return True

    monkeypatch.setattr(stream_audio, "find_chromecast", fake_find)
    monkeypatch.setattr(
        stream_audio, "play_stream_on_chromecast", lambda: played.append(True) or True
    )

    stream_audio.reconnect_loop()

    assert played == []
    assert stream_audio.connection_lost is False
    assert stream_audio.reconnect_running is False
    reset_state()
    stream_audio.stream_active = True
    stream_audio.is_paused = False
    stream_audio.connection_lost = True
    stream_audio.reconnect_running = True

    monkeypatch.setattr(stream_audio, "RECONNECT_ATTEMPTS", 3)
    monkeypatch.setattr(stream_audio, "RECONNECT_DELAY", 0)
    monkeypatch.setattr(
        stream_audio,
        "time",
        types.SimpleNamespace(
            sleep=lambda _: None,
            time=lambda: 0,
        ),
    )
    monkeypatch.setattr(stream_audio, "find_chromecast", lambda d: False)

    stream_audio.reconnect_loop()

    assert stream_audio.connection_lost is False
    assert stream_audio.reconnect_running is False


def test_reconnect_loop_gives_up_after_attempts(monkeypatch):
    reset_state()
    stream_audio.stream_active = True
    stream_audio.is_paused = False
    stream_audio.connection_lost = True
    stream_audio.reconnect_running = True

    monkeypatch.setattr(stream_audio, "RECONNECT_ATTEMPTS", 3)
    monkeypatch.setattr(stream_audio, "RECONNECT_DELAY", 0)
    monkeypatch.setattr(
        stream_audio,
        "time",
        types.SimpleNamespace(
            sleep=lambda _: None,
            time=lambda: 0,
        ),
    )
    monkeypatch.setattr(stream_audio, "find_chromecast", lambda d: False)

    stream_audio.reconnect_loop()

    assert stream_audio.connection_lost is False
    assert stream_audio.reconnect_running is False


def test_pause_clears_connection_lost(monkeypatch):
    reset_state()
    stream_audio.connection_lost = True

    with stream_audio.app.test_client() as client:
        response = client.get("/pause")

    assert response.status_code == 200
    assert stream_audio.connection_lost is False
    assert stream_audio.is_paused is True


def test_watchdog_poll_healthy_state_returns_zero(monkeypatch):
    reset_state()
    stream_audio.stream_active = True
    stream_audio.is_paused = False
    stream_audio.chromecast = mock.Mock()
    stream_audio.chromecast.status.app_id = "CC1AD845"
    stream_audio.media_controller = FakeMediaController("PLAYING")

    restarted = []
    monkeypatch.setattr(
        stream_audio, "play_stream_on_chromecast", lambda: restarted.append(True)
    )

    assert stream_audio.watchdog_poll(0) == 0
    assert restarted == []


def test_watchdog_poll_restarts_after_two_bad_polls(monkeypatch):
    reset_state()
    stream_audio.stream_active = True
    stream_audio.is_paused = False
    stream_audio.chromecast = mock.Mock()
    stream_audio.chromecast.status.app_id = "CC1AD845"
    stream_audio.media_controller = FakeMediaController("IDLE")

    restarted = []
    monkeypatch.setattr(
        stream_audio, "play_stream_on_chromecast", lambda: restarted.append(True)
    )

    assert stream_audio.watchdog_poll(0) == 1
    assert restarted == []
    assert stream_audio.watchdog_poll(1) == 0
    assert restarted == [True]


def test_watchdog_poll_skips_when_paused_or_reconnecting(monkeypatch):
    reset_state()
    stream_audio.stream_active = True
    stream_audio.is_paused = True
    stream_audio.chromecast = mock.Mock()
    stream_audio.chromecast.status.app_id = None
    stream_audio.media_controller = FakeMediaController("IDLE")

    restarted = []
    monkeypatch.setattr(
        stream_audio, "play_stream_on_chromecast", lambda: restarted.append(True)
    )

    assert stream_audio.watchdog_poll(1) == 0
    assert restarted == []


def test_watchdog_poll_skips_when_paused_on_device():
    """Device-side pause (PAUSED state) must not be fought by the watchdog."""
    reset_state()
    stream_audio.stream_active = True
    stream_audio.is_paused = False
    stream_audio.chromecast = mock.Mock()
    stream_audio.chromecast.status.app_id = "CC1AD845"
    stream_audio.media_controller = FakeMediaController("PAUSED")

    restarted = []
    stream_audio.play_stream_on_chromecast = lambda: restarted.append(True)

    assert stream_audio.watchdog_poll(1) == 0
    assert restarted == []
