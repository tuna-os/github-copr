"""The publish wave's safety rules, pinned against the incidents that taught them.

publish-rpm-wave.sh is shared by publish-tideforge-rpms.yml and
publish-build-chain-rpms.yml. Sharing it is the point: every rule here was
learned once, and a second hand-copied publisher would have to learn each of
them again. This repo has already paid for that twice -- the nightly cron
stagger that was documented but never applied, and the readiness stamp read
from two paths flatpak had stopped using.

The rules under test:

  empty wave    a build that produced nothing must not look published
  never shrink  #124: `rclone sync` deletes whatever the local tree lacks
  '+' renaming  run 32411090239: '+' in a filename 404s through the worker
  srpms         source RPMs are not installable content
"""
from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "publish-rpm-wave.sh"


@pytest.fixture
def stubbed(tmp_path):
    """rpmsign, createrepo_c and gpg stubbed; they need a keyring and a real repo.

    createrepo_c and gpg do a little more than log, because the script now
    depends on their side effects: it refuses to continue if repomd.xml is
    absent, and the signature it produces is what the tests check for.
    """
    binq = tmp_path / "bin"
    binq.mkdir()
    p = binq / "rpmsign"
    p.write_text('#!/bin/sh\necho "rpmsign $*" >> "$STUB_LOG"\nexit 0\n')
    p.chmod(0o755)

    # Real createrepo_c writes repodata/repomd.xml under the repo root, which
    # is the last argument in both invocations the script makes.
    p = binq / "createrepo_c"
    p.write_text(
        '#!/bin/sh\n'
        'echo "createrepo_c $*" >> "$STUB_LOG"\n'
        'for a in "$@"; do last="$a"; done\n'
        'mkdir -p "$last/repodata"\n'
        # Real createrepo_c REGENERATES a valid index. A stub that always
        # writes a placeholder would instead destroy the real one a test
        # pre-placed, so only stand in when there is nothing there.
        '[ -s "$last/repodata/repomd.xml" ] ||'
        ' printf "<repomd/>" > "$last/repodata/repomd.xml"\n'
        'exit 0\n'
    )
    p.chmod(0o755)

    # Honour --output so the detached signature actually appears on disk.
    p = binq / "gpg"
    p.write_text(
        '#!/bin/sh\n'
        'echo "gpg $*" >> "$STUB_LOG"\n'
        'out=""\n'
        'while [ $# -gt 0 ]; do\n'
        '  case "$1" in --output) out="$2"; shift ;; esac\n'
        '  shift\n'
        'done\n'
        '[ -n "$out" ] && printf "SIGNATURE" > "$out"\n'
        'exit 0\n'
    )
    p.chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = f"{binq}:{env['PATH']}"
    env["STUB_LOG"] = str(tmp_path / "stub.log")
    (tmp_path / "stub.log").write_text("")
    return env


def run(tmp_path, env, staged="staged", repo="repo", subdir="build-chain",
        repo_suffix=""):
    return subprocess.run(
        ["bash", str(SCRIPT), "--staged", str(tmp_path / staged),
         "--repo", str(tmp_path / repo) + repo_suffix, "--subdir", subdir],
        capture_output=True, text=True, env=env, cwd=tmp_path,
    )


def make(dirpath: Path, *names):
    dirpath.mkdir(parents=True, exist_ok=True)
    for n in names:
        (dirpath / n).write_text("rpm")


def rpms(root: Path):
    return sorted(p.name for p in root.rglob("*.rpm"))


# --- empty wave -------------------------------------------------------------


def test_an_empty_wave_is_refused(tmp_path, stubbed) -> None:
    """A build that produced nothing must not rewrite repodata and look green."""
    make(tmp_path / "staged")
    r = run(tmp_path, stubbed)
    assert r.returncode == 1
    assert "empty wave" in r.stderr


