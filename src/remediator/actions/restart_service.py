"""Restart a systemd service via SSM Run Command.

Executes the restart_service.sh script on the target instance and
verifies the service returns to active state.
"""

import logging
import time
from typing import Any

from src.shared.aws_clients import get_client
from src.shared.logger import get_logger
from src.shared.models import RemediationResult

logger: logging.Logger = get_logger("remediator")

SSM_TIMEOUT = 60
SSM_POLL_INTERVAL = 3


def restart_service(
    instance_id: str, service_name: str = "httpd"
) -> RemediationResult:
    """Restart a systemd service on an instance via SSM.

    Args:
        instance_id: The EC2 instance ID.
        service_name: Name of the systemd service to restart.

    Returns:
        RemediationResult indicating success or failure.
    """
    ssm = get_client("ssm")
    start_time = time.monotonic()

    try:
        response: dict[str, Any] = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={
                "commands": [
                    f"systemctl restart {service_name} && "
                    f"sleep 5 && "
                    f"systemctl is-active {service_name}"
                ],
                "executionTimeout": [str(SSM_TIMEOUT)],
            },
            TimeoutSeconds=SSM_TIMEOUT,
        )
        command_id: str = response["Command"]["CommandId"]
        result = _wait_for_completion(ssm, command_id, instance_id)
        duration_ms = int((time.monotonic() - start_time) * 1000)

        if result["status"] == "Success":
            output = result.get("output", "").strip()
            is_active = "active" in output.lower()
            return RemediationResult(
                action_taken=f"restart_service:{service_name}",
                success=is_active,
                details={
                    "service": service_name,
                    "output": output,
                    "instance_id": instance_id,
                },
                duration_ms=duration_ms,
            )
        else:
            return RemediationResult(
                action_taken=f"restart_service:{service_name}",
                success=False,
                details={
                    "service": service_name,
                    "error": result.get("error", "Command failed"),
                    "instance_id": instance_id,
                },
                duration_ms=duration_ms,
            )

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "Failed to restart %s on %s: %s",
            service_name,
            instance_id,
            str(e),
        )
        return RemediationResult(
            action_taken=f"restart_service:{service_name}",
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
