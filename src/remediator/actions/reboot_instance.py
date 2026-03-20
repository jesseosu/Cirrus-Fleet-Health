"""Controlled instance reboot via EC2 API.

Reboots the instance and waits for it to return to running state
with backoff polling.
"""

import logging
import time
from typing import Any

from src.shared.aws_clients import get_client
from src.shared.logger import get_logger
from src.shared.models import RemediationResult

logger: logging.Logger = get_logger("remediator")

MAX_WAIT_SECONDS = 300
INITIAL_POLL_INTERVAL = 5


def reboot_instance(instance_id: str) -> RemediationResult:
    """Reboot an EC2 instance and wait for it to return to running.

    Args:
        instance_id: The EC2 instance ID to reboot.

    Returns:
        RemediationResult indicating success or failure.
    """
    ec2 = get_client("ec2")
    start_time = time.monotonic()

    try:
        ec2.reboot_instances(InstanceIds=[instance_id])
        logger.info("Reboot initiated for instance %s", instance_id)

        final_state = _wait_for_running(ec2, instance_id)
        duration_ms = int((time.monotonic() - start_time) * 1000)

        if final_state == "running":
            return RemediationResult(
                action_taken="reboot_instance",
                success=True,
                details={
                    "instance_id": instance_id,
                    "final_state": final_state,
                },
                duration_ms=duration_ms,
            )
        else:
            return RemediationResult(
                action_taken="reboot_instance",
                success=False,
                details={
                    "instance_id": instance_id,
                    "final_state": final_state,
                    "error": f"Instance in state {final_state} after reboot",
                },
                duration_ms=duration_ms,
            )

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "Failed to reboot instance %s: %s", instance_id, str(e)
        )
        return RemediationResult(
            action_taken="reboot_instance",
            success=False,
            details={"error": str(e), "instance_id": instance_id},
            duration_ms=duration_ms,
        )


def _wait_for_running(ec2: Any, instance_id: str) -> str:
    """Wait for an instance to return to running state with backoff."""
    elapsed = 0.0
    poll_interval = INITIAL_POLL_INTERVAL

    while elapsed < MAX_WAIT_SECONDS:
        try:
            response: dict[str, Any] = ec2.describe_instance_status(
                InstanceIds=[instance_id],
                IncludeAllInstances=True,
            )
            statuses = response.get("InstanceStatuses", [])
            if statuses:
                state: str = (
                    statuses[0].get("InstanceState", {}).get("Name", "unknown")
                )
                if state == "running":
                    system_status = (
                        statuses[0]
                        .get("SystemStatus", {})
                        .get("Status", "")
                    )
                    if system_status == "ok":
                        return "running"
        except Exception as e:
            logger.warning(
                "Error polling instance %s status: %s",
                instance_id,
                str(e),
            )

        time.sleep(poll_interval)
        elapsed += poll_interval
        poll_interval = min(poll_interval * 1.5, 30)

    return "unknown"
