"""Developer utilities for JARVIS.

- `scan_projects` walks a root directory and detects common project types.
- `run_lint` runs a lightweight linter based on the detected type.

These functions are deliberately simple – they provide the required capability
without pulling in heavy external dependencies. They can be extended later.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, List


def _has_file(root: Path, name: str) -> bool:
    return (root / name).exists()


def scan_projects(root_path: Path) -> Dict[Path, List[str]]:
    """Return a mapping of project root directories to a list of detected types.

    Types include:
    - "python"  – presence of `requirements.txt`, `pyproject.toml` or `setup.py`.
    - "node"    – presence of `package.json`.
    - "react"   – a Node project containing a `src` folder with `.jsx`/`.tsx` files.
    - "fastapi" – a Python project containing `fastapi` import in any `.py` file.
    - "django"  – a Python project containing `django` import.
    """
    projects: Dict[Path, List[str]] = {}
    for dirpath, _, _ in os.walk(root_path):
        dir_path = Path(dirpath)
        types: List[str] = []
        if _has_file(dir_path, "requirements.txt") or _has_file(dir_path, "pyproject.toml") or _has_file(dir_path, "setup.py"):
            types.append("python")
        if _has_file(dir_path, "package.json"):
            types.append("node")
            # Detect React by presence of .jsx/.tsx files in src
            src_dir = dir_path / "src"
            if src_dir.is_dir():
                for f in src_dir.rglob("*.jsx"):
                    types.append("react")
                    break
                else:
                    for f in src_dir.rglob("*.tsx"):
                        types.append("react")
                        break
        # Simple content scan for fastapi/django imports (only if python detected)
        if "python" in types:
            for py_file in dir_path.rglob("*.py"):
                try:
                    text = py_file.read_text(encoding="utf-8")
                except Exception:
                    continue
                if "import fastapi" in text or "from fastapi" in text:
                    types.append("fastapi")
                if "import django" in text or "from django" in text:
                    types.append("django")
        if types:
            projects[dir_path] = list(set(types))
    return projects


def _run_subprocess(cmd: List[str], cwd: Path) -> str:
    """Run a command safely, return stdout or raise on error."""
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command {' '.join(cmd)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def run_lint(project_path: Path, project_type: str) -> str:
    """Run a lightweight lint for the given project.

    For Python projects we use `flake8` if available, otherwise a simple
    `python -m py_compile` check. For Node projects we use `npm run lint` if a
    script is defined, otherwise we return a placeholder message.
    """
    if project_type == "python":
        # Prefer flake8, fall back to py_compile of all .py files
        try:
            return _run_subprocess(["flake8", "."], cwd=project_path)
        except Exception:
            # Simple compile check
            msgs = []
            for py in project_path.rglob("*.py"):
                try:
                    subprocess.run(["python", "-m", "py_compile", str(py)], check=True, capture_output=True)
                except subprocess.CalledProcessError as e:
                    msgs.append(f"Compile error in {py}: {e.stderr.decode().strip()}")
            return "\n".join(msgs) if msgs else "Python lint passed (py_compile)"
    elif project_type == "node":
        pkg_json = project_path / "package.json"
        if not pkg_json.exists():
            return "No package.json – cannot lint Node project."
        # Check if a lint script exists
        try:
            import json
            pkg = json.loads(pkg_json.read_text())
            scripts = pkg.get("scripts", {})
            if "lint" in scripts:
                return _run_subprocess(["npm", "run", "lint"], cwd=project_path)
        except Exception:
            pass
        return "Node lint placeholder – no lint script defined."
    else:
        return f"Lint not implemented for project type '{project_type}'."
