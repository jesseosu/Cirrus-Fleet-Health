"""Tests for the health checker Lambda handler."""

from unittest.mock import MagicMock, patch

import pytest

from src.shared.constants import Severity
from src.shared.models import HealthCheckResult, HealthVerdict


class TestHealthCheckerHandler:
    """Tests for the main health checker handler."""

    @patch("src.health_checker.handler.publish_events")
    @patch("src.health_checker.handler.publish_metrics")
    @patch("src.health_checker.handler._run_checks_for_instance")
    @patch("src.health_checker.handler._discover_instances")
    def test_handler_with_healthy_instances(
        self,
        mock_discover: MagicMock,
        mock_run_checks: MagicMock,
        mock_publish_metrics: MagicMock,
        mock_publish_events: MagicMock,
    ) -> None:
        """Test handler processes discovered instances."""
        mock_discover.return_value = [
            {"InstanceId": "i-001", "PrivateIpAddress": "10.0.1.1"},
        ]
        mock_run_checks.return_value = HealthVerdict(
            instance_id="i-001",
            overall_status=Severity.HEALTHY,
            severity=Severity.HEALTHY,
        )

        from src.health_checker.handler import handler
        result = handler({}, None)
        assert result["statusCode"] == 200
        assert result["body"]["total_instances"] == 1
        assert result["body"]["healthy"] == 1
        mock_publish_metrics.assert_called_once()
        mock_publish_events.assert_called_once()

    @patch("src.health_checker.handler._discover_instances")
    def test_handler_no_instances(self, mock_discover: MagicMock) -> None:
        """Test handler when no monitored instances found."""
        mock_discover.return_value = []

        from src.health_checker.handler import handler
        result = handler({}, None)
        assert result["statusCode"] == 200
        assert "No monitored instances" in result["body"]["message"]

    @patch("src.health_checker.handler._discover_instances")
    def test_handler_exception(self, mock_discover: MagicMock) -> None:
        """Test handler handles unexpected exceptions."""
        mock_discover.side_effect = Exception("Unexpected error")

        from src.health_checker.handler import handler
        result = handler({}, None)
        assert result["statusCode"] == 500

    @patch("src.health_checker.handler.publish_events")
    @patch("src.health_checker.handler.publish_metrics")
    @patch("src.health_checker.handler._run_checks_for_instance")
    @patch("src.health_checker.handler._discover_instances")
    def test_handler_with_mixed_health(
        self,
        mock_discover: MagicMock,
        mock_run_checks: MagicMock,
        mock_publish_metrics: MagicMock,
        mock_publish_events: MagicMock,
    ) -> None:
        """Test handler counts healthy/unhealthy correctly."""
        mock_discover.return_value = [
            {"InstanceId": "i-001", "PrivateIpAddress": "10.0.1.1"},
            {"InstanceId": "i-002", "PrivateIpAddress": "10.0.1.2"},
        ]

        def side_effect(inst: dict) -> HealthVerdict:
            if inst["InstanceId"] == "i-001":
                return HealthVerdict(
                    instance_id="i-001",
                    overall_status=Severity.HEALTHY,
                    severity=Severity.HEALTHY,
                )
            return HealthVerdict(
                instance_id="i-002",
                overall_status=Severity.UNHEALTHY,
                severity=Severity.UNHEALTHY,
                failed_checks=["ec2_status"],
            )

        mock_run_checks.side_effect = side_effect

        from src.health_checker.handler import handler
        result = handler({}, None)
        assert result["body"]["healthy"] == 1
        assert result["body"]["unhealthy"] == 1


class TestDiscoverInstances:
    """Tests for instance discovery."""

    @patch("src.health_checker.handler.get_client")
    def test_discover_instances(self, mock_get_client: MagicMock) -> None:
        """Test that instances are discovered via EC2 API."""
        client = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": "i-001",
                                "PrivateIpAddress": "10.0.1.1",
                            },
                            {
                                "InstanceId": "i-002",
                                "PrivateIpAddress": "10.0.1.2",
                            },
                        ]
                    }
                ]
            }
        ]
        client.get_paginator.return_value = paginator
        mock_get_client.return_value = client

        from src.health_checker.handler import _discover_instances
        instances = _discover_instances()
        assert len(instances) == 2
        assert instances[0]["InstanceId"] == "i-001"


class TestRemediatorHandler:
    """Tests for the remediator Lambda handler."""

    @patch("src.remediator.handler.ACTION_HANDLERS")
    def test_handler_restart_service(self, mock_handlers: MagicMock) -> None:
        """Test remediator handler dispatches restart_service."""
        from src.shared.models import RemediationResult
        mock_action = MagicMock()
        mock_action.return_value = RemediationResult(
            action_taken="restart_service:httpd",
            success=True,
            duration_ms=5000,
        )
        mock_handlers.get.return_value = mock_action

        from src.remediator.handler import handler
        result = handler(
            {
                "instance_id": "i-test123",
                "body": {
                    "instance_id": "i-test123",
                    "failure_classification": {
                        "failure_type": "PROCESS_CRASHED",
                    },
                },
            },
            None,
        )
        assert result["statusCode"] == 200
        assert result["body"]["success"] is True

    def test_handler_unknown_failure_escalates(self) -> None:
        """Test that UNKNOWN failure type triggers escalation."""
        from src.remediator.handler import handler
        result = handler(
            {
                "instance_id": "i-test123",
                "body": {
                    "instance_id": "i-test123",
                    "failure_classification": {
                        "failure_type": "UNKNOWN",
                    },
                },
            },
            None,
        )
        assert result["statusCode"] == 200
        assert result["body"]["escalate"] is True

    def test_handler_missing_instance_id(self) -> None:
        """Test handler rejects events without instance_id."""
        from src.remediator.handler import handler
        result = handler({"body": {}}, None)
        assert result["statusCode"] == 400
