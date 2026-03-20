"""SSM-based process liveness health check.

Uses AWS Systems Manager Run Command to execute a process check script
on the target instance and evaluates the results.
"""

import logging
import time
from typing import Any

from src.shared.aws_clients import get_client
from src.shared.constants import CRITICAL_PROCESSES, CheckName, Severity
from src.shared.logger import get_logger
from src.shared.models import HealthCheckResult

logger: logging.Logger = get_logger("health-checker")

SSM_COMMAND_TIMEOUT = 30
SSM_POLL_INTERVAL = 2


def check_process_health(instance_id: str) -> HealthCheckResult:
    """Check if critical processes are running on an instance via SSM.

    Sends the check_process.sh script via SSM Run Command for each
    configured critical process and evaluates the results.

    Args:
        instance_id: The EC2 instance ID to check.

    Returns:
        HealthCheckResult with severity based on process status.
    """
    ssm = get_client("ssm")
    process_statuses: dict[str, Any] = {}
    overall_severity = Severity.HEALTHY

    for process_name in CRITICAL_PROCESSES:
        process_name = process_name.strip()
        if not process_name:
            continue
        try:
            response: dict[str, Any] = ssm.send_command(
                InstanceIds=[instance_id],
                DocumentName="AWS-RunShellScript",
                Parameters={
                    "commands": [
                        f"pgrep -x {process_name} > /dev/null 2>&1 "
                        f"&& echo 'RUNNING' || echo 'NOT_RUNNING'"
                    ],
                    "executionTimeout": [str(SSM_COMMAND_TIMEOUT)],
                },
                TimeoutSeconds=SSM_COMMAND_TIMEOUT,
            )
            command_id: str = response["Command"]["CommandId"]

            status = _wait_for_command(ssm, command_id, instance_id)
            if status["status"] == "Success":
                output = status.get("output", "").strip()
                if output == "RUNNING" or output.startswith("RUNNING"):
                    process_statuses[process_name] = {
                        "status": "running",
                    }
                else:
                    process_statuses[process_name] = {
                        "status": "not_running",
                    }
                    overall_severity = Severity.UNHEALTHY
            else:
                process_statuses[process_name] = {
                    "status": "check_failed",
                    "error": status.get("error", "Command failed"),
                }
                overall_severity = Severity.DEGRADED

        except Exception as e:
            logger.error(
                "SSM check failed for process %s on %s: %s",
                process_name,
                instance_id,
                str(e),
            )
            process_statuses[process_name] = {
                "status": "error",
                "error": str(e),
            }
            overall_severity = Severity.CRITICAL

    return HealthCheckResult(
        check_name=CheckName.PROCESS_HEALTH.value,
        status=overall_severity,
        details={
            "instance_id": instance_id,
            "processes": process_statuses,
        },
    )


def _wait_for_command(
    ssm: Any, command_id: str, instance_id: str
) -> dict[str, str]:
    """Poll SSM for command completion.

    Args:
        ssm: SSM client.
        command_id: The SSM command ID to poll.
        instance_id: Target instance ID.

    Returns:
        Dict with 'status' and 'output' or 'error' keys.
    """
    max_attempts = SSM_COMMAND_TIMEOUT // SSM_POLL_INTERVAL
    for _ in range(max_attempts):
        try:
            result: dict[str, Any] = ssm.get_command_invocation(
                CommandId=command_id,
                InstanceId=instance_id,
            )
            cmd_status: str = result.get("Status", "")
            if cmd_status in ("Success", "Failed", "TimedOut", "Cancelled"):
                return {
                    "status": cmd_status,
                    "output": result.get("StandardOutputContent", ""),
                    "error": result.get("StandardErrorContent", ""),
                }
        except ssm.exceptions.InvocationDoesNotExist:
            pass
        except Exception:
            pass
        time.sleep(SSM_POLL_INTERVAL)
    return {"status": "TimedOut", "error": "Command polling timed out"}
