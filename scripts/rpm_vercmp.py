"""RPM version comparison, in pure Python.

Implements the same logic as ``rpmvercmp()`` in librpm, including the
special handling for ``~`` (pre-release) and ``^`` (post-release
snapshot) characters. Reimplemented from the ``sandogasa-rpmvercmp``
crate (slopfest/sandogasa, Apache-2.0 OR MIT), whose test vectors are
carried over verbatim in tests/test_rpm_vercmp.py.

Why this exists here: `docs/FACTORY-STATUS.md` measures *presence*, not
*freshness* — "version-level staleness needs catalog version pins" — and
the gap engine treats a dependency as satisfied whenever the target
provides the name at any version. The libnotify >= 0.8.7 failure (#480)
was exactly that blind spot: the target provided libnotify, just three
releases too old, and nothing could say so before mock did, hours in.
Version comparison is the primitive every version-aware check needs, and
the CI runners have no librpm Python bindings, so it lives here as
dependency-free code.

Key behaviours (same as librpm):

- ``~`` sorts *before* the version without it: ``1.0~rc1 < 1.0 < 1.0.1``
- ``^`` sorts *after* the base version but before a new segment:
  ``1.0 < 1.0^post1 < 1.0.1``
- Digit segments compare numerically (leading zeros ignored).
- Letter segments compare lexicographically.
- A digit segment is always newer than a letter segment.
- More segments means newer when all preceding segments are equal.
"""
from __future__ import annotations

import string

_ALNUM = set(string.ascii_letters + string.digits)
_KEEP = _ALNUM | {"~", "^"}


def rpmvercmp(a: str, b: str) -> int:
    """Compare two version strings; returns -1, 0, or 1."""
    ia = ib = 0
    while True:
        # Skip non-alphanumeric characters that are not ~ or ^.
        while ia < len(a) and a[ia] not in _KEEP:
            ia += 1
        while ib < len(b) and b[ib] not in _KEEP:
            ib += 1

        # ~ (pre-release) sorts before everything, including
        # end-of-string.
        a_tilde = ia < len(a) and a[ia] == "~"
        b_tilde = ib < len(b) and b[ib] == "~"
        if a_tilde and b_tilde:
            ia += 1
            ib += 1
            continue
        if a_tilde:
            return -1
        if b_tilde:
            return 1

        # ^ (post-release snapshot) sorts after end-of-string but
        # before any other segment.
        a_caret = ia < len(a) and a[ia] == "^"
        b_caret = ib < len(b) and b[ib] == "^"
        if a_caret and b_caret:
            ia += 1
            ib += 1
            continue
        if a_caret:
            return 1 if ib >= len(b) else -1
        if b_caret:
            return -1 if ia >= len(a) else 1

        a_done = ia >= len(a)
        b_done = ib >= len(b)
        if a_done and b_done:
            return 0
        if a_done:
            return -1
        if b_done:
            return 1

        # Extract the next segment: a run of digits or a run of
        # letters.
        if a[ia].isdigit():
            ja = ia
            while ja < len(a) and a[ja].isdigit():
                ja += 1
        else:
            ja = ia
            while ja < len(a) and a[ja] in _ALNUM and not a[ja].isdigit():
                ja += 1
        if b[ib].isdigit():
            jb = ib
            while jb < len(b) and b[jb].isdigit():
                jb += 1
        else:
            jb = ib
            while jb < len(b) and b[jb] in _ALNUM and not b[jb].isdigit():
                jb += 1
        seg_a, seg_b = a[ia:ja], b[ib:jb]
        ia, ib = ja, jb

        a_num = seg_a[:1].isdigit()
        b_num = seg_b[:1].isdigit()
        # Digit segment always beats letter segment.
        if a_num and not b_num:
            return 1
        if b_num and not a_num:
            return -1
        if a_num:
            # Numeric: strip leading zeros; longer number is bigger,
            # same length compares lexicographically.
            at = seg_a.lstrip("0")
            bt = seg_b.lstrip("0")
            if len(at) != len(bt):
                return 1 if len(at) > len(bt) else -1
            if at != bt:
                return 1 if at > bt else -1
        else:
            if seg_a != seg_b:
                return 1 if seg_a > seg_b else -1


def parse_evr(evr: str) -> tuple[int, str, str | None]:
    """Split ``[epoch:]version[-release]`` into its three parts."""
    epoch = 0
    rest = evr
    if ":" in evr:
        head, rest = evr.split(":", 1)
        try:
            epoch = int(head)
        except ValueError:
            epoch = 0
    if "-" in rest:
        version, release = rest.rsplit("-", 1)
        return epoch, version, release
    return epoch, rest, None


def compare_evr(a: str, b: str) -> int:
    """Compare two ``[epoch:]version[-release]`` strings."""
    a_epoch, a_ver, a_rel = parse_evr(a)
    b_epoch, b_ver, b_rel = parse_evr(b)
    if a_epoch != b_epoch:
        return 1 if a_epoch > b_epoch else -1
    order = rpmvercmp(a_ver, b_ver)
    if order:
        return order
    if a_rel is not None and b_rel is not None:
        return rpmvercmp(a_rel, b_rel)
    if a_rel is not None:
        return 1
    if b_rel is not None:
        return -1
    return 0


def satisfies(available_evr: str, op: str, required_evr: str) -> bool:
    """Does the available EVR satisfy ``<op> required_evr``?

    RPM range semantics, matching dnf's boolean dependency comparison
    for a concrete available version: when the requirement carries no
    release, the available release is ignored for the comparison, so
    ``libnotify = 0.8.7`` is satisfied by ``0.8.7-1.el10``.
    """
    a_epoch, a_ver, a_rel = parse_evr(available_evr)
    r_epoch, r_ver, r_rel = parse_evr(required_evr)
    if r_rel is None:
        a_rel = None
    order = compare_evr(
        _join_evr(a_epoch, a_ver, a_rel), _join_evr(r_epoch, r_ver, r_rel)
    )
    if op in ("=", "=="):
        return order == 0
    if op == ">=":
        return order >= 0
    if op == "<=":
        return order <= 0
    if op == ">":
        return order > 0
    if op == "<":
        return order < 0
    raise ValueError(f"unknown dependency operator: {op!r}")


def _join_evr(epoch: int, version: str, release: str | None) -> str:
    evr = f"{epoch}:{version}"
    return f"{evr}-{release}" if release is not None else evr
