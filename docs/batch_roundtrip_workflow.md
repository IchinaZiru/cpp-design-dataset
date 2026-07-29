# Round-trip batch harness

## 目的

17対象のラウンドトリップ実験を直列実行するための土台である．

現在の最小実験では`INIWriter::write`だけが完全に設定されているため，
いきなりLLM生成を開始せず，最初に既存metadataから対象カタログと不足項目を抽出する．

## ファイル

- `scripts/roundtrip/bootstrap_batch_catalog.py`
  - `metadata/*_report.md`から17対象を抽出する．
  - draft設定とreadinessレポートを生成する．
- `scripts/roundtrip/run_batch.py`
  - 完成済み設定を直列実行する．
  - デフォルトはplanのみであり，`--execute`を付けるまで実行しない．

## 1. カタログ生成

```powershell
py -3 .\scripts\roundtrip\bootstrap_batch_catalog.py
```

生成物：

```text
configs/roundtrip/target_catalog.json
configs/roundtrip/targets/*.draft.json
reports/batch/batch_readiness.md
reports/batch/batch_readiness.csv
```

## 2. plan確認

draft設定は意図的に`enabled: false`である．
不足項目を埋め，ファイル名から`.draft`を外した後にplanを確認する．

```powershell
py -3 .\scripts\roundtrip\run_batch.py
```

## 3. 実行

すべての対象設定が検証済みになった後だけ実行する．

```powershell
py -3 .\scripts\roundtrip\run_batch.py --execute
```

実行は直列であり，再試行と自動修正は行わない．

## 設定に必要なstage_commands

各完成設定には次の6段階を配列形式で記述する．

```json
{
  "stage_commands": {
    "prepare": ["py", "-3", "scripts/roundtrip/prepare_target.py", "--target", "..."],
    "generate_design": ["py", "-3", "scripts/roundtrip/generate_design.py", "--target", "..."],
    "regenerate_code": ["py", "-3", "scripts/roundtrip/regenerate_code.py", "--target", "..."],
    "evaluate": ["py", "-3", "scripts/roundtrip/evaluate_target.py", "--target", "..."],
    "generate_report": ["py", "-3", "scripts/reporting/generate_experiment_overview.py", "--experiment", "..."],
    "register_run": ["py", "-3", "scripts/roundtrip/register_run.py", "--target", "..."]
  }
}
```

このbundleは安全なバッチ制御と対象カタログ作成までを提供する．
対象共通の`prepare/generate/evaluate/register`実装は，
readinessレポートで置換境界とビルドコマンドを確定した後に追加する．
