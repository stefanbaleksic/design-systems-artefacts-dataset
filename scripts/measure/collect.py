#!/usr/bin/env python3
"""Collect measurements for the repositories in data/artefacts.csv and write evidence.

For each repository this script:
  1. lists its remote tags (git ls-remote, no history needed),
  2. makes a shallow clone of the default branch (git clone --depth 1),
  3. records the commit SHA and the commit date (converted to UTC),
  4. measures the columns listed in MEASURE_RULES,
  5. writes one evidence file per repository.

Output for one run (default: evidence/<UTC run id>/):
    <slug>.json      all facts for one repository, including the tag list and errors
    remeasured.csv   one row per repository, same column names as data/artefacts.csv
    run.json         run metadata: UTC start and end, script version, counts

Rules that match the column meaning on the published page are marked [documented].
Rules marked [reconstructed] are the best reading of the column name. They are NOT
the original collection code. README.md ("Reproduction status") says which columns
agree with the published release and which do not.

Standard library only. Needs git on PATH and network access to github.com.

Usage:
    python3 scripts/measure/collect.py                       # all repositories, evidence/<run>/
    python3 scripts/measure/collect.py --only "Shopify Polaris"
    python3 scripts/measure/collect.py --cache /tmp/clones   # reuse existing clones
"""
import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import semver_utils  # noqa: E402
import timeutils  # noqa: E402

SCRIPT_VERSION = "collect/1.3"
PACKAGE_ROOT = HERE.parents[1]

SKIP_DIRS = {".git", "node_modules", "dist", "build", ".next", "coverage"}
TOKEN_EXT = {".json", ".css", ".scss", ".ts", ".js", ".mjs", ".cjs"}
TOKEN_NAME = re.compile(r"(token|tokens|design-tokens|theme)", re.I)
TOKEN_CSS_VAR = re.compile(r"--[a-zA-Z0-9_-]+\s*:")
# An accessibility checker is configured or called in the file (tests, Storybook config, CI helpers).
A11Y_CHECKER = re.compile(r"axe-core|jest-axe|vitest-axe|@axe-core|toHaveNoViolations|pa11y|addon-a11y", re.I)
FRAMEWORKS = {"React": ["react"], "Vue": ["vue"], "Angular": ["@angular/core"],
              "Svelte": ["svelte"], "Solid": ["solid-js"], "Lit": ["lit"]}
A11Y_DEPS = ["axe-core", "@axe-core", "jest-axe", "vitest-axe", "addon-a11y",
             "eslint-plugin-jsx-a11y", "@storybook/addon-a11y", "pa11y"]
VISUAL_DEPS = ["chromatic", "@playwright/test", "playwright", "percy", "loki", "backstop"]

# Column -> how it is measured. Kept here so the README and the report can list them.
MEASURE_RULES = {
    "storybook": "[documented] yes if .storybook/ exists or a storybook package is a dependency",
    "stories_files": "[documented] files named *.stories.{js,jsx,ts,tsx,mdx}",
    "code_connect_files": "[documented] files named *.figma.{js,jsx,ts,tsx}",
    "test_files": "[reconstructed] files named *.test.* or *.spec.* (JS/TS)",
    "codeowners": "[documented] CODEOWNERS in root, .github/ or docs/",
    "rfc_or_adr": "[reconstructed] a directory named rfc(s), adr(s) or decisions",
    "npm_exports_field": "[reconstructed] root package.json has an exports field",
    "semver_tags": "[documented] remote tags that are semantic versions (with or without v)",
    "latest_tag": "[documented] highest semantic version by precedence (semver 2.0.0)",
    "token_format": "[reconstructed] token-named file with CSS custom properties or DTCG $value",
    "token_css_vars": "[reconstructed] count of CSS custom property declarations in token files",
    "component_dirs": "[reconstructed] component folders under src/components (proxy, low validity)",
    "components_strict": "[reconstructed] component folders under src/components that contain an entry file "
                         "(index.* or a file named after the folder)",
    "visual_regression": "[reconstructed] visual tool dependencies found",
    "a11y_dependencies": "[reconstructed] accessibility test dependencies found",
    "a11y_check_files": "[reconstructed] JS/TS files under 300 kB that configure or call an accessibility checker "
                        "(axe-core, jest-axe, vitest-axe, pa11y, Storybook a11y addon)",
    "frameworks": "[reconstructed] framework dependencies found",
}


