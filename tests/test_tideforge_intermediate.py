import json
from pathlib import Path
import subprocess
import sys
import tarfile


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "tideforge-intermediate.py"


def write_recipe(path: Path) -> None:
    path.write_text(
        """schema: 1
name: payload-canary
version: '1.0'
release: 1
summary: canary
description: canary
license: MIT
source:
  url: https://example.invalid/payload-canary.tar.gz
  sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
build_system: data
files: {common: [usr/share/payload-canary/message]}
dependencies:
  runtime:
    targets:
      ubuntu: [ubuntu-runtime]
      debian: [debian-runtime]
targets: [ubuntu, debian]
"""
    )


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE)


def test_one_payload_digest_is_reused_by_two_target_plans(tmp_path: Path):
    recipe = tmp_path / "package.yaml"
    write_recipe(recipe)
    root = tmp_path / "root"
    message = root / "usr/share/payload-canary/message"
    message.parent.mkdir(parents=True)
    message.write_text("built once\n")
    intermediate = tmp_path / "payload.tfi.tar"

    run("create", "--recipe", str(recipe), "--root", str(root), "--architecture", "x86_64", "--build-contract", "theory-sdk-v0", "--output", str(intermediate))
    run("verify", str(intermediate))
    ubuntu = json.loads(run("plan", str(intermediate), "--recipe", str(recipe), "--target", "ubuntu").stdout)
    debian = json.loads(run("plan", str(intermediate), "--recipe", str(recipe), "--target", "debian").stdout)

    assert ubuntu["compile"] is debian["compile"] is False
    assert ubuntu["payload_tree_sha256"] == debian["payload_tree_sha256"]
    assert ubuntu["declared_target_runtime_dependencies"] == ["ubuntu-runtime"]
    assert debian["declared_target_runtime_dependencies"] == ["debian-runtime"]


def test_intermediate_is_reproducible(tmp_path: Path, monkeypatch):
    recipe = tmp_path / "package.yaml"
    write_recipe(recipe)
    root = tmp_path / "root"
    payload = root / "usr/bin/canary"
    payload.parent.mkdir(parents=True)
    payload.write_text("hello\n")
    payload.chmod(0o755)
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1234")
    outputs = [tmp_path / "one.tar", tmp_path / "two.tar"]
    for output in outputs:
        run("create", "--recipe", str(recipe), "--root", str(root), "--architecture", "x86_64", "--build-contract", "theory-sdk-v0", "--output", str(output))
    assert outputs[0].read_bytes() == outputs[1].read_bytes()
    with tarfile.open(outputs[0]) as archive:
        assert {member.uid for member in archive.getmembers()} == {0}


def test_intermediate_records_dynamic_elf_contract(tmp_path: Path):
    recipe = tmp_path / "package.yaml"
    write_recipe(recipe)
    root = tmp_path / "root"
    binary = root / "usr/bin/payload-canary"
    binary.parent.mkdir(parents=True)
    subprocess.run(
        ["gcc", "-x", "c", "-", "-o", str(binary)],
        input="#include <stdio.h>\nint main(void) { return puts(\"hello\") < 0; }\n",
        text=True,
        check=True,
    )
    intermediate = tmp_path / "payload.tfi.tar"
    run("create", "--recipe", str(recipe), "--root", str(root), "--architecture", "x86_64", "--build-contract", "host-glibc-theory", "--output", str(intermediate))
    plan = json.loads(run("plan", str(intermediate), "--recipe", str(recipe), "--target", "ubuntu").stdout)

    assert plan["elf_contracts"][0]["path"] == "usr/bin/payload-canary"
    assert "libc.so.6" in plan["elf_contracts"][0]["needed"]
    assert any(version.startswith("GLIBC_") for version in plan["elf_contracts"][0]["symbol_versions"])
