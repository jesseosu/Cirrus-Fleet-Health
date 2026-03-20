"""Lambda handler for the remediator.

Receives a diagnostic report, selects the appropriate remediation action,
and executes it against the affected instance.
"""

import logging
from typing import Any

from src.shared.constants import FailureType
from src.shared.logger import get_logger
from src.shared.models import DiagnosticReport, RemediationResult

from src.remediator.action_selector import select_action
from src.remediator.actions.clear_disk import clear_disk
from src.remediator.actions.reboot_instance import reboot_instance
from src.remediator.actions.replace_instance import replace_instance
from src.remediator.actions.restart_service import restart_service

logger: logging.Logger = get_logger("remediator")

ACTION_HANDLERS: dict[str, Any] = {
    "clear_disk": clear_disk,
    "reboot_instance": reboot_instance,
    "replace_instance": replace_instance,
    "restart_service": restart_service,
}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for executing remediation actions.

    Args:
        event: Event containing the diagnostic report body.
        context: Lambda context object.

    Returns:
        Serialized RemediationResult.
    """
    body = event.get("body", event)
    instance_id: str = body.get("instance_id", "")
    if not instance_id:
        logger.error("No instance_id in event")
        return {
            "statusCode": 400,
            "body": {"error": "Missing instance_id"},
        }

    failure_classification = body.get("failure_classification", {})
    failure_type_str: str = failure_classification.get(
        "failure_type", FailureType.UNKNOWN.value
    )

    try:
        failure_type = FailureType(failure_type_str)
    except ValueError:
        failure_type = FailureType.UNKNOWN

    action_name = select_action(failure_type)
    if action_name is None:
        logger.info(
            "No auto-remediation for %s on %s — escalating",
            failure_type.value,
            instance_id,
        )
        return {
            "statusCode": 200,
            "body": {
                "action_taken": "none",
                "success": False,
                "escalate": True,
                "reason": f"No remediation for {failure_type.value}",
                "instance_id": instance_id,
            },
        }

    action_handler = ACTION_HANDLERS.get(action_name)
    if not action_handler:
        logger.error("Unknown action handler: %s", action_name)
        return {
            "statusCode": 500,
            "body": {"error": f"Unknown action: {action_name}"},
        }

    logger.info(
        "Executing %s for %s (failure: %s)",
        action_name,
        instance_id,
        failure_type.value,
    )

    try:
        if action_name == "restart_service":
            service_name = body.get("service_name", "httpd")
            result: RemediationResult = action_handler(
                instance_id, service_name
            )
        else:
            result = action_handler(instance_id)

        logger.info(
            "Remediation %s for %s: success=%s",
            action_name,
            instance_id,
            result.success,
        )

        return {
            "statusCode": 200,
            "body": result.model_dump(mode="json"),
        }

    except Exception as e:
        logger.error(
            "Remediation %s failed for %s: %s",
            action_name,
            instance_id,
            str(e),
            exc_info=True,
        )
        return {
            "statusCode": 500,
            "body": {
                "action_taken": action_name,
                "success": False,
                "error": str(e),
                "instance_id": instance_id,
            },
        }