def test_a_wave_of_only_srpms_is_an_empty_wave(tmp_path, stubbed) -> None:
    make(tmp_path / "staged", "foo-1.0.src.rpm")
    r = run(tmp_path, stubbed)
    assert r.returncode == 1
    assert "empty wave" in r.stderr


# --- the happy path ---------------------------------------------------------


def test_binary_rpms_are_signed_and_placed(tmp_path, stubbed) -> None:
    make(tmp_path / "staged", "foo-1.0.el10.x86_64.rpm", "bar-2.0.el10.x86_64.rpm")
    r = run(tmp_path, stubbed)
    assert r.returncode == 0, r.stderr
    placed = tmp_path / "repo" / "build-chain"
    assert rpms(placed) == ["bar-2.0.el10.x86_64.rpm", "foo-1.0.el10.x86_64.rpm"]
    log = (tmp_path / "stub.log").read_text()
    assert log.count("rpmsign") == 2
    assert "createrepo_c" in log


def test_srpms_are_not_published(tmp_path, stubbed) -> None:
    make(tmp_path / "staged", "foo-1.0.el10.x86_64.rpm", "foo-1.0.src.rpm")
    r = run(tmp_path, stubbed)
    assert r.returncode == 0, r.stderr
    assert rpms(tmp_path / "repo") == ["foo-1.0.el10.x86_64.rpm"]


def test_existing_packages_are_preserved(tmp_path, stubbed) -> None:
    """The sync-down content must survive; publishing adds, never replaces."""
    make(tmp_path / "repo" / "tideforge", "already-1.0.el10.x86_64.rpm")
    make(tmp_path / "staged", "new-1.0.el10.x86_64.rpm")
    r = run(tmp_path, stubbed)
    assert r.returncode == 0, r.stderr
    assert rpms(tmp_path / "repo") == [
        "already-1.0.el10.x86_64.rpm", "new-1.0.el10.x86_64.rpm"
    ]


# --- the '+' rename ---------------------------------------------------------


def test_plus_is_renamed_in_staged_files(tmp_path, stubbed) -> None:
    """run 32411090239: the %2b URL 404s through the repo.tunaos.org worker."""
    make(tmp_path / "staged", "oversteer-udev-0.8.3+git74c7484.el10.noarch.rpm")
    r = run(tmp_path, stubbed)
    assert r.returncode == 0, r.stderr
    assert rpms(tmp_path / "repo") == [
        "oversteer-udev-0.8.3.git74c7484.el10.noarch.rpm"
    ]


def test_plus_is_renamed_in_files_synced_down_too(tmp_path, stubbed) -> None:
    """Otherwise the sync leaves the already-broken object in the bucket."""
    make(tmp_path / "repo" / "tideforge", "old-1.0+git.el10.x86_64.rpm")
    make(tmp_path / "staged", "new-1.0.el10.x86_64.rpm")
    r = run(tmp_path, stubbed)
    assert r.returncode == 0, r.stderr
    assert "old-1.0.git.el10.x86_64.rpm" in rpms(tmp_path / "repo")
    assert not any("+" in n for n in rpms(tmp_path / "repo"))


def test_caret_is_renamed_like_plus(tmp_path, stubbed) -> None:
    """'^' is Fedora's snapshot-version convention (quickshell-0.2.1^git…)
    and fails through the worker exactly as '+' does: librepo and dnf
    percent-encode it to %5E, the worker looks up raw R2 keys, 404. Found by
    the resolution simulator's fetchability pass: ~30 served files, each
    HEAD-verified 404 at the encoded URL. Worse than '+' operationally --
    these are runtime packages the desktop lanes install with
    --skip-unavailable, so the symptom is a silently thinner image."""
    make(tmp_path / "staged", "quickshell-0.2.1^git20260209.dacfa9d.fc43.x86_64.rpm")
    make(tmp_path / "repo" / "tideforge", "signon-8.60^20240205.c8ad982.fc43.x86_64.rpm")
    r = run(tmp_path, stubbed)
    assert r.returncode == 0, r.stderr
    served = rpms(tmp_path / "repo")
    assert "quickshell-0.2.1.git20260209.dacfa9d.fc43.x86_64.rpm" in served
    assert "signon-8.60.20240205.c8ad982.fc43.x86_64.rpm" in served
    assert not any("^" in n or "+" in n for n in served)


