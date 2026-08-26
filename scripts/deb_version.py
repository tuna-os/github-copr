"""Debian version comparison, in pure Python.

Implements dpkg's algorithm (deb-version(7)): an optional numeric
``epoch:``, an upstream version, and an optional ``-revision`` split on
the LAST hyphen. Each part compares by alternating runs of non-digits
and digits, where non-digit runs use modified ASCII — all letters sort
before all non-letters, and ``~`` sorts before everything, including
the end of the string (so ``1.0~rc1 < 1.0``).

This is NOT the RPM algorithm (scripts/rpm_vercmp.py): RPM tokenizes
into alnum segments and ranks digit segments above letter segments;
dpkg compares character by character with the letters-before-symbols
rule. The two disagree on real versions (``1.0+git1`` vs ``1.0.1``
among them), which is why the deb targets get their own module instead
of a shared approximation — a factory for every target cannot judge
Debian constraints with Fedora's ruler.

Companion to the sandogasa adaptations (docs/SANDOGASA-ADAPTATIONS.md):
sandogasa itself is Fedora/CentOS-centric here; this module is the part
this factory needed that upstream did not carry.
"""
from __future__ import annotations


def _order(char: str) -> int:
    """dpkg's character weight inside a non-digit run."""
    if char == "~":
        return -1
    if char.isalpha():
        return ord(char)
    # Non-letter, non-tilde symbols sort after all letters.
    return ord(char) + 256


def _cmp_nondigits(a: str, b: str, ia: int, ib: int) -> tuple[int, int, int]:
    while True:
        ca = a[ia] if ia < len(a) and not a[ia].isdigit() else ""
        cb = b[ib] if ib < len(b) and not b[ib].isdigit() else ""
        if not ca and not cb:
            return 0, ia, ib
        # End-of-run weighs 0; ~ weighs less than that, so `1.0~` < `1.0`.
        wa = _order(ca) if ca else 0
        wb = _order(cb) if cb else 0
        if wa != wb:
            return (1 if wa > wb else -1), ia, ib
        ia += 1
        ib += 1


def _cmp_part(a: str, b: str) -> int:
    ia = ib = 0
    while ia < len(a) or ib < len(b):
        order, ia, ib = _cmp_nondigits(a, b, ia, ib)
        if order:
            return order
        ja = ia
        while ja < len(a) and a[ja].isdigit():
            ja += 1
        jb = ib
        while jb < len(b) and b[jb].isdigit():
            jb += 1
        na = int(a[ia:ja] or "0")
        nb = int(b[ib:jb] or "0")
        if na != nb:
            return 1 if na > nb else -1
        ia, ib = ja, jb
    return 0


def parse_version(version: str) -> tuple[int, str, str]:
    """``[epoch:]upstream[-revision]`` -> (epoch, upstream, revision).

    The revision splits on the LAST hyphen — upstream versions may
    contain hyphens; a missing revision compares as ``0`` per policy.
    """
    epoch = 0
    rest = version
    if ":" in version:
        head, rest = version.split(":", 1)
        try:
            epoch = int(head)
        except ValueError:
            epoch = 0
    if "-" in rest:
        upstream, revision = rest.rsplit("-", 1)
    else:
        upstream, revision = rest, "0"
    return epoch, upstream, revision


def compare(a: str, b: str) -> int:
    """dpkg --compare-versions, returning -1, 0, or 1."""
    a_epoch, a_up, a_rev = parse_version(a)
    b_epoch, b_up, b_rev = parse_version(b)
    if a_epoch != b_epoch:
        return 1 if a_epoch > b_epoch else -1
    order = _cmp_part(a_up, b_up)
    if order:
        return order
    return _cmp_part(a_rev, b_rev)


def satisfies(available: str, op: str, required: str) -> bool:
    """Does the available version satisfy ``<op> required``?

    Debian relationship operators (deb-control(5)): ``<<`` and ``>>``
    are strict; ``<=``, ``>=``, ``=`` as expected. The obsolete ``<``
    and ``>`` are accepted with their historical (inclusive) meaning,
    as dpkg still does.
    """
    order = compare(available, required)
    if op == "=":
        return order == 0
    if op in (">=", ">"):
        return order >= 0
    if op in ("<=", "<"):
        return order <= 0
    if op == ">>":
        return order > 0
    if op == "<<":
        return order < 0
    raise ValueError(f"unknown dependency operator: {op!r}")
