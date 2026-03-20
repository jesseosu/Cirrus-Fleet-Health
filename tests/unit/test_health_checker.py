"""Tests for health check modules."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.shared.constants import Severity


class TestEC2StatusCheck:
    """Tests for ec2_status.py health check."""

    @patch("src.health_checker.checks.ec2_status.get_client")
    def test_healthy_instance(self, mock_get_client: MagicMock) -> None:
        """Test that a healthy instance returns HEALTHY."""
        client = MagicMock()
        client.describe_instance_status.return_value = {
            "InstanceStatuses": [
                {
                    "InstanceId": "i-test123",
                    "InstanceState": {"Name": "running"},
                    "SystemStatus": {"Status": "ok"},
                    "InstanceStatus": {"Status": "ok"},
                }
            ]
        }
        mock_get_client.return_value = client

        from src.health_checker.checks.ec2_status import check_ec2_status
        result = check_ec2_status("i-test123")
        assert result.status == Severity.HEALTHY
        assert result.check_name == "ec2_status"

    @patch("src.health_checker.checks.ec2_status.get_client")
    def test_impaired_instance(self, mock_get_client: MagicMock) -> None:
        """Test that an impaired instance returns UNHEALTHY."""
        client = MagicMock()
        client.describe_instance_status.return_value = {
            "InstanceStatuses": [
                {
                    "InstanceId": "i-test123",
                    "InstanceState": {"Name": "running"},
                    "SystemStatus": {"Status": "impaired"},
                    "InstanceStatus": {"Status": "ok"},
                }
            ]
        }
        mock_get_client.return_value = client

        from src.health_checker.checks.ec2_status import check_ec2_status
        result = check_ec2_status("i-test123")
        assert result.status == Severity.UNHEALTHY

    @patch("src.health_checker.checks.ec2_status.get_client")
    def test_stopped_instance(self, mock_get_client: MagicMock) -> None:
        """Test that a stopped instance returns CRITICAL."""
        client = MagicMock()
        client.describe_instance_status.return_value = {
            "InstanceStatuses": [
                {
                    "InstanceId": "i-test123",
                    "InstanceState": {"Name": "stopped"},
                    "SystemStatus": {"Status": "not-applicable"},
                    "InstanceStatus": {"Status": "not-applicable"},
                }
            ]
        }
        mock_get_client.return_value = client

        from src.health_checker.checks.ec2_status import check_ec2_status
        result = check_ec2_status("i-test123")
        assert result.status == Severity.CRITICAL

    @patch("src.health_checker.checks.ec2_status.get_client")
    def test_no_status_returned(self, mock_get_client: MagicMock) -> None:
        """Test that missing status returns CRITICAL."""
        client = MagicMock()
        client.describe_instance_status.return_value = {
            "InstanceStatuses": []
        }
        mock_get_client.return_value = client

        from src.health_checker.checks.ec2_status import check_ec2_status
        result = check_ec2_status("i-test123")
        assert result.status == Severity.CRITICAL

    @patch("src.health_checker.checks.ec2_status.get_client")
    def test_api_error_returns_critical(self, mock_get_client: MagicMock) -> None:
        """Test that API errors return CRITICAL."""
        client = MagicMock()
        client.describe_instance_status.side_effect = Exception("API Error")
        mock_get_client.return_value = client

        from src.health_checker.checks.ec2_status import check_ec2_status
        result = check_ec2_status("i-test123")
        assert result.status == Severity.CRITICAL
        assert "error" in result.details


class TestCloudWatchMetricsCheck:
    """Tests for cloudwatch_metrics.py health check."""

    @patch("src.health_checker.checks.cloudwatch_metrics.get_client")
    def test_healthy_metrics(self, mock_get_client: MagicMock) -> None:
        """Test that normal metrics return HEALTHY."""
        client = MagicMock()
        now = datetime.now(timezone.utc)
        client.get_metric_data.return_value = {
            "MetricDataResults": [
                {"Id": "cpu", "Values": [45.0], "Timestamps": [now]},
                {"Id": "memory", "Values": [60.0], "Timestamps": [now]},
                {"Id": "disk", "Values": [55.0], "Timestamps": [now]},
            ]
        }
        mock_get_client.return_value = client

        from src.health_checker.checks.cloudwatch_metrics import (
            check_cloudwatch_metrics,
        )
        result = check_cloudwatch_metrics("i-test123")
        assert result.status == Severity.HEALTHY

    @patch("src.health_checker.checks.cloudwatch_metrics.get_client")
    def test_high_cpu_returns_unhealthy(self, mock_get_client: MagicMock) -> None:
        """Test that CPU above critical threshold returns UNHEALTHY."""
        client = MagicMock()
        now = datetime.now(timezone.utc)
        client.get_metric_data.return_value = {
            "MetricDataResults": [
                {"Id": "cpu", "Values": [98.0], "Timestamps": [now]},
                {"Id": "memory", "Values": [60.0], "Timestamps": [now]},
                {"Id": "disk", "Values": [55.0], "Timestamps": [now]},
            ]
        }
        mock_get_client.return_value = client

        from src.health_checker.checks.cloudwatch_metrics import (
            check_cloudwatch_metrics,
        )
        result = check_cloudwatch_metrics("i-test123")
        assert result.status == Severity.UNHEALTHY

    @patch("src.health_checker.checks.cloudwatch_metrics.get_client")
    def test_warning_cpu_returns_degraded(self, mock_get_client: MagicMock) -> None:
        """Test that CPU above warning threshold returns DEGRADED."""
        client = MagicMock()
        now = datetime.now(timezone.utc)
        client.get_metric_data.return_value = {
            "MetricDataResults": [
                {"Id": "cpu", "Values": [85.0], "Timestamps": [now]},
                {"Id": "memory", "Values": [60.0], "Timestamps": [now]},
                {"Id": "disk", "Values": [55.0], "Timestamps": [now]},
            ]
        }
        mock_get_client.return_value = client

        from src.health_checker.checks.cloudwatch_metrics import (
            check_cloudwatch_metrics,
        )
        result = check_cloudwatch_metrics("i-test123")
        assert result.status == Severity.DEGRADED

    @patch("src.health_checker.checks.cloudwatch_metrics.get_client")
    def test_no_metric_data_returns_healthy(self, mock_get_client: MagicMock) -> None:
        """Test that missing metric data defaults to HEALTHY."""
        client = MagicMock()
        client.get_metric_data.return_value = {
            "MetricDataResults": [
                {"Id": "cpu", "Values": [], "Timestamps": []},
                {"Id": "memory", "Values": [], "Timestamps": []},
                {"Id": "disk", "Values": [], "Timestamps": []},
            ]
        }
        mock_get_client.return_value = client

        from src.health_checker.checks.cloudwatch_metrics import (
            check_cloudwatch_metrics,
        )
        result = check_cloudwatch_metrics("i-test123")
        assert result.status == Severity.HEALTHY
