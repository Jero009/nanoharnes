import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ConnectionTests(unittest.TestCase):
    def test_missing_configuration_explains_required_names(self):
        env = os.environ.copy()
        env.pop("BASE_URL", None)
        env.pop("API_KEY", None)
        env["PYTHON_DOTENV_DISABLED"] = "1"
        env["PYTHONPATH"] = str(ROOT / "src")
        result = subprocess.run(
            [sys.executable, "-c", "import config.connection"],
            cwd=ROOT, env=env, capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BASE_URL", result.stderr)
        self.assertIn("API_KEY", result.stderr)
        self.assertIn("README", result.stderr)
        self.assertNotIn("KeyError", result.stderr)


if __name__ == "__main__":
    unittest.main()
