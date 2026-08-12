# INIWriter クラスの設計仕様書

## 概要
この設計仕様書は、INIファイルを書き込むための `INIWriter` クラスの完全な定義を提供します。このクラスは静的メソッドのみを持ち、INIReader オブジェクトから読み取ったデータを INI ファイルに書き込みます。

## クラス構造

### クラス名
`INIWriter`

### アクセス修飾子
`public`

### コンストラクタ
```cpp
INIWriter() = default;
```
- デフォルトコンストラクタで、インスタンス化は可能ですが、実際の機能は静的メソッドを通じて提供されます。

## メソッド仕様

### `write` メソッド
#### 目的
INIReader オブジェクトから読み取ったデータを指定されたファイルに書き込みます。

#### シグネチャ
```cpp
inline static void write(const std::string& filepath,
                         const INIReader& reader,
                         const bool overwrite = false)
```

#### パラメータ
1. `filepath` (const std::string&)
   - 出力ファイルのパスを指定します。
2. `reader` (const INIReader&)
   - データソースとなる INIReader オブジェクトへの参照です。
3. `overwrite` (const bool, デフォルト: false)
   - 既存ファイルを上書きするかどうかを指定します。

#### 戻り値
なし (`void`)

#### 例外
1. `std::runtime_error`
   - ファイルが既に存在し、overwrite が false の場合。
   - 出力ファイルを開けない場合。

#### 処理フロー
1. `overwrite` パラメータが false であり、指定されたパスのファイルが既に存在する場合は例外を投げます。
2. 指定されたパスで出力ストリームを開きます。
3. ストリームが開けない場合は例外を投げます。
4. INIReader からセクション一覧を取得し、各セクションについて以下の処理を行います：
   - セクション名を `[section]` の形式で出力します。
   - 各セクション内のキー一覧を取得し、各キーについて以下の処理を行います：
     - `key=value` の形式で出力します。

#### 使用される外部メソッド
- `reader.Sections()`: セクション名のリストを返すメソッド。
- `reader.Keys(section)`: 指定されたセクション内のキー名のリストを返すメソッド。
- `reader.Get(section, key)`: 指定されたセクションとキーに対応する値を返すメソッド。

## 使用例
```cpp
INIReader reader("input.ini");
try {
    INIWriter::write("output.ini", reader);
} catch (const std::runtime_error& e) {
    std::cerr << "Error: " << e.what() << std::endl;
}
```

## 注意事項
1. このクラスは静的メソッドのみを提供し、インスタンス化する必要はありません。
2. ファイル操作中に発生するエラーはすべて `std::runtime_error` として投げられます。
3. INIReader オブジェクトの内容が正しくない場合（例: 不正なセクション名やキー名）についての検証は行いません。

## 再実装時の注意点
1. `INIReader` クラスのインターフェース（特に `Sections()`、`Keys()`、`Get()` メソッド）が変更されないことを前提としています。
2. ファイル操作に関するエラーハンドリングは、この仕様書に従って実装してください。
3. 静的メソッドであるため、インスタンス化せずに直接呼び出すことができます。