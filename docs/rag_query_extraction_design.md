# Repository-Context RAG v1 Phase 2 Query抽出設計

## 1. 対象範囲

Phase 2では、対応比較に用いる凍結済み17対象について、各対象の凍結source範囲からC/C++検索queryを決定的に生成する。LLMは呼び出さない。また、BM25 retrieval、1-hop expansion、context選択、設計文書生成、コード再生成、Docker、build、test、RAG formal 17対象実験は実施しない。

固定method identifierは`deterministic-cpp-query-v1`とする。target固有の手動query追加は禁止する。

## 2. 凍結source範囲

`configs/rag/query_targets_v1.json`で17 target IDと、source範囲の再現に使用するmetadata fileを固定する。

- `module_files`: 凍結target configの`source_files`に記録された各fileの正規化済み全内容を使用する。
- `class_span`: `source_metadata.json`に保存された`start_offset`と`end_offset`を使用する。非RAG harnessはdecode済み文字列をsliceしたため、これらはPython character offsetである。Phase 2ではUTF-8 byte offsetへ変換し、`original_span_sha256`を検証する。
- 旧形式`INIWriter::write`: `experiments/ini-writer-minimal/input/source_metadata.json`に保存された`design_input_start_line`から`class_end_line`までをone-based inclusive line spanとして使用する。

source textは`utf-8-sig`でdecodeし、CRLFとCRをLFへ正規化してからUTF-8 byte coordinateを記録する。これにより、checkout時の改行コードに依存せず、非RAG design inputと同じcoordinate spaceを再現する。

抽出開始前に、repository HEAD、固定commit、tracked working treeのclean状態、Phase 1 index validationの`status=pass`、`deterministic=true`、`unhandled_parser_error_count=0`を確認する。既存Phase 1 artifactはread onlyで扱う。

## 3. Query category

各`query.json`は、次のcanonical arrayを持つ。

- `target_symbols`
- `includes`
- `user_defined_types`
- `function_calls`
- `base_classes`
- `nested_types`
- `enums`
- `constants_and_macros`
- `documentation_references`
- `dependency_candidates`

quoted project includeを保持し、standard-library-only includeとidentifierは除外する。C++ keyword、built-in type、1-character identifier、literal、generic unqualified callをfilterする。qualified call、base class、nested type、enum、macro、namespace/class constant、凍結target symbolをhigh priorityとする。unqualified project-looking call、constructor candidate、user-defined type、enum/constant reference、documentation referenceをmedium priorityとする。

`dependency_candidates`は各source queryから決定的に派生させ、source queryのpriorityを継承する。Phase 1 exact symbol indexは、documentation referenceがrepository symbolかを判定するmembership checkにのみ使用できる。Phase 2ではchunk選択やretrieval context生成を行わない。

## 4. Source locationとcanonical dedup

各query recordは次を保存する。

- repository-relative POSIX path
- zero-based half-open byte range
- one-based inclusive line range
- zero-based column
- relationとevidence node type
- `high`、`medium`、`low`のpriority
- locationに依存しないstable `query_id`

canonical identityは`category`、`canonical_text`、`kind`、`relation`で構成する。同一identityがsource内に複数回出現した場合、queryを複製せず、`evidence_locations`と`evidence_node_types`へsorted uniqueで集約する。arrayはpriority、canonical text、path、byte position、kind、`query_id`の順で決定的にsortする。

## 5. Canonical JSONとSHA-256

JSONはUTF-8、LF、lexicographic key order、compact separator、final LF exactly oneでserializeする。timestampはcontentへ含めない。

`query_payload_sha256`は、`query_payload_sha256` fieldだけを除いた完全なcanonical query objectから計算する。最終file SHA-256は`query_validation.json`へ保存し、self-referenceを避ける。

## 6. 独立2回生成

`scripts/rag/build_queries.py`は、選択した全targetを別directoryで独立に2回生成する。両方のcanonical `query.json` file hashが一致した場合だけpublishする。hash mismatchまたはvalidation failure時は、独立build evidenceを保持し、既存outputを上書きしない。

publish layoutは次のとおりとする。

```text
rag/query/
  query_generation_manifest.json
  <target-id>/
    query.json
    query_validation.json
```

Phase 2は既存`rag/index/` artifact、submodule pointer、凍結済み非RAG experiment resultを書き換えない。
