import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from tools import dir_tools, file_tools, shell_tools

class ToolTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)

        # Redirect every tool module to this disposable workspace.
        self.original_file_workspace = file_tools.ALLOWED_DIR
        self.original_dir_workspace = dir_tools.ALLOWED_DIR
        self.original_shell_workspace = shell_tools.ALLOWED_DIR
        self.original_max_output = shell_tools.MAX_OUTPUT_CHARS

        file_tools.ALLOWED_DIR = self.workspace
        dir_tools.ALLOWED_DIR = self.workspace
        shell_tools.ALLOWED_DIR = self.workspace
        shell_tools.MAX_OUTPUT_CHARS = 100

    def tearDown(self):
        file_tools.ALLOWED_DIR = self.original_file_workspace
        dir_tools.ALLOWED_DIR = self.original_dir_workspace
        shell_tools.ALLOWED_DIR = self.original_shell_workspace
        shell_tools.MAX_OUTPUT_CHARS = self.original_max_output
        self.temp_dir.cleanup()

    def test_create_file_creates_inside_workspace(self):
        result = file_tools.create_file("notes/today.txt", "hello")

        self.assertEqual(result, "File created.")
        self.assertEqual(
            (self.workspace / "notes" / "today.txt").read_text(encoding="utf-8"),
            "hello",
        )

    def test_create_file_rejects_path_traversal(self):
        result = file_tools.create_file("../outside.txt", "nope")

        self.assertIn("outside the allowed workspace", result)
        self.assertFalse((self.workspace.parent / "outside.txt").exists())

    def test_create_file_rejects_existing_file(self):
        file_tools.create_file("note.txt", "first")

        result = file_tools.create_file("note.txt", "second")

        self.assertEqual(result, "Error: File already exists.")
        self.assertEqual(
            (self.workspace / "note.txt").read_text(encoding="utf-8"),
            "first",
        )

    def test_read_file_returns_content(self):
        (self.workspace / "note.txt").write_text("hello", encoding="utf-8")

        result = file_tools.read_file("note.txt")

        self.assertEqual(result, "hello")

    def test_read_file_rejects_path_traversal(self):
        result = file_tools.read_file("../.env")

        self.assertIn("outside the allowed workspace", result)

    def test_read_file_rejects_missing_file(self):
        result = file_tools.read_file("missing.txt")

        self.assertIn("not found", result)

    def test_read_file_rejects_directory(self):
        (self.workspace / "folder").mkdir()

        result = file_tools.read_file("folder")

        self.assertIn("is not a file", result)

    def test_read_file_rejects_large_file(self):
        file_path = self.workspace / "large.txt"
        file_path.write_text(
            "x" * (file_tools.MAX_FILE_SIZE_BYTES + 1),
            encoding="utf-8",
        )

        result = file_tools.read_file("large.txt")

        self.assertIn("File is too large", result)

    def test_read_file_rejects_non_utf8_file(self):
        (self.workspace / "binary.bin").write_bytes(b"\xff\xfe")

        result = file_tools.read_file("binary.bin")

        self.assertIn("not a UTF-8 text file", result)

    def test_edit_file_appends_content(self):
        file_tools.create_file("notes.txt", "first\n")

        result = file_tools.edit_file(
            "notes.txt",
            "second\n",
            mode="append",
        )

        self.assertEqual(result, "File updated (append mode).")
        self.assertEqual(
            (self.workspace / "notes.txt").read_text(encoding="utf-8"),
            "first\nsecond\n",
        )

    def test_edit_file_rejects_invalid_mode(self):
        file_tools.create_file("notes.txt", "hello")

        result = file_tools.edit_file(
            "notes.txt",
            "new content",
            mode="replace",
        )

        self.assertIn("Invalid mode 'replace'", result)
        self.assertEqual(
            (self.workspace / "notes.txt").read_text(encoding="utf-8"),
            "hello",
        )

    def test_delete_file_keeps_file_when_user_denies(self):
        file_tools.create_file("keep.txt", "important")

        confirm = Mock(return_value=False)
        result = file_tools.delete_file("keep.txt", approve=confirm)

        self.assertEqual(result, "Action canceled: User denied deletion request.")
        self.assertTrue((self.workspace / "keep.txt").exists())
        confirm.assert_called_once()

    def test_delete_file_removes_file_when_user_approves(self):
        file_tools.create_file("remove.txt", "temporary")

        confirm = Mock(return_value=True)
        result = file_tools.delete_file("remove.txt", approve=confirm)

        self.assertEqual(result, "File deleted: remove.txt")
        self.assertFalse((self.workspace / "remove.txt").exists())
        confirm.assert_called_once()

    def test_rename_file_moves_file(self):
        file_tools.create_file("old.txt", "hello")

        result = file_tools.rename_file("old.txt", "nested/new.txt")

        self.assertEqual(result, "File renamed: old.txt -> nested/new.txt")
        self.assertFalse((self.workspace / "old.txt").exists())
        self.assertEqual(
            (self.workspace / "nested" / "new.txt").read_text(encoding="utf-8"),
            "hello",
        )

    def test_rename_file_rejects_existing_destination(self):
        file_tools.create_file("source.txt", "source")
        file_tools.create_file("target.txt", "target")

        result = file_tools.rename_file("source.txt", "target.txt")

        self.assertIn("already exists", result)
        self.assertTrue((self.workspace / "source.txt").exists())
        self.assertEqual(
            (self.workspace / "target.txt").read_text(encoding="utf-8"),
            "target",
        )

    def test_rename_file_rejects_destination_traversal(self):
        file_tools.create_file("source.txt", "source")

        result = file_tools.rename_file("source.txt", "../outside.txt")

        self.assertIn("outside the allowed workspace", result)
        self.assertTrue((self.workspace / "source.txt").exists())

    def test_get_file_length_reports_lines_and_size(self):
        file_tools.create_file("note.txt", "one\ntwo\nthree\n")

        result = file_tools.get_file_length("note.txt")

        self.assertIn("3 lines", result)
        self.assertIn("14 B", result)

    def test_get_file_length_rejects_directory(self):
        (self.workspace / "folder").mkdir()

        result = file_tools.get_file_length("folder")

        self.assertIn("is not a file", result)

    def test_get_file_length_rejects_non_utf8_file(self):
        (self.workspace / "binary.bin").write_bytes(b"\xff\xfe")

        result = file_tools.get_file_length("binary.bin")

        self.assertIn("not a UTF-8 text file", result)

    def test_pwd_returns_workspace_path(self):
        self.assertEqual(dir_tools.pwd(), str(self.workspace))

    def test_ls_lists_created_file(self):
        file_tools.create_file("test.txt", "hello")

        result = dir_tools.ls()

        self.assertEqual(result, "test.txt")

    def test_ls_rejects_missing_directory(self):
        result = dir_tools.ls("missing")

        self.assertIn("not found", result)

    def test_ls_rejects_file_path(self):
        (self.workspace / "note.txt").write_text("hello", encoding="utf-8")

        result = dir_tools.ls("note.txt")

        self.assertIn("is not a directory", result)

    def test_mkdir_creates_nested_directory(self):
        result = dir_tools.mkdir("projects/nanoharnes")

        self.assertEqual(result, "Directory created.")
        self.assertTrue(
            (self.workspace / "projects" / "nanoharnes").is_dir()
        )

    def test_mkdir_rejects_path_traversal(self):
        result = dir_tools.mkdir("../outside")

        self.assertIn("outside the allowed workspace", result)
        self.assertFalse((self.workspace.parent / "outside").exists())

    def test_shell_runs_inside_workspace(self):
        confirm = Mock(return_value=True)
        result = shell_tools.execute_command("pwd", approve=confirm)

        self.assertIn("/workspace", result)
        confirm.assert_called_once()

    def test_shell_can_create_workspace_file(self):
        confirm = Mock(return_value=True)
        result = shell_tools.execute_command("touch created-by-shell.txt", approve=confirm)

        self.assertIn("Exit Code: 0", result)
        self.assertTrue((self.workspace / "created-by-shell.txt").exists())
        confirm.assert_called_once()

    def test_shell_output_is_truncated(self):
        confirm = Mock(return_value=True)
        result = shell_tools.execute_command(
            "python3 -c \"print('x' * 500)\"", approve=confirm
        )

        self.assertIn("[TRUNCATED:", result)
        self.assertLessEqual(len(result), 200)
        confirm.assert_called_once()

    def test_shell_does_not_run_when_user_denies(self):
        confirm = Mock(return_value=False)
        result = shell_tools.execute_command(
            "touch should-not-exist.txt", approve=confirm
        )

        self.assertFalse(
            (self.workspace / "should-not-exist.txt").exists()
        )
        self.assertIn("denied", result.lower())
        confirm.assert_called_once()

    def test_shell_cannot_delete_without_approval(self):
        target = self.workspace / "protected.txt"
        target.write_text("keep me", encoding="utf-8")

        confirm = Mock(return_value=False)
        result = shell_tools.execute_command("rm protected.txt", approve=confirm)

        self.assertTrue(target.exists())
        self.assertIn("denied", result.lower())
        confirm.assert_called_once()
    def test_read_lines_returns_requested_range(self):
        (self.workspace / "lines.txt").write_text(
            "one\ntwo\nthree\nfour\nfive\n",
            encoding="utf-8",
        )
        result = file_tools.read_lines(
            "lines.txt",
            start_line=2,
            line_count=3,
        )
        self.assertEqual(result, "two\nthree\nfour\n")
    def test_read_lines_rejects_path_traversal(self):
        result = file_tools.read_lines(
            "../secret.txt",
            start_line=1,
            line_count=1,
        )
        self.assertIn("outside the allowed workspace", result)
    def test_read_lines_rejects_invalid_start_line(self):
        (self.workspace / "lines.txt").write_text(
            "one\ntwo\n",
            encoding="utf-8",
        )
        result = file_tools.read_lines(
            "lines.txt",
            start_line=0,
            line_count=1,
        )
        self.assertIn("start_line must be at least 1", result)
    def test_read_lines_rejects_invalid_line_count(self):
        (self.workspace / "lines.txt").write_text(
            "one\ntwo\n",
            encoding="utf-8",
        )
        zero_result = file_tools.read_lines(
            "lines.txt",
            start_line=1,
            line_count=0,
        )
        too_many_result = file_tools.read_lines(
            "lines.txt",
            start_line=1,
            line_count=201,
        )
        self.assertIn("line_count must be at least 1", zero_result)
        self.assertIn("line_count cannot exceed 200", too_many_result)
    def test_read_lines_rejects_non_utf8_file(self):
        (self.workspace / "binary.bin").write_bytes(b"\xff\xfe")
        result = file_tools.read_lines(
            "binary.bin",
            start_line=1,
            line_count=1,
        )
        self.assertIn("not a UTF-8 text file", result)
    def test_read_lines_rejects_oversized_output(self):
        original_max_output = file_tools.MAX_OUTPUT_CHARS
        file_tools.MAX_OUTPUT_CHARS = 10
        try:
            (self.workspace / "large-lines.txt").write_text(
                "this line is too long\n",
                encoding="utf-8",
            )
            result = file_tools.read_lines(
                "large-lines.txt",
                start_line=1,
                line_count=1,
            )
            self.assertIn("output limit", result)
        finally:
            file_tools.MAX_OUTPUT_CHARS = original_max_output

if __name__ == "__main__":
    unittest.main()