# --- never shrink -----------------------------------------------------------


def test_the_count_never_shrinks_on_the_happy_path(tmp_path, stubbed) -> None:
    make(tmp_path / "repo" / "tideforge", *[f"p{i}.el10.x86_64.rpm" for i in range(5)])
    make(tmp_path / "staged", "new.el10.x86_64.rpm")
    r = run(tmp_path, stubbed)
    assert r.returncode == 0, r.stderr
    assert len(rpms(tmp_path / "repo")) == 6
    assert "repo already holds 5" in r.stdout
    assert "repo now holds 6" in r.stdout


def test_a_shrinking_tree_is_refused(tmp_path, stubbed) -> None:
    """#124: syncing up from a smaller tree DELETES the difference.

    Simulated by making the copy step lose files -- a stubbed `cp` that
    drops them stands in for whatever real cause (disk, permissions, a bad
    find) would produce the same shape.
    """
    make(tmp_path / "repo" / "tideforge", *[f"p{i}.el10.x86_64.rpm" for i in range(5)])
    make(tmp_path / "staged", "new.el10.x86_64.rpm")

    # A `cp` that silently drops the file, and a `mv` that deletes instead of
    # renaming, together shrink the tree the way a real fault would.
    sabotage = Path(stubbed["PATH"].split(":")[0]) / "cp"
    sabotage.write_text(
        "#!/bin/sh\n"
        # consume `-t DEST FILES...`, then delete two pre-existing files
        f"rm -f {tmp_path}/repo/tideforge/p0.el10.x86_64.rpm "
        f"{tmp_path}/repo/tideforge/p1.el10.x86_64.rpm\n"
        "exit 0\n"
    )
    sabotage.chmod(0o755)

    r = run(tmp_path, stubbed)
    assert r.returncode == 1
    assert "shrank from 5 to 3" in r.stderr
    assert "DELETES" in r.stderr


# --- interface --------------------------------------------------------------


def test_missing_arguments_are_refused(tmp_path, stubbed) -> None:
    r = subprocess.run(
        ["bash", str(SCRIPT), "--staged", str(tmp_path)],
        capture_output=True, text=True, env=stubbed,
    )
    assert r.returncode == 2
    assert "usage:" in r.stderr


# --- supersede --------------------------------------------------------------


def test_an_older_copy_at_the_root_is_superseded(tmp_path, stubbed) -> None:
    """Measured on xfce/10-stream-x86_64: the first build-chain wave left 107
    same-NEVRA pairs, root copy vs build-chain/ copy, with 107 DIFFERING
    checksums. An rpm-md index with two entries for one NEVRA is ambiguous —
    dnf picks one, and they are not the same bytes. The staged copy is the
    freshly signed one, so the older file of that name goes."""
    make(tmp_path / "repo", "xfwl4-4.21.0-1.el10.x86_64.rpm")
    make(tmp_path / "staged", "xfwl4-4.21.0-1.el10.x86_64.rpm")
    r = run(tmp_path, stubbed)
    assert r.returncode == 0, r.stderr
    assert rpms(tmp_path / "repo") == ["xfwl4-4.21.0-1.el10.x86_64.rpm"]
    assert (tmp_path / "repo" / "build-chain"
            / "xfwl4-4.21.0-1.el10.x86_64.rpm").exists()
    assert "superseding older copy" in r.stdout


