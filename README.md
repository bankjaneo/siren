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

4. Override configuration via environment variables:
```bash
docker-compose --env-file .env up --build
```

Create a `.env` file for custom configuration:
```env
MUSIC_FOLDER=/music
DEFAULT_DEVICE=Living room speaker
PORT=8080
LOOP_DELAY=0.2
DEFAULT_VOLUME=50
```

## Usage

The server will start on `http://localhost:5067`

### Web Interface

Navigate to `http://localhost:5067` in your browser for the web UI.

### API Endpoints

| Endpoint | Description | Example |
|----------|-------------|---------|
| `GET /play` | Start streaming to default device (auto-selects Google Nest Mini) | `curl http://localhost:5067/play` |
| `GET /play/DeviceName` | Start streaming to specific Chromecast device | `curl http://localhost:5067/play/Bedroom%20speaker` |
| `GET /pause` | Stop streaming and pause playback | `curl http://localhost:5067/pause` |
| `GET /resume` | Resume playback from paused state | `curl http://localhost:5067/resume` |
| `GET /status` | Check current streaming state and file info | `curl http://localhost:5067/status` |
| `GET /previous` | Play previous file in playlist | `curl http://localhost:5067/previous` |
| `GET /next` | Play next file in playlist | `curl http://localhost:5067/next` |
| `GET /connect` | Connect to default Chromecast device | `curl http://localhost:5067/connect` |
| `GET /connect/DeviceName` | Connect to specific Chromecast device | `curl http://localhost:5067/connect/Bedroom%20speaker` |
| `GET /devices` | List all available Chromecast devices | `curl http://localhost:5067/devices` |
| `GET /volume/{level}` | Set volume level (1-100) | `curl http://localhost:5067/volume/75` |
| `GET /files` | List available MP3 files | `curl http://localhost:5067/files` |
| `GET /config` | Get current application configuration | `curl http://localhost:5067/config` |

### Play on Chromecast

1. Start the server: `./start.sh` or `docker-compose up -d`
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

The following variables can be customized via environment variables or in `stream_audio.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `MUSIC_FOLDER` | `"music/"` | Folder containing MP3 files to stream |
| `DEFAULT_DEVICE` | `"Bedroom speaker"` | Default Chromecast device name |
| `PORT` | `5067` | Server port number |
| `LOOP_DELAY` | `0.1` | Delay between file reads (seconds) |
| `DEFAULT_VOLUME` | `5` | Default volume level (1-100) |

### Docker Configuration

For Docker deployments, you can override these values in `docker-compose.yml` or via `.env` file:

```yaml
environment:
  - MUSIC_FOLDER=/music
  - DEFAULT_DEVICE=Living room speaker
  - PORT=8080
  - LOOP_DELAY=0.2
  - DEFAULT_VOLUME=50
```

### Local Configuration

For local development, edit `stream_audio.py` directly:

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
