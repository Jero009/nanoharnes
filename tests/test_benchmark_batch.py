import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import benchmark_batch


class BatchTests(unittest.TestCase):
    def test_batch_checks_manifest_before_creating_a_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "tasks.jsonl"
            manifest.write_text(json.dumps({"instance_id": "x", "repo": "org/repo",
                                            "base_commit": "bad", "problem_statement": "Fix it"}) + "\n")
            with self.assertRaisesRegex(ValueError, "base_commit"):
                benchmark_batch.run_batch(manifest, root / "run", "base-model")
            self.assertFalse((root / "run").exists())

    def test_batch_runs_fresh_checkout_per_task_and_merges_predictions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "tasks.jsonl"
            sha = "a" * 40
            manifest.write_text(json.dumps({"instance_id": "org__repo-1", "repo": "org/repo",
                                            "base_commit": sha, "problem_statement": "Fix bug"}) + "\n")
            commands = []
            def run(command, **kwargs):
                commands.append(command)
                if "benchmark.py" in str(command):
                    output = Path(command[command.index("--output") + 1])
                    output.write_text(json.dumps({"instance_id": "org__repo-1",
                                                  "model_name_or_path": "base-model",
                                                  "model_patch": "diff --git a/a b/a\n"}) + "\n")
                return subprocess.CompletedProcess(command, 0)
            with patch.object(benchmark_batch.subprocess, "run", side_effect=run):
                benchmark_batch.run_batch(manifest, root / "run", "base-model")
            self.assertTrue(any("--depth=1" in cmd and sha in cmd for cmd in commands))
            lines = (root / "run" / "predictions.jsonl").read_text().splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0])["instance_id"], "org__repo-1")
            with self.assertRaisesRegex(ValueError, "already exists"):
                benchmark_batch.run_batch(manifest, root / "run", "base-model")


if __name__ == "__main__":
    unittest.main()
