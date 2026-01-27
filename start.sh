#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Check if MP3 files exist in music folder
if [ ! -d "music" ] || [ -z "$(ls -A music/*.mp3 2>/dev/null)" ]; then
    echo "Please place your MP3 files in the 'music/' folder"
    echo "You can download sample MP3s from: https://www.soundhelix.com/examples/mp3/"
fi

# Start the streaming server
python stream_audio.py
