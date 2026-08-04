# Repository-Context RAG Experiment Protocol

## 1. 文書管理

- Protocol version: `0.9`
- Condition ID: `rag-design-context-v1`
- Condition name: `Repository-Context RAG v1`
- Retrieval method name: `symbol-aware staged retrieval`（シンボル対応型の段階的検索）
- Author: 荒井裕太
- Created: 2026-08-04
- Baseline repository: `IchinaZiru/cpp-design-dataset`
- Frozen baseline commit: `e67c509070daf5778474b21ba452593d1d762e82`
- Baseline analysis reference:
  - `reports/analysis/analysis_manifest.json`
  - `reports/analysis/main_results.csv`
  - `reports/analysis/summary.json`
  - `reports/analysis/summary.md`
- Protocol status: pre-pilot freeze
- Formal execution status: not started

### 1.1 Revision history

| Version | Status | Description |
|---|---|---|
| 0.9 | Pre-pilot freeze | RQ、対象、corpus、chunk、query、retrieval、公平性、評価、停止規則を固定する。pilotで決定する数値は未確定とする。 |
| 1.0 | TBD after pilot | pilot対象、context format、retrieval top-k、context token budget、quota、実ライブラリversionを固定する。 |

### 1.2 未確定項目

以下はformal 17対象を確認して最適化せず、formal外pilotだけで決定する。

- `pilot_target_ids`
- `context_format`
- `retrieval_top_k`
- `context_budget_tokens`
- category quota
- token counter/version
- parser/libraryの実version
- BM25 libraryの実version

---

## 2. Research question

> 設計文書生成時に同一リポジトリ内の関連実装情報をRAGで追加することで、設計文書だけから再生成したC++コードの既存テスト通過率は、非RAG条件より向上するか。

---

## 3. 仮説

同一の対象ソース、モデル、生成条件、コード再生成promptおよびbuild/test条件を維持したまま、設計文書生成時だけrepository固有の定義、型、interface、直接依存関係および利用例を追加すると、設計文書に保持される実装情報が増え、再生成コードのbuildおよび既存テスト通過率が非RAG条件より改善する。

ただし、関連性の低いcontext、同名symbol、過剰な利用例または不正確なdependency展開は、設計文書へnoiseを加え、`PASS -> FAIL`を引き起こす可能性がある。

---

## 4. Control and treatment

### 4.1 Control

- Condition: frozen non-RAG main study
- Target count: 17
- PASS: 6
- FAIL: 11
- Pass rate: 35.3%
- Frozen analysis commit: `e67c509070daf5778474b21ba452593d1d762e82`
- Frozen results must not be rerun, repaired, overwritten or silently reclassified.

### 4.2 Treatment

```text
fixed target source
  + retrieved context from the same pinned repository commit
  -> Japanese design document
  -> design document only + the same fixed scaffold
  -> regenerated C++
  -> the same configure/build/direct/full tests
```

RAGは設計文書生成時だけ使用する。コード再生成時には、retrieved context、元ソースまたはrepository codeを渡さない。

---

## 5. Fixed target set

