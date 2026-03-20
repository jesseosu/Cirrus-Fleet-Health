"""Clear disk space via SSM Run Command.

Executes the clear_disk_space.sh script on the target instance to
remove temporary files and old logs.
"""

import logging
import time
from typing import Any

from src.shared.aws_clients import get_client
from src.shared.logger import get_logger
from src.shared.models import RemediationResult

logger: logging.Logger = get_logger("remediator")

SSM_TIMEOUT = 120
SSM_POLL_INTERVAL = 5


def clear_disk(instance_id: str) -> RemediationResult:
    """Clear disk space on an instance via SSM.

    Executes cleanup commands to remove old temp files, rotated logs,
    and vacuum journald.

    Args:
        instance_id: The EC2 instance ID.

    Returns:
        RemediationResult with space freed details.
    """
    ssm = get_client("ssm")
    start_time = time.monotonic()

    cleanup_commands = [
        "BEFORE=$(df / --output=used | tail -1 | tr -d ' ')",
        "find /tmp -type f -mtime +7 -delete 2>/dev/null || true",
        "find /var/log -name '*.gz' -delete 2>/dev/null || true",
        (
            "find /var/log -name '*.log' -size +100M "
            "-exec truncate -s 0 {} \\; 2>/dev/null || true"
        ),
        "journalctl --vacuum-time=3d 2>/dev/null || true",
        "AFTER=$(df / --output=used | tail -1 | tr -d ' ')",
        "FREED=$(( (BEFORE - AFTER) / 1024 ))",
        "USAGE=$(df / --output=pcent | tail -1 | tr -d ' %')",
        (
            "echo '{\"freed_mb\": '\"$FREED\"', "
            "\"current_usage_percent\": '\"$USAGE\"'}'"
        ),
    ]

    try:
        response: dict[str, Any] = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={
                "commands": cleanup_commands,
                "executionTimeout": [str(SSM_TIMEOUT)],
            },
            TimeoutSeconds=SSM_TIMEOUT,
        )
        command_id: str = response["Command"]["CommandId"]
        result = _wait_for_completion(ssm, command_id, instance_id)
        duration_ms = int((time.monotonic() - start_time) * 1000)

        if result["status"] == "Success":
            output = result.get("output", "").strip()
            return RemediationResult(
                action_taken="clear_disk",
                success=True,
                details={
                    "output": output,
                    "instance_id": instance_id,
                },
                duration_ms=duration_ms,
            )
        else:
            return RemediationResult(
                action_taken="clear_disk",
                success=False,
                details={
                    "error": result.get("error", "Command failed"),
                    "instance_id": instance_id,
                },
                duration_ms=duration_ms,
            )

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "Failed to clear disk on %s: %s", instance_id, str(e)
        )
        return RemediationResult(
            action_taken="clear_disk",
            success=False,
            details={"error": str(e), "instance_id": instance_id},
            duration_ms=duration_ms,
        )


def _wait_for_completion(
    ssm: Any, command_id: str, instance_id: str
) -> dict[str, str]:
    """Poll SSM for command completion."""
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
                return {
                    "status": result["Status"],
                    "output": result.get("StandardOutputContent", ""),
                    "error": result.get("StandardErrorContent", ""),
                }
        except Exception:
            pass
        time.sleep(SSM_POLL_INTERVAL)
    return {"status": "TimedOut", "error": "Polling timed out"}