def walk(root: Path):
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            entries = list(d.iterdir())
        except OSError:
            continue
        for p in entries:
            if p.is_symlink():
                continue  # never follow links: a link could point outside the clone
            if p.is_dir():
                if p.name not in SKIP_DIRS:
                    stack.append(p)
            elif p.is_file():
                yield p


def package_jsons(root: Path):
    paths = [root / "package.json"] + list(root.glob("packages/*/package.json")) \
        + list(root.glob("*/package.json"))
    out = []
    for p in paths:
        if p.is_file() and "node_modules" not in p.parts:
            try:
                out.append(json.loads(p.read_text(encoding="utf-8")))
            except (ValueError, OSError):
                pass
    return out


def dependency_names(pkgs):
    names = set()
    for pkg in pkgs:
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            names.update((pkg.get(key) or {}).keys())
    return names


def remote_tags(url: str):
    """Tag names on the remote, or None when git ls-remote fails."""
    res = subprocess.run(["git", "ls-remote", "--tags", "--refs", url],
                         capture_output=True, text=True, timeout=300)
    if res.returncode != 0:
        return None
    return [line.split("refs/tags/", 1)[1].strip()
            for line in res.stdout.splitlines() if "refs/tags/" in line]


def measure_checkout(root: Path) -> dict:
    files = list(walk(root))
    rel = [str(p.relative_to(root)).replace("\\", "/") for p in files]
    pkgs = package_jsons(root)
    deps = dependency_names(pkgs)

    storybook = (root / ".storybook").is_dir() or any(
        d == "storybook" or d.startswith("@storybook/") for d in deps)
    stories = [r for r in rel if re.search(r"\.stories\.(js|jsx|ts|tsx|mdx)$", r)]
    code_connect = [r for r in rel if re.search(r"\.figma\.(js|jsx|ts|tsx)$", r)]
    tests = [r for r in rel if re.search(r"\.(test|spec)\.(js|jsx|ts|tsx|mjs|cjs)$", r)]
    codeowners = any(r in ("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS") for r in rel)
    rfc_adr = any(re.search(r"(^|/)(rfcs?|adrs?|decisions)/", r, re.I) for r in rel)
    npm_exports = bool(pkgs) and "exports" in pkgs[0]

    a11y_files = 0
    for p in files:
        if p.suffix in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs") and p.stat().st_size < 300_000:
            if A11Y_CHECKER.search(p.read_text(encoding="utf-8", errors="ignore")):
                a11y_files += 1

    token_files, css_vars = [], 0
    json_dtcg = False
    for p, r in zip(files, rel):
        if p.suffix in TOKEN_EXT and TOKEN_NAME.search(p.name) and p.stat().st_size < 300_000:
            text = p.read_text(encoding="utf-8", errors="ignore")
            found = len(TOKEN_CSS_VAR.findall(text))
            if found:
                token_files.append(r)
                css_vars += found
            if p.suffix == ".json" and "$value" in text:
                json_dtcg = True
    if json_dtcg:
        token_format = "DTCG ($value)"
    elif token_files:
        token_format = "CSS custom properties"
    else:
        token_format = "none detected"

    comp_dirs = {"/".join(r.split("/")[:-1]) for r in rel
                 if re.match(r"(packages/[^/]+/)?src/components/[^/]+/", r)}
    strict = set()
    for r in rel:
        m = re.match(r"((?:packages/[^/]+/)?src/components/[^/]+)/(index|[^/]+)\.(js|jsx|ts|tsx|mjs|cjs)$", r)
        if m and (m.group(2) == "index" or m.group(1).rsplit("/", 1)[-1] == m.group(2)):
            strict.add(m.group(1))

    frameworks = [name for name, names in FRAMEWORKS.items() if any(d in deps for d in names)]
    a11y_deps = sorted(d for d in A11Y_DEPS if d in deps)
    visual = sorted(d for d in VISUAL_DEPS if d in deps)

    return {
        "storybook": "yes" if storybook else "no",
        "stories_files": len(stories),
        "code_connect_files": len(code_connect),
        "test_files": len(tests),
        "codeowners": "yes" if codeowners else "no",
        "rfc_or_adr": "yes" if rfc_adr else "no",
        "npm_exports_field": "yes" if npm_exports else "no",
        "token_format": token_format,
        "token_css_vars": css_vars,
        "component_dirs": len(comp_dirs),
        "components_strict": len(strict),
        "visual_regression": ", ".join(visual) if visual else "none detected",
        "a11y_dependencies": ", ".join(a11y_deps) if a11y_deps else "none detected",
        "a11y_check_files": a11y_files,
        "frameworks": ", ".join(frameworks) if frameworks else "none detected",
    }




