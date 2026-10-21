"""Export only public task inputs from a pinned SWE-bench Lite split."""
import argparse
import json
from pathlib import Path


def load_dataset(*args, **kwargs):
    from datasets import load_dataset as load
    return load(*args, **kwargs)


def export(split: str, revision: str, output: Path) -> None:
    if split not in ("dev", "test"):
        raise ValueError("Choose dev or test.")
    if output.exists():
        raise ValueError("Output already exists.")
    rows = load_dataset("princeton-nlp/SWE-bench_Lite", split=split, revision=revision)
    fields = ("instance_id", "repo", "base_commit", "problem_statement")
    with output.open("x", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps({key: row[key] for key in fields}, ensure_ascii=False) + "\n")
    print(f"Exported {len(rows)} {split} instances from {revision} to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument("--revision", required=True, help="Pinned dataset Git commit")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export(args.split, args.revision, args.output)
