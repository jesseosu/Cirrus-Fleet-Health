#!/bin/bash
# Usage: restart_service.sh <service_name>
# Restarts a systemd service and verifies it's running
# Exit codes: 0 = success, 1 = restart failed, 2 = service not found

set -euo pipefail

SERVICE_NAME="${1:?Usage: restart_service.sh <service_name>}"

# Check if service exists
if ! systemctl list-units --type=service --all | grep -q "${SERVICE_NAME}.service"; then
    echo "{\"service\": \"${SERVICE_NAME}\", \"status\": \"not_found\", \"pid\": null}"
    exit 2
fi

# Attempt restart
echo "Restarting service: ${SERVICE_NAME}" >&2
if ! systemctl restart "${SERVICE_NAME}"; then
    echo "{\"service\": \"${SERVICE_NAME}\", \"status\": \"restart_failed\", \"pid\": null}"
    exit 1
fi

# Wait for service to stabilize
sleep 5

# Verify service is active
STATUS=$(systemctl is-active "${SERVICE_NAME}" 2>/dev/null || echo "inactive")
PID=$(systemctl show "${SERVICE_NAME}" --property=MainPID --value 2>/dev/null || echo "0")

if [ "${STATUS}" = "active" ]; then
    echo "{\"service\": \"${SERVICE_NAME}\", \"status\": \"active\", \"pid\": ${PID}}"
    exit 0
else
    echo "{\"service\": \"${SERVICE_NAME}\", \"status\": \"${STATUS}\", \"pid\": null}"
    exit 1
fi
