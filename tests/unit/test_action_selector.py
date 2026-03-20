"""Tests for the remediation action selector."""

import pytest

from src.shared.constants import FailureType
from src.remediator.action_selector import select_action


class TestActionSelector:
    """Tests for failure type to remediation action mapping."""

    def test_disk_full_maps_to_clear_disk(self) -> None:
        """Test DISK_FULL maps to clear_disk action."""
        assert select_action(FailureType.DISK_FULL) == "clear_disk"

    def test_memory_exhausted_maps_to_reboot(self) -> None:
        """Test MEMORY_EXHAUSTED maps to reboot_instance."""
        assert select_action(FailureType.MEMORY_EXHAUSTED) == "reboot_instance"

    def test_cpu_saturated_maps_to_reboot(self) -> None:
        """Test CPU_SATURATED maps to reboot_instance."""
        assert select_action(FailureType.CPU_SATURATED) == "reboot_instance"

    def test_process_crashed_maps_to_restart(self) -> None:
        """Test PROCESS_CRASHED maps to restart_service."""
        assert select_action(FailureType.PROCESS_CRASHED) == "restart_service"

    def test_instance_unreachable_maps_to_replace(self) -> None:
        """Test INSTANCE_UNREACHABLE maps to replace_instance."""
        assert select_action(FailureType.INSTANCE_UNREACHABLE) == "replace_instance"

    def test_endpoint_down_maps_to_restart(self) -> None:
        """Test ENDPOINT_DOWN maps to restart_service."""
        assert select_action(FailureType.ENDPOINT_DOWN) == "restart_service"

    def test_unknown_returns_none(self) -> None:
        """Test UNKNOWN failure type returns None (escalate)."""
        assert select_action(FailureType.UNKNOWN) is None
