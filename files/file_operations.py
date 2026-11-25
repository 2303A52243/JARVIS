"""Safe file operations for JARVIS.

Every operation validates that source and destination paths are inside the
authorized folder list before performing any action.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from files.folder_permissions import require_authorized


def copy_file(src_path: str, dest_path: str) -> str:
    """Copy a file from *src_path* to *dest_path*.

    Both paths must be inside authorized folders.
    Returns the destination path as a string on success.
    """
    src = require_authorized(src_path)
    # Destination parent must also be authorized
    dest = Path(dest_path).resolve()
    require_authorized(dest.parent if dest.parent.exists() else dest.parent)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), str(dest))
    return str(dest)


def move_file(src_path: str, dest_path: str) -> str:
    """Move a file from *src_path* to *dest_path*.

    Both paths must be inside authorized folders.
    Returns the destination path as a string on success.
    """
    src = require_authorized(src_path)
    dest = Path(dest_path).resolve()
    require_authorized(dest.parent if dest.parent.exists() else dest.parent)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    return str(dest)


def rename_file(src_path: str, new_path: str) -> str:
    """Rename (or move) a file.

    Equivalent to move_file; kept as a separate entry point for semantic clarity.
    """
    return move_file(src_path, new_path)


def delete_file(path: str) -> None:
    """Delete a single file.

    The path must be inside an authorized folder.
    """
    target = require_authorized(path)
    if not target.is_file():
        raise FileNotFoundError(f"File not found: {target}")
    target.unlink()


def create_file(path: str, content: str = "", overwrite: bool = False) -> str:
    """Create a new text file at *path* with optional *content*.

    Args:
        path:      Absolute path for the new file (must be in authorized folders).
        content:   Text content to write.
        overwrite: If False and the file already exists, raises FileExistsError.

    Returns:
        The resolved path string.
    """
    target = Path(path).resolve()
    require_authorized(target.parent)
    if target.exists() and not overwrite:
        raise FileExistsError(f"File already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return str(target)
