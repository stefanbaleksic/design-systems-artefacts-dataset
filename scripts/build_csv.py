#!/usr/bin/env python3
"""Rebuild the CSV files of the Design System Artefacts Dataset.

Input : source/artifact_snapshot.html  (the published page; its <script> block
        holds the rows as a JSON array named DATA)
Output: data/artefacts_as_published.csv  every row as published (225)

        data/duplicates_removed.csv      audit log of removed rows
        data/corrections.csv             audit log of changed values

Rules (documented in README.md, section "Processing"):
  1. A row is a duplicate when its repository URL (case-insensitive, without a
     trailing slash) already appeared earlier. The first row is kept.
  2. Clone-failed rows have placeholder values. semver_tags "0" and latest_tag ""
     on those rows are replaced by "not_checked" (missing is not zero or empty).

Standard library only. Deterministic: running twice gives identical files.

Usage:
    python3 scripts/build_csv.py            # writes into ./data
    python3 scripts/build_csv.py --root DIR # DIR must contain source/ and data/
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

# (key in the published JSON, column name in the CSV, description)
COLUMNS = [
    ("naziv", "name", "Name of the design system or UI library"),
    ("type", "type", "Organisation type: DS, UI biblioteka, DS (vlada/javni sektor)"),
    ("measured", "measured", "yes = repository cloned and measured; no (clone failed) = not measured"),
    ("token_format", "token_format", "Design-token format detected in the repository"),
    ("token_css_vars", "token_css_vars", "Count of CSS custom properties found in token files"),
    ("components_strict", "components_strict", "Component count, strict rule (manual rule of the measurement)"),
    ("component_dirs", "component_dirs", "Component directories (proxy; low validity, do not aggregate)"),
    ("stories_files", "stories_files", "Number of story files"),
    ("storybook", "storybook", "Storybook detected"),
    ("figma_code_connect_files", "code_connect_files", "Figma Code Connect files found"),
    ("test_files", "test_files", "Number of test files"),
    ("visual_regression", "visual_regression", "Visual regression tooling detected"),
    ("accessibility_testing", "a11y_dependencies", "Accessibility testing dependencies detected"),
    ("a11y_source_files", "a11y_source_files", "Source files that mention accessibility"),
    ("codeowners", "codeowners", "CODEOWNERS file present"),
    ("rfc_or_adr", "rfc_or_adr", "RFC or ADR records present"),
    ("frameworks", "frameworks", "UI frameworks detected"),
    ("npm_exports_field", "npm_exports_field", "npm package.json uses an exports field"),
    ("tags_semver", "semver_tags", "Count of semantic-version git tags"),
    ("latest_tag", "latest_tag", "Latest semantic-version tag"),
    ("repo", "repository", "GitHub repository URL"),
]
CSV_COLUMNS = [csv_name for _, csv_name, _ in COLUMNS]

PLACEHOLDER = "not_checked"


def load_rows(html_path: Path):
    """Return the DATA array embedded in the published page."""
    text = html_path.read_text(encoding="utf-8")
    match = re.search(r"const DATA=(\[.*?\]);\n", text, re.S)
    if not match:
        sys.exit(f"DATA array not found in {html_path}")
    return json.loads(match.group(1))


def repo_key(url: str) -> str:
    return url.strip().rstrip("/").lower()


def to_csv_row(raw: dict) -> dict:
    return {csv_name: raw[key] for key, csv_name, _ in COLUMNS}


def build(root: Path) -> dict:
    source = root / "source" / "artifact_snapshot.html"
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    raw_rows = load_rows(source)
    published = [to_csv_row(r) for r in raw_rows]

    corrections = []
    for idx, row in enumerate(published):
        if row["measured"] != "yes":
            for column, placeholder_values in (("semver_tags", {"0"}), ("latest_tag", {""})):
                if row[column] in placeholder_values:
                    corrections.append({
                        "published_index": idx,
                        "name": row["name"],
                        "column": column,
                        "published_value": row[column],
                        "new_value": PLACEHOLDER,
                        "reason": "Clone failed; the published value was a placeholder, not a measurement",
                    })
                    row[column] = PLACEHOLDER

    kept, removed, first_seen = [], [], {}
    for idx, row in enumerate(published):
        key = repo_key(row["repository"])
        if key in first_seen:
            kept_idx = first_seen[key]
            removed.append({
                "published_index": idx,
                "removed_name": row["name"],
                "removed_repository": row["repository"],
                "kept_published_index": kept_idx,
                "kept_name": published[kept_idx]["name"],
                "reason": "Same repository URL as an earlier row",
            })
        else:
            first_seen[key] = idx
            kept.append(row)

    def write(path: Path, columns, rows):
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    write(data_dir / "artefacts_as_published.csv", CSV_COLUMNS, published)
    write(data_dir / "artefacts_snapshot_deduped.csv", CSV_COLUMNS, kept)
    write(data_dir / "duplicates_removed.csv",
          ["published_index", "removed_name", "removed_repository",
           "kept_published_index", "kept_name", "reason"], removed)
    write(data_dir / "corrections.csv",
          ["published_index", "name", "column", "published_value", "new_value", "reason"],
          corrections)

    return {"published": len(published), "kept": len(kept),
            "removed": len(removed), "corrected": len(corrections)}


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent,
                        help="package root (default: parent of scripts/)")
    args = parser.parse_args()
    counts = build(args.root)
    print("published rows:", counts["published"])
    print("rows after duplicate removal:", counts["kept"])
    print("duplicate rows removed:", counts["removed"])
    print("values corrected:", counts["corrected"])


if __name__ == "__main__":
    main()
