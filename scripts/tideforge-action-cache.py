#!/usr/bin/env python3
"""Content-addressed Tideforge build action keys and verified result manifests."""
from __future__ import annotations
import argparse, hashlib, json, pathlib
from typing import Any
import yaml
SCHEMA = 1
ROOT = pathlib.Path(__file__).resolve().parents[1]
RENDERERS = ("scripts/tideforge.py", "scripts/assemble-deb-source-tree.py", "scripts/build-chain.sh")
def digest_file(path: pathlib.Path) -> str: return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
def digest_json(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
def digest_tree(root: pathlib.Path) -> str:
    return digest_json([{"path": p.relative_to(root).as_posix(), "digest": digest_file(p)} for p in sorted(x for x in root.rglob("*") if x.is_file() and ".git" not in x.parts)])
def load_target(factory: pathlib.Path, target: str) -> dict[str, Any]:
    data = yaml.safe_load(factory.read_text(encoding="utf-8"))
    try: return data["targets"][target]
    except KeyError as exc: raise SystemExit(f"unknown factory target: {target}") from exc
def require_digest(image: str) -> str:
    if "@sha256:" not in image: raise SystemExit("build image must be immutable and digest-pinned (image@sha256:...)")
    return image
def action_inputs(args: argparse.Namespace) -> dict[str, Any]:
    recipe, factory = pathlib.Path(args.recipe), pathlib.Path(args.factory)
    target = load_target(factory, args.target)
    if args.arch not in target.get("architectures", []): raise SystemExit(f"{args.arch} is not declared for target {args.target}")
    return {"schema": SCHEMA, "recipe": {"path": recipe.as_posix(), "tree": digest_tree(recipe.parent)}, "target": {"id": args.target, "architecture": args.arch, "contract": digest_json(target)}, "build_image": require_digest(args.image), "renderer_inputs": {p: digest_file(ROOT / p) for p in RENDERERS}, "dependency_action_keys": sorted(set(args.dependency_key))}
def artifact(path: pathlib.Path) -> dict[str, Any]:
    if not path.is_file(): raise SystemExit(f"artifact is not a regular file: {path}")
    return {"name": path.name, "size": path.stat().st_size, "digest": digest_file(path)}
def result_path(key: str) -> str: return "actions/sha256/" + key.removeprefix("sha256:") + ".json"
def cmd_key(args: argparse.Namespace) -> None:
    inputs = action_inputs(args); print(json.dumps({"action_key": digest_json(inputs), "inputs": inputs}, sort_keys=True))
def cmd_result(args: argparse.Namespace) -> None:
    if not args.action_key.startswith("sha256:"): raise SystemExit("action key must be sha256:<hex>")
    print(json.dumps({"schema": SCHEMA, "action_key": args.action_key, "artifacts": [artifact(pathlib.Path(p)) for p in args.artifact]}, sort_keys=True))
def cmd_verify(args: argparse.Namespace) -> None:
    result = json.loads(pathlib.Path(args.result).read_text(encoding="utf-8"))
    if result.get("schema") != SCHEMA or not str(result.get("action_key", "")).startswith("sha256:"): raise SystemExit("unsupported or malformed action result")
    for expected in result.get("artifacts", []):
        actual = artifact(pathlib.Path(args.artifact_dir) / expected["name"])
        if actual != expected: raise SystemExit(f"artifact verification failed: {expected['name']}")
    print("verified " + result["action_key"])
def main() -> None:
    p = argparse.ArgumentParser(); sub = p.add_subparsers(required=True)
    common = argparse.ArgumentParser(add_help=False)
    for name, kw in (("--recipe", {"required": True}), ("--factory", {"default": "manifests/package-factory.yaml"}), ("--target", {"required": True}), ("--arch", {"required": True}), ("--image", {"required": True}), ("--dependency-key", {"action": "append", "default": []})): common.add_argument(name, **kw)
    key = sub.add_parser("key", parents=[common]); key.set_defaults(func=cmd_key)
    result = sub.add_parser("result"); result.add_argument("--action-key", required=True); result.add_argument("--artifact", action="append", required=True); result.set_defaults(func=cmd_result)
    verify = sub.add_parser("verify"); verify.add_argument("--result", required=True); verify.add_argument("--artifact-dir", required=True); verify.set_defaults(func=cmd_verify)
    loc = sub.add_parser("r2-path"); loc.add_argument("--action-key", required=True); loc.set_defaults(func=lambda a: print(result_path(a.action_key)))
    args = p.parse_args(); args.func(args)
if __name__ == "__main__": main()
