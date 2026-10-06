#!/usr/bin/env python3
"""Google Cast Audio Streamer - Flask application for streaming MP3 files to Chromecast devices"""

import logging
import os
import socket
import threading
import time
from collections.abc import Generator
from functools import wraps
from typing import Any

import pychromecast
from flask import Flask, Response, render_template, send_from_directory
from flask_cors import CORS
from pychromecast import CastBrowser
from pychromecast.discovery import SimpleCastListener
from zeroconf import InterfaceChoice, Zeroconf

# Configure logging with timestamps and context
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Suppress Flask development server warning
logging.getLogger("werkzeug").setLevel(logging.INFO)

app = Flask(
    __name__,
    static_folder=os.path.join("frontend", "dist", "assets"),
    static_url_path="/assets",
    template_folder=os.path.join("frontend", "dist"),
)
CORS(app)

# Environment configuration
MUSIC_FOLDER = os.environ.get("MUSIC_FOLDER", "music/")
DEFAULT_DEVICE = os.environ.get("DEFAULT_DEVICE", "Google Nest Mini")
PORT = int(os.environ.get("PORT", "5067"))
LOOP_DELAY = float(os.environ.get("LOOP_DELAY", "0.1"))
DEFAULT_VOLUME = int(os.environ.get("DEFAULT_VOLUME", "5"))
RECONNECT_DELAY = float(os.environ.get("RECONNECT_DELAY", "2"))
RECONNECT_ATTEMPTS = int(os.environ.get("RECONNECT_ATTEMPTS", "60"))
WATCHDOG_INTERVAL = float(os.environ.get("WATCHDOG_INTERVAL", "10"))

# Global state variables (thread-safe)
is_paused = True
chromecast = None
media_controller = None
current_volume = DEFAULT_VOLUME
lock = threading.Lock()
current_file_index = 0
stream_active = False
connection_lost = False
reconnect_running = False
target_device_name = DEFAULT_DEVICE

# Progress tracking for the /stream session (written by the stream generator,
# read by /status). stream_file_elapsed is the offset of the current file
# within the Chromecast's media timeline; stream_file_position is bytes sent
# of the current file (used as a fallback when no cast status is available).
stream_file_elapsed = 0.0
stream_file_position = 0
stream_file_size = 0
stream_file_duration: float | None = None

try:
    from mutagen.mp3 import MP3
except ImportError:
    MP3 = None

# Cache of parsed MP3 durations, keyed by file path
_duration_cache: dict[str, float] = {}


def get_duration(path: str) -> float:
    """Get the duration of an MP3 file in seconds

    Uses mutagen when available; otherwise estimates from file size assuming
    a typical 128 kbps bitrate. Results are cached per path.

    Args:
        path: Path to the MP3 file

    Returns:
        float: Duration in seconds
    """
    if path in _duration_cache:
        return _duration_cache[path]

    duration: float | None = None
    if MP3 is not None:
        try:
            duration = float(MP3(path).info.length)
        except Exception as e:
            logger.warning(f"Could not parse duration of {path}: {e}")

    if duration is None:
        # Typical MP3 bitrate: 128kbps = 16KB/s
        duration = os.path.getsize(path) / 16000.0

    _duration_cache[path] = duration
    return duration


class ConnectionListener:
    """Listener for Chromecast socket connection status changes.

    Detects when the speaker briefly drops off the network and triggers an
    automatic reconnect while playback is intended to be active.
    """

    def new_connection_status(self, status) -> None:
        """Handle connection status updates from the Chromecast socket.

        Args:
            status: ConnectionStatus object with a .status attribute
                (CONNECTED, DISCONNECTED, or FAILED)

        Returns:
            None
        """
        if status.status in ("DISCONNECTED", "FAILED"):
            logger.info("Connection to speaker lost, scheduling reconnect")
            start_reconnect()


