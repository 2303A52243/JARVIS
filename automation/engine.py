"""Automation engine for JARVIS.

Parses a user request into a list of discrete tool steps, shows the plan
for user approval, then executes approved steps one by one.

This module is intentionally simple and safe:
- No arbitrary code execution.
- Every step calls a registered tool through the tool registry.
- The user must approve the plan before execution starts.
- Any step can be cancelled via the emergency-stop flag.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import List, Dict, Any, Callable, Optional


@dataclass
class AutomationStep:
    """A single step in an automation plan."""
    tool_name: str
    arguments: Dict[str, Any]
    description: str
    is_risky: bool = False
    result: Optional[str] = None
    status: str = "pending"   # pending | success | failed | skipped


@dataclass
class AutomationPlan:
    """An ordered list of steps to execute."""
    title: str
    steps: List[AutomationStep] = field(default_factory=list)
    approved: bool = False
    cancelled: bool = False


# Simple keyword → tool mapping (can be extended)
_STEP_PATTERNS = [
    # (keywords_tuple, tool_name, description_template)
    (("open", "launch", "start"), "launch_app",    "Launch application: {target}"),
    (("close", "terminate", "kill"), "terminate_app", "Close application: {target}"),
    (("search", "find", "look for"), "search_files",  "Search files for: {target}"),
    (("read", "show", "open file"),  "read_document",  "Read document: {target}"),
    (("system", "laptop", "info", "status"), "get_system_info", "Retrieve system information"),
    (("apps", "installed", "programs"),      "list_installed_apps", "List installed applications"),
]


def parse_plan(user_request: str) -> AutomationPlan:
    """Very lightweight NL → plan parser.

    For each recognised keyword pattern in the request, generates a step.
    In production this would be replaced by an LLM-generated plan.
    """
    req = user_request.lower()
    steps: List[AutomationStep] = []

    # Extract a likely target word (last quoted string or last noun-ish word)
    import re
    quoted = re.findall(r'"([^"]+)"', user_request)
    target = quoted[0] if quoted else user_request.split()[-1]

    for keywords, tool, desc_tpl in _STEP_PATTERNS:
        if any(kw in req for kw in keywords):
            risky = tool in ("terminate_app", "delete_file", "move_file")
            steps.append(AutomationStep(
                tool_name=tool,
                arguments={"query": target} if "search" in tool else {"name": target},
                description=desc_tpl.format(target=target),
                is_risky=risky,
            ))

    if not steps:
        steps.append(AutomationStep(
            tool_name="get_system_info",
            arguments={},
            description="Retrieve system information (default fallback step)",
        ))

    return AutomationPlan(title=f"Automation: {user_request[:60]}", steps=steps)


class AutomationEngine:
    """Executes an approved AutomationPlan step by step."""

    def __init__(self):
        self._stop_flag = threading.Event()

    def stop(self):
        self._stop_flag.set()

    def reset(self):
        self._stop_flag.clear()

    def execute(
        self,
        plan: AutomationPlan,
        on_step_done: Optional[Callable[[AutomationStep], None]] = None,
        on_finished: Optional[Callable[[AutomationPlan], None]] = None,
    ) -> None:
        """Execute *plan* in a background thread.

        Args:
            plan:         The approved AutomationPlan to execute.
            on_step_done: Called after each step completes (runs in worker thread).
            on_finished:  Called after all steps complete or are cancelled.
        """
        if not plan.approved:
            raise RuntimeError("Plan must be approved before execution.")

        def _run():
            self._stop_flag.clear()
            for step in plan.steps:
                if self._stop_flag.is_set() or plan.cancelled:
                    step.status = "skipped"
                    continue
                try:
                    result = self._call_tool(step.tool_name, step.arguments)
                    step.result = str(result)[:500]
                    step.status = "success"
                except Exception as e:
                    step.result = f"Error: {e}"
                    step.status = "failed"
                if on_step_done:
                    on_step_done(step)

            if on_finished:
                on_finished(plan)

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    @staticmethod
    def _call_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Dispatch a tool call to the appropriate backend module."""
        if tool_name == "get_system_info":
            from system.system_info import get_system_summary
            return get_system_summary()
        elif tool_name == "list_installed_apps":
            from system.application_manager import list_installed_apps
            apps = list_installed_apps()
            return f"Found {len(apps)} installed applications."
        elif tool_name == "launch_app":
            from system.application_manager import launch_app
            return launch_app(arguments.get("name", ""))
        elif tool_name == "terminate_app":
            from system.application_manager import terminate_app
            return terminate_app(arguments.get("name", ""))
        elif tool_name == "search_files":
            from files.file_search import search_files
            results = search_files(query=arguments.get("query", ""), max_depth=4)
            return f"Found {len(results)} file(s) matching '{arguments.get('query', '')}'."
        elif tool_name == "read_document":
            from files.document_parser import parse_document
            return parse_document(arguments.get("name", ""))[:300]
        else:
            return f"Unknown tool: {tool_name}"
