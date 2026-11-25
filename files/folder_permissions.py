"""Folder permission enforcement for JARVIS file operations.

All file operations must stay within the authorized folder list defined in settings.
Any path outside the authorized folders is rejected.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union


def _authorized_folders():
    """Lazily import settings to avoid circular imports at module load time."""
    from app.config import get_settings
    return get_settings().jarvis_authorized_folders


def is_path_authorized(path: Union[str, Path]) -> bool:
    """Return True if *path* is located inside one of the authorized folders.

    The check is done against the resolved (absolute) path to prevent
    directory-traversal tricks using ``..`` or symlinks.
    """
    target = Path(path).resolve()
    for folder in _authorized_folders():
        try:
            target.relative_to(Path(folder).resolve())
            return True
        except ValueError:
            continue
    return False


def require_authorized(path: Union[str, Path]) -> Path:
    """Resolve *path* and raise PermissionError if it is not in the allow-list."""
    resolved = Path(path).resolve()
    if not is_path_authorized(resolved):
        raise PermissionError(
            f"Access denied: '{resolved}' is outside the authorized folders."
        )
    return resolved
