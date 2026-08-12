# INIWriter クラスの設計仕様書

## 概要
この設計仕様書は、INIファイルを書き込むための `INIWriter` クラスの完全な定義を提供します。このクラスは、与えられた `INIReader` オブジェクトから読み取ったデータを INI ファイルに書き込む機能を提供します。

## クラス構造

### クラス名
`INIWriter`

### アクセス修飾子
`public`

### コンストラクタ
```cpp
INIWriter() = default;
```
- デフォルトコンストラクタで、初期化は必要ありません。

### メソッド

#### `write`
```cpp
inline static void write(const std::string& filepath,
                         const INIReader& reader,
                         const bool overwrite = false)
```

##### パラメータ
1. **filepath** (`const std::string&`)
   - 出力ファイルのパスを指定します。
2. **reader** (`const INIReader&`)
   - INI データを読み取るための `INIReader` オブジェクトを参照します。
3. **overwrite** (`const bool`, デフォルト: `false`)
   - ファイルが既に存在する場合、上書きするかどうかを指定します。

##### 戻り値
- 戻り値はありません (`void`)。

##### 機能説明
1. **ファイル存在チェック**
   - `overwrite` が `false` の場合、指定されたパスのファイルが既に存在するかどうかを確認します。
   - ファイルが存在する場合、`std::runtime_error` を投げます。

2. **ファイルオープン**
   - 指定されたパスで出力ストリームを開きます。
   - ファイルを開けない場合、`std::runtime_error` を投げます。

3. **INI データ書き込み**
   - `reader.Sections()` で取得した各セクションに対して：
     - セクション名を `[section]` の形式で出力します。
     - `reader.Keys(section)` で取得した各キーに対して：
       - キーと値を `key=value` の形式で出力します。

##### 例外
- ファイルが既に存在する場合、`std::runtime_error` を投げます。
- ファイルを開けない場合、`std::runtime_error` を投げます。

## 使用例

```cpp
INIReader reader("input.ini");
INIWriter::write("output.ini", reader, true); // 上書き許可
```

## 注意事項
- `INIReader` クラスは、この仕様書の範囲外であり、別途提供される必要があります。
- `INIReader` クラスは以下のメソッドを持つ必要があります：
  - `Sections()`: セクション名のリストを返す。
  - `Keys(const std::string& section)`: 指定されたセクション内のキーのリストを返す。
  - `Get(const std::string& section, const std::string& key)`: 指定されたセクションとキーに対応する値を返す。

## 再実装ガイドライン
- `INIWriter` クラスは、上記の仕様通りに再実装してください。
- `INIReader` クラスは、この仕様書では定義されていないため、別途提供される必要があります。
- `write` メソッドは `inline static` として宣言されているため、ヘッダーファイル内で定義することを推奨します。