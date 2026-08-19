from __future__ import annotations
import importlib.util, json, pathlib, subprocess
import pytest
ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cache", ROOT / "scripts/tideforge-action-cache.py")
cache = importlib.util.module_from_spec(spec); spec.loader.exec_module(cache)
def args(tmp_path, **overrides):
    recipe = tmp_path / "pkg" / "package.yaml"; recipe.parent.mkdir(); recipe.write_text("name: demo\n")
    factory = tmp_path / "factory.yaml"; factory.write_text("targets: {fedora: {architectures: [x86_64, aarch64]}}\n")
    values = dict(recipe=str(recipe), factory=str(factory), target="fedora", arch="x86_64", image="registry.example/build@sha256:" + "a"*64, dependency_key=[]); values.update(overrides); return type("Args", (), values)()
def test_key_changes_for_target_arch_and_dependencies(tmp_path):
    base = cache.digest_json(cache.action_inputs(args(tmp_path)))
    assert base != cache.digest_json(cache.action_inputs(args(tmp_path, arch="aarch64")))
    assert base != cache.digest_json(cache.action_inputs(args(tmp_path, dependency_key=["sha256:" + "b"*64])))
def test_mutable_build_image_is_refused(tmp_path):
    with pytest.raises(SystemExit, match="digest-pinned"): cache.action_inputs(args(tmp_path, image="registry.example/build:latest"))
def test_result_verification_detects_tampering(tmp_path):
    artifact = tmp_path / "demo.rpm"; artifact.write_bytes(b"first")
    result = json.loads(subprocess.check_output(["python3", str(ROOT / "scripts/tideforge-action-cache.py"), "result", "--action-key", "sha256:" + "c"*64, "--artifact", str(artifact)], text=True))
    manifest = tmp_path / "result.json"; manifest.write_text(json.dumps(result))
    cache.cmd_verify(type("Args", (), {"result": str(manifest), "artifact_dir": str(tmp_path)})())
    artifact.write_bytes(b"second")
    with pytest.raises(SystemExit, match="verification failed"): cache.cmd_verify(type("Args", (), {"result": str(manifest), "artifact_dir": str(tmp_path)})())
