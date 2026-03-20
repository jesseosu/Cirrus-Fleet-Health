"""Lambda handler for escalation alerts.

Formats detailed alert messages and publishes them to SNS for
on-call engineer notification when auto-remediation fails.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from src.shared.aws_clients import get_client
import os
from src.shared.logger import get_logger

logger: logging.Logger = get_logger("escalation")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for formatting and publishing escalation alerts.

    Creates a detailed, human-readable alert message and publishes
    it to the configured SNS topic.

    Args:
        event: Event containing incident details.
        context: Lambda context object.

    Returns:
        Result of the SNS publish operation.
    """
    body = event.get("body", event)
    instance_id: str = body.get("instance_id", "unknown")
    failure_type: str = body.get("failure_type", "UNKNOWN")
    remediation_action: str = body.get("remediation_action", "none")
    remediation_result = body.get("remediation_result", {})
    diagnostic_summary = body.get("diagnostic_summary", {})
    severity: str = body.get("severity", "UNKNOWN")

    timestamp = datetime.now(timezone.utc).isoformat()

    subject = (
        f"[CIRRUS ALERT] {severity} - Instance {instance_id} "
        f"requires attention"
    )

    message = _format_alert_message(
        instance_id=instance_id,
        failure_type=failure_type,
        severity=severity,
        remediation_action=remediation_action,
        remediation_result=remediation_result,
        diagnostic_summary=diagnostic_summary,
        timestamp=timestamp,
    )

    json_message = json.dumps(
        {
            "instance_id": instance_id,
            "failure_type": failure_type,
            "severity": severity,
            "remediation_action": remediation_action,
            "remediation_success": remediation_result.get("success", False),
            "timestamp": timestamp,
            "diagnostic_summary": diagnostic_summary,
        },
        default=str,
    )

    try:
        sns = get_client("sns")
        topic_arn = os.environ.get("ESCALATION_TOPIC_ARN", "")
        if not topic_arn:
            logger.error("No ESCALATION_TOPIC_ARN configured")
            return {
                "statusCode": 500,
                "body": {"error": "No SNS topic ARN configured"},
            }

        response: dict[str, Any] = sns.publish(
            TopicArn=topic_arn,
            Subject=subject[:100],
            Message=message,
            MessageAttributes={
                "severity": {
                    "DataType": "String",
                    "StringValue": severity,
                },
                "failure_type": {
                    "DataType": "String",
                    "StringValue": failure_type,
                },
                "instance_id": {
                    "DataType": "String",
                    "StringValue": instance_id,
                },
            },
        )
        message_id: str = response.get("MessageId", "")
        logger.info(
            "Escalation alert published: MessageId=%s, instance=%s",
            message_id,
            instance_id,
        )
        return {
            "statusCode": 200,
            "body": {
                "message_id": message_id,
                "instance_id": instance_id,
                "alert_sent": True,
            },
        }

    except Exception as e:
        logger.error(
            "Failed to publish escalation alert for %s: %s",
            instance_id,
            str(e),
            exc_info=True,
        )
        return {
            "statusCode": 500,
            "body": {
                "error": str(e),
                "instance_id": instance_id,
                "alert_sent": False,
            },
        }


def _format_alert_message(
    instance_id: str,
    failure_type: str,
    severity: str,
    remediation_action: str,
    remediation_result: dict[str, Any],
    diagnostic_summary: dict[str, Any],
    timestamp: str,
) -> str:
    """Format a detailed, human-readable alert message.

    Args:
        instance_id: The affected EC2 instance ID.
        failure_type: The classified failure type.
        severity: Alert severity level.
        remediation_action: Action attempted (or 'none').
        remediation_result: Result of remediation attempt.
        diagnostic_summary: Summary of diagnostic findings.
        timestamp: ISO format timestamp.

    Returns:
        Formatted alert message string.
    """
    remediation_success = remediation_result.get("success", False)
    remediation_details = remediation_result.get("details", {})
    remediation_error = remediation_details.get("error", "N/A")

    lines = [
        "=" * 60,
        "CIRRUS FLEET HEALTH ALERT",
        "=" * 60,
        "",
        f"Severity:      {severity}",
        f"Instance ID:   {instance_id}",
        f"Failure Type:  {failure_type}",
        f"Timestamp:     {timestamp}",
        "",
        "-" * 40,
        "REMEDIATION ATTEMPTED",
        "-" * 40,
        f"Action:        {remediation_action}",
        f"Success:       {remediation_success}",
        f"Failure Reason: {remediation_error}",
        "",
        "-" * 40,
        "DIAGNOSTIC SUMMARY",
        "-" * 40,
    ]

    if diagnostic_summary:
        for key, value in diagnostic_summary.items():
            lines.append(f"  {key}: {value}")
    else:
        lines.append("  No diagnostic data available")

    lines.extend([
        "",
        "-" * 40,
        "NEXT STEPS",
        "-" * 40,
        "1. Check the instance in the AWS Console",
        f"2. Review CloudWatch logs: /ec2/{instance_id}",
        "3. Connect via SSM Session Manager if needed",
        "4. Refer to the Cirrus runbook for manual remediation",
        "",
        "=" * 60,
    ])

    return "\n".join(lines)
