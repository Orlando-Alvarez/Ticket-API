#!/usr/bin/env bash

set -euo pipefail

CONTAINER="ticket-api-nginx"

if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: Docker is not installed." >&2
    exit 1
fi

if [[ "$(docker inspect --format '{{.State.Running}}' "$CONTAINER" 2>/dev/null)" != "true" ]]; then
    echo "INFO: Nginx is not running. It will load the certificate on startup."
    exit 0
fi

docker exec "$CONTAINER" nginx -t

docker exec "$CONTAINER" nginx -s reload

echo "SUCCESS: Nginx reloaded after certificate renewal."
