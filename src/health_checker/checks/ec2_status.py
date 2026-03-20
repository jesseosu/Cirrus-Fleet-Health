"""EC2 system and instance status checks.

Evaluates the AWS-reported health status of an EC2 instance by querying
the describe_instance_status API for both system-level and instance-level
status checks.
"""

import logging
from typing import Any

from src.shared.aws_clients import get_client
from src.shared.constants import CheckName, Severity
from src.shared.logger import get_logger
from src.shared.models import HealthCheckResult

logger: logging.Logger = get_logger("health-checker")


def check_ec2_status(instance_id: str) -> HealthCheckResult:
    """Check EC2 system and instance status for a given instance.

    Calls describe_instance_status to evaluate both the system status
    (underlying host) and instance status (guest OS). Maps AWS status
    values to Cirrus severity levels.

    Args:
        instance_id: The EC2 instance ID to check.

    Returns:
        HealthCheckResult with severity based on AWS status checks.
    """
    ec2 = get_client("ec2")
    try:
        response: dict[str, Any] = ec2.describe_instance_status(
            InstanceIds=[instance_id],
            IncludeAllInstances=True,
        )
        statuses = response.get("InstanceStatuses", [])
        if not statuses:
            logger.warning(
                "No status returned for instance %s", instance_id
            )
            return HealthCheckResult(
                check_name=CheckName.EC2_STATUS.value,
                status=Severity.CRITICAL,
                details={
                    "error": "No status information available",
                    "instance_id": instance_id,
                },
            )

        instance_status = statuses[0]
        system_status: str = (
            instance_status.get("SystemStatus", {})
            .get("Status", "unknown")
        )
        inst_status: str = (
            instance_status.get("InstanceStatus", {})
            .get("Status", "unknown")
        )
        instance_state: str = (
            instance_status.get("InstanceState", {})
            .get("Name", "unknown")
        )

        details = {
            "instance_id": instance_id,
            "system_status": system_status,
            "instance_status": inst_status,
            "instance_state": instance_state,
        }

        if instance_state != "running":
            return HealthCheckResult(
                check_name=CheckName.EC2_STATUS.value,
                status=Severity.CRITICAL,
                details=details,
            )

        if system_status == "ok" and inst_status == "ok":
            severity = Severity.HEALTHY
        elif system_status == "impaired" or inst_status == "impaired":
            severity = Severity.UNHEALTHY
        elif system_status == "initializing" or inst_status == "initializing":
            severity = Severity.DEGRADED
        else:
            severity = Severity.UNHEALTHY

        return HealthCheckResult(
            check_name=CheckName.EC2_STATUS.value,
            status=severity,
            details=details,
        )

    except Exception as e:
        logger.error(
            "Failed to check EC2 status for %s: %s", instance_id, str(e)
        )
        return HealthCheckResult(
            check_name=CheckName.EC2_STATUS.value,
            status=Severity.CRITICAL,
            details={"error": str(e), "instance_id": instance_id},
        )
