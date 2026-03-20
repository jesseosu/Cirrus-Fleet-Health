"""Health verdict publisher.

Publishes health check results to CloudWatch custom metrics and
EventBridge for downstream processing by the remediation pipeline.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from src.shared.aws_clients import get_client
from src.shared.constants import (
    EVENT_BUS_NAME,
    EVENT_DETAIL_TYPE_PREFIX,
    EVENT_SOURCE,
    METRIC_NAMESPACE,
    Severity,
)
from src.shared.logger import get_logger
from src.shared.models import HealthVerdict

logger: logging.Logger = get_logger("health-checker")


def publish_metrics(verdicts: list[HealthVerdict]) -> None:
    """Publish fleet health metrics to CloudWatch.

    Publishes per-instance health status (1=healthy, 0=unhealthy) and
    aggregate fleet health counts.

    Args:
        verdicts: List of health verdicts for all monitored instances.
    """
    cw = get_client("cloudwatch")
    metric_data: list[dict[str, Any]] = []
    healthy_count = 0
    unhealthy_count = 0

    for verdict in verdicts:
        is_healthy = 1.0 if verdict.severity == Severity.HEALTHY else 0.0
        if is_healthy:
            healthy_count += 1
        else:
            unhealthy_count += 1

        metric_data.append({
            "MetricName": "InstanceHealth",
            "Dimensions": [
                {"Name": "InstanceId", "Value": verdict.instance_id},
            ],
            "Timestamp": datetime.now(timezone.utc),
            "Value": is_healthy,
            "Unit": "None",
        })

    metric_data.extend([
        {
            "MetricName": "HealthyCount",
            "Timestamp": datetime.now(timezone.utc),
            "Value": float(healthy_count),
            "Unit": "Count",
        },
        {
            "MetricName": "UnhealthyCount",
            "Timestamp": datetime.now(timezone.utc),
            "Value": float(unhealthy_count),
            "Unit": "Count",
        },
    ])

    # CloudWatch PutMetricData allows max 1000 metrics per call
    batch_size = 25
    for i in range(0, len(metric_data), batch_size):
        batch = metric_data[i:i + batch_size]
        try:
            cw.put_metric_data(
                Namespace=METRIC_NAMESPACE,
                MetricData=batch,
            )
        except Exception as e:
            logger.error("Failed to publish metrics batch: %s", str(e))


def publish_events(verdicts: list[HealthVerdict]) -> None:
    """Publish non-healthy verdicts to EventBridge for remediation.

    Only publishes events for instances that are not HEALTHY, using
    the detail type format: cirrus.health.{severity}.

    Args:
        verdicts: List of health verdicts for all monitored instances.
    """
    events_client = get_client("events")
    entries: list[dict[str, Any]] = []

    for verdict in verdicts:
        if verdict.severity == Severity.HEALTHY:
            continue

        detail_type = f"{EVENT_DETAIL_TYPE_PREFIX}.{verdict.severity.value}"
        detail = {
            "instance_id": verdict.instance_id,
            "severity": verdict.severity.value,
            "overall_status": verdict.overall_status.value,
            "failed_checks": verdict.failed_checks,
            "results": [
                {
                    "check_name": r.check_name,
                    "status": r.status.value,
                    "details": r.details,
                    "timestamp": r.timestamp.isoformat(),
                }
                for r in verdict.all_results
            ],
            "timestamp": verdict.timestamp.isoformat(),
        }

        entries.append({
            "Source": EVENT_SOURCE,
            "DetailType": detail_type,
            "Detail": json.dumps(detail, default=str),
            "EventBusName": EVENT_BUS_NAME,
        })

    # EventBridge allows max 10 entries per call
    batch_size = 10
    for i in range(0, len(entries), batch_size):
        batch = entries[i:i + batch_size]
        try:
            response: dict[str, Any] = events_client.put_events(
                Entries=batch,
            )
            failed: int = response.get("FailedEntryCount", 0)
            if failed > 0:
                logger.error(
                    "%d EventBridge entries failed to publish", failed
                )
        except Exception as e:
            logger.error("Failed to publish EventBridge events: %s", str(e))
