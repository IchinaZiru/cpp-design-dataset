"""Validate the fixed local Python and Tree-sitter environment."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import sys
from pathlib import Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate .venv-rag against its manifest.")
    parser.add_argument(
        "--manifest",
        default="rag/environment/rag_environment_manifest.json",
    )
    args = parser.parse_args()
    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []

    expected_os = manifest.get("os_family")
    if expected_os and platform.system().lower() != str(expected_os).lower():
        errors.append(f"os_family: expected {expected_os}, got {platform.system()}")

    if platform.python_implementation() != manifest["implementation"]:
        errors.append(
            f"implementation: expected {manifest['implementation']}, "
            f"got {platform.python_implementation()}"
        )
    actual_python = platform.python_version()
    if actual_python != manifest["python_version"]:
        errors.append(
            f"python_version: expected {manifest['python_version']}, got {actual_python}"
        )

    expected_machine = manifest.get("machine")
    if expected_machine and platform.machine().lower() != str(expected_machine).lower():
        errors.append(
            f"machine: expected {expected_machine}, got {platform.machine()}"
        )

    for package in manifest["packages"]:
        try:
            actual = importlib.metadata.version(package["name"])
        except importlib.metadata.PackageNotFoundError:
            errors.append(f"package missing: {package['name']}")
            continue
        if actual != package["version"]:
            errors.append(
                f"package {package['name']}: expected {package['version']}, got {actual}"
            )

    for path_key, hash_key in (
        ("requirements_lock_path", "requirements_lock_sha256"),
        ("retrieval_config_path", "retrieval_config_sha256"),
    ):
        path = Path(manifest[path_key])
        actual = _sha256(path)
        if actual != manifest[hash_key]:
            errors.append(
                f"{path_key} hash: expected {manifest[hash_key]}, got {actual}"
            )

    result = {
        "errors": errors,
        "manifest": manifest_path.as_posix(),
        "status": "pass" if not errors else "fail",
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
