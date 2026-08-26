"""The deb backport gap must be computed, and computed with the right rule.

RFC 011's gap engine is rpm-md only -- measure-target-gap.py is a shim over
gap_engine.py, which parses primary.xml and knows nothing about
APT. scripts/measure-deb-backport-gap.py is the deb half, and it answers a
different question: Hummingbird asks what a target fails to PROVIDE and closes
over Requires:, while a backport asks what must be REBUILT and closes over
Build-Depends:, because the packaging already exists in the donor suite.

The rule that bounds the closure is the interesting part, and the first
version of it was WRONG. "Include a build dependency when the donor's version
is newer than the target's" sounds right and is not: measured against Ubuntu
stonking, nearly every source in a devel suite is newer than in an LTS, so the
closure swallowed the archive and reported 1263 packages -- swig, gettext,
node-mocha, ruby-rspec, the Go toolchain. With the constraint honoured the
same measurement reports 16, all of them real GNOME-stack packages.

So the rule is: a build dependency forces a rebuild only when the target
FAILS A DECLARED CONSTRAINT. An unversioned build-dep is satisfied by the
target having the package at all, which is what keeps the toolchain out.
"""
from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "measure_deb_backport_gap", ROOT / "scripts" / "measure-deb-backport-gap.py"
)
gap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gap)


def test_a_tilde_sorts_below_the_release_it_precedes():
    """Load-bearing: every donor version in the manifest today is a ~alpha or
    ~beta, so a comparator that got this backwards would report the whole
    stack as already satisfied and measure a gap of zero."""
    assert gap.compare_versions("51~beta", "51") < 0
    assert gap.compare_versions("51~alpha", "51~beta") < 0
    assert gap.compare_versions("50.1", "51~beta") < 0
    assert gap.compare_versions("51", "51") == 0


def test_epoch_and_revision_follow_dpkg():
    assert gap.compare_versions("1:50.0", "50.9") > 0
    assert gap.compare_versions("1.0-1", "1.0-2") < 0
    assert gap.compare_versions("1.0", "1.0-1") < 0
    assert gap.compare_versions("2.88.0", "2.89.3") < 0


def test_an_unversioned_build_dep_is_satisfied_by_mere_presence():
    """This single rule is what separates 16 packages from 1263."""
    assert gap.satisfies("11.7.5", "", "") is True
    assert gap.satisfies(None, "", "") is False


def test_a_version_floor_is_enforced():
    assert gap.satisfies("2.88.0", ">=", "2.89.0") is False
    assert gap.satisfies("2.89.3", ">=", "2.89.0") is True
    assert gap.satisfies("1.0", ">>", "1.0") is False


def test_clauses_keep_their_constraints():
    stanza = {"Build-Depends": "debhelper, libglib2.0-dev (>= 2.89.0) [amd64], a | b"}
    clauses = gap.build_dep_clauses(stanza)
    assert ["debhelper", "", ""] == list(clauses[0][0])
    assert ["libglib2.0-dev", ">=", "2.89.0"] == list(clauses[1][0])
    assert [name for name, _, _ in clauses[2]] == ["a", "b"]


def test_a_newer_donor_dep_alone_does_not_force_a_rebuild():
    """The 1263-package regression, in miniature. `tool` is newer in the donor
    but the build-dep is unversioned, so it must NOT enter the closure."""
    donor = {
        "app": {"Package": "app", "Version": "51~beta-1", "Binary": "app",
                "Build-Depends": "tool"},
        "tool": {"Package": "tool", "Version": "2.0", "Binary": "tool"},
    }
    target = {
        "app": {"Package": "app", "Version": "50.0-1", "Binary": "app"},
        "tool": {"Package": "tool", "Version": "1.0", "Binary": "tool"},
    }
    target_binary = {"app": "50.0-1", "tool": "1.0"}
    result = gap.measure(["app"], donor, target, gap.binary_to_source(donor), target_binary)
    assert set(result["needed"]) == {"app"}, result["needed"]


