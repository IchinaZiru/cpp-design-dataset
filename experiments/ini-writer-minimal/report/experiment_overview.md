# ラウンドトリップ実験 総合レポート

> このファイルは実験成果物から自動生成した閲覧用レポートである．
> 元データは変更せず，入力・出力・評価結果を一つに集約する．

## 1. 一目で分かる結果

| 項目 | 値 |
| --- | --- |
| 実験ID | `ini-writer-minimal` |
| 実行ID | `qwen25coder32b-run-001` |
| 対象 | `INIWriter::write` |
| 粒度 | `function_body` |
| モデル | `qwen2.5-coder:32b` |
| 総合判定 | **PASS** |
| 評価工程 | 9/9 PASS |
| 直接テスト | 3/3 PASS |
| 全GoogleTest | 27/27 PASS |
| 生成処理時間 | 1分40.83秒 |
| 評価処理時間 | 24.99秒 |

## 2. 実験のデータフロー

| 段階 | 主な入力 | 主な出力 | 結果 |
| --- | --- | --- | --- |
| 元コード → 設計文書 | `design_input.cpp`＋設計書生成プロンプト | `design_document.md` | PASS |
| 設計文書 → コード | `design_document.md`＋`fixed_scaffold.cpp`＋`dependency_context.txt` | `regenerated_write_body.cpp` | PASS |
| 再生成コード → 評価 | 再生成コード＋固定commit＋Docker環境＋既存テスト | 評価JSON・要約・置換差分 | PASS |

## 3. 対象と入力条件

| 項目 | 値 |
| --- | --- |
| Repository | SSARCandy/ini-cpp |
| Repository commit | `e1779b837274de8be2051bef579c3b9ec3483522` |
| GoogleTest commit | `391ce627def20c1e8a54d10b12949b15086473dd` |
| 対象クラス | INIWriter |
| 対象関数 | INIWriter::write |
| 置換粒度 | function_body |
| ソース | `ini/ini.h` |
| 設計生成時に元関数本体を含む | はい |
| コード再生成時に元関数本体を除外 | はい |
| 置換範囲 | INIWriter::write function body only |
| 依存メソッド | Get, Keys, Sections |

## 4. LLM実行条件

| 項目 | 値 |
| --- | --- |
| Provider | ollama-local |
| Model | `qwen2.5-coder:32b` |
| Local model ID | `b92d6a0bd47e` |
| Architecture | qwen2 |
| Parameters | 32.8B |
| Quantization | Q4_K_M |
| Ollama | 0.32.0 |
| temperature | 0 |
| seed | 42 |
| num_ctx | 8192 |
| num_predict | 2048 |
| top_k | 40 |
| top_p | 0.900 |
| repeat_penalty | 1.100 |
| 再試行 | いいえ |
| 自動修正 | いいえ |

## 5. 入力ファイル

| 役割 | パス | 行数 | サイズ | SHA-256 |
| --- | --- | --- | --- | --- |
| 設計書生成へ与えた元コード | `experiments/ini-writer-minimal/input/design_input.cpp` | 32 | 1213 | `303d8a22022c6dc64e933f767eed5c16e63d089e93cd2aafb8133c75f97ebd30` |
| コード再生成時の固定スキャフォールド | `experiments/ini-writer-minimal/input/fixed_scaffold.cpp` | 20 | 692 | `1a70671c3bed03469b5b07f8a8bfae4bd7aa94c2d64156f298acaed39fe89f93` |
| コード再生成時の依存関係情報 | `experiments/ini-writer-minimal/input/dependency_context.txt` | 28 | 587 | `5f63425feaeb333918680b80e67e90fa2b7e6ae9519214a2732e84b9c4d0ae3c` |
| 設計書生成プロンプト | `experiments/ini-writer-minimal/prompts/design_generation_prompt.md` | 36 | 1182 | `4029be12e90e128c2d8f6244a59fb4000967fa6bccc56be6a0efe74d95ad6368` |
| コード再生成プロンプト | `experiments/ini-writer-minimal/prompts/code_regeneration_prompt.md` | 31 | 1166 | `10a38881a02c43f1562ef7e25cdc738088817d41d2613e5e31deaabd76f31ed7` |
| モデル・生成パラメータ | `experiments/ini-writer-minimal/configs/run_config.json` | 48 | 1568 | `2f9935bf06304cbd8ec32da82f2dc3e223f9a03adec6337346edcb9f07f88cd4` |

## 6. 生成物・評価成果物

