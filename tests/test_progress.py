"""Tests for the play progress reporting in /status."""

import types
from unittest import mock

import stream_audio
from tests.test_resume import reset_state


def reset_progress_state():
    """Reset the progress-tracking globals in addition to the core state."""
    reset_state()
    stream_audio.stream_file_elapsed = 0.0
    stream_audio.stream_file_position = 0
    stream_audio.stream_file_size = 0
    stream_audio.stream_file_duration = None


def make_media_controller(current_time: float):
    """Build a media controller double exposing adjusted_current_time."""
    return types.SimpleNamespace(
        status=types.SimpleNamespace(adjusted_current_time=current_time),
        update_status=lambda: None,
    )


def test_status_reports_position_from_cast_timeline():
    reset_progress_state()
    stream_audio.stream_active = True
    stream_audio.chromecast = mock.Mock()
    stream_audio.chromecast.cast_info.friendly_name = "Test Speaker"
    stream_audio.media_controller = make_media_controller(42.5)
    stream_audio.stream_file_elapsed = 10.0
    stream_audio.stream_file_duration = 200.0

    with stream_audio.app.test_client() as client:
        payload = client.get("/status").get_json()

    assert payload["stream_position"] == 32.5
    assert payload["stream_duration"] == 200.0


def test_status_falls_back_to_bytes_streamed():
    reset_progress_state()
    stream_audio.stream_active = True
    stream_audio.chromecast = None  # no cast status available
    stream_audio.stream_file_position = 500
    stream_audio.stream_file_size = 1000
    stream_audio.stream_file_duration = 100.0

    with stream_audio.app.test_client() as client:
        payload = client.get("/status").get_json()

    assert payload["stream_position"] == 50.0
    assert payload["stream_duration"] == 100.0


def test_status_omits_position_when_not_streaming():
    reset_progress_state()  # stream_active False

    with stream_audio.app.test_client() as client:
        payload = client.get("/status").get_json()

    assert payload["stream_position"] is None
    assert payload["stream_duration"] is None


def test_status_clamps_position_to_duration():
    reset_progress_state()
    stream_audio.stream_active = True
    stream_audio.chromecast = mock.Mock()
    stream_audio.chromecast.cast_info.friendly_name = "Test Speaker"
    stream_audio.media_controller = make_media_controller(1000.0)
    stream_audio.stream_file_elapsed = 0.0
    stream_audio.stream_file_duration = 200.0

    with stream_audio.app.test_client() as client:
        payload = client.get("/status").get_json()

    assert payload["stream_position"] == 200.0
