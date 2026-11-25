"""Unit tests for JARVIS permissions and security boundary enforcement."""

import pytest
from pathlib import Path
from core.permissions import PermissionManager, PermissionLevel, BASE_DIR


def test_permission_manager_initialization():
    pm = PermissionManager(authorized_folders=[BASE_DIR], require_confirmation=True)
    assert pm.is_path_authorized(BASE_DIR)
    assert pm.is_path_authorized(BASE_DIR / "README.md")


def test_permission_manager_blocks_forbidden_paths():
    pm = PermissionManager(authorized_folders=[BASE_DIR], require_confirmation=True)
    # Attempting to access sensitive Windows folders must be blocked
    assert not pm.is_path_safe("C:\\Windows\\System32\\config\\SAM")
    assert not pm.is_path_safe("C:\\Users\\User\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Login Data")
    assert not pm.is_path_safe("C:\\Users\\User\\.ssh\\id_rsa")


def test_permission_manager_blocks_unauthorized_paths():
    pm = PermissionManager(authorized_folders=[BASE_DIR], require_confirmation=True)
    random_external_path = Path("C:\\SomeRandomFolder\\SecretFile.txt")
    res = pm.check_permission(
        action_name="read_file",
        level=PermissionLevel.READ,
        target_resource=str(random_external_path),
    )
    assert not res.allowed
    assert "outside authorized folders" in res.reason


def test_permission_manager_blocks_forbidden_actions():
    pm = PermissionManager(authorized_folders=[BASE_DIR])
    res = pm.check_permission(
        action_name="execute_arbitrary_shell",
        level=PermissionLevel.BLOCKED,
    )
    assert not res.allowed
    assert "strictly forbidden" in res.reason


def test_emergency_stop():
    pm = PermissionManager(authorized_folders=[BASE_DIR])
    pm.trigger_emergency_stop("Test emergency stop")
    assert pm.emergency_stop_active

    res = pm.check_permission(
        action_name="read_system_info",
        level=PermissionLevel.READ,
    )
    assert not res.allowed
    assert "Emergency stop is currently ACTIVE" in res.reason

    pm.reset_emergency_stop()
    assert not pm.emergency_stop_active