def get_lan_ip() -> str:
    """Get the LAN IP address of the machine

    Returns:
        str: Local IP address or 'localhost' on failure
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
        return lan_ip
    except Exception:
        logger.warning("Could not determine LAN IP, using localhost")
        return "localhost"


def get_mp3_files() -> list[str]:
    """Get all MP3 files from the music folder

    Returns:
        List[str]: Sorted list of MP3 file paths
    """
    if not os.path.exists(MUSIC_FOLDER):
        logger.warning(f"Music folder not found: {MUSIC_FOLDER}")
        return []

    mp3_files_list = []
    for filename in os.listdir(MUSIC_FOLDER):
        if filename.lower().endswith(".mp3"):
            mp3_files_list.append(os.path.join(MUSIC_FOLDER, filename))

    return sorted(mp3_files_list)


def create_zeroconf() -> Zeroconf:
    """Create a Zeroconf instance with interface binding to avoid buffer issues

    Returns:
        Zeroconf: Configured Zeroconf instance
    """
    try:
        return Zeroconf(interfaces=InterfaceChoice.All)
    except OSError:
        logger.debug("InterfaceChoice.All failed, trying InterfaceChoice.Default")
        try:
            return Zeroconf(interfaces=InterfaceChoice.Default)
        except OSError:
            logger.debug("InterfaceChoice.Default failed, trying specific IP")
            lan_ip = get_lan_ip()
            if lan_ip != "localhost":
                return Zeroconf(interfaces=[lan_ip])
            raise


def run_discovery(handle_device, stop_when=None):
    """Run Chromecast discovery with timeout and cleanup.

    Args:
        handle_device: Callback invoked as (browser, uuid, service) for each device
        stop_when: Optional callable returning True to stop discovery early

    Returns:
        CastBrowser: Browser after discovery, or None on OSError
    """
    zconf = None
    browser = None
    try:
        zconf = create_zeroconf()
        listener = SimpleCastListener(
            add_callback=lambda uuid, service: handle_device(browser, uuid, service)
        )
        browser = CastBrowser(listener, zconf, known_hosts=None)
        browser.start_discovery()

        timeout = 5
        start_time = time.time()
        while time.time() - start_time < timeout:
            if stop_when and stop_when():
                break
            time.sleep(0.1)
        return browser
    except OSError as e:
        logger.error(f"Error during Chromecast discovery: {e}")
        return None
    finally:
        if browser:
            try:
                browser.stop_discovery()
            except Exception:
                pass
        if zconf:
            zconf.close()


def find_chromecast(device_name: str | None = None) -> bool:
    """Find and connect to Chromecast device

    Args:
        device_name: Optional specific device name to connect to

    Returns:
        bool: True if successful, False otherwise
    """
    global chromecast, media_controller, target_device_name

    logger.info(
        f"Searching for Chromecast device... (name: {device_name or DEFAULT_DEVICE})"
    )

    found_device = None
    target_name = device_name or DEFAULT_DEVICE
    target_device_name = target_name

    def add_cast_callback(browser, uuid, service):
        """Callback for device discovery."""
        nonlocal found_device
        device = browser.devices.get(uuid)
        if device:
            friendly_name = device.friendly_name
            logger.debug(f"Discovered device: {friendly_name}")
            if target_name in friendly_name and found_device is None:
                found_device = device

    try:
        browser = run_discovery(
            add_cast_callback, stop_when=lambda: found_device is not None
        )
        if browser is None:
            return False

        if not found_device:
            logger.warning(
                f"No Chromecast device found for: {device_name or DEFAULT_DEVICE}"
            )
            return False

        cast_info = found_device

        # Create Chromecast object from CastInfo
        logger.info("Connecting to Chromecast...")
        chromecast = pychromecast.get_chromecast_from_host(
            (
                cast_info.host,
                cast_info.port,
                cast_info.uuid,
                cast_info.model_name,
                cast_info.friendly_name,
            )
        )
        chromecast.wait()

        # Use the built-in media controller
        media_controller = chromecast.media_controller

        # Watch for socket drops to trigger automatic reconnect
        chromecast.register_connection_listener(ConnectionListener())

        # Set volume with retry
        if set_volume(current_volume):
            logger.info(f"Chromecast connected successfully, volume: {current_volume}%")
            return True
        else:
            logger.error("Failed to set volume after connection")
            return False

    except OSError as e:
        logger.error(f"Error during Chromecast discovery: {e}")
        return False
    except Exception:
        logger.exception("Unexpected error finding Chromecast")
        return False


def disconnect_chromecast() -> bool:
    """Disconnect from the current Chromecast device

    Returns:
        bool: True if successful, False otherwise
    """
    global \
        chromecast, \
        media_controller, \
        is_paused, \
        stream_active, \
        current_file_index, \
        connection_lost

    if chromecast is None:
        logger.warning("Cannot disconnect: No Chromecast connected")
        return False

    # Stop playback before disconnecting
    if media_controller:
        try:
            logger.info("Stopping media controller before disconnect")
            media_controller.stop()
        except Exception as e:
            logger.error(f"Error stopping media controller: {e}")

    try:
        logger.info("Disconnecting from Chromecast...")
        chromecast.disconnect(timeout=2.0)
        logger.info("Successfully disconnected from Chromecast")
    except Exception as e:
        logger.error(f"Error disconnecting from Chromecast: {e}")

    # Reset global state
    chromecast = None
    media_controller = None
    is_paused = True
    stream_active = False
    current_file_index = 0
    connection_lost = False

    return True


def require_chromecast_connected(func):
    """Decorator to check if Chromecast is connected before executing route handler

    Args:
        func: The route handler function

    Returns:
        Wrapped function with chromecast connection check
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        if chromecast is None:
            logger.warning("Cannot execute: No Chromecast connected")
            return {"status": "failed", "message": "No Chromecast device connected"}
        return func(*args, **kwargs)

    return wrapper


