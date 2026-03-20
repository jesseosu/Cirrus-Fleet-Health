"""CloudWatch Logs collector for diagnostic data.

Pulls recent error-level log entries from an instance's CloudWatch log
group to aid in failure diagnosis.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from src.shared.aws_clients import get_client
from src.shared.logger import get_logger

logger: logging.Logger = get_logger("diagnostics")

MAX_LOG_ENTRIES = 50
LOG_LOOKBACK_MINUTES = 15


def collect_logs(instance_id: str) -> list[str]:
    """Collect recent error log entries for an instance.

    Queries CloudWatch Logs for the instance's log group, filtering for
    ERROR, WARN, and FATAL level entries from the last 15 minutes.

    Args:
        instance_id: The EC2 instance ID to collect logs for.

    Returns:
        List of up to 50 recent error log lines.
    """
    logs_client = get_client("logs")
    log_group_name = f"/ec2/{instance_id}"
    now = datetime.now(timezone.utc)
    start_time = int(
        (now - timedelta(minutes=LOG_LOOKBACK_MINUTES)).timestamp() * 1000
    )
    end_time = int(now.timestamp() * 1000)

    try:
        response: dict[str, Any] = logs_client.filter_log_events(
            logGroupName=log_group_name,
            startTime=start_time,
            endTime=end_time,
            filterPattern="?ERROR ?WARN ?FATAL ?error ?warn ?fatal",
            limit=MAX_LOG_ENTRIES,
        )
        log_entries: list[str] = []
        for event in response.get("events", []):
            message: str = event.get("message", "").strip()
            if message:
                log_entries.append(message)
        logger.info(
            "Collected %d log entries for instance %s",
            len(log_entries),
            instance_id,
        )
        return log_entries

    except logs_client.exceptions.ResourceNotFoundException:
        logger.warning(
            "Log group %s not found for instance %s",
            log_group_name,
            instance_id,
        )
        return []
    except Exception as e:
        logger.error(
            "Failed to collect logs for %s: %s", instance_id, str(e)
        )
        return [f"Error collecting logs: {str(e)}"]
