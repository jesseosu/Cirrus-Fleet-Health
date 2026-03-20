"""Health verdict evaluator.

Aggregates individual health check results into a single overall health
verdict for an EC2 instance, applying severity escalation rules.
"""

from src.shared.constants import Severity
from src.shared.models import HealthCheckResult, HealthVerdict


def evaluate_health(
    instance_id: str, results: list[HealthCheckResult]
) -> HealthVerdict:
    """Aggregate health check results into a single verdict.

    Severity escalation rules:
    - Any check CRITICAL → overall CRITICAL
    - Any check UNHEALTHY → overall UNHEALTHY
    - Any check DEGRADED → overall DEGRADED
    - All checks HEALTHY → overall HEALTHY

    Args:
        instance_id: The EC2 instance ID.
        results: List of individual health check results.

    Returns:
        HealthVerdict with the aggregated severity and failing check details.
    """
    if not results:
        return HealthVerdict(
            instance_id=instance_id,
            overall_status=Severity.CRITICAL,
            severity=Severity.CRITICAL,
            failed_checks=["no_checks_ran"],
            all_results=[],
        )

    failed_checks: list[str] = []
    overall = Severity.HEALTHY

    severity_priority = {
        Severity.HEALTHY: 0,
        Severity.DEGRADED: 1,
        Severity.UNHEALTHY: 2,
        Severity.CRITICAL: 3,
    }

    for result in results:
        if result.status != Severity.HEALTHY:
            failed_checks.append(result.check_name)
        if severity_priority[result.status] > severity_priority[overall]:
            overall = result.status

    return HealthVerdict(
        instance_id=instance_id,
        overall_status=overall,
        severity=overall,
        failed_checks=failed_checks,
        all_results=results,
    )
