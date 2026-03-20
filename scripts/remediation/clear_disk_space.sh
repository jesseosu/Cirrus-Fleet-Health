#!/bin/bash
# Clears temporary files and old logs to free disk space
# Exit codes: 0 = space freed, 1 = minimal space freed

set -uo pipefail

# Record initial disk usage (root filesystem)
BEFORE_KB=$(df / --output=used | tail -1 | tr -d ' ')

echo "Starting disk cleanup..." >&2

# Clear /tmp files older than 7 days
find /tmp -type f -mtime +7 -delete 2>/dev/null || true
find /tmp -type d -empty -mtime +7 -delete 2>/dev/null || true

# Clear rotated/compressed log files
find /var/log -name '*.gz' -delete 2>/dev/null || true
find /var/log -name '*.1' -delete 2>/dev/null || true
find /var/log -name '*.old' -delete 2>/dev/null || true

# Truncate large active log files (> 100MB) — truncate, don't delete
find /var/log -name '*.log' -size +100M -exec truncate -s 0 {} \; 2>/dev/null || true

# Clean up journald logs older than 3 days
journalctl --vacuum-time=3d 2>/dev/null || true

# Clean package manager caches
if command -v yum &>/dev/null; then
    yum clean all 2>/dev/null || true
elif command -v apt-get &>/dev/null; then
    apt-get clean 2>/dev/null || true
fi

# Record final disk usage
AFTER_KB=$(df / --output=used | tail -1 | tr -d ' ')
FREED_MB=$(( (BEFORE_KB - AFTER_KB) / 1024 ))
CURRENT_USAGE=$(df / --output=pcent | tail -1 | tr -d ' %')

echo "{\"freed_mb\": ${FREED_MB}, \"current_usage_percent\": ${CURRENT_USAGE}}"

if [ "${FREED_MB}" -gt 10 ]; then
    exit 0
else
    exit 1
fi
