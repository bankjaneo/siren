#!/bin/bash

# Uninstall siren systemd service
# Usage: sudo ./uninstall-service.sh

set -e

WORKING_DIR="$(pwd)"
SERVICE_NAME_FILE="${WORKING_DIR}/.siren-service-name"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use sudo)"
    exit 1
fi

# Try to get service name from saved file
if [ -f "$SERVICE_NAME_FILE" ]; then
    SERVICE_NAME=$(cat "$SERVICE_NAME_FILE")
    echo "Found service name from previous installation: ${SERVICE_NAME}"
else
    # Try to find service by checking working directory in existing services
    SERVICE_NAME=$(systemctl list-units --type=service --all | grep "siren-" | awk '{print $1}' | while read service; do
        if systemctl cat "$service" 2>/dev/null | grep -q "WorkingDirectory=${WORKING_DIR}"; then
            echo "$service" | sed 's/.service$//'
            break
        fi
    done)
    
    if [ -z "$SERVICE_NAME" ]; then
        echo "Error: Could not find siren service for this directory"
        echo "Service may not be installed, or was installed with a different method"
        exit 1
    fi
    echo "Found service: ${SERVICE_NAME}"
fi

SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# Check if service file exists
if [ ! -f "$SERVICE_FILE" ]; then
    echo "Error: Service file not found at ${SERVICE_FILE}"
    rm -f "$SERVICE_NAME_FILE"
    exit 1
fi

echo "Stopping ${SERVICE_NAME} service..."
systemctl stop "$SERVICE_NAME" 2>/dev/null || true

echo "Disabling ${SERVICE_NAME} service..."
systemctl disable "$SERVICE_NAME" 2>/dev/null || true

echo "Removing service file..."
rm -f "$SERVICE_FILE"

echo "Cleaning up local files..."
rm -f "$SERVICE_NAME_FILE"

echo "Reloading systemd..."
systemctl daemon-reload

echo ""
echo "Service ${SERVICE_NAME} has been uninstalled successfully!"
echo "The service will no longer auto-start on boot."
