#!/usr/bin/env python3
"""Compare one evidence run with the published release. No network access.

Reads evidence/<run>/*.json, checks that every repository of data/artefacts.csv has
an evidence file, compares each measured column with the published value, and writes:
    evidence/<run>/reproduction_report.md
    evidence/<run>/comparison.csv     one row per repository and column with the two values

Exit status 1 when evidence is missing for any repository, so missing data cannot pass silently.

Usage:
    python3 scripts/measure/run_compare_from_evidence.py evidence/20261118T100000Z
"""
import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from collect import MEASURE_RULES  # noqa: E402

PACKAGE_ROOT = HERE.parents[1]
COLUMNS = list(MEASURE_RULES)


def norm(value):
    return str(value).strip()


def load_published(path: Path):
    with path.open(encoding="utf-8", newline="") as fh:
        return {r["repository"].lower().rstrip("/"): r for r in csv.DictReader(fh)}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--data", type=Path, default=PACKAGE_ROOT / "data" / "artefacts.csv")
    args = parser.parse_args()

    published = load_published(args.data)
    header = next(iter(published.values())).keys() if published else []
    absent = [c for c in ["measured"] + COLUMNS if c not in header]
    if absent:
        sys.exit(f"dataset is missing columns needed for comparison: {absent}")
    records = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(args.run_dir.glob("*.json"))
               if p.name != "run.json"]
    by_repo = {r["repository"].lower().rstrip("/"): r for r in records}

    missing = sorted(set(published) - set(by_repo))
    extra = sorted(set(by_repo) - set(published))
    if missing:
        print(f"MISSING evidence for {len(missing)} repositories:", file=sys.stderr)
        for key in missing:
            print("  ", published[key]["name"], key, file=sys.stderr)

    comparison, agree_count = [], {c: [0, 0] for c in COLUMNS}
    for key in sorted(set(published) & set(by_repo)):
        pub, rec = published[key], by_repo[key]
        for col in ["measured"] + COLUMNS:
            if col == "measured":
                pub_val, new_val = pub["measured"], rec["measured"]
            else:
                pub_val, new_val = pub[col], rec[col]
            ok = norm(pub_val) == norm(new_val)
            if col in agree_count:
                agree_count[col][1] += 1
                agree_count[col][0] += int(ok)
            comparison.append({"name": pub["name"], "repository": pub["repository"], "column": col,
                               "published": pub_val, "evidence": new_val, "agree": "yes" if ok else "no"})

    with (args.run_dir / "comparison.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["name", "repository", "column", "published", "evidence", "agree"],
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(comparison)

    lines = [
        f"# Reproduction report: {args.run_dir.name}",
        "",
        f"Repositories in dataset: {len(published)}. With evidence: {len(set(published) & set(by_repo))}. "
        f"Missing evidence: {len(missing)}. Evidence without dataset row: {len(extra)}.",
        "",
        "| Column | Agrees | Rule status |",
        "|---|---|---|",
    ]
    for col in ["measured"] + COLUMNS:
        if col == "measured":
            ok = sum(c["agree"] == "yes" for c in comparison if c["column"] == "measured")
            total = sum(1 for c in comparison if c["column"] == "measured")
            status = "[documented] clone outcome"
        else:
            ok, total = agree_count[col]
            status = MEASURE_RULES[col].split("] ")[0].strip("[")
        lines.append(f"| {col} | {ok}/{total} | {status} |")
    report = "\n".join(lines) + "\n"
    (args.run_dir / "reproduction_report.md").write_text(report, encoding="utf-8")
    print(report)

    if missing:
        sys.exit(1)


if __name__ == "__main__":
    main()
