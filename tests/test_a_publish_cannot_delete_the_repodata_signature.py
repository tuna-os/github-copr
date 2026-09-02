"""A publisher that re-indexes a served prefix must sign it, or it erases #509.

Package signatures (`gpgcheck=1`) stop an attacker serving repo.tunaos.org from
getting an unsigned RPM installed. They do nothing about the attacks that need
no forged package signature: replaying an older repomd.xml to reinstate a
withdrawn version, or serving current-looking metadata forever. Signed metadata
is the control for those, and #510 added it to publish-rpm-wave.sh.

The part that is easy to miss is that it is not enough for ONE publisher to
sign. `rclone sync` makes the destination MATCH the source, and every publisher
that syncs a locally-indexed tree into a prefix seeds that tree with
`--exclude "repodata/**"`. So a publisher that runs createrepo_c and syncs up
without signing does not merely skip a step -- the repomd.xml.asc a previous
publisher wrote is absent from its local tree and is therefore DELETED from the
bucket. `repo/10-stream-x86_64` and `repo/10-x86_64` are written by more than
one publisher, so this is not hypothetical, and while it holds repo_gpgcheck=1
can never be turned on for those prefixes.

Hence one signer -- scripts/sign-repomd.sh -- called from every path that
indexes before a sync-up.
"""

import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
SIGNER = REPO / "scripts" / "sign-repomd.sh"
WAVE = REPO / "scripts" / "publish-rpm-wave.sh"
GENERATOR = REPO / "scripts" / "generate-distributed-workflow.py"
MANIFEST = REPO / "build-order-hummingbird-desktops.yml"


def test_the_signer_exists_and_is_executable():
    assert SIGNER.is_file()
    assert SIGNER.stat().st_mode & 0o111, "publishers invoke it as a script"


def test_the_signer_refuses_a_tree_with_no_repomd(tmp_path):
    """Signing nothing and reporting success would publish unsigned metadata."""
    result = subprocess.run(
        ["bash", str(SIGNER), str(tmp_path)], capture_output=True, text=True)
    assert result.returncode != 0
    assert "repomd.xml" in result.stderr


def test_the_signer_writes_a_detached_signature(tmp_path):
    """gpg is stubbed: the contract under test is which file gets produced."""
    repodata = tmp_path / "repo" / "repodata"
    repodata.mkdir(parents=True)
    (repodata / "repomd.xml").write_text("<repomd/>")

    binq = tmp_path / "bin"
    binq.mkdir()
    stub = binq / "gpg"
    stub.write_text(
        '#!/bin/sh\n'
        'out=""\n'
        'while [ $# -gt 0 ]; do\n'
        '  case "$1" in --output) out="$2"; shift 2 ;; *) shift ;; esac\n'
        'done\n'
        'echo "SIGNATURE" > "$out"\n')
    stub.chmod(0o755)

    env = {"PATH": f"{binq}:/usr/bin:/bin", "HOME": str(tmp_path)}
    subprocess.run(["bash", str(SIGNER), str(tmp_path / "repo")],
                   check=True, capture_output=True, env=env)
    assert (repodata / "repomd.xml.asc").read_text().strip() == "SIGNATURE"


def test_the_wave_publisher_signs_through_the_shared_signer():
    """Not a hand-copied second implementation -- that is how the rules drift."""
    assert "sign-repomd.sh" in WAVE.read_text()


def test_the_generated_publisher_signs_before_it_syncs_up(tmp_path):
    """The generated workflow's upload is `rclone sync`, so it must sign first."""
    order = yaml.safe_load(MANIFEST.read_text())
    tiers = [t for t in order["tiers"] if t["name"].startswith(("bootstrap", "layer-0"))]
    src = tmp_path / "order.yml"
    src.write_text(yaml.safe_dump({"r2_path": order["r2_path"], "tiers": tiers},
                                  sort_keys=False))
    out = tmp_path / "wf.yml"
    subprocess.run(
        [sys.executable, str(GENERATOR), str(src), str(out),
         "--mock-config", "hummingbird-ci",
         "--r2-path", order["r2_path"], "--secondary-r2-path", "",
         "--no-submodules"],
        check=True, capture_output=True, cwd=REPO)

    steps = yaml.safe_load(out.read_text())["jobs"]["publish"]["steps"]
    runs = [s.get("run", "") for s in steps]

    signing = [i for i, r in enumerate(runs) if "sign-repomd.sh" in r]
    uploading = [i for i, r in enumerate(runs) if "rclone sync local-repo/" in r]
    assert signing, "the publish job never signs repodata/repomd.xml"
    assert uploading, "the publish job never syncs local-repo up"
    assert min(signing) < min(uploading), (
        "the signature must exist before the sync that makes the bucket "
        "match the local tree")
