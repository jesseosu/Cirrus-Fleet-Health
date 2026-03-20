"""Remediation action selector.

Maps failure classifications to appropriate remediation actions based
on the diagnosed failure type.
"""

from src.shared.constants import FailureType


# Maps FailureType → remediation action name
ACTION_MAP: dict[FailureType, str] = {
    FailureType.DISK_FULL: "clear_disk",
    FailureType.MEMORY_EXHAUSTED: "reboot_instance",
    FailureType.CPU_SATURATED: "reboot_instance",
    FailureType.PROCESS_CRASHED: "restart_service",
    FailureType.INSTANCE_UNREACHABLE: "replace_instance",
    FailureType.ENDPOINT_DOWN: "restart_service",
}


def select_action(failure_type: FailureType) -> str | None:
    """Select the appropriate remediation action for a failure type.

    Args:
        failure_type: The classified failure type.

    Returns:
        Action name string, or None if the failure type should be
        escalated immediately (UNKNOWN).
    """
    if failure_type == FailureType.UNKNOWN:
        return None
    return ACTION_MAP.get(failure_type)