def test_a_failed_version_floor_does_force_a_rebuild():
    """The same shape, with a constraint the target cannot meet."""
    donor = {
        "app": {"Package": "app", "Version": "51~beta-1", "Binary": "app",
                "Build-Depends": "tool (>= 2.0)"},
        "tool": {"Package": "tool", "Version": "2.0", "Binary": "tool"},
    }
    target = {
        "app": {"Package": "app", "Version": "50.0-1", "Binary": "app"},
        "tool": {"Package": "tool", "Version": "1.0", "Binary": "tool"},
    }
    target_binary = {"app": "50.0-1", "tool": "1.0"}
    result = gap.measure(["app"], donor, target, gap.binary_to_source(donor), target_binary)
    assert set(result["needed"]) == {"app", "tool"}, result["needed"]
    # tool must build BEFORE app, so it sits in an earlier tier.
    edges = gap.build_edges(result["needed"], donor, gap.binary_to_source(donor), target_binary)
    order = gap.tiers(edges)
    assert order[0] == ["tool"] and order[-1] == ["app"], order


def test_a_target_that_has_caught_up_needs_nothing():
    """The engine retires itself. Once a suite ships the stack, the answer is
    zero without anyone editing the manifest -- which is why debian/sid is
    listed even though it will get GNOME 51 on its own."""
    donor = {"app": {"Package": "app", "Version": "51.0-1", "Binary": "app"}}
    target = {"app": {"Package": "app", "Version": "51.0-1", "Binary": "app"}}
    result = gap.measure(["app"], donor, target, gap.binary_to_source(donor), {"app": "51.0-1"})
    assert result["needed"] == {}


def test_the_manifest_only_names_declared_targets():
    import yaml
    manifest = yaml.safe_load((ROOT / "manifests" / "gnome51-deb.yaml").read_text())
    contract = yaml.safe_load((ROOT / "manifests" / "package-factory.yaml").read_text())
    for name in manifest["targets"]:
        assert name in contract["targets"], name
        assert contract["targets"][name]["format"] == "deb", name
    assert manifest["roots"], "a gap over no roots measures nothing"


def test_a_package_the_donor_cannot_build_is_reported():
    """The donor suite is not static, and a source in it can be temporarily
    unbuildable from that suite alone.

    Measured: wayland-protocols 1.49-1 in Ubuntu stonking build-depends on
    libwayland-dev (>= 1.25.0), while `wayland` is 1.24.0-2 in BOTH stonking
    and resolute -- 1.26.0-1 sits in stonking-proposed and has not migrated.
    The closure was right to leave `wayland` out (the donor has nothing newer
    to offer), so the order lists a package nobody can rebuild from stonking.
    Run 32643256826 discovered that two minutes in, after paying for a
    container and a buildroot; this turns it into a line of the report.
    """
    donor = {
        "app": {"Package": "app", "Version": "2.0-1", "Binary": "app",
                "Build-Depends": "libfoo-dev (>= 9.0)"},
        "foo": {"Package": "foo", "Version": "1.0-1", "Binary": "libfoo-dev"},
    }
    donor_binary = {"app": "2.0-1", "libfoo-dev": "1.0-1"}
    blocked = gap.donor_cannot_build({"app": {}}, donor, donor_binary)
    assert blocked == {"app": ["libfoo-dev (>= 9.0)"]}, blocked


def test_virtual_build_deps_are_not_reported_as_unbuildable():
    """A Sources index lists a source's REAL binaries and says nothing about
    Provides, so every virtual package looks absent.

    The first version of this check reported all of debhelper-compat,
    dh-sequence-gir, dh-sequence-gnome and the gir1.2-*-dev virtuals, flagging
    16 of 16 packages and burying the single true finding. "Present but too
    old" is decidable from this data; "not in the map" is not.
    """
    donor = {
        "app": {"Package": "app", "Version": "2.0-1", "Binary": "app",
                "Build-Depends": "debhelper-compat (= 13), dh-sequence-gir, gir1.2-gio-2.0-dev"},
    }
    donor_binary = {"app": "2.0-1"}
    assert gap.donor_cannot_build({"app": {}}, donor, donor_binary) == {}


