"""Tests for the UI-facing API contract: /status fields and /play-file."""

from unittest import mock

import stream_audio
from tests.test_resume import FakeMediaController, reset_state


def test_status_includes_stream_and_connection_state():
    reset_state()
    stream_audio.stream_active = True
    stream_audio.connection_lost = True

    with stream_audio.app.test_client() as client:
        response = client.get("/status")
        payload = response.get_json()

    assert response.status_code == 200
    assert payload["stream_active"] is True
    assert payload["connection_lost"] is True
    assert payload["is_paused"] is True
    assert payload["chromecast_connected"] is False


def test_play_file_jumps_to_index(monkeypatch):
    reset_state()
    stream_audio.chromecast = mock.Mock()
    stream_audio.media_controller = FakeMediaController("PLAYING")
    stream_audio.current_file_index = 0
    stream_audio.is_paused = True

    calls = []
    monkeypatch.setattr(
        stream_audio, "stop_media_controller", lambda: calls.append("stop")
    )
    monkeypatch.setattr(
        stream_audio,
        "play_stream_on_chromecast",
        lambda: calls.append("play") or True,
    )

    with stream_audio.app.test_client() as client:
        response = client.get("/play-file/1")

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["status"] == "success"
    assert payload["file_index"] == 1
    assert stream_audio.current_file_index == 1
    assert stream_audio.is_paused is False
    assert stream_audio.stream_active is True
    assert calls == ["stop", "play"]


def test_play_file_rejects_out_of_range_index():
    reset_state()
    stream_audio.chromecast = mock.Mock()

    with stream_audio.app.test_client() as client:
        response = client.get("/play-file/99")

    payload = response.get_json()
    assert payload["status"] == "failed"
    assert stream_audio.current_file_index == 0


def test_play_file_requires_connected_chromecast():
    reset_state()

    with stream_audio.app.test_client() as client:
        response = client.get("/play-file/0")

    payload = response.get_json()
    assert payload["status"] == "failed"
    assert payload["message"] == "No Chromecast device connected"
