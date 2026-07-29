# C++ Design Document Round-Trip Dataset

C++ソースコードからLLMを用いて設計文書を生成し，
生成した設計文書からコードを再生成した上で，
既存のビルドおよびテストスイートによって正当性を評価する研究用リポジトリである。

## Repository contents

- `repos/`: 実験対象となる外部Gitリポジトリ
- `scripts/`: 対象抽出，生成，置換，評価，復元用スクリプト
- `experiments/`: LLM入力，プロンプト，生成結果，ログ，判定結果
- `docker/`: 固定実験環境
- `configs/`: モデルおよび実験条件
- `manifests/`: リポジトリ，対象，実験実行の一覧
- `docs/`: 実験手順および運用規則

## Current minimal experiment

- Repository: `SSARCandy/ini-cpp`
- Target: `INIWriter::write`
- Regeneration scope: function body
- Evaluation: build, direct tests and full tests
- Automatic repair: disabled
- Retry: disabled

## Reproducibility policy

各実験では，対象リポジトリのコミット，LLM入力，プロンプト，
未加工出力，評価対象コード，ビルドログ，テストログ，SHA-256，
および最終判定を保存する。
