# Prompt-preserving Detailed-design RAG v3 Formal Protocol

## 目的

Full-source round-trip 条件において、設計文書の共通9項目を固定したまま、設計文書生成時に汎用的な詳細設計知識を追加した場合、再生成コードの既存テスト通過率が変化するかを17対象のpaired comparisonで評価する。

旧v2 formal結果は凍結し、v3の直接比較には使用しない。v3では新しいnon-RAGと新しいRAGを同一設定で生成し、両者を直接比較する。

## 比較条件

### Control: `full_source_prompt_preserving_non_rag`

ソースコード全体を入力し、次の9個のlevel-2見出しだけをこの順序・表記で生成する。

1. `## 責務`
2. `## 公開インターフェース`
3. `## 入力`
4. `## 出力`
5. `## 状態`
6. `## 処理手順`
7. `## 例外・失敗条件`
8. `## 依存関係`
9. `## 重要な不変条件`

### Treatment: `full_source_prompt_preserving_detailed_design_rag`

Controlと同じ9見出しを同じ順序・表記で生成した後、`## 追加詳細設計情報`を1つだけ追加し、その配下に次の7個のlevel-3見出しを固定順序で生成する。

1. `### クラス図`
2. `### クラス・メソッド・インターフェース詳細`
3. `### シーケンス図`
4. `### メソッド仕様書`
5. `### 処理フロー図`
6. `### 状態遷移・副作用`
7. `### データ変換・制約`

RAG knowledgeは`knowledge/detailed-design/general-v3.md`を全対象で共通利用する。対象別の知識調整は行わない。該当しない成果物も見出しを省略せず、`該当なし`と根拠を記述する。確認できない情報は`確認不能`とし、推測で補完しない。

## 詳細設計知識の位置付け

追加7項目は特定のformal対象の失敗を修復するためのtarget-specific ruleではなく、一般的な詳細設計の観点として定義する。

- クラス図、クラス・メソッド・インターフェース詳細、シーケンス図、メソッド仕様書はZenn記事で確認した詳細設計成果物を基本とする。
- 処理フロー図、状態遷移・副作用、データ変換・制約は一般的なソフトウェア設計で再実装に有用な動的振る舞い・状態・データ制約の観点として追加する。
- `確認不能事項`は独立した成果物にせず、推測防止の生成規則として扱う。

Zenn記事の書誌情報は原稿化時にタイトル、URL、参照日を別途確定する。

## 固定対象

v2 formalと同じ17 targetをpair ID単位で使用する。

- `module_files`: 11 target
- `class_span`相当の`target_span`: 5 target
- `function`: 1 target

`Session`はformal 17から除外し、v3のmechanics pilotにのみ使用する。

## モデルとcontext設定

両条件で次を固定する。

- model: `qwen2.5-coder:32b`
- temperature: `0`
- seed: `42`
- `num_ctx`: `32768`
- `num_predict`: `16384`
- generations per stage: `1`
- retry: `false`
- automatic repair: `false`

2026-08のpreflightでは、ローカルモデルがnative/allocated context 32768でロードされ、保存済みv2の17 requestに対するtokenizer予測とOllama `prompt_eval_count`は全件delta 0で一致した。実装後は最終promptを用いてpreflightを再実行し、input + reserved outputが32768以内であることをformal/pilot前に再確認する。

## 公平性

対応するnon-RAG/RAGで同一に保つもの：

- 17 target inventory
- repository commit
- source/observation/replacement scope
- Docker image and image ID
- direct/full test filters and expected counts
- model ID and全generation options
- basic 9-heading output contract
- code regeneration prompt and inputs
- generation count = 1
- retry = false
- automatic repair = false
- generated-code manual edit = false
- timeouts and normalization policy

条件間で変更してよいもの：

- condition/run/experiment IDs
- design-generation時の`general-v3.md`追加
- それに伴う追加詳細設計7項目
- retrieval artifact metadata

## 設計文書の形式検証

LLM生成後、決定論的validatorでMarkdown見出し構成を検査する。

- Control: level-2見出しが基本9項目と完全一致すること。
- Treatment: level-2見出しが基本9項目 + `追加詳細設計情報`と完全一致すること。
- Treatment: `追加詳細設計情報`配下のlevel-3見出しが7項目と完全一致すること。
- クラス図、シーケンス図、処理フロー図は、該当する場合は指定Mermaid形式を含むこと。該当しない場合は`該当なし`を明示すること。

違反時は自動修正やretryを行わず、`design_generation`段階のterminal pipeline failureとして保存する。

## 出力打ち切り

設計生成・コード再生成のいずれも`done_reason=stop`を正常終了条件とする。`length`など`stop`以外はterminal generation failureであり、同じrun IDで`num_predict`変更、retry、再生成を行わない。

## コード再生成

v2 formal mechanicsを継承する。コード再生成時に入力するのは次の3つだけである。

1. generated design document
2. fixed-interface scaffold
3. dependency/include context

元ソースおよびRAG knowledge/retrieved contextはコード再生成時に再投入しない。

## 評価

生成コード置換後、configure -> build -> direct test -> full testを順に実行する。前段FAIL時は後段をskipする。PASSは既存テストが観測した範囲の正当性であり、完全な意味的等価性とは呼ばない。

最終比較では17 pairについて`FAIL->PASS`、`PASS->FAIL`、`PASS->PASS`、`FAIL->FAIL`を報告し、primary statistical comparisonはexact McNemarとする。

## 実験分離・停止規則

- v2 artifacts/configs/resultsを変更しない。
- v3は`configs/roundtrip_v3/`, `experiments/v3/`, `analysis/formal_v3/`へ保存する。
- v2/v3のrun IDとexperiment IDを再利用しない。
- formal configはcommit上`enabled=false`とし、実行時のみtemporary enabled copyを使う。
- terminal artifactを上書き・削除・再実行しない。
- source restoration hash mismatch、repository tracked dirty、config mismatch、Docker image mismatch、generation contract violation、output truncationでは即停止する。
- formal前に17対象外の`Session`でnon-RAG/RAG pilot pairを実行し、prompt contract、32K/16K設定、出力保存、source restoration、pipeline mechanicsを確認する。