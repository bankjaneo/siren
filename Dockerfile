FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY stream_audio.py .
COPY templates/ templates/
COPY music/ music/

# Expose port
EXPOSE 5067

# Run the application as root (required for host networking)
CMD ["python", "stream_audio.py"]
