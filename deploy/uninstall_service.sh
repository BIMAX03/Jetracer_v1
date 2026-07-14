#!/bin/sh
set -eu

SERVICE_NAME="jetracer.service"
SERVICE_TARGET="/etc/systemd/system/$SERVICE_NAME"

sudo systemctl disable --now "$SERVICE_NAME" 2>/dev/null || true
sudo rm -f "$SERVICE_TARGET"
sudo systemctl daemon-reload

echo "Đã gỡ dịch vụ $SERVICE_NAME."
