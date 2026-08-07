# 設計文書: INIReader クラス

## 概要
INIReaderクラスは、.iniファイルを読み込み、その内容を簡単にアクセスできるようにするためのクラスです。このクラスは、ファイルからデータを読み取り、セクションとキーに対応する値を管理します。

## 責務
- .iniファイルのパース
- セクションやキーに対する値の取得
- 新しいエントリの挿入と既存エントリの更新

## 公開インターフェース

### コンストラクタ
1. `INIReader()`: 空のコンストラクタ。
2. `INIReader(const std::string& filename)`: ファイル名を指定して初期化するコンストラクタ。ファイルが存在しない場合やパースエラーが発生した場合は例外をスローします。
3. `INIReader(std::FILE* file)`: ファイルポインタを指定して初期化するコンストラクタ。パースエラーが発生した場合は例外をスローします。

### メソッド
1. `int ParseError() const`: パース結果を返すメソッド。0は成功、-1はファイルオープンエラー、それ以外の値は最初のエラーライン番号を示します。
2. `std::set<std::string> Sections() const`: INIファイルに含まれるセクションの一覧を取得するメソッド。
3. `std::set<std::string> Keys(const std::string& section) const`: 指定されたセクション内のキーの一覧を取得するメソッド。
4. `std::unordered_map<std::string, std::string> Get(const std::string& section) const`: 指定されたセクションの値をマップとして取得するメソッド。セクションが見つからない場合は例外をスローします。
5. `template <typename T = std::string> T Get(const std::string& section, const std::string& name) const`: 指定されたセクションとキーの値を取得するメソッド。型Tに変換できない場合や、セクション/キーが見つからない場合は例外をスローします。
6. `template <typename T> T Get(const std::string& section, const std::string& name, T&& default_v) const`: 指定されたセクションとキーの値を取得するメソッド。値が見つからない場合、デフォルト値を返します。
7. `template <typename T = std::string> std::vector<T> GetVector(const std::string& section, const std::string& name) const`: 指定されたセクションとキーの値をベクトルとして取得するメソッド。パースに失敗した場合は例外をスローします。
8. `template <typename T> std::vector<T> GetVector(const std::string& section, const std::string& name, const std::vector<T>& default_v) const`: 指定されたセクションとキーの値をベクトルとして取得するメソッド。値が見つからない場合、デフォルト値を返します。
9. `template <typename T = std::string> void InsertEntry(const std::string& section, const std::string& name, const T& v)`: 指定されたセクションとキーに新しいエントリを挿入するメソッド。既存のキーが存在する場合は例外をスローします。
10. `template <typename T = std::string> void InsertEntry(const std::string& section, const std::string& name, const std::vector<T>& vs)`: 指定されたセクションとキーに新しいベクトルエントリを挿入するメソッド。既存のキーが存在する場合は例外をスローします。
11. `template <typename T = std::string> void UpdateEntry(const std::string& section, const std::string& name, const T& v)`: 指定されたセクションとキーのエントリを更新するメソッド。キーが存在しない場合は例外をスローします。
12. `template <typename T = std::string> void UpdateEntry(const std::string& section, const std::string& name, const std::vector<T>& vs)`: 指定されたセクションとキーのベクトルエントリを更新するメソッド。キーが存在しない場合は例外をスローします。

## 入力
- ファイル名 (`std::string`)
- ファイルポインタ (`std::FILE*`)
- セクション名 (`std::string`)
- キー名 (`std::string`)
- 値 (`T`型)
- デフォルト値 (`T`型)

## 出力
- エラーコード (`int`)
- セクションの一覧 (`std::set<std::string>`)
- キーの一覧 (`std::set<std::string>`)
- 値 (`T`型)
- ベクトル値 (`std::vector<T>`)

## 状態
- `_error`: パース結果を示す整数値。0は成功、-1はファイルオープンエラー、それ以外の値は最初のエラーライン番号を示します。
- `_values`: セクションとキーに対応する値を保持するマップ。

## 処理手順
1. コンストラクタで指定されたファイルからデータを読み取り、`Parse()`メソッドを使用してパースします。
2. `Parse()`メソッドでは、BOMのチェックを行い、各行を解析し、セクションとキーに対応する値をマップに格納します。エラーが発生した場合は `_error` を設定します。
3. 各種getterメソッドは、指定されたセクションとキーに対応する値を取得します。型変換やデフォルト値の処理も行います。
4. `InsertEntry()`メソッドは新しいエントリを挿入し、`UpdateEntry()`メソッドは既存のエントリを更新します。

## 例外・失敗条件
- ファイルが存在しない場合やファイルオープンに失敗した場合: `std::runtime_error`
- パース中にエラーが発生した場合: `std::runtime_error` (メッセージはエラーライン番号を含む)
- セクションまたはキーが見つからない場合: `std::runtime_error`
- 値の型変換に失敗した場合: `std::runtime_error`
- 既存のキーに対して新しいエントリを挿入しようとした場合: `std::runtime_error`

## 依存関係
- `<cstddef>`
- `<cstdio>`
- `<fstream>`
- `<set>`
- `<sstream>`
- `<stdexcept>`
- `<string>`
- `<string_view>`
- `<type_traits>`
- `<unordered_map>`
- `<utility>`
- `<vector>`

## 重要な不変条件
- `_values`は常に有効なセクションとキーのマップを保持する。
- `_error`が0以外の場合、パースに失敗したことを示す。エラーメッセージは適切な情報を含む。

この設計文書は、INIReaderクラスの機能と内部構造を詳細に説明しています。これに基づいて再実装を行うことができます。