"""Checks for the Design System Artefacts Dataset (release 1.0.0).

Run from the package root:
    python3 -m unittest discover -s tests -v

Standard library only. The tests check: file structure; the published page's numbers;
the snapshot-to-deduplicated step; the release file against its evidence run (value by value);
value rules; and that both builders are deterministic.
"""
import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SOURCE = ROOT / "source" / "artifact_snapshot.html"
sys.path.insert(0, str(ROOT / "scripts" / "measure"))
import collect  # noqa: E402

# Numbers stated on the published page (17 Nov 2026 snapshot, before cleaning).
PAGE_ROWS = 225
PAGE_MEASURED = 218
PAGE_TOKEN_FILES = 63   # token_format != "none detected", measured rows only
PAGE_STORYBOOK = 92
PAGE_CODE_CONNECT = 9
PAGE_A11Y_SOURCE = 107

# Snapshot step (scripts/build_csv.py).
SNAPSHOT_ROWS = 220
REMOVED_DUPLICATES = 5
PLACEHOLDER_CORRECTIONS = 14  # semver_tags and latest_tag for 7 failed clones

# Release (scripts/release_from_evidence.py), built from the evidence run named in data/release_source.json.
RELEASE_MEASURED = 213
RELEASE_TOKEN_FILES = 64
RELEASE_STORYBOOK = 86
RELEASE_CODE_CONNECT = 9
RELEASE_A11Y_CHECK = 98
RELEASE_SEMVER_REPOS = 162

NUMERIC = ["token_css_vars", "components_strict", "component_dirs", "stories_files",
           "code_connect_files", "test_files", "a11y_check_files", "semver_tags"]
CATEGORICAL = {
    "storybook": {"yes", "no", "not_checked"},
    "codeowners": {"yes", "no", "not_checked"},
    "rfc_or_adr": {"yes", "no", "not_checked"},
    "npm_exports_field": {"yes", "no", "not_checked"},
}
TYPES = {"DS", "UI biblioteka", "DS (vlada/javni sektor)"}
REPO_RE = re.compile(r"^https://github\.com/[^/\s]+/[^/\s]+$")


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def evidence_dir():
    release = json.loads((DATA / "release_source.json").read_text(encoding="utf-8"))
    return ROOT / "evidence" / release["evidence_run"]


class FileTests(unittest.TestCase):
    def test_required_files_exist(self):
        for name in ["artefacts.csv", "artefacts_as_published.csv", "artefacts_snapshot_deduped.csv",
                     "duplicates_removed.csv", "corrections.csv", "release_changes.csv",
                     "release_source.json", "data_dictionary.csv"]:
            self.assertTrue((DATA / name).is_file(), name)
        self.assertTrue(SOURCE.is_file())
        self.assertTrue(evidence_dir().is_dir(), "evidence run named in release_source.json is missing")

    def test_release_header_matches_dictionary(self):
        dictionary = [row["column"] for row in read_csv(DATA / "data_dictionary.csv")]
        with (DATA / "artefacts.csv").open(encoding="utf-8") as fh:
            self.assertEqual(next(csv.reader(fh)), dictionary)

    def test_dictionary_rules_match_collector(self):
        for row in read_csv(DATA / "data_dictionary.csv"):
            if row["column"] in collect.MEASURE_RULES:
                self.assertEqual(row["release_rule"], collect.MEASURE_RULES[row["column"]], row["column"])


class PublishedAndSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.published = read_csv(DATA / "artefacts_as_published.csv")
        self.snapshot = read_csv(DATA / "artefacts_snapshot_deduped.csv")
        self.removed = read_csv(DATA / "duplicates_removed.csv")
        self.corrections = read_csv(DATA / "corrections.csv")

    def test_published_row_count(self):
        self.assertEqual(len(self.published), PAGE_ROWS)

    def test_page_summary_numbers_reproduce_from_published(self):
        p = self.published
        measured = [r for r in p if r["measured"] == "yes"]
        self.assertEqual(len(measured), PAGE_MEASURED)
        self.assertEqual(sum(r["token_format"] != "none detected" for r in measured), PAGE_TOKEN_FILES)
        self.assertEqual(sum(r["storybook"] == "yes" for r in p), PAGE_STORYBOOK)
        self.assertEqual(sum(r["code_connect_files"] not in ("0", "not_checked") for r in p), PAGE_CODE_CONNECT)
        self.assertEqual(sum(r["a11y_source_files"] not in ("0", "not_checked") for r in p), PAGE_A11Y_SOURCE)

    def test_snapshot_counts(self):
        self.assertEqual(len(self.snapshot), SNAPSHOT_ROWS)
        self.assertEqual(len(self.published) - len(self.removed), len(self.snapshot))
        self.assertEqual(len(self.removed), REMOVED_DUPLICATES)
        self.assertEqual(len(self.corrections), PLACEHOLDER_CORRECTIONS)

    def test_corrections_only_touch_failed_rows(self):
        for c in self.corrections:
            row = self.published[int(c["published_index"])]
            self.assertNotEqual(row["measured"], "yes", row["name"])
            self.assertEqual(c["new_value"], "not_checked")


