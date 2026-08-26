"""Reader for a flat APT repository's Packages index.

The deb targets' `published_index` URLs are flat repos exactly as
publish-tideforge-debs.yml writes them: `Packages` (and `Packages.gz`)
at the root, one RFC-822-style stanza per binary package, `Filename:`
pointing into `pool/`. This module parses that shape into the same
row/index structures the RPM checks consume, so hygiene and the
reverse-dep gate work on every format the factory serves — not only
the RPM half (the factory ships Ubuntu and Debian Sid as supported
targets, and a check that cannot read them is a check with an EL-shaped
blind spot).

Also parses dependency fields (deb-control(5)): comma-separated
relations, `|` alternatives, `pkg (>= 1.2)` constraints, `pkg:any`
architecture qualifiers, and versioned `Provides` (`foo (= 1.0)`).
"""
from __future__ import annotations

import gzip
import lzma
import re

_RELATION = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9][A-Za-z0-9+.-]*)"
    r"(?::(?P<arch>[A-Za-z0-9-]+))?"
    r"\s*(?:\(\s*(?P<op><<|<=|=|>=|>>|<|>)\s*(?P<version>[^)]+?)\s*\))?"
    r"\s*(?:\[[^]]*\])?"          # architecture restriction list
    r"\s*(?:<[^>]*>)?\s*$")       # build profiles


def decompress(name: str, blob: bytes) -> bytes:
    if name.endswith(".gz"):
        return gzip.decompress(blob)
    if name.endswith(".xz"):
        return lzma.decompress(blob)
    return blob


def stanzas(text: str):
    """Each stanza as a {Field: value} dict, continuation lines joined."""
    current: dict[str, str] = {}
    field = None
    for line in text.splitlines():
        if not line.strip():
            if current:
                yield current
            current, field = {}, None
            continue
        if line[:1] in (" ", "\t") and field:
            current[field] += "\n" + line.strip()
            continue
        if ":" in line:
            field, _, value = line.partition(":")
            field = field.strip()
            current[field] = value.strip()
    if current:
        yield current


def parse_relation(text: str) -> tuple[str, str | None, str | None] | None:
    """One relation -> (name, op, version); None if unparseable."""
    match = _RELATION.match(text)
    if not match:
        return None
    return match.group("name"), match.group("op"), match.group("version")


def parse_depends(value: str) -> list[list[tuple[str, str | None, str | None]]]:
    """A Depends value -> [[alternative, ...], ...].

    Outer list is AND (comma), inner list is OR (`|`). Unparseable
    relations are dropped rather than guessed at — a gate must not
    fail on syntax it does not understand.
    """
    groups = []
    for clause in value.split(","):
        alternatives = []
        for alt in clause.split("|"):
            parsed = parse_relation(alt)
            if parsed:
                alternatives.append(parsed)
        if alternatives:
            groups.append(alternatives)
    return groups


def parse_packages(text: str) -> dict:
    """A Packages file in the shape the format-neutral checks consume."""
    return index_from_stanzas(stanzas(text))


def index_from_stanzas(entries) -> dict:
    """Build the standard index shape from stanza dicts.

    packages: name -> {arch, evr, srpm (the Source), requires (names),
    requires_versioned [(name, op, version)], depends (full AND/OR
    groups), files []}; provides / provides_evr as in parse_primary.
    Later stanzas win on name collision — callers that need candidate
    semantics (highest version wins, as apt selects) pre-filter the
    stanzas; the hygiene duplicate check uses iter_rows below, which
    keeps every stanza.
    """
    packages: dict[str, dict] = {}
    provides: dict[str, set] = {}
    provides_evr: dict[str, set] = {}
    for stanza in entries:
        name = stanza.get("Package")
        if not name:
            continue
        version = stanza.get("Version", "")
        depends = parse_depends(stanza.get("Depends", "")) + parse_depends(
            stanza.get("Pre-Depends", ""))
        packages[name] = {
            "arch": stanza.get("Architecture", ""),
            "evr": version,
            "srpm": (stanza.get("Source", name).split(" ")[0]),
            "requires": [group[0][0] for group in depends if len(group) == 1],
            "requires_versioned": [
                (dep, op, ver) for group in depends if len(group) == 1
                for dep, op, ver in group if op and ver
            ],
            "depends": depends,
            "files": [],
        }
        provides.setdefault(name, set()).add(name)
        provides_evr.setdefault(name, set()).add(version)
        for relation in stanza.get("Provides", "").split(","):
            parsed = parse_relation(relation)
            if not parsed or not parsed[0]:
                continue
            cap, op, ver = parsed
            provides.setdefault(cap, set()).add(name)
            if op == "=" and ver:
                provides_evr.setdefault(cap, set()).add(ver)
    return {"packages": packages, "provides": provides,
            "provides_evr": provides_evr, "files": set()}


def iter_rows(text: str):
    """Every stanza as a hygiene row, duplicates included."""
    for stanza in stanzas(text):
        name = stanza.get("Package")
        if not name:
            continue
        yield {
            "name": name,
            "arch": stanza.get("Architecture", ""),
            "evr": stanza.get("Version", ""),
            "srpm": stanza.get("Source", name).split(" ")[0],
            # Pool path relative to the index URL; see repo_index's note.
            "location": stanza.get("Filename"),
            # Flat repos carry no Contents index, so file-level conflict
            # checking is not measurable here; recorded in the hygiene
            # tool's scope notes rather than silently pretended.
            "files": [],
        }
