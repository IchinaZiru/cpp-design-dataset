# 設計文書: `INIWriter::write` 関数

## 概要
この設計文書は、`ini/ini.h` ファイルに含まれる `INIWriter::write` 関数についての詳細な仕様を記載します。対象範囲は `INIWriter::write` 関数のみであり、他の関数やクラスとの関係は必要に応じて説明します。

## 責務
- `INIReader` オブジェクトの内容を指定されたファイルパスに INI 形式で書き出す。
- 既存ファイルの上書きオプションを提供する。
- ファイル操作中に発生したエラーを適切な例外として通知する。

## 公開インターフェース
```cpp
inline static void write(const std::string& filepath, const INIReader& reader, const bool overwrite = false);
```

## 入力
- `filepath`: 書き出すファイルのパス（`std::string`）
- `reader`: ファイルに書き出す内容を保持する `INIReader` オブジェクト
- `overwrite`: 既存ファイルを上書きするかどうかを示すフラグ（デフォルトは `false`）

## 出力
- 成功時には何も返さない（戻り値なし）
- 失敗時には例外をスローする

## 状態
- ファイルの存在状況（上書きオプションに応じて変化）
- `INIReader` オブジェクトの内容（読み取り専用）

## 処理手順
1. **ファイルパスのチェック**:
   - `overwrite` が `false` の場合、指定されたファイルパスに既存ファイルがないことを確認する。
2. **ファイルオープン**:
   - 指定されたファイルパスで出力ストリームを開く。
3. **セクションとキーの書き出し**:
   - `INIReader::Sections()` を呼び出してすべてのセクションを取得し、各セクションに対して以下の処理を行う：
     1. セクション名をファイルに書き出す（`[section]\n` 形式）。
     2. `INIReader::Keys(section)` を呼び出して該当するセクション内のすべてのキーを取得し、各キーに対して以下の処理を行う：
        1. キーと値をファイルに書き出す（`key=value\n` 形式）。値は `INIReader::Get(section, key)` を使用して取得する。

## 例外・失敗条件
- 指定されたファイルパスに既存ファイルが存在し、かつ `overwrite` が `false` の場合:
  - `std::runtime_error("file: " + filepath + " already exists.")`
- 出力ファイルを開くことができない場合:
  - `std::runtime_error("cannot open output file: " + filepath)`

## 依存関係
- `INIReader` クラス（`Sections()`, `Keys(section)`, `Get(section, key)` メソッド）
- 標準ライブラリのファイルストリーム機能 (`std::ifstream`, `std::ofstream`)
- 標準ライブラリの文字列操作機能 (`std::string`)

## 重要な不変条件
- 出力ファイルが既存である場合、`overwrite` フラグが `false` の限り書き込みは行われない。
- `INIReader` オブジェクトの内容は読み取り専用であり、書き込み操作によって変更されない。