"""Tests for the health verdict publisher."""

from unittest.mock import MagicMock, call, patch

import pytest

from src.shared.constants import Severity
from src.shared.models import HealthCheckResult, HealthVerdict


class TestPublishMetrics:
    """Tests for CloudWatch metric publishing."""

    @patch("src.health_checker.publisher.get_client")
    def test_publishes_healthy_metrics(self, mock_get_client: MagicMock) -> None:
        """Test publishing metrics for healthy instances."""
        client = MagicMock()
        mock_get_client.return_value = client

        from src.health_checker.publisher import publish_metrics

        verdicts = [
            HealthVerdict(
                instance_id="i-001",
                overall_status=Severity.HEALTHY,
                severity=Severity.HEALTHY,
            ),
            HealthVerdict(
                instance_id="i-002",
                overall_status=Severity.HEALTHY,
                severity=Severity.HEALTHY,
            ),
        ]
        publish_metrics(verdicts)
        client.put_metric_data.assert_called()
        call_args = client.put_metric_data.call_args
        assert call_args.kwargs["Namespace"] == "Cirrus/Fleet"

    @patch("src.health_checker.publisher.get_client")
    def test_publishes_unhealthy_metrics(self, mock_get_client: MagicMock) -> None:
        """Test that unhealthy instances are counted correctly."""
        client = MagicMock()
        mock_get_client.return_value = client

        from src.health_checker.publisher import publish_metrics

        verdicts = [
            HealthVerdict(
                instance_id="i-001",
                overall_status=Severity.UNHEALTHY,
                severity=Severity.UNHEALTHY,
            ),
        ]
        publish_metrics(verdicts)
        client.put_metric_data.assert_called()

    @patch("src.health_checker.publisher.get_client")
    def test_handles_api_error(self, mock_get_client: MagicMock) -> None:
        """Test graceful handling of CloudWatch API errors."""
        client = MagicMock()
        client.put_metric_data.side_effect = Exception("CW Error")
        mock_get_client.return_value = client

        from src.health_checker.publisher import publish_metrics

        verdicts = [
            HealthVerdict(
                instance_id="i-001",
                overall_status=Severity.HEALTHY,
                severity=Severity.HEALTHY,
            ),
        ]
        # Should not raise
        publish_metrics(verdicts)


class TestPublishEvents:
    """Tests for EventBridge event publishing."""

    @patch("src.health_checker.publisher.get_client")
    def test_publishes_unhealthy_events(self, mock_get_client: MagicMock) -> None:
        """Test that unhealthy verdicts are published to EventBridge."""
        client = MagicMock()
        client.put_events.return_value = {"FailedEntryCount": 0}
        mock_get_client.return_value = client

        from src.health_checker.publisher import publish_events

        verdicts = [
            HealthVerdict(
                instance_id="i-001",
                overall_status=Severity.UNHEALTHY,
                severity=Severity.UNHEALTHY,
                failed_checks=["ec2_status"],
            ),
        ]
        publish_events(verdicts)
        client.put_events.assert_called_once()

    @patch("src.health_checker.publisher.get_client")
    def test_skips_healthy_events(self, mock_get_client: MagicMock) -> None:
        """Test that healthy verdicts are not published to EventBridge."""
        client = MagicMock()
        mock_get_client.return_value = client

        from src.health_checker.publisher import publish_events

        verdicts = [
            HealthVerdict(
                instance_id="i-001",
                overall_status=Severity.HEALTHY,
                severity=Severity.HEALTHY,
            ),
        ]
        publish_events(verdicts)
        client.put_events.assert_not_called()

    @patch("src.health_checker.publisher.get_client")
    def test_handles_failed_entries(self, mock_get_client: MagicMock) -> None:
        """Test logging when EventBridge entries fail."""
        client = MagicMock()
        client.put_events.return_value = {"FailedEntryCount": 1}
        mock_get_client.return_value = client

        from src.health_checker.publisher import publish_events

        verdicts = [
            HealthVerdict(
                instance_id="i-001",
                overall_status=Severity.UNHEALTHY,
                severity=Severity.UNHEALTHY,
                failed_checks=["ec2_status"],
            ),
        ]
        # Should not raise
        publish_events(verdicts)

    @patch("src.health_checker.publisher.get_client")
    def test_handles_api_error(self, mock_get_client: MagicMock) -> None:
        """Test graceful handling of EventBridge API errors."""
        client = MagicMock()
        client.put_events.side_effect = Exception("EB Error")
        mock_get_client.return_value = client

        from src.health_checker.publisher import publish_events

        verdicts = [
            HealthVerdict(
                instance_id="i-001",
                overall_status=Severity.CRITICAL,
                severity=Severity.CRITICAL,
                failed_checks=["ec2_status"],
            ),
        ]
        publish_events(verdicts)
