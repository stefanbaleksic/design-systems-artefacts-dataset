# Changelog

All notable changes to this dataset are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) as applied to datasets below.

## Rules for this file and for releases

**Versioning (dataset release = git tag `vMAJOR.MINOR.PATCH`):**

- **MAJOR**: a column is removed or renamed, the meaning or rule of a column changes, or the set of rows changes
  in a way that changes the population.
- **MINOR**: rows or columns are added without changing the meaning of existing columns.
- **PATCH**: values are corrected in place (a placeholder, a typo, a value that the evidence file contradicts) with no
  change to any definition.

**Each entry must contain:**

1. The release version and the UTC date (`YYYY-MM-DD`).
2. The evidence run the values come from (directory name under `evidence/`).
3. Counts before and after: rows added, rows removed, columns added or removed, values changed.
4. Every changed value is listed in `data/release_changes.csv` (for values taken from the evidence run)
   or `data/corrections.csv` (for placeholder values). Link the file from the entry.
5. Any change to a rule in `scripts/measure/collect.py` (`MEASURE_RULES`), stated as the old rule and the new rule.

**Writing rules:**

- Do not edit a released section after its tag is published. Add a new section.
- Do not call a value "reproduced" or "validated" unless a second, independent check produced the same value. A value
  that is copied from the evidence run it came from is not an independent check.
- Do not describe a release as peer-reviewed, reviewed by a named person, or representative unless that is true.
- Dates are UTC.

**Security entries:** if a change fixes a security problem in a script (for example, path handling of cloned
repositories), the entry says so in a `### Security` heading and links to the advisory. See `SECURITY.md`.

## [Unreleased]

## [1.0.0] - 2026-11-18

First release. Release values come from evidence run `20261118T112446Z` (UTC start 2026-11-18 11:24:46, script `collect/1.3`).
That run cloned every repository fresh, and deleted each clone after measuring it.

### Changed
- **Release values are re-measured.** The values on the published page of 17 November 2026
  (`source/artifact_snapshot.html`, kept unchanged) came from a collection procedure whose code is not part of this repository.
  Version 1.0.0 does not use them. `data/artefacts.csv` uses the evidence run. 636 values differ from the page;
  each is listed in `data/release_changes.csv`. Columns that exist only in the release (`a11y_check_files`) have no published value to compare. Most differences come from the rules in `scripts/measure/collect.py`,
  which are not the page's original rules, and from repositories that changed after the snapshot. Read the rule
  before you use a column.
- Removed 5 duplicate rows that share a repository URL (case-insensitive). The first occurrence was kept.
  Removed: Microsoft Fluent, Mistica (Telefónica), Polaris (Shopify), Porsche Design System (identical second entry),
  Skin (eBay). See `data/duplicates_removed.csv`.
- For the 7 repositories that failed to clone, `semver_tags` (published `0`) and `latest_tag` (published empty)
  are `not_checked`. Those values were placeholders. See `data/corrections.csv` (14 values).
- Translated column names to English. The original keys are in `data/data_dictionary.csv`.

### Added
- `components_strict`: a reconstructed count of component folders with an entry file. It was in the dictionary but
  not measured by the collector; it is now measured in every release row.
- Evidence for every repository of the run (`evidence/20261118T112446Z/`): commit SHA, commit date (UTC), full tag
  list, measured values, error text. Also `run.json`, `remeasured.csv`, `comparison.csv`, `reproduction_report.md`.
- Scripts: `collect.py` (measure and write evidence), `run_compare_from_evidence.py` (offline check),
  `release_from_evidence.py` (build the release file), `build_csv.py` (snapshot step), semver and UTC helpers.
- `a11y_check_files` replaces the published `a11y_source_files`. The old column counted any file with `role=` or `aria-`
  (a text match, low validity). The new column counts JS/TS files that configure or call an accessibility checker
  (axe-core, jest-axe, vitest-axe, pa11y, Storybook a11y addon).
- Tests: 61, offline, in `tests/`. They cover UTC conversion, semver precedence, the collector on fixtures, the release
  value by value against its evidence, every dictionary type and domain, and deterministic rebuilds.
- Continuous integration (`.github/workflows/tests.yml`): unit tests, rebuild, and a check that rebuilding leaves `data/` unchanged.
- Licences: CC BY 4.0 for the data (LICENSE-DATA.md), MIT for the code (LICENSE). SECURITY.md, CITATION.cff, .zenodo.json, this changelog.

### Known limitations of this release
- `a11y_check_files` counts files that configure or call an accessibility checker. It does not measure how well a system is
  accessible, and a system can have checks and still have problems.
- `component_dirs` and `components_strict` are heuristic counts of folders. Do not aggregate them across systems.
- Storybook, stories, token and framework detection use the rules in `MEASURE_RULES`. They can miss artefacts or count
  non-artefacts (see README, "Detection limits").
- Tag counts include prereleases. `latest_tag` is the highest version by semver precedence, not the newest by date.