| Target ID | Repository | Pinned commit | Granularity | Frozen non-RAG run/config |
|---|---|---|---|---|
| `echo-web-server-block-deque` | Echo-Web-Server | `fb2fadb7e7f4c340325b0a72847425f6e8b6367e` | `module_files` | `echo-web-server-block-deque-qwen25coder32b-001` / `configs/roundtrip/targets/echo-web-server-block-deque.json` |
| `echo-web-server-buffer` | Echo-Web-Server | `fb2fadb7e7f4c340325b0a72847425f6e8b6367e` | `module_files` | `echo-web-server-buffer-qwen25coder32b-001` / `configs/roundtrip/targets/echo-web-server-buffer.json` |
| `echo-web-server-config` | Echo-Web-Server | `fb2fadb7e7f4c340325b0a72847425f6e8b6367e` | `module_files` | `echo-web-server-config-qwen25coder32b-002` / `configs/roundtrip/targets/echo-web-server-config.json` |
| `echo-web-server-heap-timer` | Echo-Web-Server | `fb2fadb7e7f4c340325b0a72847425f6e8b6367e` | `module_files` | `echo-web-server-heap-timer-qwen25coder32b-001` / `configs/roundtrip/targets/echo-web-server-heap-timer.json` |
| `echo-web-server-http` | Echo-Web-Server | `fb2fadb7e7f4c340325b0a72847425f6e8b6367e` | `module_files` | `echo-web-server-http-qwen25coder32b-001` / `configs/roundtrip/targets/echo-web-server-http.json` |
| `echo-web-server-io` | Echo-Web-Server | `fb2fadb7e7f4c340325b0a72847425f6e8b6367e` | `module_files` | `echo-web-server-io-qwen25coder32b-002` / `configs/roundtrip/targets/echo-web-server-io.json` |
| `echo-web-server-ip` | Echo-Web-Server | `fb2fadb7e7f4c340325b0a72847425f6e8b6367e` | `module_files` | `echo-web-server-ip-qwen25coder32b-001` / `configs/roundtrip/targets/echo-web-server-ip.json` |
| `echo-web-server-log` | Echo-Web-Server | `fb2fadb7e7f4c340325b0a72847425f6e8b6367e` | `module_files` | `echo-web-server-log-qwen25coder32b-001` / `configs/roundtrip/targets/echo-web-server-log.json` |
| `echo-web-server-thread-pool` | Echo-Web-Server | `fb2fadb7e7f4c340325b0a72847425f6e8b6367e` | `module_files` | `echo-web-server-thread-pool-qwen25coder32b-001` / `configs/roundtrip/targets/echo-web-server-thread-pool.json` |
| `echo-web-server-util` | Echo-Web-Server | `fb2fadb7e7f4c340325b0a72847425f6e8b6367e` | `module_files` | `echo-web-server-util-qwen25coder32b-001` / `configs/roundtrip/targets/echo-web-server-util.json` |
| `ini-cpp-ini-writer` | ini-cpp | `e1779b837274de8be2051bef579c3b9ec3483522` | legacy `function` | `ini-writer-minimal` / legacy config |
| `ini-cpp-inireader` | ini-cpp | `e1779b837274de8be2051bef579c3b9ec3483522` | `class_span` | `ini-cpp-inireader-qwen25coder32b-001` / `configs/roundtrip/targets/ini-cpp-inireader.json` |
| `riscv-simulator-instruction` | RISCV-Simulator | `8989a09c357a69b68612f653380d60816f5176c2` | `module_files` | `riscv-simulator-instruction-qwen25coder32b-001` / `configs/roundtrip/targets/riscv-simulator-instruction.json` |
| `riscv-simulator-memory` | RISCV-Simulator | `8989a09c357a69b68612f653380d60816f5176c2` | `class_span` | `riscv-simulator-memory-qwen25coder32b-001` / `configs/roundtrip/targets/riscv-simulator-memory.json` |
| `riscv-simulator-parser` | RISCV-Simulator | `8989a09c357a69b68612f653380d60816f5176c2` | `class_span` | `riscv-simulator-parser-qwen25coder32b-001` / `configs/roundtrip/targets/riscv-simulator-parser.json` |
| `riscv-simulator-register` | RISCV-Simulator | `8989a09c357a69b68612f653380d60816f5176c2` | `class_span` | `riscv-simulator-register-qwen25coder32b-001` / `configs/roundtrip/targets/riscv-simulator-register.json` |
| `riscv-simulator-registerfile` | RISCV-Simulator | `8989a09c357a69b68612f653380d60816f5176c2` | `class_span` | `riscv-simulator-registerfile-qwen25coder32b-001` / `configs/roundtrip/targets/riscv-simulator-registerfile.json` |

同じ17 target IDでnon-RAGとRAGをpaired comparisonする。targetの追加、削除または置換を行わない。

---

## 6. Corpus policy

### 6.1 Include

固定commitでGit管理されているproduction C/C++実装のうち、次の拡張子を対象とする。

```text
.h
.hpp
.hh
.hxx
.c
.cc
.cpp
.cxx
.inl
.ipp
.tpp
```

### 6.2 Exclude

次を共通規則で除外する。

