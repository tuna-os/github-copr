"""Hummingbird ships packages that cannot install, including in Hummingbird.

Its protobuf and re2 were linked against abseil-cpp soname 2601, which
Hummingbird never shipped; Rawhide's abseil is 20260526.0, a different soname.
Hummingbird sits at priority 10 and wins the name, so the buildroot took the
broken copy and every build reaching it died -- measured in run 31281499563:

    package re2-2:20251105-19.hum1.x86_64 from hummingbird requires
      libabsl_hash.so.2601.0.0()(64bit), but none of the providers can be
      installed

Excluding them hands protobuf/re2 to Rawhide. The subtlety these tests exist
for is that the set must be CLOSED: protobuf-devel installs fine as shipped
and breaks only once protobuf-cpp is excluded, so a single pass produces a
config that is still wrong. Simulating the exclude before committing is what
caught that.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "target_abi_gaps", REPO / "scripts" / "target-abi-gaps.py"
)
gaps = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gaps)

ABSL = "libabsl_hash.so.2601.0.0()(64bit)"
PROTOBUF_SO = "libprotobuf.so.35.1.0()(64bit)"


def _indexes():
    """Hummingbird's protobuf/re2 shape, reduced to its bones."""
    target = {
        "packages": {
            "re2": {"srpm": "re2-1-1.hum1.src.rpm", "requires": [ABSL]},
            "protobuf-cpp": {"srpm": "protobuf-1-1.hum1.src.rpm", "requires": [ABSL]},
            "protobuf-devel": {
                "srpm": "protobuf-1-1.hum1.src.rpm",
                "requires": [PROTOBUF_SO],
            },
            "healthy": {"srpm": "healthy-1-1.hum1.src.rpm", "requires": ["libc.so.6"]},
        },
        "provides": {
            "re2": {"re2"},
            "protobuf-cpp": {"protobuf-cpp", "healthy"},
            PROTOBUF_SO: {"protobuf-cpp"},
            "protobuf-devel": {"protobuf-devel"},
            "healthy": {"healthy"},
            "libc.so.6": {"healthy"},
        },
    }
    reference = {
        "packages": {"re2": {"srpm": "re2-2-1.fc45.src.rpm", "requires": []}},
        "provides": {"re2": {"re2"}, "protobuf-cpp": {"protobuf-cpp"}},
    }
    return target, reference


def test_the_broken_packages_are_found() -> None:
    target, reference = _indexes()
    broken = gaps.unsatisfiable(target, reference)
    assert set(broken) == {"re2", "protobuf-cpp"}, broken
    assert ABSL in broken["re2"]


def test_the_closure_includes_the_package_the_exclude_orphans() -> None:
    """protobuf-devel is not broken as shipped -- excluding protobuf-cpp breaks it.

    A single pass returns {re2, protobuf-cpp} and leaves a buildroot that still
    cannot resolve protobuf-devel. This is the bug the simulation caught before
    the config was written.
    """
    target, reference = _indexes()
    closure = gaps.exclude_closure(target, reference)
    assert closure == {"re2", "protobuf-cpp", "protobuf-devel"}, closure


def test_nothing_soname_broken_survives_the_closure() -> None:
    target, reference = _indexes()
    closure = gaps.exclude_closure(target, reference)
    left = gaps.unsatisfiable(target, reference, closure)
    assert not [
        c for missing in left.values() for c in missing if gaps.is_soname(c)
    ], left


def test_a_healthy_package_is_never_excluded() -> None:
    """Over-excluding would silently swap the target's ABI for Rawhide's."""
    target, reference = _indexes()
    assert "healthy" not in gaps.exclude_closure(target, reference)


def test_python_dist_gaps_do_not_cascade() -> None:
    """`python3.14dist(...)` gaps are inert +extras metapackages, not ABI breaks.

    Excluding them would hide the gap rather than close it, and would drop 23
    Hummingbird packages from the buildroot for no benefit.
    """
    target, reference = _indexes()
    target["packages"]["python3-sentry-sdk+flask"] = {
        "srpm": "python-sentry-sdk-1-1.hum1.src.rpm",
        "requires": ["python3.14dist(flask)"],
    }
    assert "python3-sentry-sdk+flask" in gaps.unsatisfiable(target, reference)
    assert "python3-sentry-sdk+flask" not in gaps.exclude_closure(target, reference)


def test_a_graph_that_never_converges_is_an_error_not_a_hang() -> None:
    target, reference = _indexes()
    with pytest.raises(RuntimeError, match="did not converge"):
        gaps.exclude_closure(target, reference, limit=1)


def test_the_mock_config_carries_the_measured_closure() -> None:
    """The measurement is worthless if the buildroot does not apply it."""
    configured = gaps.configured_excludes(gaps.MOCK_CONFIG.read_text())
    assert configured == {
        "protobuf-compiler",
        "protobuf-cpp",
        "protobuf-devel",
        "protobuf-lite",
        "re2",
    }, f"mock/hummingbird-ci.cfg excludes {sorted(configured)}"


def test_the_config_says_why_and_how_to_recheck() -> None:
    text = gaps.MOCK_CONFIG.read_text()
    assert "2601" in text, "the config does not name the soname that broke"
    assert "target-abi-gaps.py" in text, "no pointer to the tool that recomputes it"
