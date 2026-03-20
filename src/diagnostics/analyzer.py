"""Failure classification analyzer.

Analyzes collected diagnostic data to classify the type of failure
affecting an instance, with confidence scoring and evidence tracking.
"""

import logging
import re
from typing import Optional

from src.shared.constants import (
    DISK_CRITICAL_THRESHOLD,
    MEM_CRITICAL_THRESHOLD,
    FailureType,
)
from src.shared.logger import get_logger
from src.shared.models import (
    DiagnosticReport,
    FailureClassification,
    MetricSnapshot,
    SystemInfo,
)

logger: logging.Logger = get_logger("diagnostics")


def classify_failure(
    report: DiagnosticReport,
) -> FailureClassification:
    """Classify the failure type from collected diagnostic data.

    Applies rule-based analysis across metrics, system info, and log
    entries to determine the most likely failure type.

    Args:
        report: DiagnosticReport containing all collected data.

    Returns:
        FailureClassification with type, confidence, and evidence.
    """
    candidates: list[FailureClassification] = []

    disk_result = _check_disk_full(report.metric_snapshots, report.system_info)
    if disk_result:
        candidates.append(disk_result)

    mem_result = _check_memory_exhausted(
        report.metric_snapshots, report.system_info
    )
    if mem_result:
        candidates.append(mem_result)

    cpu_result = _check_cpu_saturated(report.metric_snapshots)
    if cpu_result:
        candidates.append(cpu_result)

    process_result = _check_process_crashed(
        report.system_info, report.log_entries
    )
    if process_result:
        candidates.append(process_result)

    endpoint_result = _check_endpoint_down(report.log_entries)
    if endpoint_result:
        candidates.append(endpoint_result)

    if not candidates:
        return FailureClassification(
            failure_type=FailureType.UNKNOWN,
            confidence=0.5,
            evidence=["No specific failure pattern detected"],
        )

    candidates.sort(key=lambda c: c.confidence, reverse=True)
    return candidates[0]


def _get_latest_metric_value(
    snapshots: list[MetricSnapshot], metric_name: str
) -> Optional[float]:
    """Extract the latest value for a named metric."""
    for snapshot in snapshots:
        if snapshot.metric_name == metric_name and snapshot.datapoints:
            latest = snapshot.datapoints[-1]
            return latest.get("average") or latest.get("maximum")
    return None


def _check_disk_full(
    snapshots: list[MetricSnapshot],
    system_info: Optional[SystemInfo],
) -> Optional[FailureClassification]:
    """Check if the failure is due to full disk."""
    evidence: list[str] = []
    confidence = 0.0

    disk_value = _get_latest_metric_value(snapshots, "disk_used_percent")
    if disk_value is not None and disk_value >= DISK_CRITICAL_THRESHOLD:
        confidence = 0.9
        evidence.append(
            f"Disk usage at {disk_value:.1f}% "
            f"(threshold: {DISK_CRITICAL_THRESHOLD}%)"
        )

    if system_info and system_info.disk_usage:
        if "100%" in system_info.disk_usage or "99%" in system_info.disk_usage:
            confidence = max(confidence, 0.95)
            evidence.append("System df shows filesystem at 99-100% capacity")

    if confidence > 0:
        return FailureClassification(
            failure_type=FailureType.DISK_FULL,
            confidence=confidence,
            evidence=evidence,
        )
    return None


def _check_memory_exhausted(
    snapshots: list[MetricSnapshot],
    system_info: Optional[SystemInfo],
) -> Optional[FailureClassification]:
    """Check if the failure is due to memory exhaustion."""
    evidence: list[str] = []
    confidence = 0.0

    mem_value = _get_latest_metric_value(snapshots, "mem_used_percent")
    if mem_value is not None and mem_value >= MEM_CRITICAL_THRESHOLD:
        confidence = 0.9
        evidence.append(
            f"Memory usage at {mem_value:.1f}% "
            f"(threshold: {MEM_CRITICAL_THRESHOLD}%)"
        )

    if system_info and system_info.dmesg_tail:
        if "Out of memory" in system_info.dmesg_tail:
            confidence = max(confidence, 0.95)
            evidence.append("OOM killer detected in dmesg")
        if "oom-kill" in system_info.dmesg_tail.lower():
            confidence = max(confidence, 0.95)
            evidence.append("OOM kill event in kernel log")

    if confidence > 0:
        return FailureClassification(
            failure_type=FailureType.MEMORY_EXHAUSTED,
            confidence=confidence,
            evidence=evidence,
        )
    return None


def _check_cpu_saturated(
    snapshots: list[MetricSnapshot],
) -> Optional[FailureClassification]:
    """Check if the failure is due to CPU saturation."""
    cpu_value = _get_latest_metric_value(snapshots, "CPUUtilization")
    if cpu_value is not None and cpu_value >= 95.0:
        return FailureClassification(
            failure_type=FailureType.CPU_SATURATED,
            confidence=0.85,
            evidence=[f"CPU utilization at {cpu_value:.1f}%"],
        )
    return None


def _check_process_crashed(
    system_info: Optional[SystemInfo],
    log_entries: list[str],
) -> Optional[FailureClassification]:
    """Check if a critical process has crashed."""
    evidence: list[str] = []
    confidence = 0.0

    if system_info and system_info.failed_services:
        failed_match = re.findall(
            r"(\S+\.service)\s+loaded\s+failed", system_info.failed_services
        )
        if failed_match:
            confidence = 0.9
            evidence.append(
                f"Failed systemd services: {', '.join(failed_match)}"
            )

    crash_keywords = [
        "segfault", "core dumped", "killed", "terminated",
        "service failed", "exited with error",
    ]
    for entry in log_entries:
        entry_lower = entry.lower()
        for keyword in crash_keywords:
            if keyword in entry_lower:
                confidence = max(confidence, 0.8)
                evidence.append(f"Crash indicator in logs: {entry[:200]}")
                break

    if confidence > 0:
        return FailureClassification(
            failure_type=FailureType.PROCESS_CRASHED,
            confidence=confidence,
            evidence=evidence,
        )
    return None


def _check_endpoint_down(
    log_entries: list[str],
) -> Optional[FailureClassification]:
    """Check if the failure is an endpoint being down."""
    evidence: list[str] = []

    endpoint_keywords = [
        "connection refused", "bind failed", "address already in use",
        "port.*unavailable", "listen.*failed",
    ]
    for entry in log_entries:
        entry_lower = entry.lower()
        for keyword in endpoint_keywords:
            if re.search(keyword, entry_lower):
                evidence.append(f"Endpoint issue in logs: {entry[:200]}")
                break

    if evidence:
        return FailureClassification(
            failure_type=FailureType.ENDPOINT_DOWN,
            confidence=0.75,
            evidence=evidence,
        )
    return None
