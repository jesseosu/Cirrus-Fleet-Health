"""Tests for DynamoDB incident logging."""

from unittest.mock import MagicMock, patch

import pytest


class TestIncidentLoggerHandler:
    """Tests for the incident logger Lambda handler."""

    @patch("src.incident_logger.handler.get_resource")
    def test_create_incident(self, mock_get_resource: MagicMock) -> None:
        """Test creating a new incident record."""
        resource = MagicMock()
        table = MagicMock()
        resource.Table.return_value = table
        table.put_item.return_value = {}
        mock_get_resource.return_value = resource

        from src.incident_logger.handler import handler
        result = handler(
            {
                "action": "create",
                "instance_id": "i-test123",
                "severity": "UNHEALTHY",
                "checks_failed": ["cloudwatch_metrics"],
            },
            None,
        )
        assert result["statusCode"] == 200
        assert result["body"]["instance_id"] == "i-test123"
        assert result["body"]["status"] == "DETECTED"
        table.put_item.assert_called_once()

    @patch("src.incident_logger.handler.get_resource")
    def test_update_incident(self, mock_get_resource: MagicMock) -> None:
        """Test updating an existing incident."""
        resource = MagicMock()
        table = MagicMock()
        resource.Table.return_value = table
        table.update_item.return_value = {}
        mock_get_resource.return_value = resource

        from src.incident_logger.handler import handler
        result = handler(
            {
                "action": "update",
                "instance_id": "i-test123",
                "pk": "INSTANCE#i-test123",
                "sk": "INCIDENT#2024-01-01T00:00:00",
                "status": "DIAGNOSED",
                "failure_type": "DISK_FULL",
            },
            None,
        )
        assert result["statusCode"] == 200
        assert result["body"]["status"] == "DIAGNOSED"
        table.update_item.assert_called_once()

    def test_missing_instance_id(self) -> None:
        """Test that missing instance_id returns error."""
        from src.incident_logger.handler import handler
        result = handler({"action": "create"}, None)
        assert result["statusCode"] == 400

    @patch("src.incident_logger.handler.get_resource")
    def test_update_missing_sk(self, mock_get_resource: MagicMock) -> None:
        """Test that update without sort key returns error."""
        resource = MagicMock()
        table = MagicMock()
        resource.Table.return_value = table
        mock_get_resource.return_value = resource

        from src.incident_logger.handler import handler
        result = handler(
            {
                "action": "update",
                "instance_id": "i-test123",
                "status": "DIAGNOSED",
            },
            None,
        )
        assert result["statusCode"] == 400

    @patch("src.incident_logger.handler.get_resource")
    def test_unknown_action(self, mock_get_resource: MagicMock) -> None:
        """Test that unknown action returns error."""
        resource = MagicMock()
        mock_get_resource.return_value = resource

        from src.incident_logger.handler import handler
        result = handler(
            {
                "action": "delete",
                "instance_id": "i-test123",
            },
            None,
        )
        assert result["statusCode"] == 400
