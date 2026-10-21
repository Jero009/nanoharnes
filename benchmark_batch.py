"""Run a pinned SWE-bench manifest through NanoHarness, one isolated issue at a time."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

SINGLE = Path(__file__).with_name("benchmark.py")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
IDENTIFIER = re.compile(r"[A-Za-z0-9_.-]+\Z")
COMMIT = re.compile(r"[0-9a-fA-F]{40}\Z")


def load_tasks(manifest: Path) -> list[dict]:
    tasks = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not tasks:
        raise ValueError("Manifest is empty.")
    seen = set()
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("Every task must be an object.")
        ident, repo, commit, issue = (task.get(key) for key in
                                      ("instance_id", "repo", "base_commit", "problem_statement"))
        if not isinstance(ident, str) or not IDENTIFIER.fullmatch(ident) or ident in (".", "..") or ident in seen:
            raise ValueError("Invalid or duplicate instance_id.")
        if not isinstance(repo, str) or not REPO.fullmatch(repo) or any(part in (".", "..") for part in repo.split("/")):
            raise ValueError("Invalid repo; expected GitHub owner/repo.")
        if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
            raise ValueError("Invalid base_commit; expected a 40-character Git SHA.")
        if not isinstance(issue, str) or not issue.strip():
            raise ValueError("Problem statement is empty.")
        seen.add(ident)
    return tasks


def run_batch(manifest: Path, run_dir: Path, model: str, tool_rounds: int = 20) -> None:
    tasks = load_tasks(manifest)
    if not model or tool_rounds < 1:
        raise ValueError("Model and positive tool-round limit are required.")
    if run_dir.exists():
        raise ValueError("Run directory already exists; use a new directory for each run.")
    run_dir.mkdir(parents=True)
    predictions = run_dir / "predictions.jsonl"
    failures = run_dir / "failures.jsonl"
    with predictions.open("x", encoding="utf-8") as results, failures.open("x", encoding="utf-8") as errors:
        for task in tasks:
            ident = task["instance_id"]
            with TemporaryDirectory(prefix="issue-", dir=run_dir) as disposable:
                root = Path(disposable)
                checkout = root / "checkout"
                checkout.mkdir()
                issue_file = root / "issue.txt"
                issue_file.write_text(task["problem_statement"], encoding="utf-8")
                output = root / "prediction.jsonl"
                try:
                    subprocess.run(["git", "-C", str(checkout), "init", "-q"], check=True)
                    subprocess.run(["git", "-C", str(checkout), "fetch", "--depth=1",
                                    f"https://github.com/{task['repo']}.git", task["base_commit"]],
                                   check=True, timeout=600)
                    subprocess.run(["git", "-C", str(checkout), "checkout", "-q", "--detach", "FETCH_HEAD"], check=True)
                    subprocess.run([sys.executable, str(SINGLE), "--workspace", str(checkout),
                                    "--issue-file", str(issue_file), "--base-commit", task["base_commit"],
                                    "--instance-id", ident, "--model", model, "--output", str(output),
                                    "--tool-rounds", str(tool_rounds)], check=True, timeout=3600)
                    prediction = json.loads(output.read_text(encoding="utf-8"))
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, ValueError) as error:
                    prediction = {"instance_id": ident, "model_name_or_path": model, "model_patch": ""}
                    errors.write(json.dumps({"instance_id": ident, "error": str(error)}) + "\n")
                    errors.flush()
                results.write(json.dumps(prediction, ensure_ascii=False) + "\n")
                results.flush()
                print(f"{ident}: {'patch' if prediction['model_patch'] else 'empty patch'}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--tool-rounds", type=int, default=20)
    args = parser.parse_args()
    run_batch(args.manifest, args.run_dir, args.model, args.tool_rounds)