| 役割 | パス | 行数 | サイズ | SHA-256 |
| --- | --- | --- | --- | --- |
| LLMが生成した設計文書 | `experiments/ini-writer-minimal/generated/design_document.md` | 51 | 2991 | `e25502d694e3a6ec2d02e349d2322e038744225aa0689eb65c290a1296cddcd2` |
| 設計文書から再生成した関数本体 | `experiments/ini-writer-minimal/generated/regenerated_write_body.cpp` | 18 | 495 | `0cef6fb0215bc05f3c06f7ba651a093ad347cd2aa2ef1b3983afefc7e2393322` |
| 設計書生成APIリクエスト | `experiments/ini-writer-minimal/raw_output/design_generation_request.json` | 15 | 2797 | `4cde576b31ceab0280b0305af29122d6572f500611e0601e8b2a68c31a050e3d` |
| 設計書生成API応答 | `experiments/ini-writer-minimal/raw_output/design_generation_response.json` | 1388 | 17528 | `e19062a53ac7142f75daf083905ce11edbf3709e8197e815c7bc820d8147e6b4` |
| コード再生成APIリクエスト | `experiments/ini-writer-minimal/raw_output/code_regeneration_request.json` | 15 | 5841 | `7470cb4c1b56f61a3d8def834360d89d6118cb0a9bbfd94d5ae611483da65dfd` |
| コード再生成API応答 | `experiments/ini-writer-minimal/raw_output/code_regeneration_response.json` | 1494 | 16078 | `7a8cec42f6e9bce7e9c24943e193aaacccf699f30324586d39c788681e3d6c6e` |
| 評価結果の機械可読マニフェスト | `experiments/ini-writer-minimal/evaluation/evaluation_manifest.json` | 33 | 1560 | `5f69ce629dd723285eb77c96c759b59cc193712635cdabf22509c45501e5e1b4` |
| 評価結果の要約 | `experiments/ini-writer-minimal/evaluation/evaluation_summary.md` | 40 | 1570 | `ed5d73a6e37129f7b065d5824938e0b535b02cb35458b79f6cfe6128d1d5d6b0` |
| 一時置換した差分 | `experiments/ini-writer-minimal/evaluation/replacement_diff.patch` | 34 | 1361 | `d85fa89bbf1d54dabb03324305fb4139637bd71981935ebf4c73f7aeb2e77caa` |

## 7. 各工程の評価

| 工程 | 結果 | 詳細 | 時間 |
| --- | --- | --- | --- |
| 設計書生成 | PASS | 入力650 tokens，出力725 tokens | 1分16.74秒 |
| コード再生成 | PASS | 入力1359 tokens，出力121 tokens | 24.09秒 |
| clean configure | PASS | exit code 0 | 4.62秒 |
| full build | PASS | exit code 0 | 18.42秒 |
| 直接テスト | PASS | 3/3 passed | 0.58秒 |
| 全GoogleTest | PASS | 27/27 passed | 0.66秒 |
| CTest | PASS | exit code 0 | 0.70秒 |
| 元コード復元 | PASS | SHA-256 30dfffabdda27182ddf2351193c9224b533b42349e9186a4cecf40f781b0c7f1 | N/A |
| submodule clean | PASS | 追跡対象の差分・変更がないことを確認 | N/A |

## 8. 元コードと再生成コードのテキスト比較

| 項目 | 値 |
| --- | --- |
| 完全一致 | いいえ |
| 空白を除いた一致 | いいえ |
| 文字列類似度 | 0.0386 |
| 元コード行数 | 13 |
| 再生成コード行数 | 18 |
| 元コードSHA-256 | `2c403d3d34cef37f0567b92be924d2278f2f396c43524ac3b63bbcc3271c9358` |
| 再生成コードSHA-256 | `0cef6fb0215bc05f3c06f7ba651a093ad347cd2aa2ef1b3983afefc7e2393322` |

この比較は文字列上の差を示すだけであり，意味的等価性の評価ではない．

## 9. 評価の解釈

再生成コードは，固定環境においてconfigure，build，直接テスト，全GoogleTest，CTestをすべて通過した．

テスト通過は既存テストスイートが観測する範囲での正当性を示すものであり，未検証機能を含む完全な意味的等価性を保証しない．

## 10. 内容確認

<details>
<summary>設計書生成へ与えた元コード（experiments/ini-writer-minimal/input/design_input.cpp）</summary>

```cpp
/**
 * @brief Write the contents of an INIReader to an ini file.
 */
class INIWriter {
   public:
    INIWriter() = default;
    /**
     * @brief Write the contents of an INI file to a new file
     * @param filepath The path of the output file
     * @param reader The INIReader object to write to the file
     * @param overwrite Whether to just overwrite an existing file
     * @throws std::runtime_error if the output file already exists or cannot
     * be opened
     */
    inline static void write(const std::string& filepath,
                             const INIReader& reader,
                             const bool overwrite = false) {
        if (!overwrite && std::ifstream{filepath}) {
            throw std::runtime_error("file: " + filepath + " already exists.");
        }
        std::ofstream out{filepath};
        if (!out.is_open()) {
            throw std::runtime_error("cannot open output file: " + filepath);
        }
        for (const auto& section : reader.Sections()) {
            out << "[" << section << "]\n";
            for (const auto& key : reader.Keys(section)) {
                out << key << "=" << reader.Get(section, key) << "\n";
            }
        }
    }
};
```

</details>

<details>
<summary>生成された設計文書（experiments/ini-writer-minimal/generated/design_document.md）</summary>

