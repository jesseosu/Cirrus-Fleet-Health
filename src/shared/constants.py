"""Constants and configuration for the Cirrus fleet health platform.

Defines severity levels, failure types, incident statuses, and configurable
thresholds used across all components.
"""

import os
from enum import Enum


class Severity(str, Enum):
    """Health check severity levels."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    CRITICAL = "CRITICAL"


class FailureType(str, Enum):
    """Classified failure types from diagnostic analysis."""

    DISK_FULL = "DISK_FULL"
    MEMORY_EXHAUSTED = "MEMORY_EXHAUSTED"
    CPU_SATURATED = "CPU_SATURATED"
    PROCESS_CRASHED = "PROCESS_CRASHED"
    INSTANCE_UNREACHABLE = "INSTANCE_UNREACHABLE"
    ENDPOINT_DOWN = "ENDPOINT_DOWN"
    UNKNOWN = "UNKNOWN"


class IncidentStatus(str, Enum):
    """Lifecycle status of an incident."""

    DETECTED = "DETECTED"
    DIAGNOSED = "DIAGNOSED"
    REMEDIATED = "REMEDIATED"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


class CheckName(str, Enum):
    """Names of individual health checks."""

    EC2_STATUS = "ec2_status"
    CLOUDWATCH_METRICS = "cloudwatch_metrics"
    PROCESS_HEALTH = "process_health"
    ENDPOINT_HEALTH = "endpoint_health"


# Thresholds — all configurable via environment variables
CPU_WARNING_THRESHOLD = int(os.environ.get("CIRRUS_CPU_WARNING", "80"))
CPU_CRITICAL_THRESHOLD = int(os.environ.get("CIRRUS_CPU_CRITICAL", "95"))
MEM_WARNING_THRESHOLD = int(os.environ.get("CIRRUS_MEM_WARNING", "85"))
MEM_CRITICAL_THRESHOLD = int(os.environ.get("CIRRUS_MEM_CRITICAL", "95"))
DISK_WARNING_THRESHOLD = int(os.environ.get("CIRRUS_DISK_WARNING", "85"))
DISK_CRITICAL_THRESHOLD = int(os.environ.get("CIRRUS_DISK_CRITICAL", "95"))

# Health check configuration
HEALTH_CHECK_TIMEOUT = int(os.environ.get("HEALTH_CHECK_TIMEOUT", "10"))
CRITICAL_PROCESSES = os.environ.get(
    "CRITICAL_PROCESSES", "httpd,nginx,docker"
).split(",")
MONITORED_TAG_KEY = os.environ.get("MONITORED_TAG_KEY", "cirrus:monitored")
MONITORED_TAG_VALUE = os.environ.get("MONITORED_TAG_VALUE", "true")

# Endpoint health check settings
ENDPOINT_HEALTH_PATH = os.environ.get("ENDPOINT_HEALTH_PATH", "/health")
ENDPOINT_HEALTH_PORT = int(os.environ.get("ENDPOINT_HEALTH_PORT", "80"))
ENDPOINT_RETRIES = 3
ENDPOINT_TIMEOUT_SECONDS = 2

# Verification settings
VERIFICATION_WAIT_SECONDS = int(
    os.environ.get("VERIFICATION_WAIT_SECONDS", "60")
)

# CloudWatch metric namespace
METRIC_NAMESPACE = "Cirrus/Fleet"

# DynamoDB table name
INCIDENTS_TABLE_NAME = os.environ.get(
    "INCIDENTS_TABLE_NAME", "cirrus-incidents"
)

# SNS topic ARN for escalation
ESCALATION_TOPIC_ARN = os.environ.get("ESCALATION_TOPIC_ARN", "")

# Incident TTL (90 days in seconds)
INCIDENT_TTL_DAYS = 90

# EventBridge detail types
EVENT_SOURCE = "cirrus.health"
EVENT_DETAIL_TYPE_PREFIX = "cirrus.health"
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "default")
