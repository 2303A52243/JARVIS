"""Tests for file management utilities.

Uses a temporary directory to avoid touching real user data.
Patches the global settings so only the temp directory is authorized.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


def _make_settings(authorized_folder: Path):
    """Create a mock settings object that authorizes only the given folder."""
    settings = MagicMock()
    settings.jarvis_authorized_folders = [authorized_folder]
    return settings


@pytest.fixture()
def workspace():
    """Temporary workspace with a few test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        (base / "notes.txt").write_text("hello world")
        (base / "data.csv").write_text("col1,col2\n1,2\n3,4")
        (base / "script.py").write_text("print('hello')")
        sub = base / "sub"
        sub.mkdir()
        (sub / "readme.md").write_text("# README")
        yield base


# ---------------------------------------------------------------------------
# folder_permissions
# ---------------------------------------------------------------------------
class TestFolderPermissions:
    def test_inside_is_authorized(self, workspace):
        with patch("files.folder_permissions._authorized_folders", return_value=[workspace]):
            from files.folder_permissions import is_path_authorized
            assert is_path_authorized(workspace / "notes.txt")

    def test_outside_is_denied(self, workspace):
        outside = Path(tempfile.gettempdir()) / "outside_jarvis_test.txt"
        outside.write_text("secret")
        try:
            with patch("files.folder_permissions._authorized_folders", return_value=[workspace]):
                from files.folder_permissions import is_path_authorized
                assert not is_path_authorized(outside)
        finally:
            outside.unlink(missing_ok=True)

    def test_require_authorized_raises(self, workspace):
        outside = Path(tempfile.gettempdir()) / "not_allowed.txt"
        with patch("files.folder_permissions._authorized_folders", return_value=[workspace]):
            from files.folder_permissions import require_authorized
            with pytest.raises(PermissionError):
                require_authorized(outside)


# ---------------------------------------------------------------------------
# file_search
# ---------------------------------------------------------------------------
class TestFileSearch:
    def _search(self, workspace, query, max_depth=5):
        import files.file_search as fs_module
        original = fs_module.get_settings
        try:
            fs_module.get_settings = lambda: _make_settings(workspace)
            return fs_module.search_files(query=query, max_depth=max_depth)
        finally:
            fs_module.get_settings = original

    def test_search_by_name(self, workspace):
        results = self._search(workspace, "notes")
        assert any("notes.txt" in r for r in results)

    def test_search_by_extension(self, workspace):
        results = self._search(workspace, ".py")
        assert any("script.py" in r for r in results)

    def test_search_empty_returns_all(self, workspace):
        results = self._search(workspace, "")
        assert len(results) >= 4  # 3 root + 1 sub

    def test_max_depth_limits_results(self, workspace):
        # At depth 0 we should not descend into sub/
        results = self._search(workspace, "", max_depth=1)
        # sub/readme.md should not appear
        assert not any("readme.md" in r for r in results)


# ---------------------------------------------------------------------------
# file_operations
# ---------------------------------------------------------------------------
class TestFileOperations:
    def _patch(self, workspace):
        return patch("files.folder_permissions._authorized_folders", return_value=[workspace])

    def test_copy_file(self, workspace):
        src = str(workspace / "notes.txt")
        dest = str(workspace / "notes_copy.txt")
        with self._patch(workspace):
            from files.file_operations import copy_file
            result = copy_file(src, dest)
        assert Path(result).exists()
        assert Path(src).exists()  # original still present

    def test_move_file(self, workspace):
        src = str(workspace / "data.csv")
        dest = str(workspace / "sub" / "data_moved.csv")
        with self._patch(workspace):
            from files.file_operations import move_file
            result = move_file(src, dest)
        assert Path(result).exists()
        assert not Path(src).exists()

    def test_rename_file(self, workspace):
        src = str(workspace / "script.py")
        new = str(workspace / "renamed_script.py")
        with self._patch(workspace):
            from files.file_operations import rename_file
            result = rename_file(src, new)
        assert Path(result).exists()
        assert not Path(src).exists()

    def test_delete_file(self, workspace):
        target = workspace / "notes.txt"
        with self._patch(workspace):
            from files.file_operations import delete_file
            delete_file(str(target))
        assert not target.exists()

    def test_copy_outside_raises(self, workspace):
        src = str(workspace / "notes.txt")
        dest = str(Path(tempfile.gettempdir()) / "sneaky_copy.txt")
        with self._patch(workspace):
            from files.file_operations import copy_file
            with pytest.raises(PermissionError):
                copy_file(src, dest)

    def test_create_file(self, workspace):
        path = str(workspace / "new_file.txt")
        with self._patch(workspace):
            from files.file_operations import create_file
            result = create_file(path, content="created by JARVIS")
        assert Path(result).read_text() == "created by JARVIS"

    def test_create_file_no_overwrite(self, workspace):
        path = str(workspace / "notes.txt")  # already exists
        with self._patch(workspace):
            from files.file_operations import create_file
            with pytest.raises(FileExistsError):
                create_file(path, overwrite=False)


# ---------------------------------------------------------------------------
# document_parser
# ---------------------------------------------------------------------------
class TestDocumentParser:
    def test_parse_txt(self, workspace):
        from files.document_parser import parse_document
        text = parse_document(str(workspace / "notes.txt"))
        assert "hello world" in text

    def test_parse_csv(self, workspace):
        from files.document_parser import parse_document
        text = parse_document(str(workspace / "data.csv"))
        assert "col1" in text
        assert "col2" in text

    def test_parse_md(self, workspace):
        from files.document_parser import parse_document
        text = parse_document(str(workspace / "sub" / "readme.md"))
        assert "README" in text

    def test_parse_unsupported(self, workspace):
        unsupported = workspace / "file.bin"
        unsupported.write_bytes(b"\x00\x01\x02")
        from files.document_parser import parse_document
        with pytest.raises(ValueError):
            parse_document(str(unsupported))

    def test_parse_nonexistent(self, workspace):
        from files.document_parser import parse_document
        with pytest.raises(FileNotFoundError):
            parse_document(str(workspace / "doesnotexist.txt"))
