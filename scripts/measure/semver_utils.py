"""Semantic-version parsing and precedence (https://semver.org, version 2.0.0).

Tags are accepted with or without a leading "v". Build metadata (+...) is ignored
for precedence, as the specification requires. Tags that are not semantic
versions return None and are not counted as semver tags.
"""
import re

_SEMVER = re.compile(
    r"^v?(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


def parse(tag):
    """Return (major, minor, patch, prerelease_identifiers) or None."""
    m = _SEMVER.match(tag.strip())
    if not m:
        return None
    pre = m.group("pre")
    return (int(m.group("major")), int(m.group("minor")), int(m.group("patch")),
            tuple(pre.split(".")) if pre else ())


def _identifier_key(ident):
    # Numeric identifiers sort before alphanumeric ones; numerics compare as integers.
    if ident.isdigit():
        return (0, int(ident), "")
    return (1, 0, ident)


def sort_key(tag):
    """Key for ascending precedence. A release outranks any prerelease of the same version."""
    parsed = parse(tag)
    if parsed is None:
        raise ValueError(f"not a semantic version: {tag!r}")
    major, minor, patch, pre = parsed
    if not pre:
        return (major, minor, patch, 1, ())
    return (major, minor, patch, 0, tuple(_identifier_key(i) for i in pre))


def is_semver(tag):
    return parse(tag) is not None


def latest(tags):
    """Highest semantic version among tags, or "" when there is none. Keeps the original spelling."""
    valid = [t for t in tags if is_semver(t)]
    if not valid:
        return ""
    return max(valid, key=sort_key)
