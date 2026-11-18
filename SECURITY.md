# Security policy

## Supported versions

Only the latest dataset release receives fixes. Older releases stay available by tag and are not changed.

## Reporting a vulnerability

Do not open a public issue for a security problem. Use GitHub's private vulnerability reporting on this
repository (Security tab, "Report a vulnerability"). Include the file or script, the steps to reproduce,
and the effect. You should get an acknowledgement within 7 days; the status is then kept in that report.

Also use this channel for:

- a data record that exposes personal information about a person (names of maintainers, contact details)
  that is not already public on the listed repository;
- a credential, token or key found anywhere in the repository history.

## What this repository contains and what it does

- The dataset holds public metadata about public GitHub repositories: names, URLs, file counts, dependency names,
  tag names and commit SHAs. It holds no source code from those repositories and no personal data beyond
  what the repositories publish.
- The collection script (`scripts/measure/collect.py`) runs `git ls-remote` and `git clone --depth 1` against the
  listed URLs and then **reads** files. It does **not** run package managers, install dependencies, or execute
  any code from the cloned repositories. Keep it that way: a change that runs `npm install`, a build, or any
  repository script is a security-relevant change and must be reviewed as such.
- Cloned repositories are untrusted input. The script reads files with size limits (300 kB for content scans)
  and does not follow symbolic links out of the clone directory when it walks it. Report any path that escapes the clone.
- The scripts use no tokens. Do not add a GitHub token to a script or a config file. If one is needed, read it from the
  environment, never commit it, and state the change in `CHANGELOG.md`.

## Rules for contributors

- Never commit secrets, tokens, `.env` files, local paths that reveal personal information, or clone caches.
- Evidence files are public. Remove anything that is not public repository metadata before committing.
- Pin the commit SHA for every measured repository (already recorded in each evidence file).
