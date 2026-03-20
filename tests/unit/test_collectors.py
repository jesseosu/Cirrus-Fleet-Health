"""Tests for diagnostic data collectors."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


class TestLogCollector:
    """Tests for CloudWatch log collection."""

    @patch("src.diagnostics.collectors.log_collector.get_client")
    def test_collect_logs_success(self, mock_get_client: MagicMock) -> None:
        """Test successful log collection."""
        client = MagicMock()
        client.filter_log_events.return_value = {
            "events": [
                {"message": "ERROR: disk full"},
                {"message": "WARN: high memory"},
            ]
        }
        mock_get_client.return_value = client

        from src.diagnostics.collectors.log_collector import collect_logs
        result = collect_logs("i-test123")
        assert len(result) == 2
        assert "ERROR: disk full" in result[0]

    @patch("src.diagnostics.collectors.log_collector.get_client")
    def test_collect_logs_not_found(self, mock_get_client: MagicMock) -> None:
        """Test handling of missing log group."""
        client = MagicMock()
        ex_class = type("ResourceNotFoundException", (Exception,), {})
        client.exceptions.ResourceNotFoundException = ex_class
        client.filter_log_events.side_effect = ex_class("Not found")
        mock_get_client.return_value = client

        from src.diagnostics.collectors.log_collector import collect_logs
        result = collect_logs("i-test123")
        assert result == []

    @patch("src.diagnostics.collectors.log_collector.get_client")
    def test_collect_logs_error(self, mock_get_client: MagicMock) -> None:
        """Test handling of general API error."""
        client = MagicMock()
        client.exceptions = MagicMock()
        client.exceptions.ResourceNotFoundException = type(
            "ResourceNotFoundException", (Exception,), {}
        )
        client.filter_log_events.side_effect = Exception("API Error")
        mock_get_client.return_value = client

        from src.diagnostics.collectors.log_collector import collect_logs
        result = collect_logs("i-test123")
        assert len(result) == 1
        assert "Error" in result[0]


class TestMetricSnapshot:
    """Tests for metric snapshot collection."""

    @patch("src.diagnostics.collectors.metric_snapshot.get_client")
    def test_collect_snapshots(self, mock_get_client: MagicMock) -> None:
        """Test successful metric snapshot collection."""
        client = MagicMock()
        now = datetime.now(timezone.utc)
        client.get_metric_statistics.return_value = {
            "Datapoints": [
                {"Timestamp": now, "Average": 45.0, "Maximum": 50.0},
            ]
        }
        mock_get_client.return_value = client

        from src.diagnostics.collectors.metric_snapshot import (
            collect_metric_snapshots,
        )
        result = collect_metric_snapshots("i-test123")
        assert len(result) == 5  # 5 metrics configured
        assert result[0].metric_name == "CPUUtilization"

    @patch("src.diagnostics.collectors.metric_snapshot.get_client")
    def test_collect_snapshots_error(self, mock_get_client: MagicMock) -> None:
        """Test metric collection handles errors per metric."""
        client = MagicMock()
        client.get_metric_statistics.side_effect = Exception("CW Error")
        mock_get_client.return_value = client

        from src.diagnostics.collectors.metric_snapshot import (
            collect_metric_snapshots,
        )
        result = collect_metric_snapshots("i-test123")
        assert len(result) == 5
        assert all(len(s.datapoints) == 0 for s in result)


class TestSystemInfo:
    """Tests for system info collection via SSM."""

    @patch("src.diagnostics.collectors.system_info.get_client")
    def test_collect_system_info(self, mock_get_client: MagicMock) -> None:
        """Test successful system info collection."""
        client = MagicMock()
        client.send_command.return_value = {
            "Command": {"CommandId": "cmd-123"}
        }
        client.get_command_invocation.return_value = {
            "Status": "Success",
            "StandardOutputContent": (
                "===DISK===\n/dev/xvda1 50G 25G 25G 50% /\n"
                "===MEMORY===\ntotal 7982\n"
                "===TOP===\ntop output\n"
                "===PROCESSES===\nps output\n"
                "===DMESG===\nkernel messages\n"
                "===FAILED_SERVICES===\n0 loaded\n"
                "===NETWORK===\nss output\n"
            ),
        }
        mock_get_client.return_value = client

        from src.diagnostics.collectors.system_info import collect_system_info
        result = collect_system_info("i-test123")
        assert "50G" in result.disk_usage
        assert "7982" in result.memory_info

    @patch("src.diagnostics.collectors.system_info.get_client")
    def test_collect_system_info_error(self, mock_get_client: MagicMock) -> None:
        """Test handling of SSM error."""
        client = MagicMock()
        client.send_command.side_effect = Exception("SSM Error")
        mock_get_client.return_value = client

        from src.diagnostics.collectors.system_info import collect_system_info
        result = collect_system_info("i-test123")
        assert result.disk_usage == ""


class TestEndpointHealth:
    """Tests for endpoint health checks."""

    @patch("src.health_checker.checks.endpoint_health.urlopen")
    def test_healthy_endpoint(self, mock_urlopen: MagicMock) -> None:
        """Test healthy endpoint returns HEALTHY."""
        from src.shared.constants import Severity

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        from src.health_checker.checks.endpoint_health import (
            check_endpoint_health,
        )
        result = check_endpoint_health("i-test123", "10.0.1.1")
        assert result.status == Severity.HEALTHY

    @patch("src.health_checker.checks.endpoint_health.urlopen")
    def test_server_error_returns_unhealthy(self, mock_urlopen: MagicMock) -> None:
        """Test 500 response returns UNHEALTHY."""
        from src.shared.constants import Severity

        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        from src.health_checker.checks.endpoint_health import (
            check_endpoint_health,
        )
        result = check_endpoint_health("i-test123", "10.0.1.1")
        assert result.status == Severity.UNHEALTHY

    @patch("src.health_checker.checks.endpoint_health.urlopen")
    def test_connection_error_returns_unhealthy(self, mock_urlopen: MagicMock) -> None:
        """Test connection errors result in UNHEALTHY after retries."""
        from urllib.error import URLError
        from src.shared.constants import Severity

        mock_urlopen.side_effect = URLError("Connection refused")

        from src.health_checker.checks.endpoint_health import (
            check_endpoint_health,
        )
        result = check_endpoint_health("i-test123", "10.0.1.1")
        assert result.status == Severity.UNHEALTHY
        assert mock_urlopen.call_count == 3  # ENDPOINT_RETRIES


class TestProcessHealth:
    """Tests for process health checks."""

    @patch("src.health_checker.checks.process_health.get_client")
    def test_process_running(self, mock_get_client: MagicMock) -> None:
        """Test detecting a running process."""
        from src.shared.constants import Severity

        client = MagicMock()
        client.send_command.return_value = {
            "Command": {"CommandId": "cmd-123"}
        }
        client.get_command_invocation.return_value = {
            "Status": "Success",
            "StandardOutputContent": "RUNNING",
            "StandardErrorContent": "",
        }
        client.exceptions = MagicMock()
        client.exceptions.InvocationDoesNotExist = type(
            "InvocationDoesNotExist", (Exception,), {}
        )
        mock_get_client.return_value = client

        from src.health_checker.checks.process_health import (
            check_process_health,
        )
        result = check_process_health("i-test123")
        assert result.status == Severity.HEALTHY

    @patch("src.health_checker.checks.process_health.get_client")
    def test_process_not_running(self, mock_get_client: MagicMock) -> None:
        """Test detecting a stopped process."""
        from src.shared.constants import Severity

        client = MagicMock()
        client.send_command.return_value = {
            "Command": {"CommandId": "cmd-123"}
        }
        client.get_command_invocation.return_value = {
            "Status": "Success",
            "StandardOutputContent": "NOT_RUNNING",
            "StandardErrorContent": "",
        }
        client.exceptions = MagicMock()
        client.exceptions.InvocationDoesNotExist = type(
            "InvocationDoesNotExist", (Exception,), {}
        )
        mock_get_client.return_value = client

        from src.health_checker.checks.process_health import (
            check_process_health,
        )
        result = check_process_health("i-test123")
        assert result.status == Severity.UNHEALTHY
