#!/usr/bin/env python3
"""Build the release CSV (data/artefacts.csv) from one evidence run.

Inputs:
  data/artefacts_snapshot_deduped.csv   the 220 rows as published, duplicates removed (from build_csv.py)
  evidence/<run>/<slug>.json            one file per repository with all measured values

Outputs:
  data/artefacts.csv               release values, 220 rows, columns in data_dictionary.csv order
  data/release_changes.csv         every value that differs from the published page (for audit)
  data/release_source.json         which evidence run the release was built from

Every measured column comes from the evidence file. Nothing is copied from the published page
except name, type and repository. A repository without evidence is an error, not a blank.

Usage:
    python3 scripts/release_from_evidence.py evidence/20261118T091307Z
"""
import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "measure"))
from collect import MEASURE_RULES  # noqa: E402

ROOT = HERE.parent
MEASURED_COLUMNS = list(MEASURE_RULES)  # same names as the CSV columns


def load_csv(path: Path):
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", type=Path, nargs="?",
                        help="evidence run folder; default: evidence_run named in data/release_source.json")
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    if args.run_dir is None:
        source = json.loads((args.data / "release_source.json").read_text(encoding="utf-8"))
        args.run_dir = ROOT / "evidence" / source["evidence_run"]

    base = load_csv(args.data / "artefacts_snapshot_deduped.csv")
    evidence = {}
    for path in sorted(args.run_dir.glob("*.json")):
        if path.name == "run.json":
            continue
        rec = json.loads(path.read_text(encoding="utf-8"))
        evidence[rec["repository"].lower().rstrip("/")] = rec

    missing = [r["name"] for r in base if r["repository"].lower().rstrip("/") not in evidence]
    if missing:
        sys.exit(f"no evidence for {len(missing)} repositories, e.g. {missing[:3]}")

    dictionary = [r["column"] for r in load_csv(args.data / "data_dictionary.csv")]
    release, changes = [], []
    for row in base:
        key = row["repository"].lower().rstrip("/")
        ev = evidence[key]
        out = {}
        for col in dictionary:
            if col in MEASURED_COLUMNS or col == "measured":
                out[col] = str(ev[col])
            else:
                out[col] = row[col]
        release.append(out)
        for col in dictionary:
            if col in ("name", "type", "repository") or col not in row:
                continue  # a column absent from the snapshot has no published value to compare with
            old = str(row[col])
            if old != out[col]:
                changes.append({"name": row["name"], "repository": row["repository"], "column": col,
                                "published": old, "release": out[col]})

    args.data.mkdir(parents=True, exist_ok=True)
    with (args.data / "artefacts.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=dictionary, lineterminator="\n")
        writer.writeheader()
        writer.writerows(release)
    with (args.data / "release_changes.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["name", "repository", "column", "published", "release"],
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(changes)
    (args.data / "release_source.json").write_text(json.dumps({
        "evidence_run": args.run_dir.name,
        "rows": len(release),
        "changed_values": len(changes),
        "rules": MEASURE_RULES,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"release rows: {len(release)}, values changed from page: {len(changes)}")


if __name__ == "__main__":
    main()
