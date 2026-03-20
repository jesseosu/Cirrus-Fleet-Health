"""Pydantic v2 models for Cirrus fleet health platform.

Defines the core data structures used across health checking, diagnostics,
remediation, and incident tracking components.
"""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from src.shared.constants import (
    FailureType,
    IncidentStatus,
    Severity,
)


class HealthCheckResult(BaseModel):
    """Result of a single health check against an instance."""

    check_name: str
    status: Severity
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class HealthVerdict(BaseModel):
    """Aggregated health verdict for an EC2 instance."""

    instance_id: str
    overall_status: Severity
    severity: Severity
    failed_checks: list[str] = Field(default_factory=list)
    all_results: list[HealthCheckResult] = Field(default_factory=list)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class MetricSnapshot(BaseModel):
    """Point-in-time metric data for an instance."""

    metric_name: str
    datapoints: list[dict[str, Any]] = Field(default_factory=list)
    unit: str = ""


class SystemInfo(BaseModel):
    """System state information collected via SSM."""

    disk_usage: str = ""
    memory_info: str = ""
    top_output: str = ""
    top_processes: str = ""
    dmesg_tail: str = ""
    failed_services: str = ""
    network_info: str = ""


class FailureClassification(BaseModel):
    """Classified failure type from diagnostic analysis."""

    failure_type: FailureType
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)


class DiagnosticReport(BaseModel):
    """Complete diagnostic report for an unhealthy instance."""

    instance_id: str
    log_entries: list[str] = Field(default_factory=list)
    metric_snapshots: list[MetricSnapshot] = Field(default_factory=list)
    system_info: Optional[SystemInfo] = None
    failure_classification: Optional[FailureClassification] = None
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class RemediationResult(BaseModel):
    """Result of a remediation action."""

    action_taken: str
    success: bool
    details: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int = 0


class Incident(BaseModel):
    """Full incident record for DynamoDB storage."""

    incident_id: str = Field(default_factory=lambda: str(uuid4()))
    instance_id: str
    severity: Severity
    status: IncidentStatus = IncidentStatus.DETECTED
    failure_type: Optional[FailureType] = None
    checks_failed: list[str] = Field(default_factory=list)
    remediation_action: Optional[str] = None
    remediation_result: Optional[RemediationResult] = None
    diagnostic_summary: dict[str, Any] = Field(default_factory=dict)
    detected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    diagnosed_at: Optional[datetime] = None
    remediated_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    escalated_at: Optional[datetime] = None
    ttl: Optional[int] = None

    def to_dynamodb_item(self) -> dict[str, Any]:
        """Convert the incident to a DynamoDB-compatible item dict."""
        item: dict[str, Any] = {
            "PK": f"INSTANCE#{self.instance_id}",
            "SK": f"INCIDENT#{self.detected_at.isoformat()}",
            "incident_id": self.incident_id,
            "instance_id": self.instance_id,
            "severity": self.severity.value,
            "status": self.status.value,
            "checks_failed": self.checks_failed,
            "diagnostic_summary": self.diagnostic_summary,
            "detected_at": self.detected_at.isoformat(),
        }
        if self.failure_type:
            item["failure_type"] = self.failure_type.value
        if self.remediation_action:
            item["remediation_action"] = self.remediation_action
        if self.remediation_result:
            item["remediation_result"] = self.remediation_result.model_dump()
        for field in [
            "diagnosed_at", "remediated_at", "verified_at",
            "resolved_at", "escalated_at",
        ]:
            value = getattr(self, field)
            if value:
                item[field] = value.isoformat()
        if self.ttl:
            item["ttl"] = self.ttl
        return item
