#!/bin/bash

# Build the web UI if it hasn't been built yet (requires Node.js/npm)
if [ ! -f "frontend/dist/index.html" ]; then
    if command -v npm >/dev/null 2>&1; then
        echo "Building web UI..."
        (cd frontend && npm install && npm run build) || {
            echo "Failed to build web UI"
            exit 1
        }
    else
        echo "Web UI is not built and npm is not available."
        echo "Install Node.js, then run: cd frontend && npm install && npm run build"
        exit 1
    fi
fi

# Activate virtual environment
source venv/bin/activate

# Check if MP3 files exist in music folder
if [ ! -d "music" ] || [ -z "$(ls -A music/*.mp3 2>/dev/null)" ]; then
    echo "Please place your MP3 files in the 'music/' folder"
    echo "You can download sample MP3s from: https://www.soundhelix.com/examples/mp3/"
fi

# Start the streaming server
python stream_audio.py
