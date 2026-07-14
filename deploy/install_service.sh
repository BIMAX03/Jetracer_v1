#!/bin/sh
set -eu

SERVICE_NAME="jetracer.service"
PROJECT_DIR="/home/jet-ai-lab/Jetracer/JetRacer"
SERVICE_SOURCE="$PROJECT_DIR/deploy/$SERVICE_NAME"
SERVICE_TARGET="/etc/systemd/system/$SERVICE_NAME"

if [ ! -f "$SERVICE_SOURCE" ]; then
    echo "Không tìm thấy $SERVICE_SOURCE" >&2
    exit 1
fi

echo "Cài $SERVICE_NAME..."
sudo install -m 0644 "$SERVICE_SOURCE" "$SERVICE_TARGET"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo "JetRacer đã được bật tự khởi động."
sudo systemctl status "$SERVICE_NAME" --no-pager