def require_mp3_files(func):
    """Decorator to check if MP3 files exist before executing route handler

    Args:
        func: The route handler function

    Returns:
        Wrapped function with MP3 files check
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        mp3_files_list = get_mp3_files()
        if not mp3_files_list:
            logger.error("No MP3 files found in music/")
            return {"status": "failed", "message": "No MP3 files found in music/"}
        return func(*args, **kwargs)

    return wrapper


def set_volume(volume_percent: int, retries: int = 5, delay: float = 1) -> bool:
    """Set volume of connected Chromecast with retry mechanism

    Args:
        volume_percent: Volume level between 1-100
        retries: Number of retry attempts
        delay: Delay between retries in seconds

    Returns:
        bool: True if successful, False otherwise
    """
    global current_volume, chromecast

    if chromecast is None:
        logger.warning("Cannot set volume: No Chromecast connected")
        return False

    # Convert 1-100 to 0.0-1.0
    volume = max(0.0, min(1.0, volume_percent / 100.0))

    logger.info(f"Setting volume to {volume_percent}%")
    for attempt in range(retries):
        try:
            if chromecast and chromecast.status:
                chromecast.set_volume(volume)
                current_volume = volume_percent
                logger.info(f"Volume successfully set to {volume_percent}%")
                return True
            else:
                logger.debug(f"Attempt {attempt + 1}/{retries}: Chromecast not ready")
                time.sleep(delay)
        except Exception as e:
            logger.debug(f"Attempt {attempt + 1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                logger.error("Failed to set volume after all retries")
                return False

    return False


def stop_media_controller() -> None:
    """Stop the media controller if a Chromecast is connected

    Returns:
        None
    """
    if media_controller and chromecast:
        try:
            logger.info("Stopping media controller")
            media_controller.stop()
        except Exception as e:
            logger.error(f"Error stopping media controller: {e}")


def play_stream_on_chromecast() -> bool:
    """Start playing the audio stream on the connected Chromecast

    Returns:
        bool: True if playback started successfully, False otherwise
    """
    if not media_controller or not chromecast:
        return False

    try:
        local_ip = get_lan_ip()
        stream_url = f"http://{local_ip}:{PORT}/stream"
        logger.info(f"Playing stream from: {stream_url}")

        media_controller.play_media(
            stream_url,
            "audio/mpeg",
            stream_type="BUFFERED",
            autoplay=True,
            title="Stream",
        )
        return True
    except Exception as e:
        logger.error(f"Error starting playback: {e}")
        return False


def start_reconnect() -> None:
    """Schedule a background reconnect if playback is meant to be active.

    Spawns a single daemon thread that reconnects to the speaker and resumes
    playback from the current file. Prevents duplicate threads from running.

    Returns:
        None
    """
    global connection_lost, reconnect_running

    with lock:
        if not stream_active or is_paused:
            return
        if reconnect_running:
            return
        connection_lost = True
        reconnect_running = True

    thread = threading.Thread(target=reconnect_loop, daemon=True)
    thread.start()
    logger.info("Reconnect thread started")


def reconnect_loop() -> None:
    """Reconnect to the speaker and resume playback from the current file.

    Retries find + play until the speaker is back and playing, the playback
    is explicitly stopped/paused, or the attempt budget is exhausted.

    Returns:
        None
    """
    global connection_lost, reconnect_running, stream_active, is_paused

    try:
        for attempt in range(RECONNECT_ATTEMPTS):
            with lock:
                if not stream_active or is_paused:
                    logger.info("Playback no longer active, cancelling reconnect")
                    connection_lost = False
                    return
                if not connection_lost:
                    return

            logger.debug(f"Reconnect attempt {attempt + 1}/{RECONNECT_ATTEMPTS}")
            time.sleep(RECONNECT_DELAY)

            with lock:
                if not stream_active or is_paused:
                    connection_lost = False
                    return

            if not find_chromecast(target_device_name):
                logger.debug("Speaker not found yet, retrying")
                continue

            # Re-check before issuing playback in case the user paused/stopped
            # while find_chromecast was blocking.
            with lock:
                if not stream_active or is_paused or not connection_lost:
                    logger.info("Playback no longer active, cancelling reconnect")
                    connection_lost = False
                    return

            stop_media_controller()
            if not play_stream_on_chromecast():
                logger.debug("Playback start failed, retrying")
                continue

            # Wait briefly for playback to start
            timeout = 15
            start_time = time.time()
            while time.time() - start_time < timeout:
                with lock:
                    if not stream_active or is_paused:
                        connection_lost = False
                        return
                try:
                    status = media_controller.status
                    if status.player_state == "PLAYING":
                        logger.info("Playback resumed after reconnect")
                        connection_lost = False
                        return
                except Exception:
                    break
                time.sleep(1)

        logger.error(f"Giving up reconnect after {RECONNECT_ATTEMPTS} attempts")
        connection_lost = False
        stream_active = False
        is_paused = True
    finally:
        with lock:
            reconnect_running = False
        logger.info("Reconnect thread finished")


def watchdog_poll(stalled: int) -> int:
    """One watchdog poll. Returns the updated consecutive-stall count.

    The reconnect listener only covers cast-socket drops. This watchdog covers
    media-session failures (receiver app error, dead HTTP stream) where the
    socket stays connected but audio stops.

    Args:
        stalled: Current consecutive-stall count

    Returns:
        int: Updated stall count (0 after a restart or healthy poll)
    """
    with lock:
        active = (
            stream_active
            and not is_paused
            and not connection_lost
            and not reconnect_running
        )
    if not active or chromecast is None or media_controller is None:
        return 0

    try:
        state = media_controller.status.player_state
        app_id = chromecast.status.app_id
    except Exception:
        return 0

    if state in ("PLAYING", "BUFFERING", "LOADING", "PAUSED") and app_id:
        return 0

    stalled += 1
    if stalled < 2:
        logger.debug(f"Playback state suspicious: {state}, app_id={app_id}")
        return stalled

    logger.warning(f"Playback stalled (player_state={state}), restarting stream")
    play_stream_on_chromecast()
    return 0


def playback_watchdog() -> None:
    """Periodically poll player state and restart the stream if it stalls.

    Returns:
        None
    """
    stalled = 0
    while True:
        time.sleep(WATCHDOG_INTERVAL)
        stalled = watchdog_poll(stalled)


def stream_audio(file_index: int) -> Generator[bytes, None, None]:
    """Stream MP3 files to Chromecast in a continuous loop

    Args:
        file_index: Starting index of the file to stream

    Yields:
        bytes: Audio data chunks
    """
    global current_file_index, stream_active
    global \
        stream_file_elapsed, \
        stream_file_position, \
        stream_file_size, \
        stream_file_duration
    global_mp3_files = get_mp3_files()

    if not global_mp3_files:
        logger.warning("No MP3 files available for streaming")
        return

    if file_index < 0 or file_index >= len(global_mp3_files):
        logger.warning(f"Invalid file_index: {file_index}")
        return

    # Typical MP3 bitrate: 128kbps = 16KB/s, use 4KB chunks every 0.1s
    chunk_size = 4096
    chunk_interval = 0.1  # seconds between chunks for smoother playback

    # Start from the given index and loop continuously
    idx = file_index
    # Offset of the current file in the Chromecast's media timeline. The cast
    # sees /stream as one continuous media item, so currentTime keeps counting
    # across file boundaries; this tracks where each file begins.
    session_elapsed = 0.0

    while stream_active:
        current_file = global_mp3_files[idx]
        logger.info(f"Streaming file: {current_file}")
        current_file_index = idx
        stream_file_elapsed = session_elapsed
        stream_file_position = 0
        stream_file_size = os.path.getsize(current_file)
        stream_file_duration = get_duration(current_file)

        # Stream the file
        try:
            with open(current_file, "rb") as f:
                while True:
                    data = f.read(chunk_size)
                    if not data:
                        break
                    yield data
                    stream_file_position = f.tell()
                    # Small delay to prevent blocking
                    time.sleep(chunk_interval)
        except Exception as e:
            # Skip to the next file instead of ending the stream
            logger.warning(f"Error streaming file: {current_file}: {e}")
            time.sleep(1)

        session_elapsed += stream_file_duration or 0.0

        # Move to next file, wrap around to 0 after last file
        idx = (idx + 1) % len(global_mp3_files)


@app.route("/stream")
def stream_audio_endpoint() -> Response:
    """Serve the audio stream for the current file

    Returns:
        Response: Flask response with audio data
    """
    return Response(
        stream_audio(current_file_index),
        mimetype="audio/mpeg",
        headers={
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Expires": "0",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "audio/mpeg",
            "Connection": "keep-alive",
        },
    )


@app.route("/")
def index() -> str:
    """Serve the web UI

    Returns:
        str: Rendered HTML template
    """
    if not os.path.exists(os.path.join("frontend", "dist", "index.html")):
        return (
            "<h1>Siren UI not built</h1>"
            "<p>Run <code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code> "
            "or <code>docker compose build</code> to build the web interface.</p>"
        )
    return render_template("index.html")


@app.route("/favicon.ico")
def favicon() -> str:
    """Serve the favicon

    Returns:
        str: Favicon file
    """
    return send_from_directory("", "favicon.png")


@app.route("/play")
@app.route("/play/<device_name>")
@require_mp3_files
def play(device_name: str | None = None) -> dict[str, Any]:
    """Start the audio stream

    Args:
        device_name: Optional specific device name to use

    Returns:
        Dict: Status and message
    """
    global \
        is_paused, \
        chromecast, \
        media_controller, \
        current_file_index, \
        stream_active, \
        connection_lost

    # Connect if not already connected
    if chromecast is None and not find_chromecast(device_name):
        logger.error(
            f"Failed to connect to Chromecast: {device_name or DEFAULT_DEVICE}"
        )
        return {"status": "failed", "message": "Could not find Chromecast device"}

    with lock:
        # Prevent duplicate play requests
        if not is_paused and stream_active:
            logger.info("Playback already in progress, ignoring duplicate play request")
            return {"status": "playing", "message": "Already playing"}

        is_paused = False
        current_file_index = 0
        stream_active = True
        connection_lost = False

    # Stop current playback
    stop_media_controller()

    mp3_files_list = get_mp3_files()

    # Start playback on Chromecast (which will fetch /stream endpoint)
    if not play_stream_on_chromecast():
        return {"status": "playing", "files": len(mp3_files_list)}

    # Wait for player state to change
    timeout = 30
    start_time = time.time()
    while time.time() - start_time < timeout:
        status = media_controller.status
        if status.player_state == "PLAYING":
            logger.info("Playback started successfully")
            return {"status": "playing", "files": len(mp3_files_list)}
        time.sleep(1)

    logger.error(f"Timeout waiting for playback to start (waited {timeout}s)")
    return {"status": "failed", "message": "Timeout waiting for playback to start"}


@app.route("/play-file/<int:index>")
@require_chromecast_connected
@require_mp3_files
def play_file(index: int) -> dict[str, Any]:
    """Jump playback to the file at the given playlist index

    Args:
        index: Zero-based index into the sorted MP3 file list

    Returns:
        Dict: Status and file index
    """
    global is_paused, current_file_index, stream_active, connection_lost

    mp3_files_list = get_mp3_files()
    if index < 0 or index >= len(mp3_files_list):
        logger.warning(f"Invalid file index requested: {index}")
        return {"status": "failed", "message": "Invalid file index"}

    with lock:
        is_paused = False
        current_file_index = index
        stream_active = True
        connection_lost = False

    # Restart playback so the Chromecast re-fetches /stream from the new index
    stop_media_controller()
    time.sleep(0.5)
    if not play_stream_on_chromecast():
        return {"status": "failed", "message": "Could not start playback"}

    return {"status": "success", "file_index": index}


@app.route("/pause")
def pause() -> dict[str, str]:
    """Pause the audio stream

    Returns:
        Dict: Status
    """
    global is_paused, connection_lost

    logger.info("Pause requested")

    with lock:
        is_paused = True
        connection_lost = False
    # Pause the media player on Chromecast (preserves position)
    if media_controller and chromecast:
        try:
            logger.info("Pausing media controller")
            media_controller.pause()
        except Exception as e:
            logger.error(f"Error pausing media controller: {e}")

    return {"status": "paused"}


@app.route("/resume")
def resume() -> dict[str, str]:
    """Resume the audio stream

    Returns:
        Dict: Status
    """
    global is_paused, stream_active, connection_lost

    logger.info("Resume requested")

    with lock:
        is_paused = False
        stream_active = True

    # If the connection was lost, the reconnect thread will restore playback
    if connection_lost:
        logger.info("Connection was lost, deferring resume to reconnect thread")
        return {"status": "resumed"}

    # Check if resuming from paused state or stopped state
    if media_controller and chromecast:
        try:
            # If media is paused (not stopped), resume from paused position
            if (
                media_controller.status
                and media_controller.status.player_state == "PAUSED"
            ):
                logger.info("Resuming media controller from paused state")
                media_controller.play()
            else:
                # Media is stopped, need to restart playback from beginning
                logger.info("Media is stopped, restarting playback from beginning")
                play_stream_on_chromecast()
        except Exception as e:
            logger.error(f"Error resuming stream: {e}")

    return {"status": "resumed"}


@app.route("/stop")
def stop() -> dict[str, str]:
    """Stop the audio stream

    Returns:
        Dict: Status
    """
    global is_paused, stream_active, current_file_index, connection_lost

    logger.info("Stop requested")

    with lock:
        is_paused = True
        stream_active = False
        current_file_index = 0
        connection_lost = False

    # Stop the media player on Chromecast
    stop_media_controller()

    return {"status": "stopped"}


@app.route("/status")
def status() -> dict[str, Any]:
    """Get current status

    Returns:
        Dict: Current status information
    """
    global current_file_index
    mp3_files_list = get_mp3_files()

    position = None
    if chromecast and media_controller and stream_active:
        try:
            # Ask the cast for a fresh status; the response arrives
            # asynchronously and is picked up by the next poll.
            media_controller.update_status()
            current_time = media_controller.status.adjusted_current_time
            if current_time is not None:
                position = current_time - stream_file_elapsed
        except Exception:
            pass

    if position is None and stream_file_size > 0 and stream_file_duration:
        # Fallback: fraction of bytes streamed into the current file.
        position = (stream_file_position / stream_file_size) * stream_file_duration

    if position is not None and stream_file_duration:
        position = max(0.0, min(position, stream_file_duration))

    return {
        "is_paused": is_paused,
        "stream_active": stream_active,
        "connection_lost": connection_lost,
        "files_count": len(mp3_files_list),
        "chromecast_connected": chromecast is not None,
        "selected_device": chromecast.cast_info.friendly_name if chromecast else None,
        "current_file_index": current_file_index,
        "current_file": mp3_files_list[current_file_index] if mp3_files_list else None,
        "current_volume": current_volume,
        "stream_position": position,
        "stream_duration": stream_file_duration if stream_active else None,
    }


@app.route("/files")
def files() -> dict[str, Any]:
    """Get list of MP3 files

    Returns:
        Dict: List of files and current index
    """
    global current_file_index
    mp3_files_list = get_mp3_files()
    files = [f.replace(MUSIC_FOLDER, "") for f in mp3_files_list]
    return {"files": files, "current_file_index": current_file_index}


@app.route("/previous")
@require_mp3_files
def previous() -> dict[str, Any]:
    """Play previous file in the playlist

    Returns:
        Dict: Status and file index
    """
    return change_track(-1)


@app.route("/next")
@require_mp3_files
def next() -> dict[str, Any]:
    """Play next file in the playlist

    Returns:
        Dict: Status and file index
    """
    return change_track(1)


@app.route("/connect")
@app.route("/connect/<device_name>")
def connect(device_name: str | None = None) -> dict[str, Any]:
    """Connect to Chromecast device

    Args:
        device_name: Optional specific device name

    Returns:
        Dict: Connection status and device info
    """
    logger.info(f"Connecting to Chromecast: {device_name or DEFAULT_DEVICE}")
    with lock:
        if find_chromecast(device_name):
            return {
                "status": "connected",
                "device": chromecast.cast_info.friendly_name,
                "volume": current_volume,
            }
        return {"status": "failed", "message": "Could not find Chromecast device"}


@app.route("/disconnect")
def disconnect() -> dict[str, str]:
    """Disconnect from current Chromecast device

    Returns:
        Dict: Disconnection status
    """
    logger.info("Disconnect request received")
    with lock:
        if disconnect_chromecast():
            return {"status": "disconnected"}
        return {"status": "failed", "message": "No Chromecast device connected"}


@app.route("/devices")
def devices() -> dict[str, Any]:
    """List available Chromecast devices

    Returns:
        Dict: List of devices or error
    """
    # Use dict to deduplicate by UUID
    devices_dict: dict[str, dict[str, str]] = {}

    def add_device_callback(browser, uuid, service):
        """Callback for device discovery."""
        device = browser.devices.get(uuid)
        if device and uuid not in devices_dict:
            devices_dict[uuid] = {
                "name": device.friendly_name,
                "model": device.model_name,
                "host": device.host,
                "port": str(device.port),
            }
            logger.debug(f"Discovered device: {device.friendly_name}")

    if run_discovery(add_device_callback) is None:
        return {
            "devices": [],
            "error": "Device discovery failed - network buffer issue",
        }

    devices_list = list(devices_dict.values())
    logger.info(f"Found {len(devices_list)} Chromecast devices")
    return {"devices": devices_list}


@app.route("/volume/<int:value>")
@require_chromecast_connected
def volume(value: int) -> dict[str, Any]:
    """Set volume of connected Chromecast

    Args:
        value: Volume level between 1-100

    Returns:
        Dict: Volume status or error
    """
    global current_volume

    logger.info(f"Setting volume to {value}%")

    if value < 1 or value > 100:
        logger.warning(f"Invalid volume value: {value}")
        return {"status": "failed", "message": "Volume must be between 1 and 100"}

    with lock:
        if set_volume(value):
            return {
                "status": "success",
                "volume": value,
                "device": chromecast.cast_info.friendly_name,
            }
        return {"status": "failed", "message": "Error setting volume"}


def change_track(direction: int) -> dict[str, Any]:
    """Play previous or next file in the playlist

    Args:
        direction: -1 for previous, 1 for next

    Returns:
        Dict: Status and file index
    """
    global current_file_index, is_paused
    mp3_files_list = get_mp3_files()
    if not mp3_files_list:
        logger.error("No MP3 files available")
        return {"status": "failed", "message": "No MP3 files found"}

    current_file_index = (current_file_index + direction + len(mp3_files_list)) % len(
        mp3_files_list
    )
    logger.info(
        f"Playing {'previous' if direction < 0 else 'next'} file: {current_file_index}"
    )

    with lock:
        is_paused = False

    if media_controller and chromecast:
        try:
            stop_media_controller()
            time.sleep(0.5)  # Wait for stop to complete
            play_stream_on_chromecast()
        except Exception as e:
            logger.error(f"Error changing track: {e}")
    return {"status": "success", "file_index": current_file_index}


@app.route("/config")
def config() -> dict[str, Any]:
    """Get application configuration

    Returns:
        Dict: Current configuration
    """
    return {
        "default_volume": DEFAULT_VOLUME,
        "current_volume": current_volume,
    }


if __name__ == "__main__":
    threading.Thread(
        target=playback_watchdog, daemon=True, name="playback-watchdog"
    ).start()
    print("Starting Google Cast Audio Streamer...")
    print(f"Place your MP3 files in '{MUSIC_FOLDER}' folder")
    lan_ip = get_lan_ip()
    print(f"Access the web interface at: http://{lan_ip}:{PORT}")
    print("\nAvailable endpoints:")
    print("  / - Web interface")
    print("  /play - Start playback")
    print("  /play/:device_name - Start playback on specific device")
    print("  /play-file/:index - Jump playback to file at index")
    print("  /pause - Pause playback")
    print("  /resume - Resume playback")
    print("  /stop - Stop playback")
    print("  /disconnect - Disconnect from Chromecast device")
    print("  /status - Get current status")
    print("  /previous - Play previous file")
    print("  /next - Play next file")
    print("  /connect - Connect to Chromecast device")
    print("  /connect/:device_name - Connect to specific device")
    print("  /devices - List available Chromecast devices")
    print("  /volume/:value - Set volume (1-100)")

    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
