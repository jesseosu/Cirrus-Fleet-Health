"""Lambda handler for incident logging to DynamoDB.

Records and updates incident lifecycle events in the cirrus-incidents
DynamoDB table, supporting the full detect → diagnose → remediate →
verify → resolve/escalate pipeline.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from src.shared.aws_clients import get_resource
from src.shared.constants import (
    INCIDENT_TTL_DAYS,
    INCIDENTS_TABLE_NAME,
    IncidentStatus,
)
from src.shared.logger import get_logger
from src.shared.models import Incident

logger: logging.Logger = get_logger("incident-logger")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for recording incident events to DynamoDB.

    Handles both creating new incidents (DETECTED) and updating existing
    incidents through the lifecycle (DIAGNOSED, REMEDIATED, etc.).

    Args:
        event: Event containing incident data and action type.
        context: Lambda context object.

    Returns:
        Result of the DynamoDB operation.
    """
    body = event.get("body", event)
    action: str = body.get("action", "create")
    instance_id: str = body.get("instance_id", "")

    if not instance_id:
        logger.error("No instance_id in incident event")
        return {
            "statusCode": 400,
            "body": {"error": "Missing instance_id"},
        }

    try:
        dynamodb = get_resource("dynamodb")
        table = dynamodb.Table(INCIDENTS_TABLE_NAME)

        if action == "create":
            return _create_incident(table, body)
        elif action == "update":
            return _update_incident(table, body)
        else:
            logger.error("Unknown action: %s", action)
            return {
                "statusCode": 400,
                "body": {"error": f"Unknown action: {action}"},
            }

    except Exception as e:
        logger.error(
            "Incident logging failed for %s: %s",
            instance_id,
            str(e),
            exc_info=True,
        )
        return {
            "statusCode": 500,
            "body": {"error": str(e), "instance_id": instance_id},
        }


def _create_incident(
    table: Any, body: dict[str, Any]
) -> dict[str, Any]:
    """Create a new incident record in DynamoDB.

    Args:
        table: DynamoDB table resource.
        body: Event body with incident data.

    Returns:
        Result with the created incident ID.
    """
    from src.shared.constants import Severity

    severity_str: str = body.get("severity", "UNHEALTHY")
    try:
        severity = Severity(severity_str)
    except ValueError:
        severity = Severity.UNHEALTHY

    ttl_timestamp = int(
        (
            datetime.now(timezone.utc)
            + timedelta(days=INCIDENT_TTL_DAYS)
        ).timestamp()
    )

    incident = Incident(
        instance_id=body["instance_id"],
        severity=severity,
        status=IncidentStatus.DETECTED,
        checks_failed=body.get("checks_failed", []),
        ttl=ttl_timestamp,
    )

    item = incident.to_dynamodb_item()
    table.put_item(Item=item)

    logger.info(
        "Created incident %s for instance %s",
        incident.incident_id,
        incident.instance_id,
    )

    return {
        "statusCode": 200,
        "body": {
            "incident_id": incident.incident_id,
            "instance_id": incident.instance_id,
            "status": incident.status.value,
            "detected_at": incident.detected_at.isoformat(),
        },
    }


def _update_incident(
    table: Any, body: dict[str, Any]
) -> dict[str, Any]:
    """Update an existing incident record in DynamoDB.

    Args:
        table: DynamoDB table resource.
        body: Event body with update data including PK, SK, and new status.

    Returns:
        Result of the update operation.
    """
    pk: str = body.get("pk", f"INSTANCE#{body.get('instance_id', '')}")
    sk: str = body.get("sk", "")
    new_status: str = body.get("status", "")
    now = datetime.now(timezone.utc).isoformat()

    if not sk:
        logger.error("No sort key provided for incident update")
        return {
            "statusCode": 400,
            "body": {"error": "Missing sort key (sk)"},
        }

    update_expr_parts: list[str] = ["#st = :status"]
    expr_names: dict[str, str] = {"#st": "status"}
    expr_values: dict[str, Any] = {":status": new_status}

    status_timestamp_map: dict[str, str] = {
        IncidentStatus.DIAGNOSED.value: "diagnosed_at",
        IncidentStatus.REMEDIATED.value: "remediated_at",
        IncidentStatus.RESOLVED.value: "resolved_at",
        IncidentStatus.ESCALATED.value: "escalated_at",
    }

    timestamp_field = status_timestamp_map.get(new_status)
    if timestamp_field:
        update_expr_parts.append(f"{timestamp_field} = :ts")
        expr_values[":ts"] = now

    if "failure_type" in body:
        update_expr_parts.append("failure_type = :ft")
        expr_values[":ft"] = body["failure_type"]

    if "remediation_action" in body:
        update_expr_parts.append("remediation_action = :ra")
        expr_values[":ra"] = body["remediation_action"]

    if "remediation_result" in body:
        update_expr_parts.append("remediation_result = :rr")
        expr_values[":rr"] = body["remediation_result"]

    if "diagnostic_summary" in body:
        update_expr_parts.append("diagnostic_summary = :ds")
        expr_values[":ds"] = body["diagnostic_summary"]

    update_expr = "SET " + ", ".join(update_expr_parts)

    table.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
    )

    logger.info(
        "Updated incident %s to status %s", sk, new_status
    )

    return {
        "statusCode": 200,
        "body": {
            "pk": pk,
            "sk": sk,
            "status": new_status,
            "updated_at": now,
        },
    }
