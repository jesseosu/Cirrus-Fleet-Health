"""Lambda handler for the fleet health checker.

Triggered by EventBridge Scheduler every 60 seconds. Discovers all
monitored EC2 instances and runs health checks in parallel using
ThreadPoolExecutor.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from src.shared.aws_clients import get_client
from src.shared.constants import (
    MONITORED_TAG_KEY,
    MONITORED_TAG_VALUE,
    Severity,
)
from src.shared.logger import get_logger
from src.shared.models import HealthCheckResult, HealthVerdict

from src.health_checker.checks.cloudwatch_metrics import (
    check_cloudwatch_metrics,
)
from src.health_checker.checks.ec2_status import check_ec2_status
from src.health_checker.checks.endpoint_health import check_endpoint_health
from src.health_checker.checks.process_health import check_process_health
from src.health_checker.evaluator import evaluate_health
from src.health_checker.publisher import publish_events, publish_metrics

logger: logging.Logger = get_logger("health-checker")


def _discover_instances() -> list[dict[str, Any]]:
    """Discover EC2 instances tagged for Cirrus monitoring.

    Returns:
        List of instance dicts with 'InstanceId' and 'PrivateIpAddress'.
    """
    ec2 = get_client("ec2")
    instances: list[dict[str, Any]] = []
    paginator = ec2.get_paginator("describe_instances")
    page_iterator = paginator.paginate(
        Filters=[
            {"Name": f"tag:{MONITORED_TAG_KEY}", "Values": [MONITORED_TAG_VALUE]},
            {"Name": "instance-state-name", "Values": ["running"]},
        ]
    )
    for page in page_iterator:
        for reservation in page.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                instances.append({
                    "InstanceId": instance["InstanceId"],
                    "PrivateIpAddress": instance.get(
                        "PrivateIpAddress", ""
                    ),
                })
    logger.info("Discovered %d monitored instances", len(instances))
    return instances


def _run_checks_for_instance(
    instance: dict[str, Any],
) -> HealthVerdict:
    """Run all health checks for a single instance.

    Args:
        instance: Dict with 'InstanceId' and 'PrivateIpAddress'.

    Returns:
        HealthVerdict for the instance.
    """
    instance_id: str = instance["InstanceId"]
    private_ip: str = instance.get("PrivateIpAddress", "")
    results: list[HealthCheckResult] = []

    checks = [
        lambda: check_ec2_status(instance_id),
        lambda: check_cloudwatch_metrics(instance_id),
        lambda: check_process_health(instance_id),
    ]
    if private_ip:
        checks.append(
            lambda ip=private_ip: check_endpoint_health(instance_id, ip)
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(check): check for check in checks}
        for future in as_completed(futures):
            try:
                result = future.result(timeout=30)
                results.append(result)
            except Exception as e:
                logger.error(
                    "Check failed for instance %s: %s",
                    instance_id,
                    str(e),
                )
                results.append(
                    HealthCheckResult(
                        check_name="unknown",
                        status=Severity.CRITICAL,
                        details={"error": str(e)},
                    )
                )

    return evaluate_health(instance_id, results)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for fleet health checking.

    Discovers monitored instances, runs health checks in parallel,
    and publishes results to CloudWatch and EventBridge.

    Args:
        event: EventBridge scheduled event payload.
        context: Lambda context object.

    Returns:
        Summary of health check results.
    """
    logger.info("Starting fleet health check cycle")

    try:
        instances = _discover_instances()
        if not instances:
            logger.warning("No monitored instances found")
            return {
                "statusCode": 200,
                "body": {"message": "No monitored instances found"},
            }

        verdicts: list[HealthVerdict] = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(_run_checks_for_instance, inst): inst
                for inst in instances
            }
            for future in as_completed(futures):
                inst = futures[future]
                try:
                    verdict = future.result(timeout=60)
                    verdicts.append(verdict)
                except Exception as e:
                    logger.error(
                        "Health check failed for %s: %s",
                        inst["InstanceId"],
                        str(e),
                    )
                    verdicts.append(
                        HealthVerdict(
                            instance_id=inst["InstanceId"],
                            overall_status=Severity.CRITICAL,
                            severity=Severity.CRITICAL,
                            failed_checks=["health_check_error"],
                        )
                    )

        publish_metrics(verdicts)
        publish_events(verdicts)

        healthy = sum(
            1 for v in verdicts if v.severity == Severity.HEALTHY
        )
        unhealthy = len(verdicts) - healthy
        logger.info(
            "Health check complete: %d healthy, %d unhealthy",
            healthy,
            unhealthy,
        )

        return {
            "statusCode": 200,
            "body": {
                "total_instances": len(verdicts),
                "healthy": healthy,
                "unhealthy": unhealthy,
            },
        }

    except Exception as e:
        logger.error("Fleet health check failed: %s", str(e), exc_info=True)
        return {
            "statusCode": 500,
            "body": {"error": str(e)},
        }
