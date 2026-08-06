# Full-source RAG v2 starter

このスターターは、旧runnerと旧実験結果を変更せず、v2用の独立runnerとpilot設定を追加します。

## 配置

ZIPの中身を`cpp-design-dataset-v2`のルートへ展開してください。

## 静的確認

```powershell
py -3 -m py_compile .\scripts\roundtrip_v2\run_target_v2.py

git diff --check
git status --short
```

## 先に非RAG pilotを実行

```powershell
py -3 .\scripts\roundtrip_v2\run_target_v2.py `
  --config .\configs\roundtrip_v2\non_rag\riscv-simulator-register.json
```

出力先:

```text
experiments/v2/pilot/non-rag/riscv-simulator-register-001/
```

## 次にRAG pilotを実行

非RAGの生成物とsubmodule復元を確認してから実行します。

```powershell
py -3 .\scripts\roundtrip_v2\run_target_v2.py `
  --config .\configs\roundtrip_v2\rag\riscv-simulator-register.json
```

出力先:

```text
experiments/v2/pilot/rag/riscv-simulator-register-001/
```

## 実行後の確認

```powershell
git -C .\repos\RISCV-Simulator status --short
Get-Content .\experiments\v2\pilot\non-rag\riscv-simulator-register-001\evaluation\evaluation_manifest.json
Get-Content .\experiments\v2\pilot\rag\riscv-simulator-register-001\retrieval\retrieval_manifest.json
Get-Content .\experiments\v2\pilot\rag\riscv-simulator-register-001\evaluation\evaluation_manifest.json
```

## コミット

pilot実行前は、実装・設定・知識だけをパス指定でstageします。`git add .`は使用しません。

```powershell
git add -- `
  .\scripts\roundtrip_v2\run_target_v2.py `
  .\configs\roundtrip_v2\non_rag\riscv-simulator-register.json `
  .\configs\roundtrip_v2\rag\riscv-simulator-register.json `
  .\knowledge\detailed-design\general-v1.md `
  .\docs\experiments\full_source_design_rag_v2.md `
  .\README_APPLY.md

git diff --cached --check
git commit -m "feat: add full-source design-knowledge RAG v2 pilot"
```
