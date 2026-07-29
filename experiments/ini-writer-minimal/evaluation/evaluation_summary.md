# INIWriter最小実験 評価結果

## 実験条件

- 実験ID: `ini-writer-minimal`
- 実行ID: `qwen25coder32b-run-001`
- 対象: `INIWriter::write`
- Repository commit: `e1779b837274de8be2051bef579c3b9ec3483522`
- GoogleTest commit: `391ce627def20c1e8a54d10b12949b15086473dd`
- Docker image: `cpp-roundtrip-env:ini-cpp-v2`
- Docker image ID: `sha256:68500729fc7fc0ba42377dc0737dea8bc2930d2be6e0d20b307490713c97c802`
- 生成コードSHA-256: `0cef6fb0215bc05f3c06f7ba651a093ad347cd2aa2ef1b3983afefc7e2393322`
- 置換後`ini/ini.h` SHA-256: `e56861b7e6cb3c1cab648367eeac5195de01aed8e104c26ae35ef09cd33b8c7d`

## 評価結果

| 項目 | 結果 | 詳細 |
|---|---|---|
| clean configure | PASS | exit code `0` |
| full build | PASS | exit code `0` |
| `INIWriter.*` | PASS | 3/3 passed |
| 全GoogleTest | PASS | 27/27 passed |
| CTest | PASS | exit code `0` |
| 元コード復元 | PASS | restored SHA-256 `30dfffabdda27182ddf2351193c9224b533b42349e9186a4cecf40f781b0c7f1` |
| submodule clean | PASS | tracked diff/statusの有無を確認 |

## 総合判定

**PASS**

PASSは，固定環境においてビルド，`INIWriter.*` 3件，全GoogleTest 27件，
CTestおよび元コード復元がすべて成功したことを示す．

この判定は既存テストスイートが観測する範囲での正当性を示すものであり，
未検証機能を含む完全な意味的等価性を保証しない．

## 生ログ

詳細な標準出力・標準エラーはGit管理対象外の
`logs/ini-writer-minimal/qwen25coder32b-run-001/`に保存した．
