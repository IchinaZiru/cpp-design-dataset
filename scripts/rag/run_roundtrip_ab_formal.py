from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.rag.roundtrip_ab import RoundtripABError, load_json, resolve_project_path
from scripts.rag.roundtrip_ab_formal import (
    build_plan_v2,
    execute_condition_v2_once,
    load_common_v2,
    load_formal_manifest,
    verify_formal_authorization,
)


DEFAULT_COMMON = Path("configs/rag/roundtrip_ab_v1/common.json")
DEFAULT_MANIFEST = Path("configs/rag/roundtrip_ab_v1/formal/evaluation_manifest.json")
DEFAULT_AUTHORIZATION = Path("configs/rag/roundtrip_ab_v1/formal/execution_authorization.json")


def _path(root: Path, value: Path) -> Path:
    return value if value.is_absolute() else root / value


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guarded formal design-only A/B runner")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--target-id")
    parser.add_argument("--condition", choices=("A", "B"))
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--common", type=Path, default=DEFAULT_COMMON)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--authorization", type=Path, default=DEFAULT_AUTHORIZATION)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.project_root.resolve()
    common_path = _path(root, args.common)
    manifest_path = _path(root, args.manifest)
    authorization_path = _path(root, args.authorization)
    common = load_common_v2(common_path, root)
    manifest = load_formal_manifest(manifest_path, root)
    if args.preflight:
        result = {
            "artifact_schema_version": "roundtrip-ab-formal-runner-preflight-v1",
            "authorized": load_json(authorization_path).get("authorized") is True,
            "formal_execution_started": False,
            "generation_server_contacted": False,
            "llm_call_count": 0,
            "target_count": len(manifest["targets"]),
        }
    else:
        if not args.target_id or not args.condition:
            raise RoundtripABError("--execute requires --target-id and --condition")
        verify_formal_authorization(authorization_path, manifest_path, common_path, root)
        matches = [x for x in manifest["targets"] if x["target_id"] == args.target_id]
        if len(matches) != 1:
            raise RoundtripABError("target is not in the frozen 17-target allowlist")
        target_path = resolve_project_path(root, str(matches[0]["target_config_path"]), field="target config")
        config = load_json(target_path)
        # The output-root existence check inside execute_condition_v2_once is the
        # durable attempt/result one-shot guard.  No retry or overwrite path exists.
        build_plan_v2(config, common, root)
        result = execute_condition_v2_once(config, common, root, args.condition, formal=True)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
