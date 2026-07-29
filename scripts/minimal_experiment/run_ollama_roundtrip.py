from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_config(project_root: Path) -> dict[str, Any]:
    path = project_root / "experiments/ini-writer-minimal/configs/run_config.json"
    return json.loads(read_text(path))


def resolve(project_root: Path, relative: str) -> Path:
    return project_root / Path(relative)


def verify_design_input(project_root: Path, config: dict[str, Any]) -> None:
    path = resolve(project_root, config["inputs"]["design_input"])
    expected = config["inputs"]["design_input_sha256"].lower()
    actual = sha256_file(path).lower()
    if actual != expected:
        raise RuntimeError(
            "design_input.cpp SHA-256 mismatch.\n"
            f"Expected: {expected}\nActual:   {actual}"
        )


def ensure_not_exists(paths: list[Path], force: bool) -> None:
    existing = [str(path) for path in paths if path.exists()]
    if existing and not force:
        raise FileExistsError(
            "Output already exists and was not overwritten:\n" + "\n".join(existing)
        )


def call_ollama(
    config: dict[str, Any],
    system: str,
    prompt: str,
    request_path: Path,
    response_path: Path,
    metadata_path: Path,
) -> dict[str, Any]:
    payload = {
        "model": config["model"]["name"],
        "system": system,
        "prompt": prompt,
        "stream": config["generation"]["stream"],
        "options": config["generation"]["options"],
    }
    write_json(request_path, payload)
    request = urllib.request.Request(
        config["endpoint"],
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started_at = utc_now()
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=7200) as response:
            raw = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError) as error:
        write_json(
            metadata_path.with_name(metadata_path.stem + "_error.json"),
            {
                "started_at_utc": started_at,
                "failed_at_utc": utc_now(),
                "elapsed_seconds": time.perf_counter() - start,
                "error_type": type(error).__name__,
                "error": str(error),
                "retry_performed": False,
            },
        )
        raise
    result = json.loads(raw)
    write_json(response_path, result)
    write_json(
        metadata_path,
        {
            "started_at_utc": started_at,
            "completed_at_utc": utc_now(),
            "elapsed_seconds": time.perf_counter() - start,
            "model": result.get("model"),
            "created_at": result.get("created_at"),
            "done": result.get("done"),
            "done_reason": result.get("done_reason"),
            "total_duration_ns": result.get("total_duration"),
            "load_duration_ns": result.get("load_duration"),
            "prompt_eval_count": result.get("prompt_eval_count"),
            "prompt_eval_duration_ns": result.get("prompt_eval_duration"),
            "eval_count": result.get("eval_count"),
            "eval_duration_ns": result.get("eval_duration"),
            "retry_performed": False,
            "automatic_repair_performed": False,
        },
    )
    return result


def run_design(project_root: Path, config: dict[str, Any], force: bool) -> None:
    verify_design_input(project_root, config)
    experiment = project_root / "experiments/ini-writer-minimal"
    raw_dir = experiment / "raw_output"
    generated_dir = experiment / "generated"
    request_path = raw_dir / "design_generation_request.json"
    response_path = raw_dir / "design_generation_response.json"
    raw_text_path = raw_dir / "design_generation_raw.txt"
    metadata_path = raw_dir / "design_generation_metadata.json"
    design_path = generated_dir / "design_document.md"
    ensure_not_exists(
        [request_path, response_path, raw_text_path, metadata_path, design_path], force
    )
    template = read_text(resolve(project_root, config["prompts"]["design_generation"]))
    source = read_text(resolve(project_root, config["inputs"]["design_input"]))
    prompt = template.replace("{{DESIGN_INPUT}}", source)
    result = call_ollama(
        config,
        "Follow the task and output constraints exactly. Do not add unsupported information.",
        prompt,
        request_path,
        response_path,
        metadata_path,
    )
    output = result.get("response")
    if not isinstance(output, str):
        raise RuntimeError("Ollama response has no string response field.")
    write_text(raw_text_path, output)
    write_text(design_path, output.rstrip() + "\n")
    print(f"Design document saved: {design_path}")


def run_regenerate(project_root: Path, config: dict[str, Any], force: bool) -> None:
    experiment = project_root / "experiments/ini-writer-minimal"
    raw_dir = experiment / "raw_output"
    generated_dir = experiment / "generated"
    design_path = generated_dir / "design_document.md"
    if not design_path.exists():
        raise FileNotFoundError("Run --stage design first.")
    request_path = raw_dir / "code_regeneration_request.json"
    response_path = raw_dir / "code_regeneration_response.json"
    raw_text_path = raw_dir / "code_regeneration_raw.txt"
    metadata_path = raw_dir / "code_regeneration_metadata.json"
    body_path = generated_dir / "regenerated_write_body.cpp"
    ensure_not_exists(
        [request_path, response_path, raw_text_path, metadata_path, body_path], force
    )
    template = read_text(resolve(project_root, config["prompts"]["code_regeneration"]))
    prompt = (
        template.replace("{{DESIGN_DOCUMENT}}", read_text(design_path))
        .replace(
            "{{FIXED_SCAFFOLD}}",
            read_text(resolve(project_root, config["inputs"]["fixed_scaffold"])),
        )
        .replace(
            "{{DEPENDENCY_CONTEXT}}",
            read_text(resolve(project_root, config["inputs"]["dependency_context"])),
        )
    )
    result = call_ollama(
        config,
        "Follow the task and output constraints exactly. Return only the requested C++ body.",
        prompt,
        request_path,
        response_path,
        metadata_path,
    )
    output = result.get("response")
    if not isinstance(output, str):
        raise RuntimeError("Ollama response has no string response field.")
    # Exact model output is preserved. No code-fence removal or repair is performed.
    write_text(raw_text_path, output)
    write_text(body_path, output.rstrip() + "\n")
    print(f"Regenerated body saved: {body_path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("design", "regenerate", "all"), required=True)
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    project_root = args.project_root.resolve()
    config = load_config(project_root)
    if args.stage in ("design", "all"):
        run_design(project_root, config, args.force)
    if args.stage in ("regenerate", "all"):
        run_regenerate(project_root, config, args.force)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