- testsおよびtest source
- benchmark
- build directory
- generated codeまたはgenerated source
- experiment artifact
- previous LLM output
- current/previous report
- raw log
- README
- natural-language documentation
- vendor
- external
- third-party
- nested submodule
- unsupported file
- per-target target source overlap

RAG v1ではthird-party例外を設けない。

### 6.3 Shared corpus and per-target masking

全targetで共通のeligible production corpusを構築する。target source overlapは共有index作成時ではなく、targetごとのretrieval前に除外する。

- Method: `path_byte_overlap_v1`
- Byte interval: half-open `[start_byte, end_byte)`
- `module_files`: 対象ファイル全体を除外
- `function` / `class_span`: 実際にLLMへ渡すpathとbyte範囲だけを除外
- 同一ファイル内の非重複symbolは候補として残せる
- 別ファイルに存在するdeclaration/definitionは候補として残せる

除外されたchunkについて、path、range、countおよびreasonを記録する。

---

## 7. Chunking

### 7.1 Parser

- Parser: Tree-sitter C++
- Python package version: `TBD_IMPLEMENTATION`
- C++ grammar version/commit: `TBD_IMPLEMENTATION`
- Chunking version: `tree-sitter-symbol-v1`

Tree-sitterは完全なC++ semantic resolverとして扱わない。template instantiation、linker resolution、preprocessor branch、完全なoverload resolutionは保証しない。

### 7.2 Primary chunk unit

原則として1 symbolを1 chunkとする。

- function definition
- method definition
- constructor
- destructor
- operator
- class/struct interface
- nested type
- enum definition
- alias declaration
- typedef declaration
- namespace-scope constant
- macro definition

### 7.3 Large chunks

- 200 linesはsoft triggerでありhard limitではない
- 200 linesを超える場合、完全なdirect-child AST unit境界だけで分割する
- 構文単位を壊す分割を行わない
- 完全な単位のまま200 linesを超える場合、分割せず`oversized_unsplit=true`を記録する
- synthetic braceまたは人工的なsource補完を追加しない

### 7.4 Comments

- symbol直前のDoxygen commentを対応symbolへ付与する
- `@file`は低priorityのfile documentationとして扱う
- license/generated boilerplateは除外する

### 7.5 Parse error and fallback

- parser errorがあるfileを黙って落とさない
- macro、conditional compilation、concept/requires等へdeterministic fallbackを使用できる
- fallback method、range、reasonを記録する
- 未処理errorが残る場合、index validationを不合格とする

### 7.6 Stable chunk ID

```text
SHA-256(
  repository_commit + "\n" +
  repository_relative_path + "\n" +
  start_byte + ":" + end_byte + "\n" +
  kind + "\n" +
  content_sha256
)
```

- 64桁の完全なSHA-256を保存する
- runtime random値、timestampまたはabsolute local pathを使用しない

---

## 8. Query construction

- Method: `deterministic-cpp-query-v1`
- LLM used: false
- Target-specific manual additions: prohibited

対象ソースASTから次を抽出する。

- local/project include
- qualified identifier
- user-defined type candidate
- function/method call
- constructor call
- base class
- nested class
- enum
- constant
- macro
- template
- operator
- 明示的なDoxygen code reference

### 8.1 Doxygen query rules

候補として扱えるもの：

1. `@see`
2. repository-local symbolへ解決できる`@p` identifier
3. parseable C/C++ `@code`
4. project-local exception type in `@throws` / `@exception`
5. qualified identifierまたはbacktick code reference

すべて、許可されたrepository-local symbol/pathへdeterministically解決できる場合だけ使用する。

一般的な`@brief`、`@param`、`@return`の自然言語をqueryへ使用しない。`@example`はtestへの参照を含む可能性があるため展開しない。

### 8.2 Exclude or down-rank

- C++ keyword
- builtin
- standard-library-only identifier
- one-character identifier
- local variable
- literal
- prose
- qualified relationを持たないgeneric verb:
  - `get`
  - `set`
  - `read`
  - `write`
  - `size`
  - `begin`
  - `end`
  - `data`
  - `value`

