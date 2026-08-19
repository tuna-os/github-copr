import hashlib
import importlib.util
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts import tideforge_cache


def load_script(name):
    path = Path(__file__).parent.parent / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace("-", "_").removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fetch_sources = load_script("fetch-tideforge-sources.py")
verify_source = load_script("verify-tideforge-source.py")

PAYLOAD = b"tideforge test archive bytes"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


def make_recipe(tmp_path, sources=None):
    recipe = {
        "name": "demo",
        "version": "1.0",
        "source": {"url": "https://example.invalid/demo-1.0.tar.gz", "sha256": DIGEST},
    }
    if sources is not None:
        recipe["sources"] = sources
    path = tmp_path / "package.yaml"
    path.write_text(yaml.safe_dump(recipe))
    return path, recipe


def test_cache_key_ignores_source_order():
    one = {"source": {"sha256": "a" * 64}, "sources": [{"sha256": "b" * 64}]}
    two = {"source": {"sha256": "b" * 64}, "sources": [{"sha256": "a" * 64}]}
    assert tideforge_cache.cache_key(one) == tideforge_cache.cache_key(two)


def test_cache_key_changes_when_a_pin_changes():
    base = {"source": {"sha256": "a" * 64}}
    bumped = {"source": {"sha256": "c" * 64}}
    assert tideforge_cache.cache_key(base) != tideforge_cache.cache_key(bumped)


def test_lookup_misses_on_empty_store(tmp_path):
    assert tideforge_cache.lookup(tmp_path, DIGEST) is None


def test_store_then_lookup_round_trips(tmp_path):
    tideforge_cache.store(tmp_path, PAYLOAD)
    assert tideforge_cache.lookup(tmp_path, DIGEST) == PAYLOAD


def test_corrupted_blob_reads_as_miss_and_is_deleted(tmp_path):
    (tmp_path / DIGEST).write_bytes(b"not the pinned bytes")
    assert tideforge_cache.lookup(tmp_path, DIGEST) is None
    assert not (tmp_path / DIGEST).exists()


def test_fetch_hit_serves_from_cache_without_network(tmp_path, monkeypatch):
    recipe_path, _ = make_recipe(tmp_path)
    cache = tmp_path / "cache"
    tideforge_cache.store(cache, PAYLOAD)

    def refuse(*args, **kwargs):
        raise AssertionError("network touched on a cache hit")

    monkeypatch.setattr(fetch_sources, "urlopen", refuse)
    destination = tmp_path / "SOURCES"
    monkeypatch.setattr(
        "sys.argv",
        ["fetch", str(recipe_path), str(destination), "--cache-dir", str(cache)],
    )
    fetch_sources.main()
    assert (destination / "demo-1.0.tar.gz").read_bytes() == PAYLOAD


def test_fetch_miss_downloads_and_populates_cache(tmp_path, monkeypatch):
    recipe_path, _ = make_recipe(tmp_path)
    cache = tmp_path / "cache"

    class Response:
        def read(self):
            return PAYLOAD

    monkeypatch.setattr(fetch_sources, "urlopen", lambda request: Response())
    destination = tmp_path / "SOURCES"
    monkeypatch.setattr(
        "sys.argv",
        ["fetch", str(recipe_path), str(destination), "--cache-dir", str(cache)],
    )
    fetch_sources.main()
    assert (destination / "demo-1.0.tar.gz").read_bytes() == PAYLOAD
    assert tideforge_cache.lookup(cache, DIGEST) == PAYLOAD


def test_fetch_checksum_mismatch_still_fails_and_stores_nothing(tmp_path, monkeypatch):
    recipe_path, _ = make_recipe(tmp_path)
    cache = tmp_path / "cache"

    class Response:
        def read(self):
            return b"tampered bytes"

    monkeypatch.setattr(fetch_sources, "urlopen", lambda request: Response())
    monkeypatch.setattr(
        "sys.argv",
        ["fetch", str(recipe_path), str(tmp_path / "SOURCES"), "--cache-dir", str(cache)],
    )
    with pytest.raises(SystemExit, match="checksum mismatch"):
        fetch_sources.main()
    assert tideforge_cache.lookup(cache, hashlib.sha256(b"tampered bytes").hexdigest()) is None


