import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
import subprocess
import sys
import tempfile
from threading import Thread
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

with patch.dict(os.environ, {"BASE_URL": "http://127.0.0.1:1/v1", "API_KEY": "test"}):
    import loop
import benchmark


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.repo / "module.py").write_text("value = 1\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "module.py"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=Test", "-c", "user.email=test@example.org",
                        "commit", "-qm", "base"], check=True)
        self.base = subprocess.check_output(["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True).strip()
        self.issue = Path(self.temp.name) / "issue.txt"
        self.issue.write_text("Change the value to 2.", encoding="utf-8")
        self.output = Path(self.temp.name) / "prediction.jsonl"

    def test_dirty_or_wrong_commit_refused_before_model_call(self):
        (self.repo / "module.py").write_text("value = 2\n", encoding="utf-8")
        with patch.object(benchmark, "ALLOWED_DIR", self.repo), patch.object(benchmark, "run_turn") as turn:
            with self.assertRaisesRegex(ValueError, "clean"):
                benchmark.run_instance(self.repo, self.issue, self.base, "task-1", "base-model", self.output)
        turn.assert_not_called()
        self.assertFalse(self.output.exists())
        (self.repo / "module.py").write_text("value = 1\n", encoding="utf-8")
        with patch.object(benchmark, "ALLOWED_DIR", self.repo):
            with self.assertRaisesRegex(ValueError, "base commit"):
                benchmark.run_instance(self.repo, self.issue, "0" * 40, "task-1", "base-model", self.output)

    def test_explicit_model_and_isolated_tools_generate_prediction(self):
        def fake_turn(messages, issue, **kwargs):
            self.assertEqual(issue, "Change the value to 2.")
            self.assertEqual(kwargs["model_name"], "base-model")
            self.assertEqual(kwargs["max_tool_rounds"], 20)
            self.assertNotIn("create_memory", [t["function"]["name"] for t in kwargs["tools"]])
            (self.repo / "module.py").write_text("value = 2\n", encoding="utf-8")
            kwargs["emit"]("assistant", "Changed the file")

        with patch.object(benchmark, "run_turn", side_effect=fake_turn), patch.object(
                benchmark, "ALLOWED_DIR", self.repo), patch.object(
                benchmark, "client", SimpleNamespace(models=SimpleNamespace(list=Mock(return_value=SimpleNamespace(data=[SimpleNamespace(id="base-model")]))))):
            benchmark.run_instance(self.repo, self.issue, self.base, "task-1", "base-model", self.output)
        prediction = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(prediction["instance_id"], "task-1")
        self.assertEqual(prediction["model_name_or_path"], "base-model")
        self.assertIn("+value = 2", prediction["model_patch"])
        self.assertNotIn("Changed the file", prediction["model_patch"])

    def test_model_cannot_change_base_commit_before_patch_capture(self):
        def fake_turn(*args, **kwargs):
            (self.repo / "module.py").write_text("value = 2\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(self.repo), "add", "module.py"], check=True)
            subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=Test",
                            "-c", "user.email=test@example.org", "commit", "-qm", "oops"], check=True)
        server = SimpleNamespace(models=SimpleNamespace(list=Mock(
            return_value=SimpleNamespace(data=[SimpleNamespace(id="base-model")]))))
        with patch.object(benchmark, "ALLOWED_DIR", self.repo), patch.object(
                benchmark, "client", server), patch.object(benchmark, "run_turn", side_effect=fake_turn):
            with self.assertRaisesRegex(ValueError, "base commit changed"):
                benchmark.run_instance(self.repo, self.issue, self.base, "task-1", "base-model", self.output)
        self.assertFalse(self.output.exists())

    def test_workspace_env_is_used_by_every_file_tool(self):
        env = os.environ.copy()
        env["NANOHARNESS_WORKSPACE"] = str(self.repo)
        env["PYTHONPATH"] = str(ROOT / "src")
        code = "from tools import file_tools, dir_tools, shell_tools; print(file_tools.ALLOWED_DIR); print(dir_tools.ALLOWED_DIR); print(shell_tools.ALLOWED_DIR)"
        result = subprocess.run([sys.executable, "-c", code], env=env, cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(self.repo)] * 3)

    def test_benchmark_tool_round_limit_does_not_change_default(self):
        messages = loop.new_messages(tool_rounds=20)
        self.assertIn("20 tool rounds", messages[0]["content"])
        self.assertIn("5 tool rounds", loop.new_messages()[0]["content"])
        self.assertEqual(20, benchmark.DEFAULT_BENCHMARK_ROUNDS)

    def test_cli_runs_real_tool_loop_against_local_compatible_server(self):
        class Server(BaseHTTPRequestHandler):
            calls = 0

            def log_message(self, *args):
                pass

            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"data":[{"id":"local-model","object":"model"}]}')

            def do_POST(self):
                length = int(self.headers["Content-Length"])
                request = json.loads(self.rfile.read(length))
                assert request["model"] == "local-model"
                assert all("memory" not in tool["function"]["name"] for tool in request["tools"])
                Server.calls += 1
                if Server.calls == 1:
                    delta = {"tool_calls": [{"index": 0, "id": "call-1", "type": "function",
                                            "function": {"name": "edit_file", "arguments": json.dumps({
                                                "file_path": "module.py", "content": "value = 2\n"})}}]}
                    reason = "tool_calls"
                else:
                    assert request["messages"][-1]["tool_call_id"] == "call-1"
                    delta, reason = {"content": "Changed."}, "stop"
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                chunk = {"id": "chatcmpl-1", "object": "chat.completion.chunk", "created": 0,
                         "model": "local-model", "choices": [{"index": 0, "delta": delta,
                                                                "finish_reason": reason}]}
                self.wfile.write(b"data: " + json.dumps(chunk).encode() + b"\n\ndata: [DONE]\n\n")

        server = ThreadingHTTPServer(("127.0.0.1", 0), Server)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        env = os.environ.copy()
        env.update(BASE_URL=f"http://127.0.0.1:{server.server_port}/v1", API_KEY="local-test")
        result = subprocess.run([
            sys.executable, str(ROOT / "benchmark.py"), "--workspace", str(self.repo),
            "--issue-file", str(self.issue), "--base-commit", self.base,
            "--instance-id", "task-1", "--model", "local-model", "--output", str(self.output),
        ], cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Server.calls, 2)
        self.assertIn("+value = 2", json.loads(self.output.read_text())["model_patch"])


if __name__ == "__main__":
    unittest.main()