queryはhigh/medium/low priorityへ分類し、canonical dedup後に`query.json`へ保存する。target symbol自体は保持する。

---

## 9. Retrieval algorithm

### 9.1 Search stage: exact symbol retrieval

exact symbol indexをTree-sitter metadataから構築する。

Lookup key:

- exact canonical qualified name
- parent symbol + method
- resolved include path + short name
- exact short name fallback

取得対象：definition、declaration、class/struct interface、alias、enum、macro、namespace-scope constant、constructor、destructor、operator。

fuzzy match、substring matchまたはLLM guessを使用しない。

#### Overload resolution

- normalized parameter types
- parameter count
- cv qualifier
- ref qualifier
- `noexcept`
- template arity
- constructor/operator kind

一意に解決できない場合は、exact-name candidateをすべて保持して`ambiguous=true`を記録する。

#### Exact tie-break

1. exact qualified match
2. include relation
3. namespace/parent match
4. directory proximity
5. declaration-definition relation
6. POSIX path lexical order
7. start line
8. chunk ID

### 9.2 Search stage: BM25

- Implementation: `BM25Okapi`
- Library/version: `TBD_IMPLEMENTATION`
- Parameters: `k1=1.2`, `b=0.75`

1 symbol chunkを1 BM25 documentとして扱う。

Index field:

- canonical qualified symbol
- short symbol
- owner/parent
- signature
- raw code
- comments
- path token
- symbol kind

Tokenization:

- original identifierを保持
- PascalCase、camelCase、snake_caseを補助tokenへ分割
- ASCII lowercase auxiliary tokenを追加
- pathはcase-preserved、separatorは`/`
- lowercase tokenだけでsymbol identityを確定しない

BM25は主にcall site、usage、return value consumption、API call orderおよび補助的relationを取得する。

AST classification priority:

1. `direct_call_site`
2. `symbol_reference`
3. `explicit_comment_reference`
4. `token_cooccurrence`

BM25 scoreは同一tierおよび同一kind内だけで比較する。

### 9.3 Expand stage: direct dependency 1-hop

hop 0はexact retrieval resultとする。hop 1ではhop 0のinterface/definitionが直接参照するrepository-local symbolを追加する。

Allowed relation:

- `parameter_type`
- `return_type`
- `field_type`
- `base_type`
- `nested_type`
- `template_argument_type`
- `alias_target`
- `enum_type`
- `wrapper_direct_call`

通常のfunction bodyに含まれるすべてのcallは展開しない。単純wrapperが単一のdirect callまたはdirect returned callだけを持つ場合に限り、`wrapper_direct_call`として展開できる。hop 2以上を禁止する。

### 9.4 Refine stage

filterをrankingより先に適用する。

1. forbidden path filter
2. target source overlap filter
3. previous LLM output filter
4. experiment artifact filter
5. generated content filter
6. test content check
7. content/path overlap dedup
8. ranking
9. quota
10. context budget

#### Ranking tiers

- Tier 0: exact definition / alias / enum / full interface
- Tier 1: direct dependency interface
- Tier 2: AST-confirmed usage / call site
- Tier 3: auxiliary BM25

異種検索のraw scoreを単純加算しない。

同一tier内の順序：qualified match、parent/namespace match、include relation、direct relation、original-case match、BM25 score、directory proximity、path、start line、chunk ID。

#### Deduplication

- same chunk ID
- same content SHA-256
- equivalent overlapping range
- redundant declaration/definition

異なるinterface情報を持つdeclarationとdefinitionは両方保持できる。保持理由をartifactへ記録する。

---

## 10. Context count and token budget

- Retrieval top-k: `TBD_AFTER_PILOT`
- Total context token budget: `TBD_AFTER_PILOT`
- Category quota: `TBD_AFTER_PILOT`
- Token counter/version: `TBD_AFTER_PILOT`
- Per-target override: prohibited
- One common format/budget across all formal 17 targets

`retrieval_top_k`とLLM生成側の`generation_top_k`を明確に区別する。

### 10.1 Pilot comparison order

1. context formatを決定する
2. format固定後にbudgetを決定する

### 10.2 Context format candidates

