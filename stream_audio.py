#!/usr/bin/env python3
"""Google Cast Audio Streamer - Flask application for streaming MP3 files to Chromecast devices"""

import os
import time
import threading
import logging
import socket
from typing import Optional, List, Dict, Generator, Any
from flask import Flask, Response, render_template, send_from_directory
from flask_cors import CORS
import pychromecast
from pychromecast import CastBrowser, get_chromecast_from_host
from pychromecast.discovery import AbstractCastListener
from zeroconf import Zeroconf, InterfaceChoice

# Configure logging with timestamps and context
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Suppress Flask development server warning
logging.getLogger("werkzeug").setLevel(logging.INFO)

app = Flask(__name__)
CORS(app)

# Environment configuration
MUSIC_FOLDER = os.environ.get("MUSIC_FOLDER", "music/")
DEFAULT_DEVICE = os.environ.get("DEFAULT_DEVICE", "Bedroom speaker")
PORT = int(os.environ.get("PORT", "5067"))
LOOP_DELAY = float(os.environ.get("LOOP_DELAY", "0.1"))
DEFAULT_VOLUME = int(os.environ.get("DEFAULT_VOLUME", "5"))

# Global state variables (thread-safe)
is_paused = True
pause_event = threading.Event()
restart_event = threading.Event()
chromecast = None
media_controller = None
current_volume = DEFAULT_VOLUME
lock = threading.Lock()
current_file_index = 0
streaming_started = False


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


def get_mp3_files() -> List[str]:
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


def find_chromecast(device_name: Optional[str] = None) -> bool:
    """Find and connect to Chromecast device

    Args:
        device_name: Optional specific device name to connect to

    Returns:
        bool: True if successful, False otherwise
    """
    global chromecast, media_controller

    class CastDeviceListener(AbstractCastListener):
        """Listener for Chromecast discovery events."""

        def __init__(self):
            self.found_device = None

        def add_cast(self, uuid, service):
            """Called when a new Chromecast device is discovered."""
            device = browser.services[uuid]
            friendly_name = device.friendly_name
            logger.debug(f"Discovered device: {friendly_name}")

            if device_name:
                if device_name in friendly_name:
                    self.found_device = device
            elif DEFAULT_DEVICE in friendly_name:
                self.found_device = device

        def remove_cast(self, uuid, service, cast_info):
            """Called when a Chromecast device is removed."""
            pass

        def update_cast(self, uuid, service):
            """Called when a Chromecast device is updated."""
            pass

    zconf = None
    try:
        logger.info(
            f"Searching for Chromecast device... (name: {device_name or DEFAULT_DEVICE})"
        )
        zconf = create_zeroconf()

        listener = CastDeviceListener()
        browser = CastBrowser(listener, zconf, known_hosts=None)
        browser.start_discovery()

        timeout = 5
        start_time = time.time()
        while time.time() - start_time < timeout:
            if listener.found_device:
                break
            time.sleep(0.1)

        browser.stop_discovery()

        if not listener.found_device:
            logger.warning(
                f"No Chromecast device found for: {device_name or DEFAULT_DEVICE}"
            )
            return False

        cast_info = listener.found_device

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
    except Exception as e:
        logger.error(f"Unexpected error finding Chromecast: {e}", exc_info=True)
        return False
    finally:
        if zconf:
            zconf.close()


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


def stream_audio() -> Generator[bytes, None, None]:
    """Stream MP3 files from music folder to Chromecast

    Yields:
        bytes: Audio data chunks
    """
    global is_paused, chromecast, media_controller, current_file_index

    global_mp3_files = get_mp3_files()

    if not global_mp3_files:
        logger.warning("No MP3 files available for streaming")
        return

    if chromecast is None:
        if not find_chromecast():
            logger.error("Could not connect to Chromecast for streaming")
            return

    logger.info("Starting audio stream")
    while True:
        if pause_event.is_set():
            logger.info("Playback paused")
            while pause_event.is_set():
                time.sleep(0.1)

        current_file = global_mp3_files[current_file_index]

        try:
            logger.info(f"Playing file: {current_file}")
            with open(current_file, "rb") as f:
                while True:
                    if pause_event.is_set():
                        logger.info("Stopping current file due to pause")
                        break
                    if restart_event.is_set():
                        restart_event.clear()
                        logger.info("Restarting playback")
                        break

                    data = f.read(4096)
                    if not data:
                        break

                    yield data
        except Exception:
            logger.warning(f"Error streaming file: {current_file}")
            pass

        # Check if we need to restart
        if restart_event.is_set():
            restart_event.clear()
            continue

        # Move to next file
        current_file_index = (current_file_index + 1) % len(global_mp3_files)

        if not is_paused:
            time.sleep(LOOP_DELAY)