def test_a_satisfied_constraint_is_not_reported():
    donor = {
        "app": {"Package": "app", "Version": "2.0-1", "Binary": "app",
                "Build-Depends": "libfoo-dev (>= 1.0)"},
        "foo": {"Package": "foo", "Version": "1.0-1", "Binary": "libfoo-dev"},
    }
    donor_binary = {"app": "2.0-1", "libfoo-dev": "1.0-1"}
    assert gap.donor_cannot_build({"app": {}}, donor, donor_binary) == {}


def test_tiers_are_topological_not_breadth_first():
    """A cross-edge must still push a dependency into an earlier tier.

    BFS depth was the first implementation and is only correct on a tree.
    Measured failure: with -proposed in the donor, `wayland` and
    `wayland-protocols` both came out at depth 2 and shared a tier, even
    though wayland-protocols build-depends on libwayland-dev from wayland.
    Depth is assigned by first reach, so the later cross-edge never pushed
    wayland deeper, and the chain only worked because "wayland" sorts before
    "wayland-protocols" within a tier.

    Here `dep` is reachable at distance 1 from root AND at distance 2 via
    mid, which is exactly the shape that collapsed.
    """
    edges = {
        "root": {"mid", "dep"},
        "mid": {"dep"},
        "dep": set(),
    }
    order = gap.tiers(edges)
    assert order == [["dep"], ["mid"], ["root"]], order


def test_a_dependency_cycle_is_reported_rather_than_mis_ordered():
    """An order that silently cannot work is worse than a refusal."""
    import pytest
    with pytest.raises(SystemExit) as excinfo:
        gap.tiers({"a": {"b"}, "b": {"a"}})
    assert "cycle" in str(excinfo.value)
    assert "a" in str(excinfo.value) and "b" in str(excinfo.value)


def test_the_ubuntu_donor_includes_proposed_and_debian_does_not_need_it():
    """-proposed is a deliberate trade, recorded so it can be revisited after
    GNOME 51.0 ships: without it wayland-protocols cannot be rebuilt at all."""
    import yaml
    manifest = yaml.safe_load((ROOT / "manifests" / "gnome51-deb.yaml").read_text())
    assert manifest["targets"]["ubuntu"]["donor_suites"] == ["stonking", "stonking-proposed"]
    assert any("stonking-proposed" in url
               for url in manifest["targets"]["ubuntu"]["donor_index"])
    # Debian stages in experimental and falls back to sid; no -proposed pocket.
    assert manifest["targets"]["debian"]["donor_suites"] == ["experimental", "sid"]


# ---------------------------------------------------------------- Provides
#
# A Sources index lists a source's REAL binaries and never its `Provides:`,
# so every virtual package looks absent from it -- and "absent from the map"
# is indistinguishable there from "genuinely missing". The first real tier-0
# run (32651265182) built 7 of 10 packages and lost all three of the rest to
# that one blind spot:
#
#   builddeps:.../gexiv2-0.16.2 : Depends: debhelper-compat (= 14)
#   builddeps:.../gnome-desktop-51~alpha : Depends: debhelper-compat (= 14)
#   builddeps:.../gsettings-desktop-schemas-51~beta : Depends: debhelper-compat (= 14)
#   ...
#   E: Unable to satisfy dependencies. [no choices]
#
# Everything else apt printed underneath was the usual cascade of "but it is
# not going to be installed" for packages that were fine.
#
# Measured against the live archives: resolute's debhelper is 13.31ubuntu1
# and provides debhelper-compat 9 through 13. stonking's is 14.x. Reading the
# binary Packages indexes makes that decidable, and `debhelper` now enters
# the closure at tier-0 with the three failures ordered after it.


