"""Tests for remediation actions."""

from unittest.mock import MagicMock, patch

import pytest

from src.shared.constants import FailureType


class TestRestartService:
    """Tests for restart_service remediation action."""

    @patch("src.remediator.actions.restart_service.get_client")
    def test_successful_restart(self, mock_get_client: MagicMock) -> None:
        """Test successful service restart."""
        client = MagicMock()
        client.send_command.return_value = {
            "Command": {"CommandId": "cmd-123"}
        }
        client.get_command_invocation.return_value = {
            "Status": "Success",
            "StandardOutputContent": "active",
            "StandardErrorContent": "",
        }
        mock_get_client.return_value = client

        from src.remediator.actions.restart_service import restart_service
        result = restart_service("i-test123", "httpd")
        assert result.success is True
        assert "httpd" in result.action_taken

    @patch("src.remediator.actions.restart_service.get_client")
    def test_failed_restart(self, mock_get_client: MagicMock) -> None:
        """Test failed service restart."""
        client = MagicMock()
        client.send_command.return_value = {
            "Command": {"CommandId": "cmd-123"}
        }
        client.get_command_invocation.return_value = {
            "Status": "Failed",
            "StandardOutputContent": "",
            "StandardErrorContent": "Service not found",
        }
        mock_get_client.return_value = client

        from src.remediator.actions.restart_service import restart_service
        result = restart_service("i-test123", "httpd")
        assert result.success is False

    @patch("src.remediator.actions.restart_service.get_client")
    def test_ssm_error(self, mock_get_client: MagicMock) -> None:
        """Test handling of SSM API error."""
        client = MagicMock()
        client.send_command.side_effect = Exception("SSM Error")
        mock_get_client.return_value = client

        from src.remediator.actions.restart_service import restart_service
        result = restart_service("i-test123", "httpd")
        assert result.success is False
        assert "error" in result.details


class TestRebootInstance:
    """Tests for reboot_instance remediation action."""

    @patch("src.remediator.actions.reboot_instance.get_client")
    def test_successful_reboot(self, mock_get_client: MagicMock) -> None:
        """Test successful instance reboot."""
        client = MagicMock()
        client.reboot_instances.return_value = {}
        client.describe_instance_status.return_value = {
            "InstanceStatuses": [
                {
                    "InstanceState": {"Name": "running"},
                    "SystemStatus": {"Status": "ok"},
                }
            ]
        }
        mock_get_client.return_value = client

        from src.remediator.actions.reboot_instance import reboot_instance
        result = reboot_instance("i-test123")
        assert result.success is True
        assert result.action_taken == "reboot_instance"

    @patch("src.remediator.actions.reboot_instance.get_client")
    def test_reboot_api_error(self, mock_get_client: MagicMock) -> None:
        """Test handling of EC2 API error during reboot."""
        client = MagicMock()
        client.reboot_instances.side_effect = Exception("EC2 Error")
        mock_get_client.return_value = client

        from src.remediator.actions.reboot_instance import reboot_instance
        result = reboot_instance("i-test123")
        assert result.success is False


class TestReplaceInstance:
    """Tests for replace_instance remediation action."""

    @patch("src.remediator.actions.replace_instance.get_client")
    def test_successful_replacement(self, mock_get_client: MagicMock) -> None:
        """Test successful instance termination for ASG replacement."""
        ec2_client = MagicMock()
        ec2_client.terminate_instances.return_value = {
            "TerminatingInstances": [
                {"CurrentState": {"Name": "shutting-down"}}
            ]
        }
        asg_client = MagicMock()
        asg_client.describe_auto_scaling_instances.return_value = {
            "AutoScalingInstances": [
                {"AutoScalingGroupName": "test-asg"}
            ]
        }
        mock_get_client.side_effect = lambda svc: (
            ec2_client if svc == "ec2" else asg_client
        )

        from src.remediator.actions.replace_instance import replace_instance
        result = replace_instance("i-test123")
        assert result.success is True
        assert result.details.get("in_asg") is True


class TestClearDisk:
    """Tests for clear_disk remediation action."""

    @patch("src.remediator.actions.clear_disk.get_client")
    def test_successful_cleanup(self, mock_get_client: MagicMock) -> None:
        """Test successful disk cleanup."""
        client = MagicMock()
        client.send_command.return_value = {
            "Command": {"CommandId": "cmd-123"}
        }
        client.get_command_invocation.return_value = {
            "Status": "Success",
            "StandardOutputContent": '{"freed_mb": 512, "current_usage_percent": 75}',
            "StandardErrorContent": "",
        }
        mock_get_client.return_value = client

        from src.remediator.actions.clear_disk import clear_disk
        result = clear_disk("i-test123")
        assert result.success is True
        assert result.action_taken == "clear_disk"