class ReleaseSummaryTests(unittest.TestCase):
    def setUp(self):
        self.release = read_csv(DATA / "artefacts.csv")

    def test_row_count(self):
        self.assertEqual(len(self.release), SNAPSHOT_ROWS)

    def test_release_summary_numbers(self):
        r = self.release
        measured = [x for x in r if x["measured"] == "yes"]
        self.assertEqual(len(measured), RELEASE_MEASURED)
        self.assertEqual(sum(x["token_format"] != "none detected" for x in measured), RELEASE_TOKEN_FILES)
        self.assertEqual(sum(x["storybook"] == "yes" for x in r), RELEASE_STORYBOOK)
        self.assertEqual(sum(x["code_connect_files"] not in ("0", "not_checked") for x in r), RELEASE_CODE_CONNECT)
        self.assertEqual(sum(x["a11y_check_files"] not in ("0", "not_checked") for x in r), RELEASE_A11Y_CHECK)
        self.assertEqual(sum(x["semver_tags"] not in ("0", "not_checked") for x in r), RELEASE_SEMVER_REPOS)


class UniquenessTests(unittest.TestCase):
    def setUp(self):
        self.release = read_csv(DATA / "artefacts.csv")

    def test_repository_unique_case_insensitive(self):
        keys = [r["repository"].strip().rstrip("/").lower() for r in self.release]
        self.assertEqual({k for k in keys if keys.count(k) > 1}, set())

    def test_name_unique_case_insensitive(self):
        names = [r["name"].strip().lower() for r in self.release]
        self.assertEqual({n for n in names if names.count(n) > 1}, set())

    def test_no_empty_names(self):
        self.assertTrue(all(r["name"].strip() for r in self.release))


class ValueRuleTests(unittest.TestCase):
    def setUp(self):
        self.release = read_csv(DATA / "artefacts.csv")

    def test_type_domain(self):
        self.assertEqual([r["name"] for r in self.release if r["type"] not in TYPES], [])

    def test_measured_domain(self):
        self.assertEqual([r["name"] for r in self.release
                          if r["measured"] not in ("yes", "no (clone failed)")], [])

    def test_repository_url_format(self):
        self.assertEqual([r["repository"] for r in self.release if not REPO_RE.match(r["repository"])], [])

    def test_measured_rows_have_numbers(self):
        for r in self.release:
            if r["measured"] == "yes":
                for col in NUMERIC:
                    self.assertRegex(r[col], r"^\d+$", f"{r['name']}.{col}")

    def test_failed_rows_are_not_checked_not_zero(self):
        for r in self.release:
            if r["measured"] != "yes":
                for col in NUMERIC + list(CATEGORICAL) + ["frameworks", "token_format", "latest_tag",
                                                          "visual_regression", "a11y_dependencies"]:
                    self.assertEqual(r[col], "not_checked", f"{r['name']}.{col}")

    def test_categorical_domains(self):
        for col, allowed in CATEGORICAL.items():
            self.assertEqual([r["name"] for r in self.release if r[col] not in allowed], [], col)

    def test_latest_tag_consistent_with_semver_count(self):
        for r in self.release:
            if r["latest_tag"] in ("", "not_checked"):
                self.assertIn(r["semver_tags"], ("0", "not_checked"), r["name"])
            if r["semver_tags"] not in ("0", "not_checked"):
                self.assertNotIn(r["latest_tag"], ("", "not_checked"), r["name"])

    def test_latest_tag_is_a_semver_tag(self):
        for r in self.release:
            if r["latest_tag"] not in ("", "not_checked"):
                self.assertIsNotNone(collect.semver_utils.parse(r["latest_tag"]), r["name"])


