# Source-faithful Direct-Include Repository-Context RAG v5 Evaluation Protocol

## 位置付け

v5は、凍結済みv4評価とその失敗分析を見た後に設計するpost-hoc refinement / sensitivity evaluationである。v4結果は変更・再実行・再分類しない。v5の17対象も独立なconfirmatory experimentとは扱わない。

v4では、対象`source_files`全体と汎用詳細設計知識`knowledge/detailed-design/general-v4.md`を設計文書生成へ入力した。一方、対象コードから直接参照されるリポジトリ固有ヘッダーが`source_files`外にある場合、その定義本文は設計文書生成LLMへ入力されていない。

v5の目的は、v4の汎用source-fidelity規則を維持したまま、対象ソースが直接includeするリポジトリ固有ファイル全文を機械的に補完したとき、設計文書およびdownstream再生成結果がどう変化するかを確認することである。

## Treatment

condition: `full_source_source_faithful_direct_include_rag_v5`

設計文書生成入力は次の3要素とする。

1. v4と同じ汎用詳細設計知識`general-v4.md`
2. Direct-Include Repository Context
3. v4と同じ対象`source_files`全文

対象に`.h/.hpp`と`.cpp`の両方が設定されている場合、両方を従来どおり対象ソース全文として入力する。RAGはそれらの代替ではない。

## Direct-Include Repository Contextの固定規則

対象の全`source_files`について、`#include "..."`のみを決定的に抽出する。`#include <...>`は取得しない。

quoted includeは固定repository commitのtracked file集合に対して次の順で解決する。

1. include元ファイルのディレクトリからの相対パス
2. repository rootからの相対パス
3. repository-relative suffixの一意一致
4. basenameの一意一致

候補が複数なら`ambiguous`、存在しなければ`unresolved`とする。target別の例外規則や手動path指定は禁止する。

一意に解決されたファイルが対象`source_files`自身なら重複取得しない。対象外なら全文を取得する。同一ファイルは1回だけ追加する。取得したファイル内部のincludeは追跡しない。depthは1 hopで固定する。

LLMをquery生成、ファイル選択、ranking、再検索に使用しない。vector retrieval、BM25、agentic retrieval、multi-hop retrieval、外部Web/API documentationはv5 treatmentに含めない。

## Retrieval-only preflight

本実験前に17対象すべてについてLLMを呼ばないretrieval-only auditを1回行う。

GO条件:

- 17対象すべてを処理できる
- quoted includeに`unresolved`がない
- repository内解決に`ambiguous`がない
- target source自身がretrieved contextへ重複しない
- selected fileはtracked repository fileの全文である
- target別manual tuningがない
- 実際にLLMへ渡すcombined contextとSHA-256を保存できる

代表例としてInstruction、ThreadPool、Parser等のselected pathと`context.txt`を目視確認してよい。ただし目視結果を使ったtarget別retrieval規則変更は禁止する。

formal execution時はretrievalを同じ規則で再構成し、preflightで凍結したcombined-context SHA-256と一致しないtargetを実行しない。

## 固定条件

v4から次を変更しない。

- target inventory: 17
- repository commit
- source_files / observation scope
- model: `qwen2.5-coder:32b`
- temperature: 0
- seed: 42
- num_ctx: 32768
- num_predict: 16384
- generations per stage: 1
- retry: false
- automatic repair: false
- generated-code manual edit: false
- design heading validation: advisory / non-blocking
- code-regeneration prompt structure
- original source in code regeneration: false
- retrieved repository context in code regeneration: false
- Docker image / configure / build / direct test / full test

コード再生成は従来どおりgenerated design document + fixed scaffold + dependency/include contextのみを使用する。

## 比較

v5の直接のreferenceは凍結済みv4 treatment 17 runsとする。各pairについて`FAIL->PASS`、`PASS->FAIL`、`PASS->PASS`、`FAIL->FAIL`を報告する。

v5はv4結果を見て設計したpost-hoc条件なので、改善しても未知repositoryへの一般化性能を確証したとは扱わない。方式を凍結した後、必要に応じて別repository / hold-out targetで独立検証する。
