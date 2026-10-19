import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class InstallScriptTests(unittest.TestCase):
    def test_installs_from_another_directory_without_touching_workspace(self):
        installer = PROJECT_ROOT / "install.sh"
        self.assertTrue(installer.is_file(), "install.sh is missing")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkout = root / "checkout"
            checkout.mkdir()
            shutil.copy2(installer, checkout / "install.sh")
            shutil.copy2(PROJECT_ROOT / ".env.example", checkout / ".env.example")
            (checkout / "workspace").mkdir()
            (checkout / "workspace" / "user.txt").write_text("keep", encoding="utf-8")
            bin_dir = root / "bin"
            bin_dir.mkdir()
            (bin_dir / "uv").write_text('#!/bin/sh\nprintf "%s" "$*" > "$UV_TEST_LOG"\n', encoding="utf-8")
            (bin_dir / "uv").chmod(0o755)
            (bin_dir / "bwrap").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            (bin_dir / "bwrap").chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
            env["UV_TEST_LOG"] = str(root / "uv-call")
            result = subprocess.run(["/bin/sh", str(checkout / "install.sh")],
                                    cwd=root, env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((root / "uv-call").read_text(encoding="utf-8"), "sync --frozen")
            self.assertEqual((checkout / ".env").read_bytes(),
                             (checkout / ".env.example").read_bytes())
            self.assertEqual((checkout / "workspace" / "user.txt").read_text(encoding="utf-8"), "keep")
            self.assertFalse((root / ".env").exists())
            (checkout / ".env").write_text("BASE_URL=custom\n", encoding="utf-8")
            again = subprocess.run(["/bin/sh", str(checkout / "install.sh")],
                                   cwd=root, env=env, text=True, capture_output=True)
            self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
            self.assertEqual((checkout / ".env").read_text(encoding="utf-8"), "BASE_URL=custom\n")
            self.assertEqual((checkout / "workspace" / "user.txt").read_text(encoding="utf-8"), "keep")


    def test_missing_uv_fails_before_creating_configuration(self):
        installer = PROJECT_ROOT / "install.sh"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            (bin_dir / "uname").symlink_to(shutil.which("uname"))
            env = os.environ.copy()
            env["PATH"] = str(bin_dir)
            checkout = root / "checkout"
            checkout.mkdir()
            shutil.copy2(installer, checkout / "install.sh")
            shutil.copy2(PROJECT_ROOT / ".env.example", checkout / ".env.example")
            result = subprocess.run(["/bin/sh", str(checkout / "install.sh")], cwd=root,
                                    env=env, text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Install uv first", result.stderr)
            self.assertFalse((checkout / ".env").exists())


if __name__ == "__main__":
    unittest.main()