- A: file-structure format
- B: role/category format
- C: combined format

### 10.3 Format selection priority

1. structural reference informationの保持
2. false addition/conflict/noiseの少なさ
3. pilot round-trip test
4. input tokenの少なさと形式の単純さ

### 10.4 Budget selection priority

1. 必要なexact definition/direct dependencyをすべて含めたpilot数
2. structural coverage
3. design document preservation
4. pilot test pass
5. 同点なら小さいtoken/chunk数

必要十分な最小budgetを選ぶ。

---

## 11. Prompt condition

非RAGの設計文書生成promptと出力要件を維持し、retrieval sectionだけを追加する。

```text
1. same non-RAG design instruction
2. clearly delimited retrieved repository context
3. target source
4. same output constraints
```

retrieval sectionはtarget sourceの直前へ置く。

情報が衝突する場合の優先順位：

1. target source
2. exact definition/interface
3. usage example
4. auxiliary BM25

設計文書内で「RAGによると」「検索結果によると」などのmeta表現を使用しない。コード再生成promptへretrieval contextを渡さない。

---

## 12. Retrieval artifacts

### 12.1 Shared index

```text
rag/index/<repository>/<commit>/
  corpus_manifest.json
  chunks.jsonl
  symbol_index.jsonl
  bm25_index_metadata.json
  index_validation.json
```

### 12.2 Per-target

```text
retrieval/
  query.json
  corpus_manifest.json
  candidates.jsonl
  selected_chunks.jsonl
  context.txt
  retrieval_manifest.json
  gold_relevance.json
```

必須記録：exact `context.txt`、context SHA-256、query SHA-256、repository commit、source SHA-256、retrieval config SHA-256、selected chunk IDs/order、各version、token count、leakage audit、determinism result。

### 12.3 Canonical serialization

- UTF-8
- LF
- repository-relative POSIX path
- fixed JSON key/array order
- canonical JSON
- final newline 1つ
- timestamps excluded from content hash
- parallel outputをdeterministicにpost-sort

---

## 13. Leakage prevention

Forbidden categories:

- test/tests/testing
- benchmark
- build
- generated
- reports/logs
- experiment artifact
- previous LLM output
- README/docs
- vendor/third-party/external

Exclusion reasons:

- `forbidden_path`
- `target_source_overlap`
- `test_content_detected`
- `previous_llm_output`
- `experiment_artifact`
- `generated_content`
- `third_party`

test detectionはpath、symbol kind、AST structureおよびtest macro/expected outputを組み合わせる。`assert`だけで除外しない。最終`context.txt`をauditし、不明な候補またはleakageがある場合は自動置換せず停止する。

---

## 14. Determinism

同一commit、config、environmentでindex buildからcontext生成までを独立に2回行い、query SHA-256、corpus/index/chunk hash、selected IDs/order、context SHA-256を比較する。一致後のみ`deterministic=true`とする。

formal入力を固定するため、正式生成前に`context.txt`を事前生成・凍結し、そのSHA-256をtarget config/manifestへ記録する。formal generationは凍結済みcontextだけを読む。

LLM出力自体の完全一致は保証しないため、各target一回生成、retryなしで評価する。

---

## 15. Automatically derived structural reference set

17対象すべてについて、固定repositoryとtarget source範囲から評価用の構造的参照集合を自動導出する。

> 固定リポジトリと対象ソースから自動導出した構造的参照集合

これは完全なhuman goldまたは完全なC++ semantic ground truthではない。

抽出対象：required symbol、definition、alias/enum/class/function kind、parameter/return/base/direct dependency、path/range、`resolved`、`ambiguous`、`unresolved`。

retrieved candidate、rank、selected chunk、BM25 score、generated design/code、RAG PASS/FAILを参照集合作成に使わない。target ASTとrepository exact definition mapからranking前に導出する。

利用指標：structural symbol coverage、direct dependency coverage、structural consistency。

---

## 16. Pilot

### 16.1 Pilot target selection

- 3～5 targets
- formal 17対象外
- 原則として各repositoryから最低1 target
- production C++
- fixed commits
- existing tests
- original build/test PASS
- source replacement/restoration可能
- formal target source rangeと重複しない
- formal `module_files`対象のファイル全体を除外

