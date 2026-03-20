"""Replace an instance by terminating it (ASG handles replacement).

For instances in an Auto Scaling Group, termination triggers automatic
replacement via the ASG's desired capacity configuration.
"""

import logging
import time
from typing import Any

from src.shared.aws_clients import get_client
from src.shared.logger import get_logger
from src.shared.models import RemediationResult

logger: logging.Logger = get_logger("remediator")


def replace_instance(instance_id: str) -> RemediationResult:
    """Terminate an instance to trigger ASG replacement.

    Args:
        instance_id: The EC2 instance ID to terminate.

    Returns:
        RemediationResult indicating success or failure.
    """
    ec2 = get_client("ec2")
    start_time = time.monotonic()

    try:
        # Check if instance is in an ASG
        autoscaling = get_client("autoscaling")
        asg_response: dict[str, Any] = (
            autoscaling.describe_auto_scaling_instances(
                InstanceIds=[instance_id]
            )
        )
        asg_instances = asg_response.get("AutoScalingInstances", [])
        in_asg = len(asg_instances) > 0
        asg_name = (
            asg_instances[0]["AutoScalingGroupName"] if in_asg else None
        )

        response: dict[str, Any] = ec2.terminate_instances(
            InstanceIds=[instance_id]
        )
        terminating_instances = response.get(
            "TerminatingInstances", []
        )
        duration_ms = int((time.monotonic() - start_time) * 1000)

        if terminating_instances:
            current_state: str = (
                terminating_instances[0]
                .get("CurrentState", {})
                .get("Name", "unknown")
            )
            logger.info(
                "Instance %s terminated (state: %s, in_asg: %s)",
                instance_id,
                current_state,
                in_asg,
            )
            return RemediationResult(
                action_taken="replace_instance",
                success=True,
                details={
                    "instance_id": instance_id,
                    "current_state": current_state,
                    "in_asg": in_asg,
                    "asg_name": asg_name,
                },
                duration_ms=duration_ms,
            )
        else:
            return RemediationResult(
                action_taken="replace_instance",
                success=False,
                details={
                    "instance_id": instance_id,
                    "error": "No termination response received",
                },
                duration_ms=duration_ms,
            )

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "Failed to replace instance %s: %s", instance_id, str(e)
        )
        return RemediationResult(
            action_taken="replace_instance",
            success=False,
            details={"error": str(e), "instance_id": instance_id},
            duration_ms=duration_ms,
        )