def test_an_unversioned_provides_cannot_satisfy_a_versioned_dependency():
    """Debian policy 7.5, and the whole answer for debhelper-compat.

    If a provider counted regardless of version, resolute's debhelper would
    look adequate for `debhelper-compat (= 14)` and the closure would stay
    wrong -- in the other direction, and just as silently.
    """
    module = gap
    provides = {"dh-sequence-python3": [None], "debhelper-compat": ["13"]}
    # Unversioned dep, unversioned Provides: satisfied.
    assert module.clause_satisfied("dh-sequence-python3", "", "", {}, provides)
    # Versioned dep against the version resolute actually provides.
    assert module.clause_satisfied("debhelper-compat", "=", "13", {}, provides)
    assert not module.clause_satisfied("debhelper-compat", "=", "14", {}, provides)
    # An unversioned Provides against a versioned dep: never.
    assert not module.clause_satisfied("dh-sequence-python3", ">=", "1", {}, provides)


def test_a_virtual_the_target_cannot_supply_pulls_in_the_source_that_can():
    """The fix, end to end, on the shape that broke.

    gexiv2 build-depends `debhelper-compat (= 14)`; the target's debhelper
    provides 13. The measurement has to reach `debhelper` -- a source no root
    names and no Sources index connects to that clause.
    """
    module = gap
    donor = {
        "gexiv2": {"Package": "gexiv2", "Version": "0.16.2-1", "Binary": "libgexiv2-2",
                   "Build-Depends": "debhelper-compat (= 14)"},
        "debhelper": {"Package": "debhelper", "Version": "14.1", "Binary": "debhelper"},
    }
    target = {"gexiv2": {"Package": "gexiv2", "Version": "0.14.0-1", "Binary": "libgexiv2-2"},
              "debhelper": {"Package": "debhelper", "Version": "13.31", "Binary": "debhelper"}}
    result = module.measure(
        ["gexiv2"], donor, target, module.binary_to_source(donor),
        {"libgexiv2-2": "0.14.0-1", "debhelper": "13.31"},
        target_provides={"debhelper-compat": ["9", "10", "11", "12", "13"]},
        donor_virtual_source={"debhelper-compat": "debhelper"},
    )
    assert set(result["needed"]) == {"gexiv2", "debhelper"}
    assert not result["unattributable"]


def test_a_virtual_the_target_already_supplies_stays_out_of_the_closure():
    """`dh-sequence-python3` is provided unversioned by the target's dh-python.

    Apt listed it under the same failure, which made it look like a second
    missing package. It was cascade noise: once one member of a builddeps
    group has no candidate, apt reports the whole group. Pulling dh-python
    into a backport it does not need would be its own kind of wrong.
    """
    module = gap
    donor = {
        "gexiv2": {"Package": "gexiv2", "Version": "0.16.2-1", "Binary": "libgexiv2-2",
                   "Build-Depends": "dh-sequence-python3"},
        "dh-python": {"Package": "dh-python", "Version": "9", "Binary": "dh-python"},
    }
    target = {"gexiv2": {"Package": "gexiv2", "Version": "0.14.0-1", "Binary": "libgexiv2-2"}}
    result = module.measure(
        ["gexiv2"], donor, target, module.binary_to_source(donor),
        {"libgexiv2-2": "0.14.0-1"},
        target_provides={"dh-sequence-python3": [None]},
        donor_virtual_source={"dh-sequence-python3": "dh-python"},
    )
    assert set(result["needed"]) == {"gexiv2"}


def test_an_unsatisfiable_clause_nobody_can_supply_is_reported_not_dropped():
    """This is the guard, and it is the part that generalises.

    Before, a clause that no alternative satisfied and that mapped to no
    source was simply skipped -- so the measurement reported a closure that
    could not build, and said nothing. Whatever the next unmappable name
    turns out to be, it has to come out as a finding rather than as three
    failed builds in a dispatched chain.
    """
    module = gap
    donor = {"gexiv2": {"Package": "gexiv2", "Version": "0.16.2-1", "Binary": "libgexiv2-2",
                        "Build-Depends": "dh-sequence-invented (>= 3)"}}
    target = {"gexiv2": {"Package": "gexiv2", "Version": "0.14.0-1", "Binary": "libgexiv2-2"}}
    result = module.measure(
        ["gexiv2"], donor, target, module.binary_to_source(donor),
        {"libgexiv2-2": "0.14.0-1"}, target_provides={}, donor_virtual_source={})
    assert result["unattributable"] == {"gexiv2": ["dh-sequence-invented (>= 3)"]}


