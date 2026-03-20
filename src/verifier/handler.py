"""Lambda handler for post-remediation verification.

Re-runs health checks against a remediated instance to confirm the
remediation was successful.
"""

import logging
from typing import Any

from src.shared.aws_clients import get_client
from src.shared.constants import Severity
from src.shared.logger import get_logger
from src.shared.models import HealthCheckResult

from src.health_checker.checks.cloudwatch_metrics import (
    check_cloudwatch_metrics,
)
from src.health_checker.checks.ec2_status import check_ec2_status
from src.health_checker.checks.endpoint_health import check_endpoint_health
from src.health_checker.checks.process_health import check_process_health
from src.health_checker.evaluator import evaluate_health

logger: logging.Logger = get_logger("verifier")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for post-remediation health verification.

    Re-runs all health checks for the specified instance and returns
    whether the remediation was successful.

    Args:
        event: Event containing instance_id and remediation details.
        context: Lambda context object.

    Returns:
        Verification result with REMEDIATION_SUCCEEDED or REMEDIATION_FAILED.
    """
    body = event.get("body", event)
    instance_id: str = body.get("instance_id", "")
    if not instance_id:
        logger.error("No instance_id in verification event")
        return {
            "statusCode": 400,
            "body": {"error": "Missing instance_id"},
        }

    logger.info("Starting verification for instance %s", instance_id)

    try:
        results: list[HealthCheckResult] = []

        results.append(check_ec2_status(instance_id))
        results.append(check_cloudwatch_metrics(instance_id))
        results.append(check_process_health(instance_id))

        private_ip = _get_private_ip(instance_id)
        if private_ip:
            results.append(check_endpoint_health(instance_id, private_ip))

        verdict = evaluate_health(instance_id, results)

        if verdict.severity == Severity.HEALTHY:
            status = "REMEDIATION_SUCCEEDED"
            is_healthy = True
        else:
            status = "REMEDIATION_FAILED"
            is_healthy = False

        logger.info(
            "Verification for %s: %s (severity: %s)",
            instance_id,
            status,
            verdict.severity.value,
        )

        return {
            "statusCode": 200,
            "body": {
                "instance_id": instance_id,
                "verification_status": status,
                "is_healthy": is_healthy,
                "severity": verdict.severity.value,
                "failed_checks": verdict.failed_checks,
            },
        }

    except Exception as e:
        logger.error(
            "Verification failed for %s: %s",
            instance_id,
            str(e),
            exc_info=True,
        )
        return {
            "statusCode": 500,
            "body": {
                "instance_id": instance_id,
                "verification_status": "REMEDIATION_FAILED",
                "is_healthy": False,
                "error": str(e),
            },
        }


def _get_private_ip(instance_id: str) -> str:
    """Retrieve the private IP address for an instance."""
    ec2 = get_client("ec2")
    try:
        response: dict[str, Any] = ec2.describe_instances(
            InstanceIds=[instance_id]
        )
        reservations = response.get("Reservations", [])
        if reservations and reservations[0].get("Instances"):
            return reservations[0]["Instances"][0].get(
                "PrivateIpAddress", ""
            )
    except Exception as e:
        logger.warning(
            "Could not get private IP for %s: %s", instance_id, str(e)
        )
    return ""
