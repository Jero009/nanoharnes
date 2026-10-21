"""Run one prepared SWE-bench issue through NanoHarness and save its patch."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

DEFAULT_BENCHMARK_ROUNDS = 20

# Configuration is read when the agent modules are imported. Set it first.
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True, help="Fresh checkout at the issue's base commit")
    parser.add_argument("--issue-file", type=Path, required=True, help="Problem statement only; keep outside workspace")
    parser.add_argument("--base-commit", required=True)
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--model", required=True, help="Exact model ID served by BASE_URL")
    parser.add_argument("--output", type=Path, required=True, help="New one-line SWE-bench prediction JSONL")
    parser.add_argument("--tool-rounds", type=int, default=DEFAULT_BENCHMARK_ROUNDS)
    args = parser.parse_args()
    os.environ["NANOHARNESS_WORKSPACE"] = str(args.workspace.resolve())

from config import ALLOWED_DIR
from loop import client, new_messages, run_turn
from tools import TOOLS, TOOL_FUNCTIONS


def git(workspace: Path, *arguments: str) -> str:
    return subprocess.check_output(["git", "-C", str(workspace), *arguments], text=True)


def run_instance(workspace: Path, issue_file: Path, base_commit: str, instance_id: str,
                 model: str, output: Path, tool_rounds: int = DEFAULT_BENCHMARK_ROUNDS) -> None:
    workspace = workspace.resolve(strict=True)
    if workspace != ALLOWED_DIR:
        raise ValueError("Workspace must match NANOHARNESS_WORKSPACE before importing agent tools.")
    if issue_file.resolve(strict=True).is_relative_to(workspace):
        raise ValueError("Issue file must be outside the workspace.")
    if tool_rounds < 1:
        raise ValueError("Tool rounds must be positive.")
    if not instance_id or not model or not base_commit:
        raise ValueError("Instance, model and base commit are required.")
    if git(workspace, "rev-parse", "--show-toplevel").strip() != str(workspace):
        raise ValueError("Workspace must be the root of an isolated Git checkout.")
    if git(workspace, "rev-parse", "HEAD").strip() != base_commit:
        raise ValueError("Workspace is not at the requested base commit.")
    if git(workspace, "status", "--porcelain", "--untracked-files=all").strip():
        raise ValueError("Workspace must be clean before running the benchmark.")
    issue = issue_file.read_text(encoding="utf-8")
    if not issue.strip():
        raise ValueError("Issue description is empty.")
    if output.exists():
        raise ValueError("Output already exists; use a new path for each run.")
    available = {entry.id for entry in client.models.list().data}
    if model not in available:
        raise ValueError(f"Model {model!r} is not loaded; available: {sorted(available)}")
    names = {name for name in TOOL_FUNCTIONS if not name.endswith("_memory") and name != "list_memory"}
    tools = [tool for tool in TOOLS if tool["function"]["name"] in names]
    functions = {name: TOOL_FUNCTIONS[name] for name in names}
    messages = new_messages(tool_rounds=tool_rounds)
    messages[0]["content"] += "\nFor this benchmark, do not use memory. Solve the issue in the existing repository; make a minimal code change."
    events = []
    run_turn(messages, issue, model_name=model, max_tool_rounds=tool_rounds,
             tools=tools, tool_functions=functions, approve=lambda _: True,
             emit=lambda kind, text: events.append((kind, text)) if kind == "status" else None)
    if git(workspace, "rev-parse", "HEAD").strip() != base_commit:
        raise ValueError("Workspace base commit changed during agent run.")
    # Intent-to-add includes newly created files without staging their contents.
    subprocess.run(["git", "-C", str(workspace), "add", "-N", "--all"], check=True)
    patch = git(workspace, "diff", "--binary", "HEAD", "--")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as file:
        file.write(json.dumps({"instance_id": instance_id, "model_name_or_path": model,
                               "model_patch": patch}, ensure_ascii=False) + "\n")
    print(f"{instance_id}: patch bytes={len(patch.encode('utf-8'))}; status={events}")


if __name__ == "__main__":
    run_instance(args.workspace, args.issue_file, args.base_commit, args.instance_id,
                 args.model, args.output, args.tool_rounds)
