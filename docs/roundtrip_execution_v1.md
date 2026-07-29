# Round-trip execution v1

## 目的

既存の17対象draftをローカルリポジトリから補完し，検証済み設定だけを直列実行する．

## 安全条件

- `--probe`前にはLLMを実行しない．
- `run_batch.py`は`--execute`なしではplanだけを生成する．
- 各対象は元ソースをfinallyで復元する．
- 再試行，自動修正，出力補正を行わない．
- コード再生成の形式違反は失敗として記録する．

## 1. 実行設定を作る

まず設定候補だけ作る．

```powershell
py -3 .\scripts\roundtrip\configure_execution.py
```

最初はEcho-Web-Server/ioだけのベースラインを実行して設定を有効化する．

```powershell
py -3 .\scripts\roundtrip\configure_execution.py `
  --target echo-web-server-io `
  --probe `
  --force
```

`--probe`なしで作った設定は無効のままであり，LLM実験には使用されない．

結果は`reports/batch/execution_config_readiness.md`へ保存される．

## 2. planを確認する

```powershell
py -3 .\scripts\roundtrip\run_batch.py
```

## 3. 単一対象を実行する

最初はEcho-Web-Server/ioを指定する．

```powershell
py -3 .\scripts\roundtrip\run_target.py `
  --config .\configs\roundtrip\targets\echo-web-server-io.json
```

## 4. 全ready対象を実行する

```powershell
py -3 .\scripts\roundtrip\run_batch.py --execute
```

全対象は直列実行される．1対象の失敗後も次対象へ進む．
