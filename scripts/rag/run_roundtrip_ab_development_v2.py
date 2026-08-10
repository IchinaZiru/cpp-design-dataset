from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.rag.roundtrip_ab import RoundtripABError, load_json
from scripts.rag.roundtrip_ab_formal import execute_condition_v2_once, load_common_v2, validate_target_v2, write_plan_v2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Formal-excluded v2 development runner")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--condition", choices=("A", "B"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--common", type=Path, default=Path("configs/rag/roundtrip_ab_v1/common.json"))
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    resolve = lambda value: value if value.is_absolute() else root / value
    config = load_json(resolve(args.config))
    validate_target_v2(config, formal=False)
    common = load_common_v2(resolve(args.common), root)
    if args.plan_only:
        result = write_plan_v2(config, common, root)
    else:
        if args.condition is None:
            raise RoundtripABError("--execute requires --condition")
        result = execute_condition_v2_once(config, common, root, args.condition, formal=False)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
