# SSARCandy/ini-cpp データセット適格性評価

## 結論

`INIReader`と`INIWriter`はいずれも「採用」と判定した。固定環境でbaselineが3回安定し、class定義spanだけを変更してpublic signatureを維持でき、各対象の主要責務を壊す3件すべてを対応する直接testが検出した。

この判定は既存testが観測する範囲で再生成codeを評価できることを示し、未検証範囲を含む完全な意味的等価性を保証しない。

## 固定環境と履歴分離

- Repository commit: `e1779b837274de8be2051bef579c3b9ec3483522`
- GoogleTest submodule: `391ce627def20c1e8a54d10b12949b15086473dd`
- Docker: `cpp-roundtrip-env:ini-cpp-v2`
- Image ID: `sha256:68500729fc7fc0ba42377dc0737dea8bc2930d2be6e0d20b307490713c97c802`
- Ubuntu 22.04.5 LTS、GCC 11.4.0、CMake 3.22.1、Git 2.34.1、libboost-dev 1.74.0.3ubuntu7
- host project全体を`/workspace`へmountし、repositoryは`/workspace/repos/ini-cpp`、成果物は`/workspace/logs`と`/workspace/metadata`へ保存した。
- `environment_setup/v1_missing_boost/`と`wrong_working_directory/`は参照のみで、今回の集計・判定へ含めていない。

## 実装構造と置換境界

- `INIReader`: `ini/ini.h`のclass span（lines 113–528）。Reader外の`detail` helperは依存として残す。
- `INIWriter`: 同headerのclass span（lines 533–561）。Readerの公開APIだけを利用する。
- 同一headerであること自体は除外理由にせず、変更diffが対象span内に限定され、public signatureを維持し、full build可能で、sibling定義を変更せず、復元後に両filterが成功することを確認した。
- Readerのsection mutationではWriterのround-trip系2 testも失敗したが、Reader公開behaviorへの依存によるcross-class観測であり、Writer定義の変更や置換境界逸脱ではない。

## 静的指標とtest対応

| target | scope | total/blank/comment/code | methods | declarations/discovered | filter |
|---|---|---:|---:|---:|---|
| INIReader | class definition span lines 113-528 | 416/27/122/267 | 45 | 24/24 | `INIReader.*` (24) |
| INIWriter | class definition span lines 533-561 | 29/0/8/21 | 4 | 3/3 | `INIWriter.*` (3) |

class spanはcomment/stringを認識するbrace scannerで抽出した。行分類とmethod抽出はEcho-Web-Server評価と同じ規則を再利用した。test宣言名とruntime discovery名は両suiteで一致した。

## ベースライン

- clean configure / full build: 成功
- CTest: `ctest --test-dir build/test --output-on-failure`で1/1成功 × 3回
- 全GoogleTest: `/workspace/repos/ini-cpp/build/test`から27/27成功 × 3回
- `INIReader.*`: 24/24成功 × 3回
- `INIWriter.*`: 3/3成功 × 3回
- 全反復でtest名、順序、件数、成否が一致した。0件filter実行はなかった。

## ミューテーション結果

| mutation | target | 壊した責務 | classification | scope | 主な失敗test |
|---|---|---|---|---|---|
| `reader_01_section_assignment` | INIReader | replace parsed section assignment with an empty section name | test_killed | direct_test_killed | INIReader.comments, INIReader.crlf_line_endings, INIReader.from_file_pointer, INIReader.get_keys, INIReader.get_sections, INIReader.get_single_value, INIReader.get_single_value_with_default, INIReader.get_vector, INIReader.get_vector_with_default, INIReader.insert_and_update_errors, INIReader.long_lines_and_section_names, INIReader.numeric_conversions, INIReader.read_big_file, INIReader.section_quirks, INIReader.utf8_bom, INIReader.whitespace_and_empty_values |
| `reader_02_bool_fixed_false` | INIReader | return false for every boolean token and skip invalid-token validation | test_killed | direct_test_killed | INIReader.bool_conversions, INIReader.exception, INIReader.get_single_value, INIReader.get_single_value_with_default |
| `reader_03_update_scalar_noop` | INIReader | make scalar UpdateEntry a no-op | test_killed | direct_test_killed | INIReader.UpdateEntry, INIReader.insert_and_update_errors |
| `writer_01_write_noop` | INIWriter | make write a no-op so no output file is generated | test_killed | direct_test_killed | INIWriter.exception, INIWriter.overwrite, INIWriter.write |
| `writer_02_overwrite_guard_off` | INIWriter | disable the overwrite=false existing-file guard | test_killed | direct_test_killed | INIWriter.exception, INIWriter.overwrite |
| `writer_03_omit_values` | INIWriter | emit keys with empty values instead of serialized values | test_killed | direct_test_killed | INIWriter.overwrite, INIWriter.write |

集計: `test_killed=6`、`direct_test_killed=6`、`indirect_test_killed=0`、`compile_killed=0`、`runtime_killed=0`、`survived=0`、`execution_error=0`。
全6件で元byte列、SHA-256、空diff、再build、復元後の対象・sibling filter成功を確認した。

## 観測範囲と未検証範囲

| target | 観測したbehavior | 未検証behavior |
|---|---|---|
| INIReader | section/key列挙、scalar/vector取得、default、file/FILE*解析、duplicate/error、insert/update、BOM、CRLF、comment、空白/空値、section境界、長行、数値・bool変換 | 同時access、allocation失敗、FILE*読取error、全locale/文字encoding、極端な巨大入力、全charconv境界 |
| INIWriter | INIReader内容のround-trip出力、既存file拒否、overwrite=trueによる置換 | permission/disk-full/partial-write/close error、atomic replacement、Unicode path、同時writer、全特殊文字escaping |

## 判定

- **INIReader — 採用**: 解析、bool変換、値更新の3責務を直接testが検出した。
- **INIWriter — 採用**: 出力実行、overwrite保護、value serializationの3責務を直接testが検出した。

## 最終検証

- 通常実装のfull build、CTest、全27件、両filter: すべて成功
- Parent HEAD: `e1779b837274de8be2051bef579c3b9ec3483522`
- Submodule HEAD: `391ce627def20c1e8a54d10b12949b15086473dd`
- Parent diff/status: 空
- Submodule diff/status: 空
- 非ignore未追跡: なし
- `build/`は存在し、`.gitignore:3:build/`でignoreされている。

## 人間が最終判断すべき事項

- Reader class spanが比較的大きく、LLM設計書・再生成のtoken予算に適するか。
- Reader外の`detail` helperを固定依存として残すclass単位のdataset設計が研究目的に合うか。
- file permission、disk-full、concurrency等の未検証error pathを評価範囲へ追加するか。
