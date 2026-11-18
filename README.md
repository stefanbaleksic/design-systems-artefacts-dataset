# Design System Artefacts Dataset

Artefacts of design systems and UI libraries in public GitHub repositories: design tokens, components, stories,
Storybook, Figma Code Connect, tests, accessibility checkers, governance files (CODEOWNERS, RFC/ADR), frameworks,
npm exports field, and semantic-version tags.

- **Version:** 1.0.0 (see [CHANGELOG.md](CHANGELOG.md)). Not yet tagged; the DOI is added after tagging.
- **Rows:** 220 repositories.
- **Release values:** evidence run [`evidence/20261118T112446Z`](evidence/20261118T112446Z/), UTC 2026-11-18 11:24:46.
- **Reproduction check:** a second, independent run [`evidence/20261118T114444Z`](evidence/20261118T114444Z/) with an empty clone cache. See [Reproduction](#reproduction).
- **Licence:** data under CC BY 4.0 ([LICENSE-DATA.md](LICENSE-DATA.md)); code under MIT ([LICENSE](LICENSE)). **Security:** see [SECURITY.md](SECURITY.md).
- **Citation:** see [CITATION.cff](CITATION.cff) and [.zenodo.json](.zenodo.json). The DOI is added after tagging.

> Read the rule before you use a column. Each measured column has its rule in `data/data_dictionary.csv`
> (column `release_rule`) and a detection limit in the table below. "none detected" means the pattern was not found
> in the clone. It does not mean the artefact is absent.

## Contents

| Path | Content |
|---|---|
| `data/artefacts.csv` | **The release.** 220 rows, 21 columns, in the order of `data_dictionary.csv`. Use this file. |
| `data/data_dictionary.csv` | Every column: type, allowed values, meaning, rule, and the original key on the published page. |
| `data/release_changes.csv` | Every value that differs from the published page (636 values). |
| `data/release_source.json` | Which evidence run the release was built from, and the rules used. |
| `data/artefacts_as_published.csv` | All 225 rows as published on 17 Nov 2026, before cleaning. |
| `data/artefacts_snapshot_deduped.csv` | The published values after duplicate removal (220 rows). Names, types and repositories come from here. |
| `data/duplicates_removed.csv` | The 5 removed rows and the row kept in each case. |
| `data/corrections.csv` | The 14 placeholder values changed in the snapshot step. |
| `source/artifact_snapshot.html` | The published page. Its embedded `DATA` array is the source of the snapshot CSV files. |
| `evidence/<run>/` | One evidence run: one JSON per repository (commit SHA, UTC times, full tag list, every value, error text), `remeasured.csv`, `run.json`, `comparison.csv`, `reproduction_report.md`. |
| `scripts/build_csv.py` | Snapshot step: builds the published and deduplicated CSV files from `source/`. |
| `scripts/measure/collect.py` | Clones and measures the repositories; writes an evidence run; deletes each clone after measuring. |
| `scripts/measure/run_compare_from_evidence.py` | Checks an evidence run for completeness and compares it with the release. No network. |
| `scripts/measure/compare_runs.py` | Compares two evidence runs. Same-commit differences are failures; changed commits are drift. No network. |
| `scripts/release_from_evidence.py` | Builds `data/artefacts.csv` from the evidence run named in `data/release_source.json`. |
| `scripts/measure/semver_utils.py`, `timeutils.py` | Semantic-version precedence and UTC conversion. |
| `tests/test_dataset.py`, `tests/test_scripts.py` | 61 offline tests. |
| `.github/workflows/tests.yml` | CI: tests, rebuild, and a check that the rebuild leaves `data/` unchanged. |
| `LICENSE`, `LICENSE-DATA.md` | MIT for the code; CC BY 4.0 for the data. |
| `.zenodo.json`, `CITATION.cff` | Metadata for Zenodo and for citation. |

## Quick start

Python 3.8 or newer and `git` on the PATH. Everything except `collect.py` runs offline.

```bash
python3 -m unittest discover -s tests -v                         # 61 tests
python3 scripts/build_csv.py                                     # snapshot CSVs (deterministic)
python3 scripts/release_from_evidence.py                         # release CSV (deterministic)
python3 scripts/measure/run_compare_from_evidence.py evidence/20261118T112446Z
python3 scripts/measure/compare_runs.py evidence/20261118T112446Z evidence/20261118T114444Z

# A new collection needs the network: shallow clones of 220 repositories, each deleted after measuring.
# Takes about 20 minutes. Writes to evidence/<UTC start time>/ and refuses to overwrite a run.
python3 scripts/measure/collect.py
python3 scripts/measure/run_compare_from_evidence.py evidence/<new-run>
```

`collect.py` exits with status 0 even when some repositories fail to clone; those are recorded as
`measured = no (clone failed)` with `not_checked` values. A run is complete only when
`run_compare_from_evidence.py` reports no missing evidence (exit status 0).

## How the release was made

1. `build_csv.py` reads the published page, removes 5 duplicate rows (same repository URL, case-insensitive; first kept)
   and sets the placeholder values of the 7 failed clones to `not_checked`.
2. `collect.py` ran on all 220 repositories with an empty clone cache (run `20261118T112446Z`). Every value is in its
   evidence file.
3. `release_from_evidence.py` writes each measured value from the evidence file. Names, types and repositories come from step 1.
4. The tests check the release value by value against the evidence files, and check every dictionary type and domain.

## Reproduction

Two checks, with different strength:

**Check 1: release against its evidence run.** `run_compare_from_evidence.py` shows 100% agreement for every column.
This is true by construction, because the release is the evidence run. It shows that the release was built correctly,
not that the values are right.

**Check 2: two independent runs.** Run `20261118T112446Z` and run `20261118T114444Z` both cloned every repository
with an empty cache, 20 minutes apart. `compare_runs.py` gives:

- Repositories compared: 220. Present in one run only: 0.
- Same commit, different value (reproduction failures): **0**.
- Commit changed between the runs: 4 repositories. Values changed in one of them (Fluent UI: one story file and one test file added).
- Tags, Storybook, token, component and dependency values agree in all 220 repositories.

This is the reproduction result for 1.0.0. The 4 changed commits show that repositories move; the data is a snapshot of
11:24 to 11:44 UTC on 18 November 2026, not of a fixed point in time.

**What is not reproduced:** the values on the published page of 17 November 2026. Their collection code is not in this
repository, and 636 of them differ from the release (`data/release_changes.csv`). Read the release as "values produced by
`collect/1.3` on 2026-11-18", not as "confirmed against the original procedure".

## Detection limits

Detection finds a pattern. A missing detection means the pattern was not found in the clone. Neither result proves the
presence or absence of the artefact. Every rule is in `MEASURE_RULES` (`scripts/measure/collect.py`).

| Column | Rule basis | Known limits |
|---|---|---|
| storybook | documented: `.storybook/` folder, or a `storybook` / `@storybook/*` dependency | Storybook configured in a sub-package only, or in another folder, may be missed. |
| stories_files | documented: `*.stories.{js,jsx,ts,tsx,mdx}` | Other naming schemes are not counted. Generated files are counted. |
| code_connect_files | documented: `*.figma.{js,jsx,ts,tsx}` | Mappings with other names, or kept in Figma only, are not found. |
| test_files | reconstructed: `*.test.*`, `*.spec.*` (JS/TS) | Tests in other languages or naming schemes are missed. Vendored tests may be counted. |
| codeowners | documented: `CODEOWNERS` in root, `.github/` or `docs/` | Elsewhere is not found. |
| rfc_or_adr | reconstructed: folder named `rfc(s)`, `adr(s)`, `decisions` | Records kept outside the repository are not found. |
| npm_exports_field | reconstructed: root `package.json` has `exports` | Packages in sub-folders are not checked. |
| semver_tags | documented: remote tags that are semver 2.0.0 (with or without `v`); prereleases included | GitHub Releases without tags are not counted. Non-semver tag schemes are not counted. |
| latest_tag | documented: highest version by semver precedence | Not the newest by date. A repository whose newest release is a non-semver tag shows an older version. |
| token_format, token_css_vars | reconstructed: token-named JS/JSON/CSS files with `--name:` declarations or DTCG `$value` | Other token formats (for example Sass maps) and other file names are missed. |
| component_dirs | reconstructed: folders under `src/components/` | Proxy with low validity. Do not aggregate. |
| components_strict | reconstructed: component folders under `src/components/` that contain an entry file | Components in other folders are not counted. Heuristic. |
| visual_regression, a11y_dependencies, frameworks | reconstructed: dependency names in `package.json` files | A tool used only in scripts or CI, not listed as a dependency, is not found. |
| a11y_check_files | reconstructed: JS/TS files under 300 kB that configure or call an accessibility checker (axe-core, jest-axe, vitest-axe, pa11y, Storybook a11y addon) | Shows that checks exist, not that the system is accessible. A system can have checks and still have problems. Detects only the checkers named in the rule. |

Dataset limits: a convenience sample of publicly listed systems, not a census or a ranking; one release built from one
evidence run; one repository is treated as one system; missing values are not random and are `not_checked`, never zero.

## Decisions taken for 1.0.0

These decisions were made on 18 November 2026 and are recorded here so they can be changed in a later release.

- **Release values come from the fresh evidence run**, not from the published page. The page is kept as a snapshot.
- **Accessibility column**: `a11y_source_files` (a text match, low validity) is replaced by `a11y_check_files`, which counts
  files that configure or call an accessibility checker. The old column is not in the release.
- **Tag columns** come from the run. Prereleases count as semver tags; `latest_tag` is the highest by precedence.
- **Storybook and stories** use the rules in `MEASURE_RULES`. The original rule could not be recovered.
- **Reconstructed columns** keep the values from the run, not the page values. They are labelled with their basis above.
- **Evidence is committed in full** (about 12 MB per run, one JSON per repository). The archive for Zenodo uses the same files,
  so the data can be checked without network access. The full tag lists are kept because they are the basis of the tag columns.

## Time and UTC

- Every timestamp in the evidence files is UTC, written as `YYYY-MM-DDTHH:MM:SSZ`.
- Commit dates come from `git log --format=%cI` (ISO 8601 with offset) and are converted to UTC. A timestamp without an
  offset is rejected, because its zone cannot be known.
- Run folder names are the UTC start time with separators removed.
- Tests cover offset conversion (`+10:00`, `+02:00`, `-05:00`), midnight roll-over, `Z` and `+00:00` input, and
  rejection of naive timestamps.

## Semantic versions

- A tag counts as a semantic version when it matches the semver 2.0.0 grammar, with or without a leading `v`.
  Build metadata (`+...`) is ignored for precedence.
- `latest_tag` is the highest version by precedence. A release outranks its prereleases (`v2.0.0` > `v2.0.0-rc.1`),
  numeric prerelease identifiers compare as numbers, and the tag keeps its original spelling.
- Tags that are not semantic versions (for example `nightly`) are not counted.
- Tests cover precedence, `v` prefixes, prerelease ordering, hyphens inside identifiers, and rejection of invalid tags.

## Security

- The collector reads repositories with `git ls-remote` and `git clone --depth 1`. It does not install packages,
  build, or run code from the repositories. Symbolic links are not followed when walking a clone. Each clone is deleted after measuring.
- Report vulnerabilities through GitHub private vulnerability reporting, as described in [SECURITY.md](SECURITY.md).

## Licence

Data: CC BY 4.0 (`LICENSE-DATA.md`). Code: MIT (`LICENSE`). Each source repository keeps its own licence.

## Changes

Recorded in [CHANGELOG.md](CHANGELOG.md). Its header holds the rules for versions, entries and security notes.

## Limitations

- Convenience sample of publicly listed design systems and UI libraries.
- One release, built from one evidence run, checked by one independent second run. The data cannot show change over time.
- One repository is treated as one system; systems spread over several repositories are under-counted.
- Pattern-based detection (see the table above) finds patterns, not quality.