@app.route("/stream")
def stream_audio_endpoint() -> Response:
    """Serve the audio stream

    Returns:
        Response: Flask response with audio data
    """
    return Response(
        stream_audio(),
        mimetype="audio/mpeg",
        headers={
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Expires": "0",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "audio/mpeg",
        },
    )


@app.route("/")
def index() -> str:
    """Serve the web UI

    Returns:
        str: Rendered HTML template
    """
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
def play(device_name: Optional[str] = None) -> Dict[str, Any]:
    """Start the audio stream

    Args:
        device_name: Optional specific device name to use

    Returns:
        Dict: Status and message
    """
    global is_paused, chromecast, media_controller, current_file_index

    # Check for music files first
    mp3_files_list = get_mp3_files()
    if not mp3_files_list:
        logger.error("No MP3 files found in music/")
        return {"status": "failed", "message": "No MP3 files found in music/"}

    # Connect if not already connected
    if chromecast is None:
        if not find_chromecast(device_name):
            logger.error(
                f"Failed to connect to Chromecast: {device_name or DEFAULT_DEVICE}"
            )
            return {"status": "failed", "message": "Could not find Chromecast device"}

    with lock:
        is_paused = False
        pause_event.clear()
        streaming_started = True
        current_file_index = 0
        restart_event.clear()

    # Stop current playback
    if media_controller and chromecast:
        try:
            logger.info("Stopping current playback")
            media_controller.stop()
        except Exception:
            pass

    # Start audio streaming in background thread
    streaming_thread = threading.Thread(target=stream_audio, daemon=True)
    streaming_thread.start()

    # Start playback on Chromecast
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


@app.route("/pause")
def pause() -> Dict[str, str]:
    """Pause the audio stream

    Returns:
        Dict: Status
    """
    global is_paused

    logger.info("Pause requested")

    with lock:
        is_paused = True
        pause_event.set()

    # Also pause the media player on Chromecast
    if media_controller and chromecast:
        try:
            logger.info("Pausing media controller")
            media_controller.pause()
        except Exception as e:
            logger.error(f"Error pausing media controller: {e}")

    return {"status": "paused"}


@app.route("/resume")
def resume() -> Dict[str, str]:
    """Resume the audio stream

    Returns:
        Dict: Status
    """
    global is_paused, streaming_started

    logger.info("Resume requested")

    with lock:
        is_paused = False
        pause_event.clear()

    # If streaming hasn't started yet, treat as /play
    if not streaming_started:
        streaming_started = True
        streaming_thread = threading.Thread(target=stream_audio, daemon=True)
        streaming_thread.start()
        logger.info("Starting audio stream for resume")

    # Resume the media player on Chromecast
    if media_controller and chromecast:
        try:
            status = media_controller.status
            if status and status.player_state != "PLAYING":
                # Check if there's an active session
                if status.player_state in ("IDLE", "UNKNOWN"):
                    # No active session, need to start playback
                    logger.info("No active session found, starting playback")
                    play_stream_on_chromecast()
                else:
                    logger.info("Resuming media controller")
                    media_controller.play()
            else:
                logger.info("Media already playing")
        except Exception as e:
            logger.error(f"Error resuming media controller: {e}")

    return {"status": "resumed"}


@app.route("/status")
def status() -> Dict[str, Any]:
    """Get current status

    Returns:
        Dict: Current status information
    """
    global current_file_index
    mp3_files_list = get_mp3_files()
    return {
        "is_paused": is_paused,
        "files_count": len(mp3_files_list),
        "chromecast_connected": chromecast is not None,
        "selected_device": chromecast.name if chromecast else None,
        "current_file_index": current_file_index,
        "current_file": mp3_files_list[current_file_index] if mp3_files_list else None,
    }


@app.route("/files")
def files() -> Dict[str, Any]:
    """Get list of MP3 files

    Returns:
        Dict: List of files and current index
    """
    global current_file_index
    mp3_files_list = get_mp3_files()
    files = [f.replace(MUSIC_FOLDER, "") for f in mp3_files_list]
    return {"files": files, "current_file_index": current_file_index}