def test_supersession_does_not_trip_the_never_shrink_guard(tmp_path, stubbed) -> None:
    """The one intended shrink. Two of three staged names already exist at the
    root, so the tree ends one file LARGER than it started — but a naive
    baseline compare would see 3 -> 3 and only pass by luck. Make the margin
    real: four legacy files, three of which are superseded."""
    make(tmp_path / "repo", "a-1.el10.x86_64.rpm", "b-1.el10.x86_64.rpm",
         "c-1.el10.x86_64.rpm", "keep-1.el10.x86_64.rpm")
    make(tmp_path / "staged", "a-1.el10.x86_64.rpm", "b-1.el10.x86_64.rpm",
         "c-1.el10.x86_64.rpm")
    r = run(tmp_path, stubbed)
    assert r.returncode == 0, r.stderr + r.stdout
    assert rpms(tmp_path / "repo") == [
        "a-1.el10.x86_64.rpm", "b-1.el10.x86_64.rpm",
        "c-1.el10.x86_64.rpm", "keep-1.el10.x86_64.rpm",
    ]
    assert (tmp_path / "repo" / "keep-1.el10.x86_64.rpm").exists()


def test_a_different_publishers_subdir_is_superseded_too(tmp_path, stubbed) -> None:
    """Two publishers on one prefix is the #124 hazard in a different dress:
    if tideforge/ and build-chain/ both carry one NEVRA the index is still
    ambiguous. Supersession is by NAME across the whole tree, not by
    directory."""
    make(tmp_path / "repo" / "tideforge", "xfconf-4.21.2-6.el10.x86_64.rpm")
    make(tmp_path / "staged", "xfconf-4.21.2-6.el10.x86_64.rpm")
    r = run(tmp_path, stubbed)
    assert r.returncode == 0, r.stderr
    assert rpms(tmp_path / "repo") == ["xfconf-4.21.2-6.el10.x86_64.rpm"]
    assert (tmp_path / "repo" / "build-chain"
            / "xfconf-4.21.2-6.el10.x86_64.rpm").exists()


def test_a_trailing_slash_on_repo_does_not_delete_the_staged_file(
        tmp_path, stubbed) -> None:
    """`find repo/ ...` and `find repo//build-chain ...` print the same file
    under different path strings. Excluding the staged copy by comparing
    those strings would make the wave delete exactly what it just placed —
    and then the NEVER SHRINK guard is the only thing between that and an
    rclone sync erasing the package from the bucket."""
    make(tmp_path / "staged", "solo-1.el10.x86_64.rpm")
    r = run(tmp_path, stubbed, repo_suffix="/")
    assert r.returncode == 0, r.stderr + r.stdout
    assert rpms(tmp_path / "repo") == ["solo-1.el10.x86_64.rpm"]


def test_supersession_survives_the_plus_rename(tmp_path, stubbed) -> None:
    """Both copies are renamed '+' -> '.', so they must be compared AFTER the
    rename or the legacy copy survives under a name that now collides."""
    make(tmp_path / "repo", "oversteer-udev-0.8.3+git74c7484.el10.noarch.rpm")
    make(tmp_path / "staged", "oversteer-udev-0.8.3+git74c7484.el10.noarch.rpm")
    r = run(tmp_path, stubbed)
    assert r.returncode == 0, r.stderr + r.stdout
    assert rpms(tmp_path / "repo") == [
        "oversteer-udev-0.8.3.git74c7484.el10.noarch.rpm"
    ]


def test_an_unrelated_older_package_is_never_removed(tmp_path, stubbed) -> None:
    """Supersession is same-NAME only. A different version of the same
    package is a different file name and stays — cleaning old versions is a
    separate decision from resolving a duplicate."""
    make(tmp_path / "repo", "xfwl4-4.20.0-1.el10.x86_64.rpm")
    make(tmp_path / "staged", "xfwl4-4.21.0-1.el10.x86_64.rpm")
    r = run(tmp_path, stubbed)
    assert r.returncode == 0, r.stderr
    assert rpms(tmp_path / "repo") == [
        "xfwl4-4.20.0-1.el10.x86_64.rpm", "xfwl4-4.21.0-1.el10.x86_64.rpm"
    ]


