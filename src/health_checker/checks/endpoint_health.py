"""HTTP endpoint health check.

Performs HTTP GET requests against a configurable health endpoint on each
instance to verify application-level health.
"""

import logging
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from src.shared.constants import (
    ENDPOINT_HEALTH_PATH,
    ENDPOINT_HEALTH_PORT,
    ENDPOINT_RETRIES,
    ENDPOINT_TIMEOUT_SECONDS,
    CheckName,
    Severity,
)
from src.shared.logger import get_logger
from src.shared.models import HealthCheckResult

logger: logging.Logger = get_logger("health-checker")


def check_endpoint_health(
    instance_id: str, private_ip: str
) -> HealthCheckResult:
    """Check HTTP endpoint health on an instance.

    Performs an HTTP GET to the configured health endpoint with retries.
    Evaluates response status code and response time.

    Args:
        instance_id: The EC2 instance ID (for reporting).
        private_ip: The private IP address of the instance.

    Returns:
        HealthCheckResult with severity based on endpoint responsiveness.
    """
    url = f"http://{private_ip}:{ENDPOINT_HEALTH_PORT}{ENDPOINT_HEALTH_PATH}"
    last_error: str = ""
    response_time_ms: float = 0.0

    for attempt in range(ENDPOINT_RETRIES):
        try:
            import time

            start = time.monotonic()
            req = Request(url, method="GET")
            with urlopen(req, timeout=ENDPOINT_TIMEOUT_SECONDS) as resp:
                elapsed = (time.monotonic() - start) * 1000
                response_time_ms = elapsed
                status_code: int = resp.status

                details: dict[str, Any] = {
                    "instance_id": instance_id,
                    "url": url,
                    "status_code": status_code,
                    "response_time_ms": round(response_time_ms, 2),
                    "attempt": attempt + 1,
                }

                if 200 <= status_code < 300:
                    return HealthCheckResult(
                        check_name=CheckName.ENDPOINT_HEALTH.value,
                        status=Severity.HEALTHY,
                        details=details,
                    )
                elif 500 <= status_code < 600:
                    return HealthCheckResult(
                        check_name=CheckName.ENDPOINT_HEALTH.value,
                        status=Severity.UNHEALTHY,
                        details=details,
                    )
                else:
                    return HealthCheckResult(
                        check_name=CheckName.ENDPOINT_HEALTH.value,
                        status=Severity.DEGRADED,
                        details=details,
                    )

        except URLError as e:
            last_error = str(e)
            logger.warning(
                "Endpoint check attempt %d/%d failed for %s: %s",
                attempt + 1,
                ENDPOINT_RETRIES,
                instance_id,
                last_error,
            )
        except Exception as e:
            last_error = str(e)
            logger.warning(
                "Endpoint check attempt %d/%d failed for %s: %s",
                attempt + 1,
                ENDPOINT_RETRIES,
                instance_id,
                last_error,
            )

    return HealthCheckResult(
        check_name=CheckName.ENDPOINT_HEALTH.value,
        status=Severity.UNHEALTHY,
        details={
            "instance_id": instance_id,
            "url": url,
            "error": last_error,
            "attempts": ENDPOINT_RETRIES,
        },
    )
