"""The served combination of prefixes is checked, not each in isolation.

Adapted from hs-relmon's dupe-subpkgs / file-conflicts checks
(slopfest/sandogasa). Every check pins a defect class this repository
has already shipped: the createrepo_c --update stale entry (#358), one
NEVRA served twice across el10's two published prefixes (#471), and the
glib2-Obsoletes shape where whichever repo wins decides what installs.
"""
from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "hygiene", ROOT / "scripts" / "check-published-hygiene.py"
)
hygiene = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hygiene)


def row(name, evr="0:1.0-1.el10", arch="x86_64", srpm=None, files=()):
    return {"name": name, "evr": evr, "arch": arch,
            "srpm": srpm or f"{name}-1.0-1.el10.src.rpm",
            "files": list(files)}


def test_a_clean_prefix_set_has_no_findings():
    findings = hygiene.analyse({
        "https://repo/a": [row("glib2", files=["/usr/bin/gio"]),
                           row("gtk4", files=["/usr/bin/gtk4-update-icon-cache"])],
        "https://repo/b": [row("xfconf", files=["/usr/bin/xfconf-query"])],
    })
    assert hygiene.total(findings) == 0


def test_the_createrepo_update_class_a_stale_duplicate_nevra():
    """#358: --update kept the old entry beside the new one.

    Same name, same EVR, same arch, twice in one index. dnf tolerates
    it, which is exactly why nothing noticed until it broke something
    else — the index is lying about its own size.
    """
    findings = hygiene.analyse({
        "https://repo/a": [row("glib2"), row("glib2")],
    })
    dupes = findings["duplicate_nevra_in_prefix"]
    assert len(dupes) == 1
    assert dupes[0]["name"] == "glib2"
    assert dupes[0]["count"] == 2


def test_two_sources_shipping_one_binary_name_in_one_prefix():
    """hs-relmon's dupe-subpkgs: dnf picks by version, not by intent."""
    findings = hygiene.analyse({
        "https://repo/a": [
            row("python3-tools", srpm="kernel-6.1-1.el10.src.rpm"),
            row("python3-tools", evr="0:2.0-1.el10",
                srpm="python-tools-2.0-1.el10.src.rpm"),
        ],
    })
    dupe = findings["duplicate_name_two_sources_in_prefix"]
    assert len(dupe) == 1
    assert dupe[0]["sources"] == ["kernel", "python-tools"]


def test_one_name_from_two_prefixes_is_shadowing_when_versions_differ():
    """#471's class: both prefixes are in the same buildroot's universe.

    Different EVRs means repo priority silently decides what installs —
    and #453/#455 proved priority is not a defence here.
    """
    findings = hygiene.analyse({
        "https://repo/a": [row("libnotify", evr="0:0.8.6-1.el10")],
        "https://repo/b": [row("libnotify", evr="0:0.8.7-1.el10")],
    })
    served = findings["name_served_by_multiple_prefixes"]
    assert len(served) == 1
    assert served[0]["severity"] == "shadowing"
    assert set(served[0]["prefixes"]) == {"https://repo/a", "https://repo/b"}


def test_one_name_from_two_prefixes_at_one_version_is_redundant():
    findings = hygiene.analyse({
        "https://repo/a": [row("libnotify")],
        "https://repo/b": [row("libnotify")],
    })
    assert findings["name_served_by_multiple_prefixes"][0]["severity"] == "redundant"


def test_a_file_owned_by_two_differently_named_packages_is_a_conflict():
    """dnf resolves both packages happily; rpm fails the transaction."""
    findings = hygiene.analyse({
        "https://repo/a": [row("kernel-tools", files=["/usr/bin/ynl"])],
        "https://repo/b": [row("python3-ynl", files=["/usr/bin/ynl"])],
    })
    conflicts = findings["file_conflicts"]
    assert len(conflicts) == 1
    assert conflicts[0]["file"] == "/usr/bin/ynl"
    assert len(conflicts[0]["owners"]) == 2


def test_the_same_package_in_two_prefixes_is_not_a_file_conflict():
    """Redundancy is its own (milder) finding; it is not a file fight."""
    findings = hygiene.analyse({
        "https://repo/a": [row("xfconf", files=["/usr/bin/xfconf-query"])],
        "https://repo/b": [row("xfconf", files=["/usr/bin/xfconf-query"])],
    })
    assert findings["file_conflicts"] == []


def test_subpackages_of_one_source_sharing_a_file_is_not_a_conflict():
    """rpm permits identical files across subpackages of one source.

    net-snmp and net-snmp-utils both ship /usr/bin/snmpd from the
    net-snmp source, deliberately. Measured live: reporting these
    buries the real cross-source conflicts under packaging choices.
    """
    findings = hygiene.analyse({
        "https://repo/a": [
            row("net-snmp", srpm="net-snmp-5.9-1.el10.src.rpm",
                files=["/usr/bin/snmpd"]),
            row("net-snmp-utils", srpm="net-snmp-5.9-1.el10.src.rpm",
                files=["/usr/bin/snmpd"]),
        ],
    })
    assert findings["file_conflicts"] == []


def test_source_rpms_do_not_participate_in_binary_checks():
    findings = hygiene.analyse({
        "https://repo/a": [row("glib2", arch="src"),
                           row("glib2", arch="x86_64")],
        "https://repo/b": [row("glib2", arch="src")],
    })
    assert findings["name_served_by_multiple_prefixes"] == []


def test_the_xml_iterator_keeps_duplicate_entries():
    """parse_primary keys by name; the duplicate checks must not."""
    blob = b"""<?xml version="1.0"?>
<metadata xmlns="http://linux.duke.edu/metadata/common"
          xmlns:rpm="http://linux.duke.edu/metadata/rpm" packages="2">
  <package type="rpm">
    <name>glib2</name><arch>x86_64</arch>
    <version epoch="0" ver="2.87.3" rel="1.el10"/>
    <format>
      <rpm:sourcerpm>glib2-2.87.3-1.el10.src.rpm</rpm:sourcerpm>
      <file>/usr/bin/gio</file>
      <file type="dir">/etc/glib-2.0</file>
      <file type="ghost">/var/lib/gio.cache</file>
    </format>
  </package>
  <package type="rpm">
    <name>glib2</name><arch>x86_64</arch>
    <version epoch="0" ver="2.87.3" rel="1.el10"/>
    <format>
      <rpm:sourcerpm>glib2-2.87.3-1.el10.src.rpm</rpm:sourcerpm>
    </format>
  </package>
</metadata>"""
    rows = list(hygiene.iter_packages(blob))
    assert len(rows) == 2
    assert rows[0]["name"] == rows[1]["name"] == "glib2"
    assert rows[0]["evr"] == "0:2.87.3-1.el10"
    assert rows[0]["files"] == ["/usr/bin/gio"]
