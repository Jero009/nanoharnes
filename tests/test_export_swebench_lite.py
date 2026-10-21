import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import export_swebench_lite


class ExportTests(unittest.TestCase):
    def test_manifest_does_not_include_answers_or_tests(self):
        row = {"instance_id": "org__repo-1", "repo": "org/repo", "base_commit": "a" * 40,
               "problem_statement": "Fix it", "patch": "SECRET_SOLUTION", "test_patch": "HIDDEN_TEST"}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "dev.jsonl"
            with patch.object(export_swebench_lite, "load_dataset", return_value=[row]):
                export_swebench_lite.export("dev", "pinned-revision", output)
            saved = json.loads(output.read_text())
            self.assertEqual(set(saved), {"instance_id", "repo", "base_commit", "problem_statement"})
            self.assertNotIn("SECRET_SOLUTION", output.read_text())


if __name__ == "__main__":
    unittest.main()
