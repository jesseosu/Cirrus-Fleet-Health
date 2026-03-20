#!/bin/bash
# Collects system diagnostic information
# Outputs structured JSON with system state

set -uo pipefail

collect_section() {
    local name="$1"
    shift
    local output
    output=$("$@" 2>/dev/null) || output="command failed"
    # Escape special JSON characters
    output=$(echo "$output" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/\\t/g' | tr '\n' '|' | sed 's/|/\\n/g')
    echo "\"${name}\": \"${output}\""
}

echo "{"

# Disk usage
echo "$(collect_section "disk_usage" df -h),"

# Memory info
echo "$(collect_section "memory_info" free -m),"

# Top output (snapshot)
echo "$(collect_section "top_output" top -bn1 -w 120),"

# Top memory-consuming processes
echo "$(collect_section "top_processes" ps aux --sort=-%mem),"

# Recent kernel messages
echo "$(collect_section "dmesg_tail" dmesg),"

# Failed systemd services
echo "$(collect_section "failed_services" systemctl --failed),"

# Network: listening ports
NETWORK_INFO=$(ss -tlnp 2>/dev/null || echo "ss not available")
IP_INFO=$(ip addr 2>/dev/null || echo "ip not available")
COMBINED="${NETWORK_INFO}\n${IP_INFO}"
COMBINED=$(echo "$COMBINED" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/\\t/g' | tr '\n' '|' | sed 's/|/\\n/g')
echo "\"network_info\": \"${COMBINED}\""

echo "}"
