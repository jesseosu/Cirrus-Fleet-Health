"""System state collector via SSM Run Command.

Executes the collect_diagnostics.sh script on the target instance to
capture system-level diagnostic information.
"""

import logging
import time
from typing import Any

from src.shared.aws_clients import get_client
from src.shared.logger import get_logger
from src.shared.models import SystemInfo

logger: logging.Logger = get_logger("diagnostics")

SSM_TIMEOUT = 30
SSM_POLL_INTERVAL = 2


def collect_system_info(instance_id: str) -> SystemInfo:
    """Collect system diagnostic information from an instance via SSM.

    Executes commands to capture disk usage, memory, top processes,
    and recent kernel messages.

    Args:
        instance_id: The EC2 instance ID.

    Returns:
        SystemInfo with captured system state data.
    """
    ssm = get_client("ssm")
    commands = [
        "echo '===DISK===' && df -h",
        "echo '===MEMORY===' && free -m",
        "echo '===TOP===' && top -bn1 | head -20",
        "echo '===PROCESSES===' && ps aux --sort=-%mem | head -10",
        "echo '===DMESG===' && dmesg | tail -50",
        "echo '===FAILED_SERVICES===' && systemctl --failed",
        "echo '===NETWORK===' && ss -tlnp && ip addr",
    ]

    try:
        response: dict[str, Any] = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={
                "commands": [" && ".join(commands)],
                "executionTimeout": [str(SSM_TIMEOUT)],
            },
            TimeoutSeconds=SSM_TIMEOUT,
        )
        command_id: str = response["Command"]["CommandId"]
        output = _wait_and_get_output(ssm, command_id, instance_id)

        return _parse_output(output)

    except Exception as e:
        logger.error(
            "Failed to collect system info for %s: %s",
            instance_id,
            str(e),
        )
        return SystemInfo()


def _wait_and_get_output(
    ssm: Any, command_id: str, instance_id: str
) -> str:
    """Wait for SSM command to complete and return output."""
    max_attempts = SSM_TIMEOUT // SSM_POLL_INTERVAL
    for _ in range(max_attempts):
        try:
            result: dict[str, Any] = ssm.get_command_invocation(
                CommandId=command_id,
                InstanceId=instance_id,
            )
            if result.get("Status") in (
                "Success", "Failed", "TimedOut", "Cancelled"
            ):
                return result.get("StandardOutputContent", "")
        except Exception:
            pass
        time.sleep(SSM_POLL_INTERVAL)
    return ""


def _parse_output(output: str) -> SystemInfo:
    """Parse the combined command output into SystemInfo sections."""
    sections: dict[str, str] = {}
    current_section = ""
    current_lines: list[str] = []

    for line in output.split("\n"):
        if line.startswith("===") and line.endswith("==="):
            if current_section:
                sections[current_section] = "\n".join(current_lines)
            current_section = line.strip("=")
            current_lines = []
        else:
            current_lines.append(line)

    if current_section:
        sections[current_section] = "\n".join(current_lines)

    return SystemInfo(
        disk_usage=sections.get("DISK", ""),
        memory_info=sections.get("MEMORY", ""),
        top_output=sections.get("TOP", ""),
        top_processes=sections.get("PROCESSES", ""),
        dmesg_tail=sections.get("DMESG", ""),
        failed_services=sections.get("FAILED_SERVICES", ""),
        network_info=sections.get("NETWORK", ""),
    )
