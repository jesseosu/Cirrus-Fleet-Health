"""Tests for the health verdict evaluator."""

import pytest

from src.shared.constants import Severity
from src.shared.models import HealthCheckResult
from src.health_checker.evaluator import evaluate_health


class TestEvaluator:
    """Tests for health verdict evaluation logic."""

    def test_all_healthy(self) -> None:
        """Test that all healthy checks produce HEALTHY verdict."""
        results = [
            HealthCheckResult(check_name="ec2_status", status=Severity.HEALTHY),
            HealthCheckResult(check_name="cloudwatch_metrics", status=Severity.HEALTHY),
            HealthCheckResult(check_name="process_health", status=Severity.HEALTHY),
        ]
        verdict = evaluate_health("i-test123", results)
        assert verdict.severity == Severity.HEALTHY
        assert verdict.failed_checks == []

    def test_one_degraded_produces_degraded(self) -> None:
        """Test that a single DEGRADED check produces DEGRADED verdict."""
        results = [
            HealthCheckResult(check_name="ec2_status", status=Severity.HEALTHY),
            HealthCheckResult(check_name="cloudwatch_metrics", status=Severity.DEGRADED),
            HealthCheckResult(check_name="process_health", status=Severity.HEALTHY),
        ]
        verdict = evaluate_health("i-test123", results)
        assert verdict.severity == Severity.DEGRADED
        assert "cloudwatch_metrics" in verdict.failed_checks

    def test_unhealthy_overrides_degraded(self) -> None:
        """Test that UNHEALTHY takes precedence over DEGRADED."""
        results = [
            HealthCheckResult(check_name="ec2_status", status=Severity.DEGRADED),
            HealthCheckResult(check_name="cloudwatch_metrics", status=Severity.UNHEALTHY),
            HealthCheckResult(check_name="process_health", status=Severity.HEALTHY),
        ]
        verdict = evaluate_health("i-test123", results)
        assert verdict.severity == Severity.UNHEALTHY
        assert len(verdict.failed_checks) == 2

    def test_critical_is_highest_severity(self) -> None:
        """Test that CRITICAL is the highest severity level."""
        results = [
            HealthCheckResult(check_name="ec2_status", status=Severity.CRITICAL),
            HealthCheckResult(check_name="cloudwatch_metrics", status=Severity.UNHEALTHY),
        ]
        verdict = evaluate_health("i-test123", results)
        assert verdict.severity == Severity.CRITICAL

    def test_empty_results_returns_critical(self) -> None:
        """Test that no check results returns CRITICAL."""
        verdict = evaluate_health("i-test123", [])
        assert verdict.severity == Severity.CRITICAL
        assert "no_checks_ran" in verdict.failed_checks

    def test_all_results_included_in_verdict(self) -> None:
        """Test that all check results are preserved in the verdict."""
        results = [
            HealthCheckResult(check_name="ec2_status", status=Severity.HEALTHY),
            HealthCheckResult(check_name="cloudwatch_metrics", status=Severity.UNHEALTHY),
        ]
        verdict = evaluate_health("i-test123", results)
        assert len(verdict.all_results) == 2
        assert verdict.instance_id == "i-test123"