```markdown
## 1. クラスの責務
INIファイルにデータを書き込むための機能を提供する。

## 2. 対象関数の責務
与えられたINIReaderオブジェクトの内容を指定されたファイルパスにINI形式で書き込む。

## 3. 入力
- filepath: 出力ファイルのパス（文字列）
- reader: ファイルに出力するINIデータを持つINIReaderオブジェクト
- overwrite: 既存ファイルを上書きするかどうかを示す真偽値（デフォルトはfalse）

## 4. 出力
関数自体が直接出力を返さない。代わりに、指定されたファイルパスにINIデータを書き込む。

## 5. 使用する内部状態
- ソースコードからは判断できない

## 6. 呼び出す依存関数
- std::ifstreamのコンストラクタとis_openメソッド: ファイルが既に存在するか確認するために使用。
- std::ofstreamのコンストラクタとis_openメソッド: 出力ファイルを開くために使用。
- INIReader::Sectionsメソッド: セクション名の一覧を取得するために使用。
- INIReader::Keysメソッド: 指定されたセクション内のキーの一覧を取得するために使用。
- INIReader::Getメソッド: 指定されたセクションとキーに対応する値を取得するために使用。

## 7. 事前条件
- filepathが有効なファイルパスであること。
- readerが適切に初期化され、データを持っていること。

## 8. 処理手順
1. overwriteフラグがfalseで、指定されたファイルパスのファイルが既に存在する場合、例外をスローする。
2. 出力ファイルを開く。開けない場合は例外をスローする。
3. INIReaderオブジェクトからセクション名の一覧を取得し、各セクションに対して以下の処理を行う：
   - セクション名を出力ファイルに書き込む。
   - そのセクション内のキーの一覧を取得し、各キーに対して以下の処理を行う：
     - キーと値を出力ファイルに書き込む。

## 9. 分岐条件
- overwriteフラグがfalseでかつ指定されたファイルパスのファイルが既存の場合。
- 出力ファイルを開くことができない場合。

## 10. 反復処理
- INIReaderオブジェクトから取得したセクション名に対して繰り返し処理を行う。
- 各セクション内のキーに対して繰り返し処理を行う。

## 11. 例外・失敗条件
- 指定されたファイルパスのファイルが既に存在する場合、std::runtime_errorをスローする。
- 出力ファイルを開くことができない場合、std::runtime_errorをスローする。

## 12. 保持すべき振る舞い
- overwriteフラグがfalseの場合、既存のファイルは上書きされないこと。
- INIReaderオブジェクトから取得したデータが正しい形式でファイルに出力されること。
```

</details>

<details>
<summary>再生成された関数本体（experiments/ini-writer-minimal/generated/regenerated_write_body.cpp）</summary>

```cpp
if (!overwrite) {
    std::ifstream file(filepath);
    if (file.is_open()) {
        throw std::runtime_error("File already exists.");
    }
}

std::ofstream outFile(filepath);
if (!outFile.is_open()) {
    throw std::runtime_error("Cannot open output file.");
}

for (const auto& section : reader.Sections()) {
    outFile << "[" << section << "]" << std::endl;
    for (const auto& key : reader.Keys(section)) {
        outFile << key << "=" << reader.Get(section, key) << std::endl;
    }
}
```

</details>

<details>
<summary>一時置換差分（experiments/ini-writer-minimal/evaluation/replacement_diff.patch）</summary>

```diff
diff --git a/ini/ini.h b/ini/ini.h
index d119bbc..7e9fcbd 100644
--- a/ini/ini.h
+++ b/ini/ini.h
@@ -544,17 +544,22 @@ class INIWriter {
     inline static void write(const std::string& filepath,
                              const INIReader& reader,
                              const bool overwrite = false) {
-        if (!overwrite && std::ifstream{filepath}) {
-            throw std::runtime_error("file: " + filepath + " already exists.");
+        if (!overwrite) {
+            std::ifstream file(filepath);
+            if (file.is_open()) {
+                throw std::runtime_error("File already exists.");
+            }
         }
-        std::ofstream out{filepath};
-        if (!out.is_open()) {
-            throw std::runtime_error("cannot open output file: " + filepath);
+
+        std::ofstream outFile(filepath);
+        if (!outFile.is_open()) {
+            throw std::runtime_error("Cannot open output file.");
         }
+
         for (const auto& section : reader.Sections()) {
-            out << "[" << section << "]\n";
+            outFile << "[" << section << "]" << std::endl;
             for (const auto& key : reader.Keys(section)) {
-                out << key << "=" << reader.Get(section, key) << "\n";
+                outFile << key << "=" << reader.Get(section, key) << std::endl;
             }
         }
     }
```

</details>

## 11. 再現性のための主要ファイル

- 実験条件：`configs/run_config.json`
- 設計生成プロンプト：`prompts/design_generation_prompt.md`
- コード再生成プロンプト：`prompts/code_regeneration_prompt.md`
- 設計生成API記録：`raw_output/design_generation_*.json`
- コード再生成API記録：`raw_output/code_regeneration_*.json`
- 評価マニフェスト：`evaluation/evaluation_manifest.json`
- 詳細な標準出力・標準エラー：`logs/ini-writer-minimal/qwen25coder32b-run-001/`
