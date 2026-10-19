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

    def test_create_file_rejects_oversized_utf8_content_before_writing(self):
        with patch.object(file_tools, "MAX_FILE_SIZE_BYTES", 4):
            result = file_tools.create_file("nested/oversized.txt", "ééé")
        self.assertIn("too large", result.lower())
        self.assertFalse((self.workspace / "nested").exists())

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

    def test_read_file_bounds_bytes_if_file_grows_after_stat(self):
        (self.workspace / "growing.txt").write_bytes(b"12345")
        real_fstat = file_tools.os.fstat
        def old_size(fd):
            info = real_fstat(fd)
            return Mock(st_mode=info.st_mode, st_size=0)
        with patch.object(file_tools, "MAX_FILE_SIZE_BYTES", 4), patch.object(
            file_tools.os, "fstat", side_effect=old_size,
        ):
            result = file_tools.read_file("growing.txt")
        self.assertIn("too large", result.lower())

    def test_read_file_closes_descriptor_if_stat_fails(self):
        import os
        (self.workspace / "note.txt").write_text("safe", encoding="utf-8")
        descriptors = []
        def fail_stat(descriptor):
            descriptors.append(descriptor)
            raise OSError("injected stat failure")
        with patch.object(file_tools.os, "fstat", side_effect=fail_stat):
            result = file_tools.read_file("note.txt")
        self.assertIn("Error", result)
        self.assertEqual(len(descriptors), 1)
        with self.assertRaises(OSError):
            os.fstat(descriptors[0])

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

    def test_overwrite_write_failure_preserves_original_and_cleans_temporary_file(self):
        target = self.workspace / "notes.txt"
        target.write_text("ORIGINAL", encoding="utf-8")
        import tempfile
        original_tempfile = tempfile.NamedTemporaryFile
        class FailingTempFile:
            def __init__(self, **kwargs):
                self.file = original_tempfile(**kwargs)
                self.name = self.file.name
            def __enter__(self):
                self.file.__enter__()
                return self
            def __exit__(self, *args):
                return self.file.__exit__(*args)
            def write(self, content):
                self.file.write("PARTIAL")
                raise OSError("injected write failure")
        with patch.object(tempfile, "NamedTemporaryFile", FailingTempFile):
            result = file_tools.edit_file("notes.txt", "REPLACEMENT")
        self.assertIn("Error", result)
        self.assertEqual(target.read_text(encoding="utf-8"), "ORIGINAL")
        self.assertEqual(list(self.workspace.iterdir()), [target])

    def test_overwrite_replaces_file_successfully(self):
        target = self.workspace / "notes.txt"
        target.write_text("ORIGINAL", encoding="utf-8")
        self.assertEqual(file_tools.edit_file("notes.txt", "NEW"), "File updated (overwrite mode).")
        self.assertEqual(target.read_text(encoding="utf-8"), "NEW")

    def test_overwrite_write_only_file_does_not_require_read_permission(self):
        target = self.workspace / "write-only.txt"
        target.write_text("OLD", encoding="utf-8")
        target.chmod(0o200)
        self.assertEqual(file_tools.edit_file("write-only.txt", "NEW"),
                         "File updated (overwrite mode).")
        self.assertEqual(target.stat().st_mode & 0o777, 0o200)
        target.chmod(0o600)
        self.assertEqual(target.read_text(encoding="utf-8"), "NEW")

    def test_overwrite_preserves_existing_file_permissions(self):
        target = self.workspace / "notes.txt"
        target.write_text("ORIGINAL", encoding="utf-8")
        target.chmod(0o644)
        file_tools.edit_file("notes.txt", "NEW")
        self.assertEqual(target.stat().st_mode & 0o777, 0o644)

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

    def test_edit_rejects_oversized_overwrite_and_append_without_changing_file(self):
        target = self.workspace / "notes.txt"
        target.write_text("hello", encoding="utf-8")
        with patch.object(file_tools, "MAX_FILE_SIZE_BYTES", 6):
            self.assertIn("too large", file_tools.edit_file("notes.txt", "éééé").lower())
            self.assertIn("too large", file_tools.edit_file("notes.txt", "é", mode="append").lower())
        self.assertEqual(target.read_text(encoding="utf-8"), "hello")

    def test_delete_file_keeps_file_when_user_denies(self):
        file_tools.create_file("keep.txt", "important")

        confirm = Mock(return_value=False)
        result = file_tools.delete_file("keep.txt", approve=confirm)

        self.assertEqual(result, "Action canceled: User denied deletion request.")
        self.assertTrue((self.workspace / "keep.txt").exists())
        confirm.assert_called_once()

    def test_delete_file_approval_error_denies_without_deleting(self):
        target = self.workspace / "keep.txt"
        target.write_text("important", encoding="utf-8")
        result = file_tools.delete_file("keep.txt", approve=Mock(side_effect=RuntimeError("UI closed")))
        self.assertIn("denied", result.lower())
        self.assertTrue(target.exists())

    def test_delete_file_non_boolean_approval_denies(self):
        target = self.workspace / "keep.txt"
        target.write_text("important", encoding="utf-8")
        result = file_tools.delete_file("keep.txt", approve=lambda _: "yes")
        self.assertIn("denied", result.lower())
        self.assertTrue(target.exists())

    def test_delete_file_removes_file_when_user_approves(self):
        file_tools.create_file("remove.txt", "temporary")

        confirm = Mock(return_value=True)
        result = file_tools.delete_file("remove.txt", approve=confirm)

        self.assertEqual(result, "File deleted: remove.txt")
        self.assertFalse((self.workspace / "remove.txt").exists())
        confirm.assert_called_once()

    def test_delete_does_not_follow_changed_parent_after_approval(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            allowed = base / "allowed"
            nested = allowed / "nested"
            outside = base / "outside"
            nested.mkdir(parents=True)
            outside.mkdir()
            (nested / "note.txt").write_text("inside", encoding="utf-8")
            protected = outside / "note.txt"
            protected.write_text("outside", encoding="utf-8")

            def approve(_):
                nested.rename(allowed / "moved")
                nested.symlink_to(outside, target_is_directory=True)
                return True

            with patch.object(file_tools, "ALLOWED_DIR", allowed):
                file_tools.delete_file("nested/note.txt", approve=approve)
            self.assertEqual(protected.read_text(encoding="utf-8"), "outside")

    def test_file_and_directory_tools_reject_symlinks_to_outside(self):
        with tempfile.TemporaryDirectory() as root:
            outside = Path(root) / "outside"
            outside.mkdir()
            secret = outside / "secret.txt"
            secret.write_text("private", encoding="utf-8")
            (self.workspace / "external").symlink_to(outside, target_is_directory=True)
            (self.workspace / "file-link").symlink_to(secret)
            source = self.workspace / "source.txt"
            source.write_text("inside", encoding="utf-8")
            operations = [
                lambda: file_tools.read_file("external/secret.txt"),
                lambda: file_tools.read_file("file-link"),
                lambda: file_tools.create_file("external/new.txt", "no"),
                lambda: file_tools.edit_file("external/secret.txt", "no"),
                lambda: file_tools.edit_file("file-link", "no", mode="append"),
                lambda: file_tools.rename_file("source.txt", "external/new.txt"),
                lambda: file_tools.get_file_length("external/secret.txt"),
                lambda: file_tools.read_lines("external/secret.txt"),
                lambda: dir_tools.ls("external"),
                lambda: dir_tools.mkdir("external/new"),
            ]
            for operation in operations:
                with self.subTest(operation=operation):
                    result = operation()
                    self.assertIn("Error", result)
                    self.assertNotIn("private", result)
            self.assertEqual(secret.read_text(encoding="utf-8"), "private")
            self.assertEqual(source.read_text(encoding="utf-8"), "inside")
            self.assertFalse((outside / "new.txt").exists())
            self.assertFalse((outside / "new").exists())

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

    def test_shell_stops_process_when_output_limit_is_reached(self):
        result = shell_tools.execute_command(
            "python3 -c \"import sys,time; print('x'*1000000); "
            "sys.stdout.flush(); time.sleep(2); open('late.txt','w').write('ran')\"",
            approve=lambda _: True,
        )
        self.assertIn("[TRUNCATED:", result)
        self.assertFalse((self.workspace / "late.txt").exists())

    def test_shell_cannot_read_host_file_or_use_network(self):
        with tempfile.TemporaryDirectory() as outside_dir:
            outside = Path(outside_dir) / "host-secret.txt"
            outside.write_text("hidden", encoding="utf-8")
            result = shell_tools.execute_command(f"cat {outside}", approve=lambda _: True)
            self.assertNotIn("hidden", result)
            self.assertIn("Exit Code:", result)

        result = shell_tools.execute_command(
            "python3 -c 'import socket; socket.create_connection((\"1.1.1.1\", 53), timeout=2)'", approve=lambda _: True,
        )
        self.assertNotIn("Exit Code: 0", result)

    def test_shell_does_not_inherit_agent_secrets(self):
        with patch.dict("os.environ", {"NANOHARNESS_TEST_SECRET": "do-not-expose"}):
            result = shell_tools.execute_command(
                "python3 -c 'import os; print(os.getenv(\"NANOHARNESS_TEST_SECRET\", \"absent\"))'",
                approve=lambda _: True,
            )
        self.assertIn("absent", result)
        self.assertNotIn("do-not-expose", result)

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

    def test_shell_approval_error_denies_without_running(self):
        with patch.object(shell_tools.shutil, "which", return_value="/bin/bwrap"):
            result = shell_tools.execute_command(
                "touch should-not-exist.txt", approve=Mock(side_effect=RuntimeError("UI closed"))
            )
        self.assertIn("denied", result.lower())
        self.assertFalse((self.workspace / "should-not-exist.txt").exists())

    def test_shell_non_boolean_approval_denies(self):
        result = shell_tools.execute_command("touch should-not-exist.txt", approve=lambda _: "yes")
        self.assertIn("denied", result.lower())
        self.assertFalse((self.workspace / "should-not-exist.txt").exists())

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