from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


RUNNER = Path(__file__).resolve().parent / "run_target_v3.py"
spec = importlib.util.spec_from_file_location("roundtrip_v3_runner", RUNNER)
if spec is None or spec.loader is None:
    raise RuntimeError(RUNNER)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def base_config(condition: str) -> dict:
    return {
        "target_name": "Dummy",
        "granularity": "module_files",
        "source_files": ["dummy.h"],
        "locator": {},
        "condition": condition,
    }


def control_document() -> str:
    return "\n\n".join(f"## {name}\n内容" for name in mod.BASE_SECTIONS) + "\n"


def rag_document() -> str:
    base = control_document().rstrip()
    details = [
        "### クラス図\n```mermaid\nclassDiagram\nclass Dummy\n```",
        "### クラス・メソッド・インターフェース詳細\n|項目|内容|\n|---|---|\n|型|Dummy|",
        "### シーケンス図\n該当なし：相互作用を確認できない。",
        "### メソッド仕様書\n|項目|内容|\n|---|---|\n|目的|確認可能な処理|",
        "### 処理フロー図\n```mermaid\nflowchart TD\nA[Start] --> B[End]\n```",
        "### 状態遷移・副作用\n該当なし：状態変更を確認できない。",
        "### データ変換・制約\n|項目|内容|\n|---|---|\n|変換|なし|",
    ]
    return base + f"\n\n## {mod.DETAIL_ROOT_SECTION}\n\n" + "\n\n".join(details) + "\n"


def main() -> int:
    design_input = "===== FILE: dummy.h =====\nstruct Dummy {};\n"
    control = base_config(mod.CONTROL_CONDITION)
    system_control, control_prompt = mod.build_design_prompt(control, design_input, "")
    rag = base_config(mod.RAG_CONDITION)
    system_rag, rag_prompt = mod.build_design_prompt(rag, design_input, "DETAIL KNOWLEDGE")

    assert system_control == system_rag == mod.SYSTEM_PROMPT
    for section in mod.BASE_SECTIONS:
        token = f"## {section}"
        assert token in control_prompt
        assert token in rag_prompt
    assert f"## {mod.DETAIL_ROOT_SECTION}" not in control_prompt
    assert f"## {mod.DETAIL_ROOT_SECTION}" in rag_prompt
    for section in mod.DETAIL_SECTIONS:
        assert f"### {section}" in rag_prompt
    assert "DETAIL KNOWLEDGE" in rag_prompt

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        control_result = mod.validate_generated_design(
            control, control_document(), root / "control"
        )
        assert control_result["passed"] is True
        rag_result = mod.validate_generated_design(rag, rag_document(), root / "rag")
        assert rag_result["passed"] is True

        invalid = rag_document().replace("### データ変換・制約", "### 別名", 1)
        try:
            mod.validate_generated_design(rag, invalid, root / "invalid")
        except RuntimeError:
            pass
        else:
            raise AssertionError("Invalid detail heading must fail")

    print("Prompt and design-contract tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())