候補listをpilot結果を見る前に自動抽出する。alias/enum、cross-file relation、class/inheritance、call site、multiple dependencies、template/namespace、formalと近い規模を重視する。選定後は差し替えない。

### 16.2 Pilot rules

- one generation per condition
- no retry
- no automatic repair
- no manual patch
- compared variable以外を同一にする
- pilot artifactsをformal resultへ再利用しない

修正可能なのはimplementation/path/serialization/deterministic ordering/manifest schema bugだけである。formal 17の結果を見たtuning、target-specific query、retry/repair policy変更は禁止する。

---

## 17. Formal model and execution fairness

各RAG target configは対応non-RAG target configから複製する。

変更可能：condition ID、RAG run ID、output directory、design prompt retrieval section、retrieval config/version、context path/hash。

同一に保つ：repository commit、target source、tests、granularity、filters、Docker environment、model ID、temperature、seed、generation top-k、top-p、repeat penalty、`num_ctx`、`num_predict`、timeout、normalization、code-regeneration prompt、configure/build/direct/full test、generation count、retry/repair policy。

対応non-RAG targetごとの値を継承し、全targetを一律値へ変更しない。

- Design generation count: 1
- Code regeneration count: 1
- Retry: false
- Automatic repair: false
- Manual generated-code patch: false

contextが`num_ctx`へ収まらない場合、targetごとの`num_ctx`を変えず、pilotで共通context budgetを小さくする。

---

## 18. Source restoration

既存non-RAG harnessと同じbackup/restore規則を使用する。

必須確認：original source hash、backup hash、replacement hash、restored hash、tracked working tree status、submodule status。

source restorationに失敗した場合、formal batch全体を停止する。

---

## 19. Evaluation

### 19.1 Primary

- RAG full-pipeline PASS count/rate
- paired transition table: `FAIL -> PASS`, `PASS -> FAIL`, `PASS -> PASS`, `FAIL -> FAIL`
- exact McNemar test on discordant pairs

N=17のためp-valueだけで結論を出さず、target-level evidenceとstage diagnosisを併記する。

### 19.2 Secondary

- design/code generation completion
- configure/build/direct/full pass
- structural symbol coverage
- direct dependency coverage
- context length/token count
- leakage count
- exact definition retrieval
- PASS -> FAILのnoise/context competition

全17対象のhuman gold、Precision@k、Recall@k、MRRは必須としない。代表subsetの人手評価もformal tuningへ使用しない。

### 19.3 Seven-stage diagnosis

1. `Corpus`
2. `Candidate`
3. `Selection`
4. `Context`
5. `Design`
6. `Code`
7. `Execution`

最初に必要情報を失ったstageまたは最初に失敗したstageをprimary causeとする。

---

## 20. Stop and failure rules

### 20.1 Target FAILとして次へ進む

- design generation failure
- code regeneration failure
- configure/build/direct/full failure
- target timeout

同じrun IDでrerunしない。

### 20.2 Formal batch全体を停止

- repository commit mismatch
- source hash mismatch
- leakage
- target source overlap
- nondeterministic retrieval/context
- budget violation
- frozen context hash mismatch
- code regenerationへのcontext混入
- non-RAG environment/config mismatch
- source restoration failure

artifactを保存して停止理由を記録し、同じrun IDで黙って再開しない。

---

## 21. Directory and naming

```text
docs/rag_experiment_protocol.md
configs/rag/retrieval_v1.json
configs/rag/pilot/
configs/rag/targets/
scripts/rag/
rag/index/<repository>/<commit>/
experiments/rag/pilot/format/
experiments/rag/pilot/budget/
experiments/rag/<target-id>-roundtrip/
reports/rag/pilot/
reports/rag/retrieval-audit/
reports/rag/formal/
reports/rag/analysis/
manifests/rag_targets.csv
manifests/rag_runs.csv
```

Run IDs:

- `rag-v1-pilot-format-<pilot-id>-<format>`
- `rag-v1-pilot-budget-<pilot-id>-<budget>`
- `rag-v1-formal-<target-id>`
- replacementは`-run02`等の新suffix

