"""CloudWatch metric snapshot collector.

Captures the last 15 minutes of key performance metrics at 1-minute
granularity for diagnostic analysis.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from src.shared.aws_clients import get_client
from src.shared.logger import get_logger
from src.shared.models import MetricSnapshot

logger: logging.Logger = get_logger("diagnostics")

SNAPSHOT_METRICS: list[dict[str, str]] = [
    {"namespace": "AWS/EC2", "name": "CPUUtilization", "unit": "Percent"},
    {"namespace": "CWAgent", "name": "mem_used_percent", "unit": "Percent"},
    {"namespace": "CWAgent", "name": "disk_used_percent", "unit": "Percent"},
    {"namespace": "AWS/EC2", "name": "NetworkIn", "unit": "Bytes"},
    {"namespace": "AWS/EC2", "name": "NetworkOut", "unit": "Bytes"},
]


def collect_metric_snapshots(
    instance_id: str,
) -> list[MetricSnapshot]:
    """Collect last 15 minutes of key metrics for an instance.

    Args:
        instance_id: The EC2 instance ID.

    Returns:
        List of MetricSnapshot objects with timeseries data.
    """
    cw = get_client("cloudwatch")
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(minutes=15)
    snapshots: list[MetricSnapshot] = []

    for metric_def in SNAPSHOT_METRICS:
        try:
            response: dict[str, Any] = cw.get_metric_statistics(
                Namespace=metric_def["namespace"],
                MetricName=metric_def["name"],
                Dimensions=[
                    {"Name": "InstanceId", "Value": instance_id},
                ],
                StartTime=start_time,
                EndTime=now,
                Period=60,
                Statistics=["Average", "Maximum"],
            )
            datapoints: list[dict[str, Any]] = [
                {
                    "timestamp": dp["Timestamp"].isoformat()
                    if isinstance(dp["Timestamp"], datetime)
                    else str(dp["Timestamp"]),
                    "average": dp.get("Average", 0.0),
                    "maximum": dp.get("Maximum", 0.0),
                }
                for dp in response.get("Datapoints", [])
            ]
            datapoints.sort(key=lambda x: x["timestamp"])
            snapshots.append(
                MetricSnapshot(
                    metric_name=metric_def["name"],
                    datapoints=datapoints,
                    unit=metric_def["unit"],
                )
            )
        except Exception as e:
            logger.error(
                "Failed to collect metric %s for %s: %s",
                metric_def["name"],
                instance_id,
                str(e),
            )
            snapshots.append(
                MetricSnapshot(
                    metric_name=metric_def["name"],
                    datapoints=[],
                    unit=metric_def["unit"],
                )
            )

    return snapshots
