"""Tests for the measurement scripts. Offline: no network, no clones.

Run from the package root:
    python3 -m unittest discover -s tests -v
"""
import csv
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEASURE = ROOT / "scripts" / "measure"
sys.path.insert(0, str(MEASURE))

import semver_utils  # noqa: E402
import timeutils  # noqa: E402
import collect  # noqa: E402


class SemverTests(unittest.TestCase):
    def test_parse_accepts_v_prefix_and_plain(self):
        self.assertEqual(semver_utils.parse("v1.2.3"), (1, 2, 3, ()))
        self.assertEqual(semver_utils.parse("1.2.3"), (1, 2, 3, ()))

    def test_parse_prerelease_and_build(self):
        self.assertEqual(semver_utils.parse("v7.0.0-alpha.2"), (7, 0, 0, ("alpha", "2")))
        self.assertEqual(semver_utils.parse("1.0.0+build.5"), (1, 0, 0, ()))

    def test_rejects_non_semver(self):
        for tag in ["latest", "v1.2", "1.2.3.4", "v01.2.3", "release-2", ""]:
            self.assertIsNone(semver_utils.parse(tag), tag)

    def test_hyphen_inside_prerelease_identifier_is_valid(self):
        # Salesforce publishes "v3.0.0-alpha-5"; this is a valid prerelease identifier.
        self.assertEqual(semver_utils.parse("v3.0.0-alpha-5"), (3, 0, 0, ("alpha-5",)))

    def test_release_outranks_its_prerelease(self):
        self.assertLess(semver_utils.sort_key("v2.0.0-rc.1"), semver_utils.sort_key("v2.0.0"))

    def test_prerelease_numeric_identifiers_compare_as_numbers(self):
        self.assertLess(semver_utils.sort_key("v1.0.0-alpha.2"), semver_utils.sort_key("v1.0.0-alpha.10"))

    def test_numeric_identifiers_sort_before_alphanumeric(self):
        self.assertLess(semver_utils.sort_key("v1.0.0-1"), semver_utils.sort_key("v1.0.0-alpha"))

    def test_shorter_prerelease_set_is_lower(self):
        self.assertLess(semver_utils.sort_key("v1.0.0-alpha"), semver_utils.sort_key("v1.0.0-alpha.1"))

    def test_latest_picks_highest_precedence_and_keeps_spelling(self):
        self.assertEqual(semver_utils.latest(["v7.0.0-alpha.1", "v7.0.0-alpha.2"]), "v7.0.0-alpha.2")
        self.assertEqual(semver_utils.latest(["3.0.1417", "3.0.1419", "nightly"]), "3.0.1419")
        self.assertEqual(semver_utils.latest(["v1.10.0", "v1.9.0"]), "v1.10.0")

    def test_latest_empty_when_no_semver(self):
        self.assertEqual(semver_utils.latest([]), "")
        self.assertEqual(semver_utils.latest(["nightly", "latest"]), "")

    def test_sort_key_rejects_invalid(self):
        with self.assertRaises(ValueError):
            semver_utils.sort_key("nightly")


