"""Application discovery and control utilities for JARVIS.

* Lists installed Windows applications by scanning Start Menu shortcuts (User & System).
* Allows launching by application name, shortcut name, or system command.
* Supports opening folders like 'jarvis folder', 'downloads', 'documents', 'desktop'.
* Allows checking if running and terminating applications safely.
* Enforces permission checks for CONTROL and ADVANCED actions.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Dict, Optional

from core.permissions import PermissionLevel, get_permission_manager
from security.audit_logger import get_audit_logger


# Start Menu directories on Windows
USER_START_MENU = Path(os.getenv("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
SYS_START_MENU = Path(os.getenv("PROGRAMDATA", r"C:\ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"

# Project root directory for "jarvis folder"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Resolve Desktop / Documents / Downloads including Windows OneDrive Known Folder Move
_HOME = Path.home()
_ONEDRIVE = _HOME / "OneDrive"
_DESKTOP_DIR = (_ONEDRIVE / "Desktop") if (_ONEDRIVE / "Desktop").exists() else (_HOME / "Desktop")
_DOCS_DIR = (_ONEDRIVE / "Documents") if (_ONEDRIVE / "Documents").exists() else (_HOME / "Documents")
_PICS_DIR = (_ONEDRIVE / "Pictures") if (_ONEDRIVE / "Pictures").exists() else (_HOME / "Pictures")

# Common Windows system app aliases
SYSTEM_APP_MAP = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "files": "explorer.exe",
    "paint": "mspaint.exe",
    "mspaint": "mspaint.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "terminal": "wt.exe",
    "taskmgr": "taskmgr.exe",
    "task manager": "taskmgr.exe",
    "control": "control.exe",
    "control panel": "control.exe",
}

# Special folder aliases
FOLDER_MAP = {
    "jarvis": PROJECT_ROOT,
    "jarvis folder": PROJECT_ROOT,
    "jarvis directory": PROJECT_ROOT,
    "project": PROJECT_ROOT,
    "project folder": PROJECT_ROOT,
    "downloads": _HOME / "Downloads",
    "downloads folder": _HOME / "Downloads",
    "desktop": _DESKTOP_DIR,
    "desktop folder": _DESKTOP_DIR,
    "documents": _DOCS_DIR,
    "documents folder": _DOCS_DIR,
    "pictures": _PICS_DIR,
    "music": _HOME / "Music",
    "videos": _HOME / "Videos",
}

_APPS_CACHE: Optional[List[Dict[str, str]]] = None
_APPS_CACHE_TS: float = 0.0


def list_installed_apps(use_cache: bool = True) -> List[Dict[str, str]]:
    """Return a list of installed applications discovered via Start-Menu shortcuts.

    Each entry contains ``name`` (shortcut display name) and ``path`` (full .lnk path).
    """
    global _APPS_CACHE, _APPS_CACHE_TS
    if use_cache and _APPS_CACHE is not None and (time.monotonic() - _APPS_CACHE_TS) < 60.0:
        return _APPS_CACHE

    logger = get_audit_logger()
    apps: Dict[str, str] = {}

    for sm_dir in [USER_START_MENU, SYS_START_MENU]:
        if not sm_dir.exists():
            continue
        for root, _, files in os.walk(sm_dir):
            for file in files:
                if file.lower().endswith(".lnk"):
                    stem = Path(file).stem
                    full_path = str(Path(root) / file)
                    if stem not in apps:
                        apps[stem] = full_path

    result = [{"name": name, "path": path} for name, path in sorted(apps.items())]
    _APPS_CACHE = result
    _APPS_CACHE_TS = time.monotonic()
    logger.info(f"Discovered {len(result)} installed applications across Start Menus.")
    return result


def is_app_running(process_name: str) -> bool:
    """Check if any process with *process_name* (case-insensitive) is running."""
    import psutil
    clean = process_name.lower().replace(".exe", "").strip()
    for proc in psutil.process_iter(["name"]):
        try:
            pname = proc.info.get("name")
            if pname and pname.lower().replace(".exe", "").startswith(clean):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def _clean_folder_query(raw: str) -> tuple[str, bool]:
    """Strip wrapper words like 'folder'/'directory' and report if folder intent was explicit."""
    q = raw.lower().strip()
    is_folder_hint = bool(re.search(r"\b(folder|directory|dir)\b", q))
    q = re.sub(r"^(?:the|my|a)\s+", "", q)
    q = re.sub(r"\b(?:folder|directory|dir)\b", " ", q)
    q = re.sub(r"\b(?:the|my)\b", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    return q, is_folder_hint


def _find_matching_folder(query: str) -> Optional[Path]:
    """Search common user directories for a folder matching *query* cleanly."""
    clean_q, _ = _clean_folder_query(query)
    if not clean_q:
        return None
    compact_q = re.sub(r"[^a-z0-9]", "", clean_q)
    tokens = [t for t in clean_q.split() if len(t) >= 2]

    search_roots: List[tuple[Path, int]] = [
        (_DESKTOP_DIR, 2),
        (_HOME / "Desktop", 1),
        (_HOME / "Downloads", 2),
        (_DOCS_DIR, 2),
        (_HOME / "Documents", 1),
        (_HOME / "OneDrive", 1),
        (PROJECT_ROOT, 1),
    ]
    seen_roots: set[Path] = set()
    best_score = 0
    best_path: Optional[Path] = None
    skip_names = {".git", "__pycache__", "node_modules", "venv", ".venv", "AppData"}

    for root, max_depth in search_roots:
        try:
            resolved_root = root.resolve()
            if resolved_root in seen_roots or not resolved_root.is_dir():
                continue
            seen_roots.add(resolved_root)
            for dirpath, dirnames, _ in os.walk(resolved_root):
                rel_parts = Path(dirpath).relative_to(resolved_root).parts
                depth = len(rel_parts)
                if depth >= max_depth:
                    dirnames.clear()
                    continue
                dirnames[:] = [d for d in dirnames if d not in skip_names and not d.startswith(".")]
                for dname in dirnames:
                    dl = dname.lower()
                    dcompact = re.sub(r"[^a-z0-9]", "", dl)
                    score = 0
                    if dl == clean_q:
                        score = 100
                    elif compact_q and dcompact == compact_q:
                        score = 95
                    elif compact_q and len(compact_q) >= 4 and compact_q in dcompact:
                        score = 80
                    elif clean_q in dl and len(clean_q) >= 3:
                        score = 75
                    elif tokens and all(t in dl or t in dcompact for t in tokens):
                        score = 65
                    elif len(tokens) >= 2 and sum(1 for t in tokens if t in dl or t in dcompact) >= max(2, len(tokens) - 1):
                        score = 50
                    if score > best_score:
                        best_score = score
                        best_path = Path(dirpath) / dname
                        if best_score == 100:
                            return best_path
        except (OSError, PermissionError):
            continue

    return best_path


def launch_app(target: str) -> str:
    """Launch an application, system utility, shortcut, or folder by name or path.

    Parameters:
        target: Application name (e.g. 'notepad', 'Chrome', 'VS Code'),
                folder name ('jarvis folder', 'downloads', 'agentic AI PPTs'), or absolute path.

    Returns:
        A human-readable status message.
    """
    logger = get_audit_logger()
    pm = get_permission_manager()

    perm = pm.check_permission(
        action_name="launch_app",
        level=PermissionLevel.CONTROL,
        target_resource=target,
        details={"target": target},
    )
    if not perm.allowed:
        raise PermissionError(f"Permission denied for launch_app: {perm.reason}")

    clean = target.lower().strip()
    clean_no_folder, is_folder_hint = _clean_folder_query(target)

    # 1. Check explicit folder aliases
    for candidate in (clean, clean_no_folder):
        for alias, folder_path in FOLDER_MAP.items():
            if candidate == alias or candidate.replace("the ", "") == alias:
                if folder_path.exists():
                    subprocess.Popen(["explorer.exe", str(folder_path)], shell=False)
                    logger.info(f"Opened folder: {folder_path}")
                    return f"Opened folder '{folder_path.name}' in File Explorer."

    # 2. Check exact path (directory or file/.lnk)
    target_path = Path(target)
    if target_path.is_dir():
        subprocess.Popen(["explorer.exe", str(target_path.resolve())], shell=False)
        logger.info(f"Opened folder: {target_path}")
        return f"Opened folder '{target_path.name}' in File Explorer."
    if target_path.is_file():
        subprocess.Popen(["cmd.exe", "/c", "start", "", f'"{target_path.resolve()}"'], shell=False)
        logger.info(f"Launched application from path: {target_path}")
        return f"Launched {target_path.stem}."

    # 3. If user explicitly asked to open a folder/directory, search user folders first
    if is_folder_hint:
        matched_dir = _find_matching_folder(target)
        if matched_dir and matched_dir.exists():
            subprocess.Popen(["explorer.exe", str(matched_dir)], shell=False)
            logger.info(f"Opened matching folder: {matched_dir}")
            return f"Opened folder '{matched_dir.name}' in File Explorer."

    # 4. Check system app aliases (notepad, calc, cmd, etc.)
    for alias, exe_name in SYSTEM_APP_MAP.items():
        if clean == alias or clean.replace("the ", "") == alias:
            exe_path = shutil.which(exe_name) or exe_name
            subprocess.Popen([exe_path], shell=False)
            logger.info(f"Launched system application: {exe_name}")
            return f"Launched {alias.title()}."

    # 5. Check shutil.which for PATH binaries (e.g. code, git, python, etc.)
    binary = shutil.which(clean)
    if binary:
        subprocess.Popen([binary], shell=False)
        logger.info(f"Launched binary from PATH: {binary}")
        return f"Launched {clean}."

    # 6. Search installed Start Menu shortcuts (exact & substring)
    apps = list_installed_apps()
    for a in apps:
        if a["name"].lower() == clean:
            subprocess.Popen(["cmd.exe", "/c", "start", "", f'"{a["path"]}"'], shell=False)
            logger.info(f"Launched shortcut: {a['name']}")
            return f"Launched {a['name']}."

    for a in apps:
        if clean in a["name"].lower():
            subprocess.Popen(["cmd.exe", "/c", "start", "", f'"{a["path"]}"'], shell=False)
            logger.info(f"Launched matching shortcut: {a['name']}")
            return f"Launched {a['name']}."

    # 7. Fallback to folder search even if 'folder' word wasn't spoken (e.g. 'open agentic AI PPTs')
    matched_dir = _find_matching_folder(target)
    if matched_dir and matched_dir.exists():
        subprocess.Popen(["explorer.exe", str(matched_dir)], shell=False)
        logger.info(f"Opened matching folder: {matched_dir}")
        return f"Opened folder '{matched_dir.name}' in File Explorer."

    # 8. Last-resort token match on Start Menu shortcuts
    tokens = clean.split()
    for a in apps:
        if any(t in a["name"].lower() for t in tokens if len(t) > 2):
            subprocess.Popen(["cmd.exe", "/c", "start", "", f'"{a["path"]}"'], shell=False)
            logger.info(f"Launched matching shortcut: {a['name']}")
            return f"Launched {a['name']}."

    raise FileNotFoundError(
        f"Could not find an application, folder, or shortcut matching '{target}'. "
        "Try using the exact name or checking the 'Apps' tab."
    )


def terminate_app(process_name: str) -> str:
    """Terminate all processes matching *process_name* (case-insensitive)."""
    logger = get_audit_logger()
    pm = get_permission_manager()
    perm = pm.check_permission(
        action_name="terminate_app",
        level=PermissionLevel.ADVANCED,
        target_resource=process_name,
        details={"process_name": process_name},
    )
    if not perm.allowed:
        raise PermissionError(f"Permission denied for terminate_app: {perm.reason}")

    import psutil
    clean = process_name.lower().replace(".exe", "").strip()
    # Map common aliases (e.g. 'notepad' -> 'notepad.exe')
    if clean in SYSTEM_APP_MAP:
        clean = SYSTEM_APP_MAP[clean].replace(".exe", "")

    terminated = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            pname = proc.info.get("name")
            if pname and pname.lower().replace(".exe", "").startswith(clean):
                proc.kill()
                terminated.append(proc.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    logger.info(f"Terminated {len(terminated)} processes for '{process_name}'.")
    if terminated:
        return f"Successfully closed {process_name} (terminated {len(terminated)} process instances)."
    return f"No active process found matching '{process_name}'."


# Register tools for LLM usage
from core.tool_registry import register_tool

_APP_LIST_SPEC = {
    "name": "list_installed_apps",
    "description": "Return a list of installed applications.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}
register_tool(
    name="list_installed_apps",
    func=lambda _: list_installed_apps(),
    spec=_APP_LIST_SPEC,
    level=PermissionLevel.READ,
)

_LAUNCH_SPEC = {
    "name": "launch_app",
    "description": "Launch an application, system utility, or folder by name or path.",
    "parameters": {
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Name or path of the application or folder."}
        },
        "required": ["target"],
    },
}
register_tool(
    name="launch_app",
    func=lambda args: launch_app(args.get("target") or args.get("app_path", "")),
    spec=_LAUNCH_SPEC,
    level=PermissionLevel.CONTROL,
)

_TERMINATE_SPEC = {
    "name": "terminate_app",
    "description": "Terminate all processes matching a given executable or app name.",
    "parameters": {
        "type": "object",
        "properties": {
            "process_name": {"type": "string", "description": "Base name of the process (e.g., 'notepad', 'code')."}
        },
        "required": ["process_name"],
    },
}
register_tool(
    name="terminate_app",
    func=lambda args: terminate_app(args["process_name"]),
    spec=_TERMINATE_SPEC,
    level=PermissionLevel.ADVANCED,
)
