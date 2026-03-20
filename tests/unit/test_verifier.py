"""Tests for post-remediation verification."""

from unittest.mock import MagicMock, patch

import pytest


class TestVerifierHandler:
    """Tests for the verifier Lambda handler."""

    @patch("src.verifier.handler._get_private_ip")
    @patch("src.verifier.handler.check_process_health")
    @patch("src.verifier.handler.check_cloudwatch_metrics")
    @patch("src.verifier.handler.check_ec2_status")
    def test_healthy_verification(
        self,
        mock_ec2: MagicMock,
        mock_cw: MagicMock,
        mock_proc: MagicMock,
        mock_ip: MagicMock,
    ) -> None:
        """Test verification returns REMEDIATION_SUCCEEDED when healthy."""
        from src.shared.constants import Severity
        from src.shared.models import HealthCheckResult

        mock_ec2.return_value = HealthCheckResult(
            check_name="ec2_status", status=Severity.HEALTHY
        )
        mock_cw.return_value = HealthCheckResult(
            check_name="cloudwatch_metrics", status=Severity.HEALTHY
        )
        mock_proc.return_value = HealthCheckResult(
            check_name="process_health", status=Severity.HEALTHY
        )
        mock_ip.return_value = ""

        from src.verifier.handler import handler
        result = handler({"instance_id": "i-test123"}, None)
        assert result["statusCode"] == 200
        assert result["body"]["verification_status"] == "REMEDIATION_SUCCEEDED"
        assert result["body"]["is_healthy"] is True

    @patch("src.verifier.handler._get_private_ip")
    @patch("src.verifier.handler.check_process_health")
    @patch("src.verifier.handler.check_cloudwatch_metrics")
    @patch("src.verifier.handler.check_ec2_status")
    def test_still_unhealthy(
        self,
        mock_ec2: MagicMock,
        mock_cw: MagicMock,
        mock_proc: MagicMock,
        mock_ip: MagicMock,
    ) -> None:
        """Test verification returns REMEDIATION_FAILED when still unhealthy."""
        from src.shared.constants import Severity
        from src.shared.models import HealthCheckResult

        mock_ec2.return_value = HealthCheckResult(
            check_name="ec2_status", status=Severity.HEALTHY
        )
        mock_cw.return_value = HealthCheckResult(
            check_name="cloudwatch_metrics", status=Severity.UNHEALTHY
        )
        mock_proc.return_value = HealthCheckResult(
            check_name="process_health", status=Severity.HEALTHY
        )
        mock_ip.return_value = ""

        from src.verifier.handler import handler
        result = handler({"instance_id": "i-test123"}, None)
        assert result["body"]["verification_status"] == "REMEDIATION_FAILED"
        assert result["body"]["is_healthy"] is False

    def test_missing_instance_id(self) -> None:
        """Test handler rejects events without instance_id."""
        from src.verifier.handler import handler
        result = handler({}, None)
        assert result["statusCode"] == 400

    @patch("src.verifier.handler._get_private_ip")
    @patch("src.verifier.handler.check_process_health")
    @patch("src.verifier.handler.check_cloudwatch_metrics")
    @patch("src.verifier.handler.check_ec2_status")
    def test_exception_returns_failed(
        self,
        mock_ec2: MagicMock,
        mock_cw: MagicMock,
        mock_proc: MagicMock,
        mock_ip: MagicMock,
    ) -> None:
        """Test that exceptions result in REMEDIATION_FAILED."""
        mock_ec2.side_effect = Exception("Connection error")
        mock_ip.return_value = ""

        from src.verifier.handler import handler
        result = handler({"instance_id": "i-test123"}, None)
        assert result["statusCode"] == 500
        assert result["body"]["is_healthy"] is False