@app.route("/previous")
def previous() -> Dict[str, Any]:
    """Play previous file in the playlist

    Returns:
        Dict: Status and file index
    """
    global current_file_index, is_paused
    mp3_files_list = get_mp3_files()
    if not mp3_files_list:
        logger.error("No MP3 files available")
        return {"status": "failed", "message": "No MP3 files found"}

    current_file_index = (current_file_index - 1 + len(mp3_files_list)) % len(
        mp3_files_list
    )
    logger.info(f"Playing previous file: {current_file_index}")

    with lock:
        is_paused = False
        pause_event.clear()
        restart_event.set()

    if media_controller and chromecast:
        try:
            logger.info("Stopping media controller for previous track")
            media_controller.stop()
            play_stream_on_chromecast()
        except Exception as e:
            logger.error(f"Error playing previous: {e}")
    return {"status": "success", "file_index": current_file_index}


@app.route("/next")
def next() -> Dict[str, Any]:
    """Play next file in the playlist

    Returns:
        Dict: Status and file index
    """
    global current_file_index, is_paused
    mp3_files_list = get_mp3_files()
    if not mp3_files_list:
        logger.error("No MP3 files available")
        return {"status": "failed", "message": "No MP3 files found"}

    current_file_index = (current_file_index + 1) % len(mp3_files_list)
    logger.info(f"Playing next file: {current_file_index}")

    with lock:
        is_paused = False
        pause_event.clear()
        restart_event.set()

    if media_controller and chromecast:
        try:
            logger.info("Stopping media controller for next track")
            media_controller.stop()
            play_stream_on_chromecast()
        except Exception as e:
            logger.error(f"Error playing next: {e}")
    return {"status": "success", "file_index": current_file_index}


@app.route("/connect")
@app.route("/connect/<device_name>")
def connect(device_name: Optional[str] = None) -> Dict[str, Any]:
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


@app.route("/devices")
def devices() -> Dict[str, Any]:
    """List available Chromecast devices

    Returns:
        Dict: List of devices or error
    """
    zconf = None
    try:
        zconf = create_zeroconf()

        class DeviceListListener(AbstractCastListener):
            """Listener for collecting device information."""

            def __init__(self):
                self.devices = []

            def add_cast(self, uuid, service):
                """Called when a new Chromecast device is discovered."""
                device = browser.services[uuid]
                self.devices.append(
                    {
                        "name": device.friendly_name,
                        "model": device.model_name,
                        "host": device.host,
                        "port": device.port,
                    }
                )

            def remove_cast(self, uuid, service, cast_info):
                """Called when a Chromecast device is removed."""
                pass

            def update_cast(self, uuid, service):
                """Called when a Chromecast device is updated."""
                pass

        listener = DeviceListListener()
        browser = CastBrowser(listener, zconf, known_hosts=None)
        browser.start_discovery()

        timeout = 5
        start_time = time.time()
        while time.time() - start_time < timeout:
            time.sleep(0.1)

        browser.stop_discovery()

        logger.info(f"Found {len(listener.devices)} Chromecast devices")
        return {"devices": listener.devices}
    except OSError as e:
        logger.error(f"Error discovering Chromecast devices: {e}")
        return {
            "devices": [],
            "error": "Device discovery failed - network buffer issue",
        }
    finally:
        if zconf:
            zconf.close()


@app.route("/volume/<int:value>")
def volume(value: int) -> Dict[str, Any]:
    """Set volume of connected Chromecast

    Args:
        value: Volume level between 1-100

    Returns:
        Dict: Volume status or error
    """
    global current_volume

    logger.info(f"Setting volume to {value}%")

    if chromecast is None:
        logger.warning("Cannot set volume: No Chromecast connected")
        return {"status": "failed", "message": "No Chromecast device connected"}

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


@app.route("/config")
def config() -> Dict[str, Any]:
    """Get application configuration

    Returns:
        Dict: Current configuration
    """
    return {
        "default_volume": DEFAULT_VOLUME,
        "current_volume": current_volume,
    }


if __name__ == "__main__":
    print("Starting Google Cast Audio Streamer...")
    print(f"Place your MP3 files in '{MUSIC_FOLDER}' folder")
    lan_ip = get_lan_ip()
    print(f"Access the web interface at: http://{lan_ip}:{PORT}")
    print("\nAvailable endpoints:")
    print("  / - Web interface")
    print("  /play - Start playback")
    print("  /play/:device_name - Start playback on specific device")
    print("  /pause - Pause playback")
    print("  /resume - Resume playback")
    print("  /status - Get current status")
    print("  /previous - Play previous file")
    print("  /next - Play next file")
    print("  /connect - Connect to Chromecast device")
    print("  /connect/:device_name - Connect to specific device")
    print("  /devices - List available Chromecast devices")
    print("  /volume/:value - Set volume (1-100)")

    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
