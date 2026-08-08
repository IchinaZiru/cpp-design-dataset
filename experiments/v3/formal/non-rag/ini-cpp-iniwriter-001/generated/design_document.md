# 対象
- target: INIWriter::write
- granularity: target_span
- target_kind: function
- target_symbol: INIWriter::write

# 対象範囲
元コード全体は対象部分を理解するための文脈として参照してください。
設計文書はtarget_symbolで指定した対象部分だけについて作成してください。
対象外の関数やクラスは、対象部分との関係を説明する場合に限って記載してください。

# 基本設計項目の出力構成（全条件共通・固定）

## 責務
INIファイルにINIReaderオブジェクトの内容を書き込む責任を持ちます。既存ファイルの上書きはオプションで制御できます。

## 公開インターフェース
```cpp
inline static void write(const std::string& filepath, const INIReader& reader, const bool overwrite = false);
```

## 入力
- `filepath`: 書き込み先のファイルパス（`std::string`）
- `reader`: 書き込むINIデータを保持するINIReaderオブジェクト（`const INIReader&`）
- `overwrite`: 既存ファイルを上書きするかどうかを示すフラグ（`bool`、デフォルトは`false`）

## 出力
なし

## 状態
- ファイルの存在状況: `overwrite`が`false`の場合、指定されたファイルパスにファイルが既存であるか確認されます。
- 書き込みモード: `std::ofstream`を使用してファイルを開きます。

## 処理手順
1. `overwrite`フラグが`false`で、指定されたファイルパスにファイルが存在する場合、例外をスローします。
2. 指定されたファイルパスにファイルを開きます。開けない場合は例外をスローします。
3. INIReaderオブジェクトからセクション名のリストを取得し、各セクションに対して以下の処理を行います：
   - セクション名を書き込みます（例: `[section]`）。
   - 各セクション内のキー名と値のペアを取得し、キー=値の形式でファイルに書き込みます。

## 例外・失敗条件
- 指定されたファイルパスに既存ファイルがあり、かつ`overwrite`が`false`の場合、`std::runtime_error`をスローします。
- ファイルを開くことができない場合、`std::runtime_error`をスローします。

## 依存関係
- `INIReader`: INIデータを保持するためのクラス。`Sections()`メソッドと`Keys(section)`メソッド、および`Get(section, key)`メソッドを使用しています。
- `std::ofstream`: ファイルへの書き込みに使用されます。

## 重要な不変条件
- 出力ファイルはUTF-8エンコーディングで保存されることが期待されます（ただし、元コードでは明示的なエンコーディング指定が行われていません）。
- セクション名とキー名は`INIReader::Sections()`と`INIReader::Keys(section)`によって提供され、これらはユニークである必要があります。