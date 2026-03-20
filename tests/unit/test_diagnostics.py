"""Tests for diagnostic collection and analysis."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.shared.constants import FailureType, Severity
from src.shared.models import (
    DiagnosticReport,
    FailureClassification,
    MetricSnapshot,
    SystemInfo,
)
from src.diagnostics.analyzer import classify_failure


class TestAnalyzer:
    """Tests for failure classification logic."""

    def test_disk_full_classification(self) -> None:
        """Test that high disk usage classifies as DISK_FULL."""
        report = DiagnosticReport(
            instance_id="i-test123",
            metric_snapshots=[
                MetricSnapshot(
                    metric_name="disk_used_percent",
                    datapoints=[{"average": 97.0, "maximum": 98.0}],
                    unit="Percent",
                ),
            ],
            system_info=SystemInfo(disk_usage="100%"),
        )
        result = classify_failure(report)
        assert result.failure_type == FailureType.DISK_FULL
        assert result.confidence >= 0.9

    def test_memory_exhausted_classification(self) -> None:
        """Test that high memory usage classifies as MEMORY_EXHAUSTED."""
        report = DiagnosticReport(
            instance_id="i-test123",
            metric_snapshots=[
                MetricSnapshot(
                    metric_name="mem_used_percent",
                    datapoints=[{"average": 98.0, "maximum": 99.0}],
                    unit="Percent",
                ),
            ],
        )
        result = classify_failure(report)
        assert result.failure_type == FailureType.MEMORY_EXHAUSTED
        assert result.confidence >= 0.9

    def test_oom_killer_boosts_memory_confidence(self) -> None:
        """Test that OOM killer in dmesg boosts confidence."""
        report = DiagnosticReport(
            instance_id="i-test123",
            metric_snapshots=[
                MetricSnapshot(
                    metric_name="mem_used_percent",
                    datapoints=[{"average": 96.0}],
                    unit="Percent",
                ),
            ],
            system_info=SystemInfo(
                dmesg_tail="[12345.678] Out of memory: Kill process 1234"
            ),
        )
        result = classify_failure(report)
        assert result.failure_type == FailureType.MEMORY_EXHAUSTED
        assert result.confidence >= 0.95

    def test_cpu_saturated_classification(self) -> None:
        """Test that high CPU classifies as CPU_SATURATED."""
        report = DiagnosticReport(
            instance_id="i-test123",
            metric_snapshots=[
                MetricSnapshot(
                    metric_name="CPUUtilization",
                    datapoints=[{"average": 99.0}],
                    unit="Percent",
                ),
            ],
        )
        result = classify_failure(report)
        assert result.failure_type == FailureType.CPU_SATURATED

    def test_process_crashed_from_logs(self) -> None:
        """Test that crash indicators in logs classify as PROCESS_CRASHED."""
        report = DiagnosticReport(
            instance_id="i-test123",
            log_entries=[
                "ERROR: segfault in httpd worker",
                "FATAL: core dumped",
            ],
        )
        result = classify_failure(report)
        assert result.failure_type == FailureType.PROCESS_CRASHED

    def test_unknown_when_no_indicators(self) -> None:
        """Test that no failure indicators returns UNKNOWN."""
        report = DiagnosticReport(
            instance_id="i-test123",
            metric_snapshots=[
                MetricSnapshot(
                    metric_name="CPUUtilization",
                    datapoints=[{"average": 30.0}],
                    unit="Percent",
                ),
                MetricSnapshot(
                    metric_name="mem_used_percent",
                    datapoints=[{"average": 40.0}],
                    unit="Percent",
                ),
                MetricSnapshot(
                    metric_name="disk_used_percent",
                    datapoints=[{"average": 50.0}],
                    unit="Percent",
                ),
            ],
        )
        result = classify_failure(report)
        assert result.failure_type == FailureType.UNKNOWN


class TestDiagnosticsHandler:
    """Tests for the diagnostics Lambda handler."""

    @patch("src.diagnostics.handler.collect_system_info")
    @patch("src.diagnostics.handler.collect_metric_snapshots")
    @patch("src.diagnostics.handler.collect_logs")
    def test_handler_returns_report(
        self,
        mock_logs: MagicMock,
        mock_metrics: MagicMock,
        mock_sysinfo: MagicMock,
    ) -> None:
        """Test that handler returns a complete diagnostic report."""
        mock_logs.return_value = ["ERROR: test"]
        mock_metrics.return_value = []
        mock_sysinfo.return_value = SystemInfo()

        from src.diagnostics.handler import handler
        result = handler({"instance_id": "i-test123"}, None)
        assert result["statusCode"] == 200
        assert result["body"]["instance_id"] == "i-test123"

    def test_handler_missing_instance_id(self) -> None:
        """Test that handler rejects events without instance_id."""
        from src.diagnostics.handler import handler
        result = handler({}, None)
        assert result["statusCode"] == 400
