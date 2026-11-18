#!/usr/bin/env python3
"""Compare two evidence runs with each other (independent reproduction check). No network access.

Values are compared only where both runs measured the same commit. A difference where the commit
changed is reported as drift, not as a failure. A difference where the commit is the same is a
reproduction failure: the same code must give the same values.

Writes <run_b>/stability_vs_<run_a>.md and exits with status 1 on any same-commit difference.

Usage:
    python3 scripts/measure/compare_runs.py evidence/<run_a> evidence/<run_b>
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from collect import MEASURE_RULES  # noqa: E402

COLUMNS = list(MEASURE_RULES) + ["measured", "latest_tag"]


def load(run_dir: Path):
    out = {}
    for p in run_dir.glob("*.json"):
        if p.name == "run.json":
            continue
        rec = json.loads(p.read_text(encoding="utf-8"))
        out[rec["repository"].lower().rstrip("/")] = rec
    return out


def compare(a: dict, b: dict):
    """Return (same_commit_failures, drift_rows, repos_compared)."""
    failures, drift = [], []
    common = sorted(set(a) & set(b))
    for key in common:
        ra, rb = a[key], b[key]
        changed_commit = ra.get("commit") != rb.get("commit")
        for col in COLUMNS:
            if ra.get(col) == rb.get(col):
                continue
            row = {"name": ra["name"], "column": col, "run_a": ra.get(col), "run_b": rb.get(col)}
            (drift if changed_commit else failures).append(row)
    return failures, drift, len(common), sorted(set(a) ^ set(b))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_a", type=Path)
    parser.add_argument("run_b", type=Path)
    args = parser.parse_args()
    a, b = load(args.run_a), load(args.run_b)
    failures, drift, compared, only_one = compare(a, b)
    changed = sorted({r["name"] for r in drift})
    lines = [
        f"# Stability: {args.run_a.name} vs {args.run_b.name}",
        "",
        f"Repositories compared: {compared}. Present in one run only: {len(only_one)}.",
        f"Same commit, different value (reproduction failures): {len(failures)}.",
        f"Commit changed between runs (drift): {len(changed)} repositories, {len(drift)} values.",
        "",
    ]
    if failures:
        lines += ["## Reproduction failures", "", "| Repository | Column | Run A | Run B |", "|---|---|---|---|"]
        lines += [f"| {r['name']} | {r['column']} | {r['run_a']} | {r['run_b']} |" for r in failures]
    if drift:
        counts = Counter(r["column"] for r in drift)
        lines += ["## Drift (commit changed)", "", "| Column | Values |", "|---|---|"]
        lines += [f"| {c} | {n} |" for c, n in counts.most_common()]
        lines += ["", "Repositories: " + ", ".join(changed)]
    report = "\n".join(lines) + "\n"
    (args.run_b / f"stability_vs_{args.run_a.name}.md").write_text(report, encoding="utf-8")
    print(report)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
