#!/usr/bin/env python3
import os
import time
import threading
import logging
import socket
from flask import Flask, Response, request, render_template, send_from_directory
from flask_cors import CORS
from pychromecast import get_chromecasts
from pychromecast.controllers.media import MediaController
from zeroconf import Zeroconf, InterfaceChoice

# Suppress Flask development server warning
logging.getLogger("werkzeug").setLevel(logging.INFO)

app = Flask(__name__)
CORS(app)

MUSIC_FOLDER = os.environ.get("MUSIC_FOLDER", "music/")
DEFAULT_DEVICE = os.environ.get("DEFAULT_DEVICE", "Bedroom speaker")
PORT = int(os.environ.get("PORT", "5067"))
LOOP_DELAY = float(os.environ.get("LOOP_DELAY", "0.1"))
DEFAULT_VOLUME = int(os.environ.get("DEFAULT_VOLUME", "5"))

is_paused = True
pause_event = threading.Event()
restart_event = threading.Event()
chromecast = None
media_controller = None
selected_device = None
current_volume = DEFAULT_VOLUME
lock = threading.Lock()
current_file_index = 0
mp3_files = []
streaming_started = False


def get_lan_ip():
    """Get the LAN IP address of the machine"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
        return lan_ip
    except Exception:
        return "localhost"


def get_mp3_files():
    """Get all MP3 files from the music folder"""
    if not os.path.exists(MUSIC_FOLDER):
        return []

    mp3_files = []
    for filename in os.listdir(MUSIC_FOLDER):
        if filename.lower().endswith(".mp3"):
            mp3_files.append(os.path.join(MUSIC_FOLDER, filename))

    return sorted(mp3_files)


def create_zeroconf():
    """Create a Zeroconf instance with interface binding to avoid buffer issues"""
    try:
        # Try to use all interfaces first
        return Zeroconf(interfaces=InterfaceChoice.All)
    except OSError:
        # Fall back to default interface only
        try:
            return Zeroconf(interfaces=InterfaceChoice.Default)
        except OSError:
            # Last resort: bind to the main network interface IP only
            lan_ip = get_lan_ip()
            if lan_ip != "localhost":
                return Zeroconf(interfaces=[lan_ip])
            raise


def find_chromecast(device_name=None):
    """Find and connect to Chromecast device"""
    global chromecast, media_controller

    zconf = None
    try:
        zconf = create_zeroconf()
        chromecasts, browser = get_chromecasts(zeroconf_instance=zconf)

        if not chromecasts:
            return False

        # Find specific device if name provided
        if device_name:
            for cc in chromecasts:
                if device_name in cc.cast_info.friendly_name:
                    chromecast = cc
                    break
        else:
            # Try to find default device specifically
            for cc in chromecasts:
                if DEFAULT_DEVICE in cc.cast_info.friendly_name:
                    chromecast = cc
                    break

        if not chromecast:
            return False

        # Connect to the device
        chromecast.start()

        # Wait for connection to be ready
        time.sleep(2)

        # Use the built-in media controller
        media_controller = chromecast.media_controller

        # Set volume with retry
        set_volume(current_volume)

        return True
    except OSError as e:
        app.logger.error(f"Error during Chromecast discovery: {e}")
        return False
    finally:
        if zconf:
            zconf.close()


def set_volume(volume_percent, retries=5, delay=1):
    """Set volume of connected Chromecast with retry mechanism"""
    global current_volume, chromecast

    if chromecast is None:
        return False

    # Convert 1-100 to 0.0-1.0
    volume = max(0.0, min(1.0, volume_percent / 100.0))

    for attempt in range(retries):
        try:
            if chromecast and chromecast.status:
                chromecast.set_volume(volume)
                current_volume = volume_percent
                return True
            else:
                time.sleep(delay)
        except Exception:
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                return False

    return False


def stream_audio():
    """Stream MP3 files from music folder to Chromecast"""
    global is_paused, chromecast, media_controller, current_file_index

    mp3_files = get_mp3_files()

    if not mp3_files:
        return

    if chromecast is None:
        if not find_chromecast():
            return

    while True:
        if pause_event.is_set():
            while pause_event.is_set():
                time.sleep(0.1)

        current_file = mp3_files[current_file_index]

        try:
            with open(current_file, "rb") as f:
                while True:
                    if pause_event.is_set():
                        break
                    if restart_event.is_set():
                        restart_event.clear()
                        break

                    data = f.read(4096)
                    if not data:
                        break

                    yield data
        except Exception:
            pass

        # Check if we need to restart
        if restart_event.is_set():
            restart_event.clear()
            continue

        # Move to next file
        current_file_index = (current_file_index + 1) % len(mp3_files)

        if not is_paused:
            time.sleep(LOOP_DELAY)


@app.route("/stream")
def stream_audio_endpoint():
    """Serve the audio stream"""
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
def index():
    """Serve the web UI"""
    return render_template("index.html")


@app.route("/favicon.ico")
def favicon():
    """Serve the favicon"""
    return send_from_directory("", "favicon.png")


@app.route("/play")
@app.route("/play/<device_name>")
def play(device_name=None):
    """Start the audio stream"""
    global is_paused, chromecast, media_controller, current_file_index

    # Check for music files first
    mp3_files = get_mp3_files()
    if not mp3_files:
        return {"status": "failed", "message": "No MP3 files found in music/"}

    # Connect if not already connected
    if chromecast is None:
        if not find_chromecast(device_name):
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
            media_controller.stop()
        except Exception:
            pass

    # Start audio streaming in background thread
    streaming_thread = threading.Thread(target=stream_audio, daemon=True)
    streaming_thread.start()

    # Start playback on Chromecast
    if media_controller and chromecast:
        try:
            local_ip = get_lan_ip()
            stream_url = f"http://{local_ip}:{PORT}/stream"

            # Try with stream_type parameter
            media_controller.play_media(
                stream_url,
                "audio/mpeg",
                stream_type="BUFFERED",
                autoplay=True,
                title="Stream",
            )

            # Wait for player state to change
            timeout = 30
            start_time = time.time()
            while time.time() - start_time < timeout:
                status = media_controller.status
                if status.player_state == "PLAYING":
                    return {"status": "playing", "files": len(mp3_files)}
                time.sleep(1)

            return {
                "status": "failed",
                "message": "Timeout waiting for playback to start",
            }

        except Exception:
            return {"status": "failed", "message": "Error starting playback"}

    return {"status": "playing", "files": len(mp3_files)}


@app.route("/pause")
def pause():
    """Pause the audio stream"""
    global is_paused, is_playing

    with lock:
        is_paused = True
        is_playing = False
        pause_event.set()

    # Also pause the media player on Chromecast
    if media_controller and chromecast:
        try:
            media_controller.pause()
        except Exception:
            pass

    return {"status": "paused"}


@app.route("/resume")
def resume():
    """Resume the audio stream"""
    global is_paused, streaming_started

    with lock:
        is_paused = False
        pause_event.clear()

    # If streaming hasn't started yet, treat as /play
    if not streaming_started:
        streaming_started = True
        streaming_thread = threading.Thread(target=stream_audio, daemon=True)
        streaming_thread.start()

    # Resume the media player on Chromecast
    if media_controller and chromecast:
        try:
            status = media_controller.status
            if status and status.player_state != "PLAYING":
                # Check if there's an active session
                if status.player_state == "IDLE" or status.player_state == "UNKNOWN":
                    # No active session, need to start playback
                    local_ip = get_lan_ip()
                    stream_url = f"http://{local_ip}:{PORT}/stream"
                    media_controller.play_media(
                        stream_url,
                        "audio/mpeg",
                        stream_type="BUFFERED",
                        autoplay=True,
                        title="Stream",
                    )
                else:
                    media_controller.play()
        except Exception:
            pass

    return {"status": "resumed"}


@app.route("/status")
def status():
    """Get current status"""
    global current_file_index
    mp3_files = get_mp3_files()
    return {
        "is_paused": is_paused,
        "files_count": len(mp3_files),
        "chromecast_connected": chromecast is not None,
        "selected_device": chromecast.cast_info.friendly_name if chromecast else None,
        "current_file_index": current_file_index,
        "current_file": mp3_files[current_file_index] if mp3_files else None,
    }


@app.route("/files")
def files():
    """Get list of MP3 files"""
    global current_file_index
    mp3_files = get_mp3_files()
    # Strip the MUSIC_FOLDER prefix from file paths
    files = [f.replace(MUSIC_FOLDER, "") for f in mp3_files]
    return {"files": files, "current_file_index": current_file_index}


@app.route("/previous")
def previous():
    """Play previous file in the playlist"""
    global current_file_index, is_paused
    mp3_files = get_mp3_files()
    if not mp3_files:
        return {"status": "failed", "message": "No MP3 files found"}
    current_file_index = (current_file_index - 1 + len(mp3_files)) % len(mp3_files)
    with lock:
        is_paused = False
        pause_event.clear()
        restart_event.set()

    if media_controller and chromecast:
        try:
            media_controller.stop()
            local_ip = get_lan_ip()
            stream_url = f"http://{local_ip}:{PORT}/stream"
            media_controller.play_media(
                stream_url,
                "audio/mpeg",
                stream_type="BUFFERED",
                autoplay=True,
                title="Stream",
            )
        except Exception:
            pass
    return {"status": "success", "file_index": current_file_index}


@app.route("/next")
def next():
    """Play next file in the playlist"""
    global current_file_index, is_paused
    mp3_files = get_mp3_files()
    if not mp3_files:
        return {"status": "failed", "message": "No MP3 files found"}
    current_file_index = (current_file_index + 1) % len(mp3_files)
    with lock:
        is_paused = False
        pause_event.clear()
        restart_event.set()

    if media_controller and chromecast:
        try:
            media_controller.stop()
            local_ip = get_lan_ip()
            stream_url = f"http://{local_ip}:{PORT}/stream"
            media_controller.play_media(
                stream_url,
                "audio/mpeg",
                stream_type="BUFFERED",
                autoplay=True,
                title="Stream",
            )
        except Exception:
            pass
    return {"status": "success", "file_index": current_file_index}


@app.route("/connect")
@app.route("/connect/<device_name>")
def connect(device_name=None):
    """Connect to Chromecast device"""
    with lock:
        if find_chromecast(device_name):
            return {
                "status": "connected",
                "device": chromecast.cast_info.friendly_name,
                "volume": current_volume,
            }
        return {"status": "failed", "message": "Could not find Chromecast device"}


@app.route("/devices")
def devices():
    """List available Chromecast devices"""
    zconf = None
    try:
        zconf = create_zeroconf()
        chromecasts, browser = get_chromecasts(zeroconf_instance=zconf)
        devices_list = []
        for cc in chromecasts:
            devices_list.append(
                {
                    "name": cc.cast_info.friendly_name,
                    "model": cc.cast_info.model_name,
                    "host": cc.cast_info.host,
                    "port": cc.cast_info.port,
                }
            )
        return {"devices": devices_list}
    except OSError as e:
        app.logger.error(f"Error discovering Chromecast devices: {e}")
        return {
            "devices": [],
            "error": "Device discovery failed - network buffer issue",
        }
    finally:
        if zconf:
            zconf.close()


@app.route("/volume/<int:value>")
def volume(value):
    """Set volume of connected Chromecast"""
    global current_volume

    if chromecast is None:
        return {"status": "failed", "message": "No Chromecast device connected"}

    if value < 1 or value > 100:
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
def config():
    """Get application configuration"""
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