def test_verify_hit_passes_without_network(tmp_path, monkeypatch):
    recipe_path, _ = make_recipe(tmp_path)
    cache = tmp_path / "cache"
    tideforge_cache.store(cache, PAYLOAD)

    def refuse(*args, **kwargs):
        raise AssertionError("network touched on a cache hit")

    monkeypatch.setattr(verify_source, "urlopen", refuse)
    monkeypatch.setattr("sys.argv", ["verify", str(recipe_path), "--cache-dir", str(cache)])
    verify_source.main()


def test_verify_miss_downloads_and_populates_cache(tmp_path, monkeypatch):
    recipe_path, _ = make_recipe(tmp_path)
    cache = tmp_path / "cache"

    class Response:
        def read(self):
            return PAYLOAD

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(verify_source, "urlopen", lambda request, **_kwargs: Response())
    monkeypatch.setattr("sys.argv", ["verify", str(recipe_path), "--cache-dir", str(cache)])
    verify_source.main()
    assert tideforge_cache.lookup(cache, DIGEST) == PAYLOAD


def test_oras_push_noop_when_disabled(tmp_path, monkeypatch):
    tideforge_cache.store(tmp_path, PAYLOAD)
    monkeypatch.setattr(tideforge_cache, "ORAS_PUSH_ENABLED", False)
    assert tideforge_cache.oras_push(tmp_path, DIGEST) is False


def test_oras_push_skips_missing_blob(tmp_path):
    assert tideforge_cache.oras_push(tmp_path, DIGEST) is False


def test_oras_pull_calls_subprocess(tmp_path, monkeypatch):
    """oras_pull calls the ORAS CLI and validates the pulled blob."""
    cache = tmp_path / "cache"
    cache.mkdir()

    def fake_run(cmd, **kwargs):
        # Simulate oras pull writing the blob into cache_dir
        (cache / DIGEST).write_bytes(PAYLOAD)
        return subprocess.CompletedProcess(cmd, 0)

    import subprocess as sp
    monkeypatch.setattr(tideforge_cache, "ORAS_REPO", "ghcr.io/test/repo")
    monkeypatch.setattr(sp, "run", fake_run)
    assert tideforge_cache.oras_pull(cache, DIGEST) is True
    assert tideforge_cache.lookup(cache, DIGEST) == PAYLOAD


def test_oras_pull_bad_blob_reads_as_miss(tmp_path, monkeypatch):
    """When ORAS pull writes a corrupted blob, oras_pull returns False."""
    cache = tmp_path / "cache"
    cache.mkdir()

    def fake_run(cmd, **kwargs):
        (cache / DIGEST).write_bytes(b"tampered")
        return subprocess.CompletedProcess(cmd, 0)

    import subprocess as sp
    monkeypatch.setattr(tideforge_cache, "ORAS_REPO", "ghcr.io/test/repo")
    monkeypatch.setattr(sp, "run", fake_run)
    assert tideforge_cache.oras_pull(cache, DIGEST) is False
    assert not (cache / DIGEST).exists()


def test_oras_lookup_falls_back_to_oras_on_local_miss(tmp_path, monkeypatch):
    """When the local cache misses, oras_lookup tries the ORAS registry."""
    cache = tmp_path / "cache"
    cache.mkdir()

    def fake_run(cmd, **kwargs):
        (cache / DIGEST).write_bytes(PAYLOAD)
        return subprocess.CompletedProcess(cmd, 0)

    import subprocess as sp
    monkeypatch.setattr(tideforge_cache, "ORAS_REPO", "ghcr.io/test/repo")
    monkeypatch.setattr(sp, "run", fake_run)
    assert tideforge_cache.oras_lookup(cache, DIGEST) == PAYLOAD


def test_oras_lookup_returns_none_when_both_miss(tmp_path, monkeypatch):
    """When both local and ORAS miss, oras_lookup returns None."""
    cache = tmp_path / "cache"
    cache.mkdir()

    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("no oras binary")

    import subprocess as sp
    monkeypatch.setattr(sp, "run", fake_run)
    assert tideforge_cache.oras_lookup(cache, DIGEST) is None