def test_the_ordering_resolves_virtuals_the_same_way_the_closure_does():
    """If the two disagreed, a package would enter the closure through a
    virtual clause and then be ordered as though that clause did not exist.

    That is worse than the bug this fixes: a chain that builds things in the
    wrong order goes red somewhere unrelated, rather than reporting a gap.
    """
    module = gap
    donor = {
        "gexiv2": {"Package": "gexiv2", "Version": "0.16.2-1", "Binary": "libgexiv2-2",
                   "Build-Depends": "debhelper-compat (= 14)"},
        "debhelper": {"Package": "debhelper", "Version": "14.1", "Binary": "debhelper"},
    }
    needed = {"gexiv2": {}, "debhelper": {}}
    edges = module.build_edges(
        needed, donor, module.binary_to_source(donor), {"debhelper": "13.31"},
        target_provides={"debhelper-compat": ["13"]},
        donor_virtual_source={"debhelper-compat": "debhelper"})
    assert edges["gexiv2"] == {"debhelper"}
    assert module.tiers(edges) == [["debhelper"], ["gexiv2"]]


def test_the_binary_index_is_derived_from_the_declared_source_index():
    """Not a second hand-maintained list of the same suite/component pairings.

    Two lists can disagree, and a disagreement here is invisible: a wrong
    binary URL reads as "that virtual package does not exist", which is
    exactly the failure mode being fixed.
    """
    module = gap
    assert module.packages_url(
        "https://archive.ubuntu.com/ubuntu/dists/resolute/universe/source/Sources.xz"
    ) == "https://archive.ubuntu.com/ubuntu/dists/resolute/universe/binary-amd64/Packages.xz"
    import yaml
    manifest = yaml.safe_load((ROOT / "manifests" / "gnome51-deb.yaml").read_text())
    for spec in manifest["targets"].values():
        for url in spec["target_index"] + spec["donor_index"]:
            derived = module.packages_url(url)
            assert derived != url, f"the transform did not fire on {url}"
            assert derived.endswith("/binary-amd64/Packages.xz")


def test_provides_and_source_are_read_the_way_deb822_writes_them():
    module = gap
    assert module.parse_provides("foo, bar (= 1.2), baz:any") == [
        ("foo", None), ("bar", "1.2"), ("baz", None)]
    text = (
        "Package: debhelper\n"
        "Version: 14.1\n"
        "Provides: debhelper-compat (= 14)\n"
        "\n"
        "Package: dh-python\n"
        "Source: dh-python-src (9.0)\n"
        "Version: 9\n"
        "Provides: dh-sequence-python3,\n"
        " dh-sequence-python2\n"
    )
    packages = module.parse_packages(text)
    assert packages["debhelper"]["Version"] == "14.1"
    assert module.provides_map(packages)["debhelper-compat"] == ["14"]
    # `Source:` is omitted when it equals the binary name, and may carry a
    # version in parentheses.
    virtual = module.virtual_to_source(packages)
    assert virtual["debhelper-compat"] == "debhelper"
    assert virtual["dh-sequence-python3"] == "dh-python-src"
    assert virtual["dh-sequence-python2"] == "dh-python-src"


def test_the_measured_report_records_the_debhelper_finding():
    """The committed report is the evidence, so it has to carry the answer.

    `debhelper` at tier-0 with gexiv2, gnome-desktop and
    gsettings-desktop-schemas after it IS the fix for run 32651265182.
    """
    import json
    report = json.loads(
        (ROOT / "docs" / "gnome51-deb-gap.json").read_text())["targets"]["ubuntu"]
    assert "debhelper" in report["tiers"][0]
    later = {name for tier in report["tiers"][1:] for name in tier}
    for source in ("gexiv2", "gnome-desktop", "gsettings-desktop-schemas"):
        assert source in later, f"{source} must be ordered after debhelper"
    assert report["unattributable"] == {}, (
        "a measured gap with unattributable clauses is a gap that cannot build"
    )