class ReleaseMatchesEvidenceTests(unittest.TestCase):
    """Every value in the release equals the value in the evidence file for that repository."""

    def test_each_value_equals_evidence(self):
        release = {r["repository"].lower().rstrip("/"): r for r in read_csv(DATA / "artefacts.csv")}
        files = [p for p in evidence_dir().glob("*.json") if p.name != "run.json"]
        self.assertEqual(len(files), len(release))
        for path in files:
            ev = json.loads(path.read_text(encoding="utf-8"))
            row = release[ev["repository"].lower().rstrip("/")]
            self.assertEqual(row["measured"], ev["measured"], ev["name"])
            for col in collect.MEASURE_RULES:
                self.assertEqual(row[col], str(ev[col]), f"{ev['name']}.{col}")

    def test_compare_report_has_no_disagreement(self):
        res = subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "measure" /
                                                        "run_compare_from_evidence.py"), str(evidence_dir())],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        rows = read_csv(evidence_dir() / "comparison.csv")
        self.assertEqual([r for r in rows if r["agree"] == "no"], [])

    def test_release_changes_log_is_consistent(self):
        changes = read_csv(DATA / "release_changes.csv")
        published = {r["repository"].lower().rstrip("/"): r for r in read_csv(DATA / "artefacts_snapshot_deduped.csv")}
        release = {r["repository"].lower().rstrip("/"): r for r in read_csv(DATA / "artefacts.csv")}
        for c in changes:
            key = c["repository"].lower().rstrip("/")
            self.assertIn(c["column"], published[key], "change logged for a column with no published value")
            self.assertEqual(published[key][c["column"]], c["published"])
            self.assertEqual(release[key][c["column"]], c["release"])
            self.assertNotEqual(c["published"], c["release"])


class RebuildTests(unittest.TestCase):
    def test_snapshot_build_is_deterministic(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            (tmp / "source").mkdir()
            shutil.copy(SOURCE, tmp / "source" / "artifact_snapshot.html")
            sys.path.insert(0, str(ROOT / "scripts"))
            import build_csv
            build_csv.build(tmp)
            for name in ["artefacts_as_published.csv", "artefacts_snapshot_deduped.csv",
                         "duplicates_removed.csv", "corrections.csv"]:
                self.assertEqual((tmp / "data" / name).read_bytes(), (DATA / name).read_bytes(), name)
        finally:
            shutil.rmtree(tmp)

    def test_release_build_is_deterministic(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            for name in ["artefacts_snapshot_deduped.csv", "data_dictionary.csv"]:
                shutil.copy(DATA / name, tmp / name)
            subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "release_from_evidence.py"),
                            str(evidence_dir()), "--data", str(tmp)], check=True, capture_output=True)
            self.assertEqual((tmp / "artefacts.csv").read_bytes(), (DATA / "artefacts.csv").read_bytes())
            self.assertEqual((tmp / "release_changes.csv").read_bytes(), (DATA / "release_changes.csv").read_bytes())
        finally:
            shutil.rmtree(tmp)


class DictionaryDomainTests(unittest.TestCase):
    """Every column in data_dictionary.csv is checked against its declared type and allowed values."""

    def setUp(self):
        self.dictionary = read_csv(DATA / "data_dictionary.csv")
        self.release = read_csv(DATA / "artefacts.csv")

    def test_every_dictionary_column_is_in_release(self):
        header = set(self.release[0].keys())
        self.assertEqual({d["column"] for d in self.dictionary}, header)

    def test_integer_columns(self):
        for d in self.dictionary:
            if d["type"] != "integer":
                continue
            for r in self.release:
                self.assertTrue(r[d["column"]] == "not_checked" or re.fullmatch(r"\d+", r[d["column"]]),
                                f"{r['name']}.{d['column']}={r[d['column']]!r}")

    def test_categorical_columns_with_yes_no_domain(self):
        for d in self.dictionary:
            if d["type"] == "categorical" and d["allowed_values"] == "yes | no | not_checked":
                bad = [r["name"] for r in self.release if r[d["column"]] not in ("yes", "no", "not_checked")]
                self.assertEqual(bad, [], d["column"])

    def test_url_columns(self):
        for d in self.dictionary:
            if d["type"] == "url":
                bad = [r[d["column"]] for r in self.release if not REPO_RE.match(r[d["column"]])]
                self.assertEqual(bad, [], d["column"])

    def test_text_columns_have_no_control_characters(self):
        for d in self.dictionary:
            for r in self.release:
                self.assertFalse(re.search(r"[\x00-\x08\x0b-\x1f]", r[d["column"]]), d["column"])

    def test_no_leading_or_trailing_spaces(self):
        for r in self.release:
            for k, v in r.items():
                self.assertEqual(v, v.strip(), f"{r['name']}.{k}")


if __name__ == "__main__":
    unittest.main()
