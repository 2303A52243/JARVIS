"""File search utilities for JARVIS.

Searches within authorized folders only.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

# Top-level import so the name is patchable in tests (patch 'files.file_search.get_settings')
from app.config import get_settings as get_settings  # noqa: PLC0414


def search_files(query: str, max_depth: int = 5) -> List[str]:
    """Search for files matching *query* (name substring or extension) in authorized folders.

    Args:
        query:     Case-insensitive substring to match against file names.
                   If the query starts with '.' it is treated as an extension filter.
        max_depth: Maximum directory depth to recurse into.

    Returns:
        A sorted list of absolute path strings for matching files.
    """
    authorized = get_settings().jarvis_authorized_folders

    results: List[str] = []
    query_lower = query.lower().strip()

    for root_folder in authorized:
        root = Path(root_folder).resolve()
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            # Enforce max_depth
            depth = len(Path(dirpath).relative_to(root).parts)
            if depth >= max_depth:
                dirnames.clear()
                continue
            for fname in filenames:
                if not query_lower:
                    results.append(os.path.join(dirpath, fname))
                elif query_lower.startswith("."):
                    if fname.lower().endswith(query_lower):
                        results.append(os.path.join(dirpath, fname))
                else:
                    if query_lower in fname.lower():
                        results.append(os.path.join(dirpath, fname))

    return sorted(results)