# --- signed repository metadata ---------------------------------------------


def test_repomd_is_detach_signed(tmp_path, stubbed) -> None:
    """rpmsign signs the packages; this signs the index that points at them.

    Without repodata/repomd.xml.asc, clients cannot set repo_gpgcheck=1, and
    gpgcheck=1 alone does not stop an attacker replaying an older, still-signed
    index to reinstate a withdrawn package (downgrade) or serving
    current-looking metadata forever (freeze).
    """
    make(tmp_path / "staged", "foo-1.0.el10.x86_64.rpm")
    r = run(tmp_path, stubbed)
    assert r.returncode == 0, r.stderr

    sig = tmp_path / "repo" / "repodata" / "repomd.xml.asc"
    assert sig.is_file(), "repomd.xml.asc was not produced"
    assert sig.read_text() == "SIGNATURE"


def test_repomd_signature_is_armored_and_detached(tmp_path, stubbed) -> None:
    """A clearsigned or inline signature is not what repo_gpgcheck reads."""
    make(tmp_path / "staged", "foo-1.0.el10.x86_64.rpm")
    r = run(tmp_path, stubbed)
    assert r.returncode == 0, r.stderr

    gpg_calls = [ln for ln in (tmp_path / "stub.log").read_text().splitlines()
                 if ln.startswith("gpg ")]
    assert len(gpg_calls) == 1, gpg_calls
    assert "--detach-sign" in gpg_calls[0]
    assert "--armor" in gpg_calls[0]
    assert "repodata/repomd.xml.asc" in gpg_calls[0]


def test_repomd_is_signed_after_it_is_generated(tmp_path, stubbed) -> None:
    """Signing a stale index would be worse than not signing at all."""
    make(tmp_path / "staged", "foo-1.0.el10.x86_64.rpm")
    r = run(tmp_path, stubbed)
    assert r.returncode == 0, r.stderr

    log = (tmp_path / "stub.log").read_text().splitlines()
    createrepo = max(i for i, ln in enumerate(log) if ln.startswith("createrepo_c "))
    signed = next(i for i, ln in enumerate(log) if ln.startswith("gpg "))
    assert signed > createrepo, log


def test_the_signing_key_follows_rpmmacros(tmp_path, stubbed) -> None:
    """The same key rpmsign uses, so no second secret has to be provisioned."""
    home = tmp_path / "home"
    home.mkdir()
    (home / ".rpmmacros").write_text(
        "%_signature gpg\n%_gpg_name DEADBEEFCAFE1234\n"
    )
    env = dict(stubbed)
    env["HOME"] = str(home)

    make(tmp_path / "staged", "foo-1.0.el10.x86_64.rpm")
    r = run(tmp_path, env)
    assert r.returncode == 0, r.stderr

    gpg_call = next(ln for ln in (tmp_path / "stub.log").read_text().splitlines()
                    if ln.startswith("gpg "))
    assert "--local-user DEADBEEFCAFE1234" in gpg_call


def test_a_missing_repomd_is_fatal(tmp_path, stubbed) -> None:
    """createrepo_c reporting success without producing an index must not
    publish silently unsigned metadata."""
    binq = tmp_path / "bin"
    (binq / "createrepo_c").write_text(
        '#!/bin/sh\necho "createrepo_c $*" >> "$STUB_LOG"\nexit 0\n'
    )
    (binq / "createrepo_c").chmod(0o755)

    make(tmp_path / "staged", "foo-1.0.el10.x86_64.rpm")
    r = run(tmp_path, stubbed)
    assert r.returncode != 0
    assert "refusing to publish" in r.stderr


# --- never break rdeps ------------------------------------------------------


