#!/usr/bin/env python3
"""One definition of which target-contract fields can change a build.

`manifests/package-factory.yaml` describes each target in a single block, and
that block mixes three different audiences:

  * what a BUILD reads   -- buildroot, probe_image, build_repositories,
                            architectures, format, and (for rpm) the
                            published_index a buildroot adds as a repo;
  * where PUBLISHING writes -- r2_path, r2_path_aarch64;
  * what REPORTING reads -- status, gap_measurement.

Two places decide "did this change matter": scripts/plan-package-factory.py,
which selects cells to run, and scripts/tideforge-action-cache.py, which
computes each cell's content-addressed key. Both must agree, so the answer
lives here rather than in either of them.

## Why this file exists (#473)

The planner already carried a partial version of this idea -- published_index
stripped for deb and pkg.tar.zst, added after declaring the served apt indexes
re-planned every deb cell (run 32397627179). The action key had no
counterpart, so a change to a bucket WRITE path rebuilt every cell on that
target from scratch.

Two readers of one contract, one of them incomplete, is the same shape as the
defect #471 fixed: published_index had two hand-copied readers that both
assumed a string, and fixing one would have left the other wrong. So this is
imported, not duplicated.

## The rule for adding a field here

A field belongs in this set only when NO build and NO verify reads it --
checked by grepping consumers, not by reading the name. published_index is
the field that makes the distinction sharp: it looks like publishing metadata
and is inert for deb and Arch, but an rpm buildroot genuinely adds it as a
repo, so for rpm it is a live build input and must keep re-keying. Getting
that backwards would let a cell reuse output built against a different
package universe.
"""
from __future__ import annotations

from typing import Any

# Inert for every format: nothing in any build or verify path reads these.
#   r2_path / r2_path_aarch64  bucket WRITE paths, read by the publishers and
#                              scripts/generate-distributed-workflow.py
#   gap_measurement            read only by scripts/measure-hummingbird-gap.py
#   status                     a reporting label (supported / scaffold)
BUILD_INERT_KEYS = frozenset({
    "r2_path",
    "r2_path_aarch64",
    "gap_measurement",
    "status",
})

# Inert for these formats only. An rpm buildroot ADDS published_index as a
# repo (scripts/run-package-factory-cell.sh writes it into
# /etc/yum.repos.d), so for rpm it is a live build input; the deb and Arch
# pipelines never look at it.
FORMAT_INERT_KEYS: dict[str, frozenset[str]] = {
    "deb": frozenset({"published_index"}),
    "pkg.tar.zst": frozenset({"published_index"}),
}


def inert_keys(spec: Any) -> frozenset[str]:
    """Fields of this target contract that cannot change a build's output."""
    if not isinstance(spec, dict):
        return BUILD_INERT_KEYS
    return BUILD_INERT_KEYS | FORMAT_INERT_KEYS.get(spec.get("format"), frozenset())


def build_view(spec: Any) -> Any:
    """The target contract as a build sees it, with inert fields removed.

    Non-mappings pass through: a malformed contract must reach the caller
    that validates it, not be silently normalised into an empty dict here.
    """
    if not isinstance(spec, dict):
        return spec
    drop = inert_keys(spec)
    return {key: value for key, value in spec.items() if key not in drop}
