"""Tests for escalation alert formatting and SNS publishing."""

import os
from unittest.mock import MagicMock, patch

import pytest


class TestEscalationHandler:
    """Tests for the escalation Lambda handler."""

    @patch.dict(os.environ, {"ESCALATION_TOPIC_ARN": "arn:aws:sns:us-east-1:123456:test"})
    @patch("src.escalation.handler.get_client")
    def test_successful_escalation(self, mock_get_client: MagicMock) -> None:
        """Test successful escalation alert publishing."""
        client = MagicMock()
        client.publish.return_value = {"MessageId": "msg-123"}
        mock_get_client.return_value = client

        from src.escalation.handler import handler
        result = handler(
            {
                "instance_id": "i-test123",
                "failure_type": "DISK_FULL",
                "severity": "UNHEALTHY",
            },
            None,
        )
        assert result["statusCode"] == 200
        assert result["body"]["alert_sent"] is True
        client.publish.assert_called_once()

    @patch.dict(os.environ, {"ESCALATION_TOPIC_ARN": ""})
    @patch("src.escalation.handler.get_client")
    def test_missing_topic_arn(self, mock_get_client: MagicMock) -> None:
        """Test that missing topic ARN returns error."""
        from src.escalation.handler import handler
        result = handler({"instance_id": "i-test123"}, None)
        assert result["statusCode"] == 500

    @patch.dict(os.environ, {"ESCALATION_TOPIC_ARN": "arn:aws:sns:us-east-1:123456:test"})
    @patch("src.escalation.handler.get_client")
    def test_sns_publish_error(self, mock_get_client: MagicMock) -> None:
        """Test handling of SNS publish failure."""
        client = MagicMock()
        client.publish.side_effect = Exception("SNS Error")
        mock_get_client.return_value = client

        from src.escalation.handler import handler
        result = handler(
            {"instance_id": "i-test123", "severity": "CRITICAL"},
            None,
        )
        assert result["statusCode"] == 500
        assert result["body"]["alert_sent"] is False


class TestAlertFormatting:
    """Tests for alert message formatting."""

    def test_format_includes_all_fields(self) -> None:
        """Test that formatted message includes all required fields."""
        from src.escalation.handler import _format_alert_message

        message = _format_alert_message(
            instance_id="i-test123",
            failure_type="DISK_FULL",
            severity="UNHEALTHY",
            remediation_action="clear_disk",
            remediation_result={"success": False, "details": {"error": "insufficient permissions"}},
            diagnostic_summary={"disk_usage": "99%"},
            timestamp="2024-01-01T00:00:00Z",
        )
        assert "i-test123" in message
        assert "DISK_FULL" in message
        assert "UNHEALTHY" in message
        assert "clear_disk" in message
        assert "NEXT STEPS" in message
