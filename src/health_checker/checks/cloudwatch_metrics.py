"""CloudWatch metric-based health checks.

Evaluates CPU utilization, memory usage, and disk usage metrics from
CloudWatch to determine instance health based on configurable thresholds.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from src.shared.aws_clients import get_client
from src.shared.constants import (
    CPU_CRITICAL_THRESHOLD,
    CPU_WARNING_THRESHOLD,
    DISK_CRITICAL_THRESHOLD,
    DISK_WARNING_THRESHOLD,
    MEM_CRITICAL_THRESHOLD,
    MEM_WARNING_THRESHOLD,
    CheckName,
    Severity,
)
from src.shared.logger import get_logger
from src.shared.models import HealthCheckResult

logger: logging.Logger = get_logger("health-checker")

METRIC_QUERIES: list[dict[str, Any]] = [
    {
        "Id": "cpu",
        "MetricStat": {
            "Metric": {
                "Namespace": "AWS/EC2",
                "MetricName": "CPUUtilization",
                "Dimensions": [],
            },
            "Period": 300,
            "Stat": "Average",
        },
        "ReturnData": True,
    },
    {
        "Id": "memory",
        "MetricStat": {
            "Metric": {
                "Namespace": "CWAgent",
                "MetricName": "mem_used_percent",
                "Dimensions": [],
            },
            "Period": 300,
            "Stat": "Average",
        },
        "ReturnData": True,
    },
    {
        "Id": "disk",
        "MetricStat": {
            "Metric": {
                "Namespace": "CWAgent",
                "MetricName": "disk_used_percent",
                "Dimensions": [],
            },
            "Period": 300,
            "Stat": "Average",
        },
        "ReturnData": True,
    },
]


def _build_queries(instance_id: str) -> list[dict[str, Any]]:
    """Build metric data queries with instance-specific dimensions."""
    queries: list[dict[str, Any]] = []
    for query in METRIC_QUERIES:
        q = {
            "Id": query["Id"],
            "MetricStat": {
                "Metric": {
                    "Namespace": query["MetricStat"]["Metric"]["Namespace"],
                    "MetricName": query["MetricStat"]["Metric"]["MetricName"],
                    "Dimensions": [
                        {"Name": "InstanceId", "Value": instance_id}
                    ],
                },
                "Period": query["MetricStat"]["Period"],
                "Stat": query["MetricStat"]["Stat"],
            },
            "ReturnData": True,
        }
        queries.append(q)
    return queries


def _evaluate_metric(
    metric_id: str, value: float
) -> Severity:
    """Evaluate a single metric value against thresholds."""
    thresholds: dict[str, tuple[int, int]] = {
        "cpu": (CPU_WARNING_THRESHOLD, CPU_CRITICAL_THRESHOLD),
        "memory": (MEM_WARNING_THRESHOLD, MEM_CRITICAL_THRESHOLD),
        "disk": (DISK_WARNING_THRESHOLD, DISK_CRITICAL_THRESHOLD),
    }
    warning, critical = thresholds.get(metric_id, (80, 95))
    if value >= critical:
        return Severity.UNHEALTHY
    elif value >= warning:
        return Severity.DEGRADED
    return Severity.HEALTHY


def check_cloudwatch_metrics(instance_id: str) -> HealthCheckResult:
    """Check CloudWatch metrics for CPU, memory, and disk usage.

    Queries the last 10 minutes of metric data and evaluates the most
    recent values against configured thresholds.

    Args:
        instance_id: The EC2 instance ID to check.

    Returns:
        HealthCheckResult with the worst severity across all metrics.
    """
    cw = get_client("cloudwatch")
    now = datetime.now(timezone.utc)
    try:
        response: dict[str, Any] = cw.get_metric_data(
            MetricDataQueries=_build_queries(instance_id),
            StartTime=now - timedelta(minutes=10),
            EndTime=now,
        )
        metric_results: dict[str, Any] = {}
        worst_severity = Severity.HEALTHY
        for result in response.get("MetricDataResults", []):
            metric_id: str = result["Id"]
            values: list[float] = result.get("Values", [])
            if values:
                latest_value = values[0]
                severity = _evaluate_metric(metric_id, latest_value)
                metric_results[metric_id] = {
                    "value": latest_value,
                    "status": severity.value,
                }
                if severity == Severity.UNHEALTHY:
                    worst_severity = Severity.UNHEALTHY
                elif (
                    severity == Severity.DEGRADED
                    and worst_severity == Severity.HEALTHY
                ):
                    worst_severity = Severity.DEGRADED
            else:
                metric_results[metric_id] = {
                    "value": None,
                    "status": "NO_DATA",
                }

        return HealthCheckResult(
            check_name=CheckName.CLOUDWATCH_METRICS.value,
            status=worst_severity,
            details={
                "instance_id": instance_id,
                "metrics": metric_results,
            },
        )

    except Exception as e:
        logger.error(
            "Failed to check CloudWatch metrics for %s: %s",
            instance_id,
            str(e),
        )
        return HealthCheckResult(
            check_name=CheckName.CLOUDWATCH_METRICS.value,
            status=Severity.DEGRADED,
            details={"error": str(e), "instance_id": instance_id},
        )
