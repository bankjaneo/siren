# Google Nest Mini Audio Streamer

A Python service that continuously streams MP3 files from a folder to your Chromecast device using direct Chromecast control.

## Setup

### Local Development

1. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Place your MP3 files in the `music/` folder

4. Start the server:
```bash
chmod +x start.sh
./start.sh
```

### Docker

1. Build the Docker image:
```bash
docker build -t siren-stream .
```

2. Run with bind mount for music folder:
```bash
docker run --network=host -v $(pwd)/music:/app/music siren-stream
```

3. Or use docker-compose:
```bash
docker-compose up --build
```

## Usage

The server will start on `http://localhost:5067`

### Web Interface

Navigate to `http://localhost:5067` in your browser for the web UI.

### API Endpoints

- **Play**: `curl http://localhost:5067/play` - Start streaming (auto-selects Google Nest Mini)
- **Play with device**: `curl http://localhost:5067/play/Bedroom%20speaker` - Start streaming to specific device
- **Pause**: `curl http://localhost:5067/pause` - Stop streaming
- **Resume**: `curl http://localhost:5067/resume` - Continue streaming
- **Status**: `curl http://localhost:5067/status` - Check current state (includes current file index and file)
- **Previous**: `curl http://localhost:5067/previous` - Play previous file in playlist
- **Next**: `curl http://localhost:5067/next` - Play next file in playlist
- **Connect**: `curl http://localhost:5067/connect` - Connect to Google Nest Mini
- **Connect with device**: `curl http://localhost:5067/connect/Bedroom%20speaker` - Connect to specific device
- **Devices**: `curl http://localhost:5067/devices` - List available Chromecast devices
- **Volume**: `curl http://localhost:5067/volume/75` - Set volume to 75%
- **Files**: `curl http://localhost:5067/files` - List available MP3 files
- **Config**: `curl http://localhost:5067/config` - Get application configuration

### Play on Chromecast

1. Start the server: `./start.sh` or `docker-compose up`
2. List available devices: `curl http://localhost:5067/devices`
3. Navigate to `http://localhost:5067` in your browser
4. Use `/play` to start the continuous loop (auto-selects Google Nest Mini)
5. Or use `/play/DeviceName` to specify which device to play on

### Volume Control

- Set volume after connecting: `curl http://localhost:5067/volume/50`
- Volume range: 1-100 (default: 5)
- Volume is set automatically when connecting to a device

The audio will start playing and loop continuously. Use `/play` or `/pause` endpoints to control playback.

## Configuration

The following variables in `stream_audio.py` can be customized:

| Variable | Default | Description |
|----------|---------|-------------|
| `MUSIC_FOLDER` | `"music/"` | Folder containing MP3 files to stream |
| `DEFAULT_DEVICE` | `"Google Nest Mini"` | Default Chromecast device name |
| `PORT` | `5067` | Server port number |
| `LOOP_DELAY` | `0.1` | Delay between file reads (seconds) |
| `DEFAULT_VOLUME` | `5` | Default volume level (1-100) |

Edit these values in `stream_audio.py` before starting the server.

## Notes

- The server automatically discovers and connects to Google Nest Mini
- No need for Google Home app - direct Chromecast control
- Multiple MP3 files in the `music/` folder will loop automatically
- Use the pause/resume endpoints to control playback
- Device names are case-sensitive and should match exactly what's returned by /devices
- Volume is set automatically when connecting to a device
- Default volume is 5 (5%)
- The stream URL is automatically detected from the server's IP address

## Troubleshooting

### Chromecast Discovery Issues in Docker

If you see `[Errno 105] No buffer space available` when discovering devices, the Linux kernel's network buffer limits are too low for mDNS multicast discovery.

**Fix: Increase host system limits**

Since the container uses `network_mode: host`, kernel network settings must be configured on the host system.

**Temporary (until reboot):**
```bash
sudo sysctl -w net.core.rmem_max=2097152
sudo sysctl -w net.core.wmem_max=2097152
sudo sysctl -w net.ipv4.igmp_max_memberships=256
```

**Persistent (survives reboot):**

Add to `/etc/sysctl.conf` or create `/etc/sysctl.d/chromecast.conf`:
```
net.core.rmem_max=2097152
net.core.wmem_max=2097152
net.ipv4.igmp_max_memberships=256
```

Then apply: `sudo sysctl -p`

After setting these values, restart the container:
```bash
docker-compose restart
```
