#!/bin/bash
# Usage: check_process.sh <process_name>
# Checks if a process is running
# Exit codes: 0 = running, 1 = not running

set -uo pipefail

PROCESS_NAME="${1:?Usage: check_process.sh <process_name>}"

# Find process using pgrep
PIDS=$(pgrep -d ',' "${PROCESS_NAME}" 2>/dev/null) || true

if [ -z "${PIDS}" ]; then
    echo "{\"process\": \"${PROCESS_NAME}\", \"running\": false, \"pid\": null, \"cpu_percent\": null, \"mem_percent\": null, \"uptime\": null}"
    exit 1
fi

# Get the first PID for detailed info
FIRST_PID=$(echo "${PIDS}" | cut -d',' -f1)

# Get CPU and memory usage
CPU_PERCENT=$(ps -p "${FIRST_PID}" -o %cpu= 2>/dev/null | tr -d ' ' || echo "0.0")
MEM_PERCENT=$(ps -p "${FIRST_PID}" -o %mem= 2>/dev/null | tr -d ' ' || echo "0.0")

# Get process uptime (elapsed time)
UPTIME=$(ps -p "${FIRST_PID}" -o etime= 2>/dev/null | tr -d ' ' || echo "unknown")

echo "{\"process\": \"${PROCESS_NAME}\", \"running\": true, \"pid\": ${FIRST_PID}, \"all_pids\": \"${PIDS}\", \"cpu_percent\": ${CPU_PERCENT}, \"mem_percent\": ${MEM_PERCENT}, \"uptime\": \"${UPTIME}\"}"
exit 0
