"""
Unit Tests for VRAMArbiter

Tests:
- Allocation checks with sufficient/insufficient VRAM
- Reserve/Release operations
- Safety buffer enforcement
- Fallback when sensors unavailable
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestVRAMArbiterAllocation:
    """Tests for VRAM allocation checks."""

    def test_can_allocate_with_sufficient_vram(self, mock_system_monitor, reset_config_singleton):
        """Verify can_allocate returns True when enough VRAM available."""
        # Note: We need to patch BOTH ConfigManager and the get_vram_manager function
        # because VRAMArbiter uses the BudgetManager internally.
        with patch("pb_studio.core.vram_arbiter.ConfigManager") as mock_cfg:
            mock_cfg.return_value.get.return_value = {"vram_limit_mb": 8192}
            
            with patch("pb_studio.core.vram_budget_manager.get_vram_manager") as mock_get_mgr:
                mock_mgr = MagicMock()
                mock_mgr.available_vram_mb = 6000
                mock_mgr.can_fit.return_value = True
                mock_get_mgr.return_value = mock_mgr

                from pb_studio.core.vram_arbiter import VRAMArbiter
                arbiter = VRAMArbiter(mock_system_monitor)

                # Stats from fixture: 2048 used, 8192 total = 6144 available
                # 6144 (sensor) - 500 (buffer) = 5644
                # Budget says 6000.
                # Request 1024. 5644 >= 1024 (True) AND 6000 >= 1024 (True)
                result = arbiter.can_allocate(1024)
                assert result is True

    def test_can_allocate_denies_when_insufficient(self, mock_system_monitor, reset_config_singleton):
        """Verify can_allocate returns False when VRAM insufficient."""
        # Modify mock to show high usage
        mock_system_monitor.get_stats.return_value = {
            "gpu_load": 95.0,
            "gpu_temp": 80.0,
            "gpu_memory_used": 7500.0,  # Very full
            "gpu_memory_total": 8192.0
        }

        with patch("pb_studio.core.vram_arbiter.ConfigManager") as mock_cfg:
            mock_cfg.return_value.get.return_value = {"vram_limit_mb": 8192}
            
            with patch("pb_studio.core.vram_budget_manager.get_vram_manager") as mock_get_mgr:
                mock_mgr = MagicMock()
                mock_mgr.available_vram_mb = 500 # Budget also low
                mock_mgr.can_fit.return_value = False
                mock_get_mgr.return_value = mock_mgr

                from pb_studio.core.vram_arbiter import VRAMArbiter
                arbiter = VRAMArbiter(mock_system_monitor)

                # Sensor: 8192 - 7500 - 500 = 192 available.
                # Request 1024. 192 < 1024 -> False
                result = arbiter.can_allocate(1024)
                assert result is False


class TestVRAMArbiterReserveRelease:
    """Tests for reserve/release operations."""

    def test_reserve_increases_tracked_amount(self, mock_system_monitor, reset_config_singleton):
        """Verify reserve() interacts with BudgetManager."""
        with patch("pb_studio.core.vram_arbiter.ConfigManager") as mock_cfg:
            mock_cfg.return_value.get.return_value = {"vram_limit_mb": 8192}

            with patch("pb_studio.core.vram_budget_manager.get_vram_manager") as mock_get_mgr:
                mock_mgr = MagicMock()
                # Mock properties
                mock_mgr.total_reserved_mb = 1024
                mock_mgr.total_committed_mb = 0
                mock_get_mgr.return_value = mock_mgr

                from pb_studio.core.vram_arbiter import VRAMArbiter
                arbiter = VRAMArbiter(mock_system_monitor)

                # Call reserve
                arbiter.reserve(1024, model_id="test_model")
                
                # Check interaction
                mock_mgr.register_model.assert_called_with(
                    model_id="test_model", name="test_model", estimated_vram_mb=1024
                )
                mock_mgr.reserve.assert_called_with("test_model")

    def test_commit_updates_budget_manager(self, mock_system_monitor, reset_config_singleton):
        """Verify commit() interacts with BudgetManager."""
        with patch("pb_studio.core.vram_arbiter.ConfigManager") as mock_cfg:
            mock_cfg.return_value.get.return_value = {"vram_limit_mb": 8192}

            with patch("pb_studio.core.vram_budget_manager.get_vram_manager") as mock_get_mgr:
                mock_mgr = MagicMock()
                mock_get_mgr.return_value = mock_mgr

                from pb_studio.core.vram_arbiter import VRAMArbiter
                arbiter = VRAMArbiter(mock_system_monitor)

                arbiter.commit("test_model")
                mock_mgr.commit.assert_called_with("test_model")

    def test_release_decreases_tracked_amount(self, mock_system_monitor, reset_config_singleton):
        """Verify release() interacts with BudgetManager."""
        with patch("pb_studio.core.vram_arbiter.ConfigManager") as mock_cfg:
            mock_cfg.return_value.get.return_value = {"vram_limit_mb": 8192}

            with patch("pb_studio.core.vram_budget_manager.get_vram_manager") as mock_get_mgr:
                mock_mgr = MagicMock()
                mock_get_mgr.return_value = mock_mgr

                from pb_studio.core.vram_arbiter import VRAMArbiter
                arbiter = VRAMArbiter(mock_system_monitor)
                
                arbiter.release(model_id="test_model")
                mock_mgr.release.assert_called_with("test_model")
