"""Lambda handler for the diagnostics collector.

Invoked by Step Functions when an unhealthy event is detected. Collects
diagnostic data from multiple sources and classifies the failure type.
"""

import logging
from typing import Any

from src.shared.logger import get_logger
from src.shared.models import DiagnosticReport

from src.diagnostics.analyzer import classify_failure
from src.diagnostics.collectors.log_collector import collect_logs
from src.diagnostics.collectors.metric_snapshot import (
    collect_metric_snapshots,
)
from src.diagnostics.collectors.system_info import collect_system_info

logger: logging.Logger = get_logger("diagnostics")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for diagnostic data collection and analysis.

    Receives a health verdict event, runs all diagnostic collectors,
    and classifies the failure type.

    Args:
        event: Event containing instance_id and health verdict data.
        context: Lambda context object.

    Returns:
        Serialized DiagnosticReport with failure classification.
    """
    instance_id: str = event.get("instance_id", "")
    if not instance_id:
        logger.error("No instance_id provided in event")
        return {
            "statusCode": 400,
            "body": {"error": "Missing instance_id"},
        }

    logger.info("Starting diagnostics for instance %s", instance_id)

    try:
        log_entries = collect_logs(instance_id)
        metric_snapshots = collect_metric_snapshots(instance_id)
        system_info = collect_system_info(instance_id)

        report = DiagnosticReport(
            instance_id=instance_id,
            log_entries=log_entries,
            metric_snapshots=metric_snapshots,
            system_info=system_info,
        )

        classification = classify_failure(report)
        report.failure_classification = classification

        logger.info(
            "Diagnostics complete for %s: failure_type=%s, confidence=%.2f",
            instance_id,
            classification.failure_type.value,
            classification.confidence,
        )

        return {
            "statusCode": 200,
            "body": report.model_dump(mode="json"),
        }

    except Exception as e:
        logger.error(
            "Diagnostics failed for %s: %s",
            instance_id,
            str(e),
            exc_info=True,
        )
        return {
            "statusCode": 500,
            "body": {
                "error": str(e),
                "instance_id": instance_id,
            },
        }
