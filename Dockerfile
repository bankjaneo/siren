# --- Stage 1: build the web UI ---
FROM node:22-alpine AS ui

WORKDIR /ui

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# --- Stage 2: Python runtime ---
FROM python:3.11-alpine

WORKDIR /app

# Install build dependencies, Python packages, then clean up
RUN apk add --no-cache --virtual .build-deps gcc musl-dev \
    && pip install --no-cache-dir flask==3.0.0 flask-cors==4.0.0 pychromecast==14.0.9 zeroconf==0.135.0 \
    && apk del .build-deps

# Copy application files (music folder is mounted as volume)
COPY stream_audio.py .
COPY favicon.png .
COPY --from=ui /ui/dist frontend/dist

# Create empty music directory for volume mount
RUN mkdir -p music

EXPOSE 5067

CMD ["sh", "-c", "export MUSIC_FOLDER=$MUSIC_FOLDER && export DEFAULT_DEVICE=$DEFAULT_DEVICE && export PORT=$PORT && export LOOP_DELAY=$LOOP_DELAY && export DEFAULT_VOLUME=$DEFAULT_VOLUME && python stream_audio.py"]