non-RAG artifactsを上書きしない。

---

## 22. Implementation environment

RAG corpus、parsing、retrieval、context生成は既存non-RAG generation/build環境から分離したローカルPythonで実装する。

- OS: Windows
- Python: CPython `TBD_IMPLEMENTATION`
- Environment: `.venv-rag/`
- Direct dependencies: `requirements/rag.in`
- Locked dependencies: `requirements/rag.lock.txt`
- Environment manifest: `rag/environment/rag_environment_manifest.json`

`.venv-rag/`はcommitしない。version mismatch時は停止する。LLM generationとbuild/testには対応non-RAGと同じOllama/Docker環境を使用する。

---

## 23. Index schema and validation

Required artifacts:

- `corpus_manifest.json`
- `chunks.jsonl`
- `symbol_index.jsonl`
- `index_validation.json`

Range convention:

- line: 1-based inclusive
- column: 0-based
- byte: 0-based half-open `[start_byte, end_byte)`
- path: repository-relative POSIX

CRLF入力をrange計算前にLFへ変換しない。artifact serializationだけLFへ統一する。

Canonical order:

- files: path
- chunks: path, start_byte, end_byte, kind, chunk_id
- symbols: canonical_name, index_role, path, start_line, chunk_id

次でvalidation failureとする：commit mismatch、source hash change、duplicate ID、invalid range、empty chunk、content slice mismatch、unrecorded parser error、nondeterministic order、independent rebuild hash mismatch。

---

## 24. Fixed fixture validation

実repository index前に、通常関数、namespace、class/struct、declaration/definition、constructor/destructor/operator、overload、`const`/`noexcept`、alias/typedef、enum、nested class、inheritance、template、macro fallback、Doxygen、oversized unit、parse errorを固定fixtureで検証する。

```text
tests/rag/fixtures/
tests/rag/expected/
tests/rag/test_indexing.py
```

合格条件：全fixture PASS、期待metadata一致、byte slice一致、duplicate ID 0、unrecorded parser error 0、独立2回のartifact hash一致。

---

## 25. Work order

1. protocol v0.9 commit
2. environment/config/index implementation
3. formal外pilot targetを3～5件選定
4. context format A/B/C pilot
5. context budget pilot
6. protocol v1.0 commit
7. 17 structural reference sets生成
8. 17 retrieval-only dry runを独立2回
9. leakage/hash/determinism audit
10. frozen contextを用いたformal preparation
11. formal 17 one-shot run
12. paired analysis

formal 17のretrieval/generated output/PASS/FAILを見てretrieval settingを調整しない。

---

## 26. Commit plan

1. `docs: define repository-context RAG protocol`
2. `feat: add deterministic RAG index builder`
3. `test: validate C++ symbol chunking fixtures`
4. `data: add deterministic ini-cpp RAG index`
5. `data: add deterministic RISCV-Simulator RAG index`
6. `data: add deterministic Echo-Web-Server RAG index`
7. `feat(rag): add deterministic query and retrieval pipeline`
8. `experiment: record RAG pilot results`
9. `docs: freeze repository-context RAG protocol v1.0`
10. `audit: record formal RAG retrieval-only audit`
11. `config: prepare RAG formal experiments`
12. `config: enable RAG formal experiment batch`
13. `experiment: record RAG round-trip results`
14. `analysis: compare paired non-RAG and RAG results`

`git add .`を使用せず、対象pathだけをstageする。

---

## 27. Approval and deviation control

### 27.1 Protocol v0.9 approval

- Pre-pilot protocol approved: 2026-08-04
- Baseline non-RAG results frozen: yes
- RAG formal run started: no

### 27.2 Protocol v1.0 approval

- Pilot completed: no
- Context format frozen: no
- Retrieval top-k frozen: no
- Context budget frozen: no
- Formal execution approved: no

### 27.3 Deviations

protocolからの逸脱は、理由、影響範囲、変更前後の値およびrevisionを記録する。formal結果確認後に、同じcondition IDまたはrun IDの設定を変更しない。
