"""Central Tool Registry for JARVIS.

Registers, documents, and executes tools with strict permission checks.
Every tool call is validated against the PermissionManager before execution.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
from core.permissions import PermissionLevel, get_permission_manager
from security.audit_logger import get_audit_logger


class ToolRegistry:
    """Singleton registry holding all tool definitions and handlers."""

    def __init__(self) -> None:
        self._tools: Dict[str, Dict[str, Any]] = {}
        self.logger = get_audit_logger()

    def register(
        self,
        name: str,
        func: Callable[[Dict[str, Any]], Any],
        spec: Dict[str, Any],
        level: PermissionLevel = PermissionLevel.READ,
    ) -> None:
        """Register a new tool."""
        self._tools[name] = {
            "name": name,
            "func": func,
            "spec": spec,
            "level": level,
        }
        self.logger.info(f"Registered tool '{name}' [level={level.name}]")

    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return list(self._tools.values())

    def get_openai_tools(self) -> List[Dict[str, Any]]:
        """Return tools formatted for OpenAI function calling."""
        return [
            {"type": "function", "function": t["spec"]}
            for t in self._tools.values()
        ]

    def execute_tool(self, name: str, args: Dict[str, Any]) -> Any:
        """Validate permissions and execute the tool."""
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool '{name}' is not registered.")

        pm = get_permission_manager()
        perm = pm.check_permission(
            action_name=name,
            level=tool["level"],
            target_resource=str(args),
            details=args,
        )
        if not perm.allowed:
            raise PermissionError(f"Permission denied for '{name}': {perm.reason}")

        self.logger.info(f"Executing tool '{name}' with args {args}")
        return tool["func"](args)


_GLOBAL_REGISTRY: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = ToolRegistry()
    return _GLOBAL_REGISTRY


def register_tool(name: str, func: Callable[[Dict[str, Any]], Any], spec: Dict[str, Any], level: PermissionLevel = PermissionLevel.READ) -> None:
    get_tool_registry().register(name, func, spec, level)
