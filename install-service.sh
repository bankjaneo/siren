#!/bin/bash

# Install siren as a systemd service
# Usage: sudo ./install-service.sh

set -e

WORKING_DIR="$(pwd)"
PYTHON_PATH="${WORKING_DIR}/venv/bin/python"

# Generate unique service name based on directory
# This ensures multiple siren instances can coexist
SERVICE_BASE="siren"
SERVICE_NAME="${SERVICE_BASE}-$(echo "$WORKING_DIR" | md5sum | cut -c1-8)"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use sudo)"
    exit 1
fi

# Check if a siren service already exists from this directory
EXISTING_SERVICE=$(systemctl list-unit-files --type=service | grep "^${SERVICE_BASE}-" | grep -o "^${SERVICE_BASE}-[^ ]*" | head -1)
if [ -n "$EXISTING_SERVICE" ] && [ "$EXISTING_SERVICE" != "$SERVICE_NAME" ]; then
    echo "Warning: Another siren service is already installed: ${EXISTING_SERVICE}"
    read -p "Do you want to continue and install a new instance? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled"
        exit 0
    fi
fi

# Check if virtual environment exists
if [ ! -f "$PYTHON_PATH" ]; then
    echo "Error: Virtual environment not found at ${WORKING_DIR}/venv"
    echo "Please create it first: python -m venv venv"
    exit 1
fi

# Check if service file exists in current directory
if [ ! -f "siren.service" ]; then
    echo "Error: siren.service file not found in current directory"
    exit 1
fi

# Create service file with correct paths
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Siren Google Cast (${WORKING_DIR})
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=${WORKING_DIR}
ExecStart=${PYTHON_PATH} stream_audio.py
User=root
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

echo "Created service file at ${SERVICE_FILE}"

# Reload systemd
systemctl daemon-reload

# Enable service to start on boot
systemctl enable "$SERVICE_NAME"

# Save service name to file for uninstall script
echo "$SERVICE_NAME" > "${WORKING_DIR}/.siren-service-name"

echo ""
echo "Service installed successfully!"
echo "Service name: ${SERVICE_NAME}"
echo ""
echo "Commands:"
echo "  sudo systemctl start ${SERVICE_NAME}    # Start the service"
echo "  sudo systemctl stop ${SERVICE_NAME}     # Stop the service"
echo "  sudo systemctl status ${SERVICE_NAME}   # Check service status"
echo "  sudo systemctl restart ${SERVICE_NAME}  # Restart the service"
echo "  sudo journalctl -u ${SERVICE_NAME} -f   # View logs"
echo ""
echo "The service will auto-start on boot."
echo "To uninstall, run: sudo ./uninstall-service.sh"
