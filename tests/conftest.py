"""Shared pytest fixtures for Cirrus test suite.

Provides mocked AWS clients, sample events, and pre-built test objects
used across unit and integration tests.
"""

from datetime import datetime, timezone
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest

from src.shared.constants import FailureType, IncidentStatus, Severity
from src.shared.models import (
    DiagnosticReport,
    FailureClassification,
    HealthCheckResult,
    HealthVerdict,
    MetricSnapshot,
    RemediationResult,
    SystemInfo,
)


@pytest.fixture
def mock_ec2_client() -> Generator[MagicMock, None, None]:
    """Mocked EC2 client returning configurable instance data."""
    with patch("src.shared.aws_clients.get_client") as mock_get:
        client = MagicMock()
        # Default: one running, healthy instance
        client.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-test123",
                            "PrivateIpAddress": "10.0.1.100",
                            "State": {"Name": "running"},
                        }
                    ]
                }
            ]
        }
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
        # Make paginator work
        paginator = MagicMock()
        paginator.paginate.return_value = [
            client.describe_instances.return_value
        ]
        client.get_paginator.return_value = paginator

        mock_get.return_value = client
        yield client


@pytest.fixture
def mock_cloudwatch_client() -> Generator[MagicMock, None, None]:
    """Mocked CloudWatch client returning configurable metric data."""
    with patch("src.shared.aws_clients.get_client") as mock_get:
        client = MagicMock()
        now = datetime.now(timezone.utc)
        client.get_metric_data.return_value = {
            "MetricDataResults": [
                {
                    "Id": "cpu",
                    "Values": [45.0],
                    "Timestamps": [now],
                },
                {
                    "Id": "memory",
                    "Values": [60.0],
                    "Timestamps": [now],
                },
                {
                    "Id": "disk",
                    "Values": [55.0],
                    "Timestamps": [now],
                },
            ]
        }
        client.get_metric_statistics.return_value = {
            "Datapoints": [
                {
                    "Timestamp": now,
                    "Average": 45.0,
                    "Maximum": 50.0,
                }
            ]
        }
        mock_get.return_value = client
        yield client


@pytest.fixture
def mock_ssm_client() -> Generator[MagicMock, None, None]:
    """Mocked SSM client returning configurable command results."""
    with patch("src.shared.aws_clients.get_client") as mock_get:
        client = MagicMock()
        client.send_command.return_value = {
            "Command": {"CommandId": "cmd-test123"}
        }
        client.get_command_invocation.return_value = {
            "Status": "Success",
            "StandardOutputContent": "RUNNING",
            "StandardErrorContent": "",
        }
        # Simulate no exceptions class on mock
        client.exceptions = MagicMock()
        client.exceptions.InvocationDoesNotExist = type(
            "InvocationDoesNotExist", (Exception,), {}
        )
        mock_get.return_value = client
        yield client


@pytest.fixture
def mock_dynamodb_resource() -> Generator[MagicMock, None, None]:
    """Mocked DynamoDB table resource."""
    with patch("src.shared.aws_clients.get_resource") as mock_get:
        resource = MagicMock()
        table = MagicMock()
        resource.Table.return_value = table
        table.put_item.return_value = {}
        table.update_item.return_value = {}
        mock_get.return_value = resource
        yield table


@pytest.fixture
def mock_sns_client() -> Generator[MagicMock, None, None]:
    """Mocked SNS client."""
    with patch("src.shared.aws_clients.get_client") as mock_get:
        client = MagicMock()
        client.publish.return_value = {"MessageId": "msg-test123"}
        mock_get.return_value = client
        yield client


@pytest.fixture
def sample_health_verdict() -> HealthVerdict:
    """Pre-built unhealthy health verdict for testing."""
    return HealthVerdict(
        instance_id="i-test123",
        overall_status=Severity.UNHEALTHY,
        severity=Severity.UNHEALTHY,
        failed_checks=["cloudwatch_metrics", "process_health"],
        all_results=[
            HealthCheckResult(
                check_name="ec2_status",
                status=Severity.HEALTHY,
                details={"instance_state": "running"},
            ),
            HealthCheckResult(
                check_name="cloudwatch_metrics",
                status=Severity.UNHEALTHY,
                details={"metrics": {"cpu": {"value": 98.0}}},
            ),
            HealthCheckResult(
                check_name="process_health",
                status=Severity.UNHEALTHY,
                details={"processes": {"httpd": {"status": "not_running"}}},
            ),
        ],
    )


@pytest.fixture
def sample_diagnostic_report() -> DiagnosticReport:
    """Pre-built diagnostic report for testing."""
    return DiagnosticReport(
        instance_id="i-test123",
        log_entries=[
            "ERROR: httpd service crashed",
            "FATAL: segfault in worker process",
        ],
        metric_snapshots=[
            MetricSnapshot(
                metric_name="CPUUtilization",
                datapoints=[{"timestamp": "2024-01-01T00:00:00", "average": 45.0}],
                unit="Percent",
            ),
            MetricSnapshot(
                metric_name="mem_used_percent",
                datapoints=[{"timestamp": "2024-01-01T00:00:00", "average": 60.0}],
                unit="Percent",
            ),
            MetricSnapshot(
                metric_name="disk_used_percent",
                datapoints=[{"timestamp": "2024-01-01T00:00:00", "average": 55.0}],
                unit="Percent",
            ),
        ],
        system_info=SystemInfo(
            disk_usage="Filesystem  Size  Used Avail Use% Mounted on\n/dev/xvda1   50G   25G   25G  50% /",
            memory_info="              total  used  free\nMem:           7982  4800  3182",
            failed_services="0 loaded units listed.",
        ),
        failure_classification=FailureClassification(
            failure_type=FailureType.PROCESS_CRASHED,
            confidence=0.9,
            evidence=["Failed systemd services detected"],
        ),
    )
