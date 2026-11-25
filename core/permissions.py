"""Permission and Security Enforcement Engine for JARVIS.

Enforces strict boundaries on system inspection, file access, and application control.
Prevents arbitrary command execution, directory traversal, and unauthorized changes.
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel

from security.audit_logger import get_audit_logger
from app.config import BASE_DIR


class PermissionLevel(str, Enum):
    """Categorization of tool and action capabilities."""
    READ = "READ"           # Inspecting authorized status (CPU, RAM, listing files)
    CONTROL = "CONTROL"     # Safe, reversible operations (opening approved app, creating new file)
    ADVANCED = "ADVANCED"   # Sensitive operations (deleting, overwriting, closing apps)
    BLOCKED = "BLOCKED"     # Strictly forbidden actions (arbitrary shell, reading credentials)


# Explicit blacklist of sensitive paths that must NEVER be accessed under any condition
FORBIDDEN_PATH_SUBSTRINGS = [
    "AppData\\Local\\Microsoft\\Vault",
    "AppData\\Roaming\\Mozilla\\Firefox\\Profiles",
    "AppData\\Local\\Google\\Chrome\\User Data",
    "AppData\\Local\\BraveSoftware\\Brave-Browser\\User Data",
    "AppData\\Local\\Microsoft\\Edge\\User Data",
    ".ssh",
    ".aws",
    ".azure",
    ".kube",
    "id_rsa",
    "id_ed25519",
    "System32",
    "SysWOW64",
    "Windows\\Security",
    "SAM",
    "SECURITY",
    "NTUSER.DAT",
]


# Explicitly forbidden commands/actions
BLOCKED_ACTIONS = {
    "execute_arbitrary_shell",
    "read_browser_passwords",
    "extract_tokens",
    "disable_antivirus",
    "disable_windows_defender",
    "modify_system_registry",
    "delete_system_files",
    "purchase_online",
    "send_unapproved_email",
}


class PermissionResult(BaseModel):
    """Result of a permission evaluation."""
    allowed: bool
    requires_confirmation: bool
    reason: str
    level: PermissionLevel
    details: Dict[str, Any] = {}


class PermissionManager:
    """Central authority for authorizing and gating all JARVIS actions."""

    _instance: Optional[PermissionManager] = None

    def __init__(self, authorized_folders: Optional[List[Path]] = None, require_confirmation: Optional[bool] = None):
        from app.config import get_settings
        settings = get_settings()
        explicit_folders = authorized_folders is not None
        self.authorized_folders: List[Path] = [
            p.resolve() for p in (authorized_folders if explicit_folders else settings.jarvis_authorized_folders)
        ]
        self.full_pc_access: bool = (not explicit_folders) and getattr(settings, "jarvis_full_pc_access", False)
        if require_confirmation is not None:
            self.require_confirmation = require_confirmation
        else:
            self.require_confirmation = False if self.full_pc_access else settings.jarvis_require_confirmation
        self.emergency_stop_active = False
        self._confirmation_handler: Optional[Callable[[str, str, Dict[str, Any]], bool]] = None
        self.audit_logger = get_audit_logger()

    @classmethod
    def get_instance(cls) -> PermissionManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_confirmation_handler(self, handler: Callable[[str, str, Dict[str, Any]], bool]) -> None:
        """Register a GUI or CLI callback to prompt the user for interactive approval."""
        self._confirmation_handler = handler

    def trigger_emergency_stop(self, reason: str = "User initiated emergency stop") -> None:
        """Immediately block all operations across the entire application."""
        self.emergency_stop_active = True
        self.audit_logger.log_event(
            event_type="EMERGENCY_STOP",
            action="trigger_emergency_stop",
            status="TRIGGERED",
            details={"reason": reason},
            level="CRITICAL",
        )

    def reset_emergency_stop(self) -> None:
        """Reset the emergency stop state."""
        self.emergency_stop_active = False
        self.audit_logger.log_event(
            event_type="EMERGENCY_STOP",
            action="reset_emergency_stop",
            status="RESET",
            level="WARNING",
        )

    def is_path_safe(self, target_path: Path | str) -> bool:
        """Verify that target_path does not point to sensitive Windows credentials or system roots."""
        path_str = str(Path(target_path).resolve())
        for forbidden in FORBIDDEN_PATH_SUBSTRINGS:
            if forbidden.lower() in path_str.lower():
                return False
        return True

    def is_path_authorized(self, target_path: Path | str) -> bool:
        """Verify that target_path is within an authorized directory allowlist and is safe."""
        if not self.is_path_safe(target_path):
            return False

        try:
            resolved_target = Path(target_path).resolve()
        except Exception:
            return False

        for auth_dir in self.authorized_folders:
            try:
                # Target path is either the authorized folder itself or located inside it
                if resolved_target == auth_dir or auth_dir in resolved_target.parents:
                    return True
            except Exception:
                continue

        return False

    def check_permission(
        self,
        action_name: str,
        level: PermissionLevel,
        target_resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> PermissionResult:
        """Evaluate whether an action is permitted, blocked, or requires confirmation."""
        details = details or {}
        context = {
            "action": action_name,
            "level": level.value,
            "target": target_resource,
            **details,
        }

        # 1. Emergency stop check
        if self.emergency_stop_active:
            self.audit_logger.log_event("PERMISSION_DENIED", action_name, "BLOCKED_EMERGENCY_STOP", context, "WARNING")
            return PermissionResult(
                allowed=False,
                requires_confirmation=False,
                reason="Emergency stop is currently ACTIVE. All actions are halted.",
                level=PermissionLevel.BLOCKED,
                details=details,
            )

        # 2. Hardcoded blocked actions
        if action_name in BLOCKED_ACTIONS or level == PermissionLevel.BLOCKED:
            self.audit_logger.log_event("PERMISSION_DENIED", action_name, "HARD_BLOCKED", context, "WARNING")
            return PermissionResult(
                allowed=False,
                requires_confirmation=False,
                reason=f"Action '{action_name}' violates JARVIS safety policy and is strictly forbidden.",
                level=PermissionLevel.BLOCKED,
                details=details,
            )

        # 3. Path safety & allowlist checks if a file/path target is provided
        if target_resource:
            target_p = Path(target_resource)
            if not self.is_path_safe(target_p):
                self.audit_logger.log_event("PERMISSION_DENIED", action_name, "PATH_UNSAFE", context, "WARNING")
                return PermissionResult(
                    allowed=False,
                    requires_confirmation=False,
                    reason=f"Access to '{target_resource}' is blocked because it targets protected system or credential stores.",
                    level=PermissionLevel.BLOCKED,
                    details=details,
                )

            # If action touches files, verify directory allowlist
            if any(k in action_name.lower() for k in ("file", "folder", "dir", "read", "write", "delete", "code")):
                if not self.is_path_authorized(target_p):
                    self.audit_logger.log_event("PERMISSION_DENIED", action_name, "PATH_NOT_AUTHORIZED", context, "WARNING")
                    return PermissionResult(
                        allowed=False,
                        requires_confirmation=False,
                        reason=f"Path '{target_resource}' is outside authorized folders: {[str(p) for p in self.authorized_folders]}",
                        level=PermissionLevel.BLOCKED,
                        details=details,
                    )

        # 4. Confirmation requirement for ADVANCED or CONTROL
        needs_confirm = False
        if not self.full_pc_access:
            if level == PermissionLevel.ADVANCED:
                needs_confirm = True
            elif level == PermissionLevel.CONTROL and self.require_confirmation:
                needs_confirm = True
        elif self.require_confirmation and level == PermissionLevel.ADVANCED:
            needs_confirm = True

        if needs_confirm:
            # If an interactive confirmation handler is registered, query it
            if self._confirmation_handler is not None:
                prompt_msg = f"JARVIS is requesting permission to execute: {action_name}"
                if target_resource:
                    prompt_msg += f" on target '{target_resource}'"
                user_approved = self._confirmation_handler(action_name, prompt_msg, details)
                if not user_approved:
                    self.audit_logger.log_event("PERMISSION_REJECTED", action_name, "USER_REJECTED", context, "INFO")
                    return PermissionResult(
                        allowed=False,
                        requires_confirmation=True,
                        reason="Action was cancelled by user confirmation.",
                        level=level,
                        details=details,
                    )
            else:
                # If no handler registered yet, flag that interactive confirmation is required
                return PermissionResult(
                    allowed=True,
                    requires_confirmation=True,
                    reason="Action requires explicit user confirmation before execution.",
                    level=level,
                    details=details,
                )

        self.audit_logger.log_event("PERMISSION_GRANTED", action_name, "ALLOWED", context, "INFO")
        return PermissionResult(
            allowed=True,
            requires_confirmation=False,
            reason="Action authorized within security boundaries.",
            level=level,
            details=details,
        )


def get_permission_manager() -> PermissionManager:
    """Helper to retrieve the permission manager singleton."""
    return PermissionManager.get_instance()
