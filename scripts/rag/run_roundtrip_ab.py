from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.rag.roundtrip_ab import (
    RoundtripABError,
    execute_condition_once,
    load_common_config,
    load_json,
    run_retrieval_only,
    validate_target_config,
    write_plan_artifacts,
)


DEFAULT_COMMON = "configs/rag/roundtrip_ab_v1/common.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the isolated design-only C++ round-trip A/B protocol."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--retrieval-only", action="store_true")
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--condition", choices=("A", "B"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--common", type=Path, default=Path(DEFAULT_COMMON))
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.project_root.resolve()
    config_path = args.config if args.config.is_absolute() else root / args.config
    common_path = args.common if args.common.is_absolute() else root / args.common
    config = load_json(config_path)
    validate_target_config(config)
    if args.retrieval_only:
        result = run_retrieval_only(config, root)
    else:
        common = load_common_config(common_path, root)
        if args.plan_only:
            result = write_plan_artifacts(config, common, root)
        else:
            if args.condition is None:
                raise RoundtripABError("--execute requires --condition A or B")
            result = execute_condition_once(config, common, root, args.condition)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