def slug_for(url: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", url.split("github.com/", 1)[1]).strip("_")


def collect_one(row: dict, cache: Path, started_utc: str, keep_clones: bool = False) -> dict:
    url = row["repository"]
    record = {
        "name": row["name"],
        "repository": url,
        "slug": slug_for(url),
        "collected_utc": started_utc,
        "script": SCRIPT_VERSION,
        "measured": "yes",
        "commit": "",
        "commit_date_utc": "",
        "error": "",
        "tags": [],
        "semver_tags": "not_checked",
        "latest_tag": "",
    }
    for key in MEASURE_RULES:
        record[key] = "not_checked"

    tags = remote_tags(url)
    if tags is None:
        record["error"] = "git ls-remote --tags failed"
    else:
        record["tags"] = sorted(tags)
        semver = [t for t in tags if semver_utils.is_semver(t)]
        record["semver_tags"] = len(semver)
        record["latest_tag"] = semver_utils.latest(semver)

    target = cache / record["slug"]
    try:
        if not target.exists():
            res = subprocess.run(["git", "clone", "-q", "--depth", "1", url, str(target)],
                                 capture_output=True, text=True, timeout=900)
            if res.returncode != 0:
                raise RuntimeError(res.stderr.strip() or "git clone failed")
        head = subprocess.run(["git", "-C", str(target), "log", "-1", "--format=%H%n%cI"],
                              capture_output=True, text=True, timeout=60)
        if head.returncode != 0:
            raise RuntimeError("git log failed")
        sha, commit_iso = head.stdout.strip().split("\n", 1)
        record["commit"] = sha
        record["commit_date_utc"] = timeutils.to_utc_iso(commit_iso)
        record.update(measure_checkout(target))
    except (RuntimeError, subprocess.TimeoutExpired, OSError, ValueError) as exc:
        record["measured"] = "no (clone failed)"
        record["error"] = (record["error"] + "; " if record["error"] else "") + str(exc)[:300]
        for key in MEASURE_RULES:
            record[key] = "not_checked"
    finally:
        if not keep_clones and target.exists():
            shutil.rmtree(target, ignore_errors=True)  # keeps disk use low; evidence holds the facts
    return record


CSV_FIELDS = ["name", "repository", "measured", "commit", "token_format", "token_css_vars",
              "component_dirs", "stories_files", "storybook", "code_connect_files", "test_files",
              "visual_regression", "a11y_dependencies", "a11y_check_files", "codeowners",
              "rfc_or_adr", "frameworks", "npm_exports_field", "semver_tags", "latest_tag", "error"]


def write_outputs(records, run_dir: Path, started_utc: str, finished_utc: str):
    run_dir.mkdir(parents=True, exist_ok=True)
    for rec in records:
        (run_dir / f"{rec['slug']}.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (run_dir / "remeasured.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)
    meta = {
        "script": SCRIPT_VERSION,
        "started_utc": started_utc,
        "finished_utc": finished_utc,
        "repositories": len(records),
        "measured": sum(r["measured"] == "yes" for r in records),
        "clone_failed": sum(r["measured"] != "yes" for r in records),
    }
    (run_dir / "run.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=PACKAGE_ROOT / "data" / "artefacts.csv")
    parser.add_argument("--cache", type=Path, default=Path("/tmp/artefacts-clones"))
    parser.add_argument("--evidence", type=Path, default=PACKAGE_ROOT / "evidence",
                        help="folder that receives one run directory")
    parser.add_argument("--run", help="run id; default: UTC start time")
    parser.add_argument("--only", action="append", help="repeat to limit to these names")
    parser.add_argument("--keep-clones", action="store_true",
                        help="keep the clone folders in --cache (default: delete each after measuring)")
    args = parser.parse_args()

    started = timeutils.now_utc_iso()
    run_id = args.run or timeutils.run_id_from(started)
    if (args.evidence / run_id).exists():
        sys.exit(f"run already exists, refusing to overwrite: {args.evidence / run_id}")
    with args.data.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if args.only:
        rows = [r for r in rows if r["name"] in args.only]
    args.cache.mkdir(parents=True, exist_ok=True)

    records = []
    for i, row in enumerate(rows, 1):
        rec = collect_one(row, args.cache, started, args.keep_clones)
        records.append(rec)
        print(f"[{i}/{len(rows)}] {row['name']}: {rec['measured']}", file=sys.stderr)

    finished = timeutils.now_utc_iso()
    meta = write_outputs(records, args.evidence / run_id, started, finished)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