class UtcTests(unittest.TestCase):
    def test_offset_converted_to_utc(self):
        # Git %cI example from the Shopify Polaris check: +10:00
        self.assertEqual(timeutils.to_utc_iso("2026-09-10T04:59:03+10:00"), "2026-09-09T18:59:03Z")

    def test_belgrade_summer_and_winter_offsets(self):
        self.assertEqual(timeutils.to_utc_iso("2026-07-01T12:00:00+02:00"), "2026-07-01T10:00:00Z")
        self.assertEqual(timeutils.to_utc_iso("2026-11-18T10:00:00+01:00"), "2026-11-18T09:00:00Z")

    def test_zulu_and_zero_offset(self):
        self.assertEqual(timeutils.to_utc_iso("2026-11-18T09:00:00Z"), "2026-11-18T09:00:00Z")
        self.assertEqual(timeutils.to_utc_iso("2026-11-18T09:00:00+00:00"), "2026-11-18T09:00:00Z")

    def test_date_rolls_over_midnight(self):
        self.assertEqual(timeutils.to_utc_iso("2026-01-01T00:30:00+02:00"), "2025-12-31T22:30:00Z")

    def test_negative_offset(self):
        self.assertEqual(timeutils.to_utc_iso("2026-03-01T08:00:00-05:00"), "2026-03-01T13:00:00Z")

    def test_aware_datetime_input(self):
        dt = datetime(2026, 11, 18, 10, 0, tzinfo=timezone(timedelta(hours=1)))
        self.assertEqual(timeutils.to_utc_iso(dt), "2026-11-18T09:00:00Z")

    def test_naive_timestamp_rejected(self):
        with self.assertRaises(ValueError):
            timeutils.to_utc_iso("2026-11-18T10:00:00")
        with self.assertRaises(ValueError):
            timeutils.to_utc_iso(datetime(2026, 11, 18, 10, 0))

    def test_output_format(self):
        out = timeutils.to_utc_iso("2026-11-18T10:00:00+01:00")
        self.assertRegex(out, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def test_run_id_is_directory_safe(self):
        self.assertEqual(timeutils.run_id_from("2026-11-18T09:00:00Z"), "20261118T090000Z")


class SlugTests(unittest.TestCase):
    def test_slug_from_url(self):
        self.assertEqual(collect.slug_for("https://github.com/Shopify/polaris"), "Shopify_polaris")
        self.assertEqual(collect.slug_for("https://github.com/porsche-design-system/porsche-design-system"),
                         "porsche-design-system_porsche-design-system")

    def test_slug_has_no_path_separators(self):
        self.assertNotIn("/", collect.slug_for("https://github.com/owner/re po/x"))


class MeasureCheckoutTests(unittest.TestCase):
    """Fixture checkout with known content; counts must match what the rules say."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        r = self.root
        (r / ".storybook").mkdir()
        (r / "src/components/button").mkdir(parents=True)
        (r / "src/components/card").mkdir(parents=True)
        (r / "src/components/button/index.ts").write_text("export {}")
        (r / "src/components/button/Button.stories.tsx").write_text("x")
        (r / "src/components/button/Button.test.tsx").write_text("x")
        (r / "src/components/button/Button.figma.tsx").write_text("x")
        (r / "src/components/card/Card.spec.ts").write_text("x")
        (r / "tokens").mkdir()
        (r / "tokens/color-tokens.css").write_text(":root{--a: 1;--b: 2;}")
        (r / "tokens/spacing.json").write_text('{"x": {"$value": "4px"}}')
        (r / "src/a11y.ts").write_text("import { axe } from 'axe-core';")
        (r / ".github").mkdir()
        (r / ".github/CODEOWNERS").write_text("* @team")
        (r / "docs/adr").mkdir(parents=True)
        (r / "docs/adr/0001.md").write_text("decision")
        (r / "package.json").write_text(json.dumps({
            "exports": {".": "./dist/index.js"},
            "dependencies": {"react": "18"},
            "devDependencies": {"@storybook/react": "8", "jest-axe": "1", "@playwright/test": "1"},
        }))

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_counts(self):
        m = collect.measure_checkout(self.root)
        self.assertEqual(m["storybook"], "yes")
        self.assertEqual(m["stories_files"], 1)
        self.assertEqual(m["code_connect_files"], 1)
        self.assertEqual(m["test_files"], 2)
        self.assertEqual(m["codeowners"], "yes")
        self.assertEqual(m["rfc_or_adr"], "yes")
        self.assertEqual(m["npm_exports_field"], "yes")
        self.assertEqual(m["token_format"], "CSS custom properties")
        self.assertEqual(m["token_css_vars"], 2)
        self.assertEqual(m["component_dirs"], 2)
        # button has an index file, card has only a spec file: only button is a strict component
        self.assertEqual(m["components_strict"], 1)
        self.assertEqual(m["frameworks"], "React")
        self.assertEqual(m["a11y_dependencies"], "jest-axe")
        self.assertEqual(m["visual_regression"], "@playwright/test")
        self.assertEqual(m["a11y_check_files"], 1)

    def test_empty_checkout_reports_none_not_missing(self):
        empty = Path(tempfile.mkdtemp())
        try:
            m = collect.measure_checkout(empty)
            self.assertEqual(m["storybook"], "no")
            self.assertEqual(m["token_format"], "none detected")
            self.assertEqual(m["frameworks"], "none detected")
            self.assertEqual(m["stories_files"], 0)
        finally:
            shutil.rmtree(empty)

    def test_every_measure_rule_has_a_key_in_measure_output(self):
        m = collect.measure_checkout(self.root)
        self.assertEqual(set(m) - set(collect.MEASURE_RULES), set())
        # semver_tags and latest_tag come from the remote tag list, not from the checkout.
        self.assertEqual(set(collect.MEASURE_RULES) - set(m), {"semver_tags", "latest_tag"})


class RunStabilityTests(unittest.TestCase):
    """compare_runs: same commit with different values is a failure; a changed commit is drift."""

    def _run(self, tmp, name, commit, stories):
        d = tmp / name
        d.mkdir()
        base = {c: "not_checked" for c in collect.MEASURE_RULES}
        base.update({"name": "Alpha", "repository": "https://github.com/o/alpha", "measured": "yes",
                     "commit": commit, "stories_files": stories})
        (d / "alpha.json").write_text(json.dumps(base), encoding="utf-8")
        return d

    def _compare(self, a, b):
        import compare_runs
        return compare_runs.compare(compare_runs.load(a), compare_runs.load(b))

    def test_same_commit_difference_is_failure(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            a = self._run(tmp, "a", "sha1", 5)
            b = self._run(tmp, "b", "sha1", 6)
            failures, drift, compared, _ = self._compare(a, b)
            self.assertEqual(compared, 1)
            self.assertEqual([r["column"] for r in failures], ["stories_files"])
            self.assertEqual(drift, [])
        finally:
            shutil.rmtree(tmp)

    def test_changed_commit_difference_is_drift(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            a = self._run(tmp, "a", "sha1", 5)
            b = self._run(tmp, "b", "sha2", 6)
            failures, drift, _, _ = self._compare(a, b)
            self.assertEqual(failures, [])
            self.assertEqual([r["column"] for r in drift], ["stories_files"])
        finally:
            shutil.rmtree(tmp)


class SymlinkTests(unittest.TestCase):
    def test_symlinks_are_not_followed(self):
        outside = Path(tempfile.mkdtemp())
        root = Path(tempfile.mkdtemp())
        try:
            (outside / "Leak.stories.tsx").write_text("x")
            (root / "linkdir").symlink_to(outside, target_is_directory=True)
            files = [p.name for p in collect.walk(root)]
            self.assertNotIn("Leak.stories.tsx", files)
        finally:
            shutil.rmtree(outside)
            shutil.rmtree(root)


class EvidenceComparisonTests(unittest.TestCase):
    """run_compare_from_evidence must fail when a repository has no evidence."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.data = self.tmp / "artefacts.csv"
        columns = ["name", "repository", "measured"] + list(collect.MEASURE_RULES)
        def row(name, repo, storybook):
            base = {c: "not_checked" for c in columns}
            base.update({"name": name, "repository": repo, "measured": "yes", "storybook": storybook})
            return [base[c] for c in columns]
        with self.data.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(columns)
            w.writerow(row("Alpha", "https://github.com/o/alpha", "yes"))
            w.writerow(row("Beta", "https://github.com/o/beta", "no"))
        self.run = self.tmp / "run"
        self.run.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _record(self, name, repo, storybook):
        rec = {"name": name, "repository": repo, "measured": "yes", "storybook": storybook}
        for k in collect.MEASURE_RULES:
            rec.setdefault(k, "not_checked")
        (self.run / f"{name}.json").write_text(json.dumps(rec), encoding="utf-8")

    def _run_compare(self):
        return subprocess.run([sys.executable, "-I", str(MEASURE / "run_compare_from_evidence.py"),
                               str(self.run), "--data", str(self.data)],
                              capture_output=True, text=True)

    def test_missing_evidence_fails(self):
        self._record("Alpha", "https://github.com/o/alpha", "yes")
        res = self._run_compare()
        self.assertEqual(res.returncode, 1)
        self.assertIn("MISSING evidence for 1", res.stderr)

    def test_complete_evidence_passes_and_reports_agreement(self):
        self._record("Alpha", "https://github.com/o/alpha", "yes")
        self._record("Beta", "https://github.com/o/beta", "yes")  # published "no" -> disagreement
        res = self._run_compare()
        self.assertEqual(res.returncode, 0, res.stderr)
        report = (self.run / "reproduction_report.md").read_text(encoding="utf-8")
        self.assertIn("| storybook | 1/2 |", report)
        with (self.run / "comparison.csv").open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        bad = [r for r in rows if r["agree"] == "no"]
        self.assertEqual([(r["name"], r["column"]) for r in bad], [("Beta", "storybook")])


if __name__ == "__main__":
    unittest.main()
