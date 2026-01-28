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
docker run -p 5000:5000 -v $(pwd)/music:/app/music siren-stream
```

3. Or use docker-compose:
```bash
docker-compose up --build
```

## Usage

The server will start on `http://localhost:5000`

### Web Interface

Navigate to `http://localhost:5000` in your browser for the web UI.

### API Endpoints

- **Play**: `curl http://localhost:5000/play` - Start streaming (auto-selects Google Nest Mini)
- **Play with device**: `curl http://localhost:5000/play/Bedroom%20speaker` - Start streaming to specific device
- **Pause**: `curl http://localhost:5000/pause` - Stop streaming
- **Resume**: `curl http://localhost:5000/resume` - Continue streaming
- **Status**: `curl http://localhost:5000/status` - Check current state (includes current file index and file)
- **Previous**: `curl http://localhost:5000/previous` - Play previous file in playlist
- **Next**: `curl http://localhost:5000/next` - Play next file in playlist
- **Connect**: `curl http://localhost:5000/connect` - Connect to Google Nest Mini
- **Connect with device**: `curl http://localhost:5000/connect/Bedroom%20speaker` - Connect to specific device
- **Devices**: `curl http://localhost:5000/devices` - List available Chromecast devices
- **Volume**: `curl http://localhost:5000/volume/75` - Set volume to 75%
- **Files**: `curl http://localhost:5000/files` - List available MP3 files
- **Config**: `curl http://localhost:5000/config` - Get application configuration

### Play on Chromecast

1. Start the server: `./start.sh` or `docker-compose up`
2. List available devices: `curl http://localhost:5000/devices`
3. Navigate to `http://localhost:5000` in your browser
4. Use `/play` to start the continuous loop (auto-selects Google Nest Mini)
5. Or use `/play/DeviceName` to specify which device to play on

### Volume Control

- Set volume after connecting: `curl http://localhost:5000/volume/50`
- Volume range: 1-100 (default: 5)
- Volume is set automatically when connecting to a device

The audio will start playing and loop continuously. Use `/play` or `/pause` endpoints to control playback.

## Notes

- The server automatically discovers and connects to Google Nest Mini
- No need for Google Home app - direct Chromecast control
- Multiple MP3 files in the `music/` folder will loop automatically
- Use the pause/resume endpoints to control playback
- Device names are case-sensitive and should match exactly what's returned by /devices
- Volume is set automatically when connecting to a device
- Default volume is 5 (5%)
- The stream URL is automatically detected from the server's IP address