def _repodata(root: Path, packages: str) -> None:
    """A minimal real rpm-md index, since createrepo_c is stubbed here."""
    import gzip
    repodata = root / "repodata"
    repodata.mkdir(parents=True, exist_ok=True)
    primary = f"""<?xml version="1.0"?>
<metadata xmlns="http://linux.duke.edu/metadata/common"
          xmlns:rpm="http://linux.duke.edu/metadata/rpm">{packages}</metadata>"""
    (repodata / "primary.xml.gz").write_bytes(gzip.compress(primary.encode()))
    (repodata / "repomd.xml").write_text("""<?xml version="1.0"?>
<repomd xmlns="http://linux.duke.edu/metadata/repo">
  <revision>1</revision>
  <data type="primary">
    <location href="repodata/primary.xml.gz"/>
    <checksum type="sha256">x</checksum>
  </data>
</repomd>""")


def _pkg_xml(name: str, provides: list[str] = (), requires: list[str] = ()) -> str:
    pro = "".join(f'<rpm:entry name="{p}"/>' for p in provides)
    req = "".join(f'<rpm:entry name="{r}"/>' for r in requires)
    return f"""<package type="rpm"><name>{name}</name><arch>x86_64</arch>
      <version epoch="0" ver="1.0" rel="1.el10"/>
      <format><rpm:provides>{pro}</rpm:provides>
      <rpm:requires>{req}</rpm:requires></format></package>"""


def test_a_wave_that_breaks_a_served_reverse_dep_is_refused(tmp_path, stubbed):
    """NEVER BREAK RDEPS, in the shared implementation both publishers use.

    The served tree holds gtkgreet, which needs libgreetd.so.1 from the
    served greetd. The wave replaces greetd with a build that dropped
    the provide. Signing, copying, and indexing must all be refused —
    the gate runs before any of them.
    """
    make(tmp_path / "staged", "greetd-1.0-2.el10.x86_64.rpm")
    make(tmp_path / "repo", "greetd-1.0-1.el10.x86_64.rpm",
         "gtkgreet-1.0-1.el10.x86_64.rpm")
    _repodata(tmp_path / "repo",
              _pkg_xml("greetd", provides=["greetd", "libgreetd.so.1"])
              + _pkg_xml("gtkgreet", requires=["libgreetd.so.1"]))
    # createrepo_c is a stub, so the staged index is pre-placed; the
    # real tool would regenerate it in place.
    _repodata(tmp_path / "staged",
              _pkg_xml("greetd", provides=["greetd", "libgreetd.so.2"]))
    r = run(tmp_path, stubbed)
    assert r.returncode != 0
    assert "does not keep the served index installable" in r.stdout
    assert "rpmsign" not in (tmp_path / "stub.log").read_text(), (
        "the gate must refuse the wave before anything is signed")


def test_a_wave_that_keeps_reverse_deps_resolvable_publishes(tmp_path, stubbed):
    make(tmp_path / "staged", "greetd-1.0-2.el10.x86_64.rpm")
    make(tmp_path / "repo", "greetd-1.0-1.el10.x86_64.rpm",
         "gtkgreet-1.0-1.el10.x86_64.rpm")
    _repodata(tmp_path / "repo",
              _pkg_xml("greetd", provides=["greetd", "libgreetd.so.1"])
              + _pkg_xml("gtkgreet", requires=["libgreetd.so.1"]))
    _repodata(tmp_path / "staged",
              _pkg_xml("greetd", provides=["greetd", "libgreetd.so.1"]))
    r = run(tmp_path, stubbed)
    assert r.returncode == 0, r.stderr
    assert "every served package still resolves" in r.stdout


def test_a_first_publish_with_no_served_repodata_skips_the_gate(tmp_path, stubbed):
    """Nothing served means nothing to break — not a reason to fail."""
    make(tmp_path / "staged", "greetd-1.0-1.el10.x86_64.rpm")
    r = run(tmp_path, stubbed)
    assert r.returncode == 0, r.stderr
    assert "reverse-dep gate skipped" in r.stdout
