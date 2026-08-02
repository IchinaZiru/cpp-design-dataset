# INIReader クラスの設計文書

## 責務
INIファイルを読み込み、その内容を解析し、セクションやキーに対する値を取得・更新する機能を提供します。

## 公開インターフェース

### コンストラクタ
- `INIReader()`: 空のコンストラクタ。
- `INIReader(const std::string& filename)`: ファイル名からINIファイルを読み込みます。パースエラーが発生した場合は`std::runtime_error`をスローします。
- `INIReader(std::FILE* file)`: ファイルポインタからINIファイルを読み込みます。パースエラーが発生した場合は`std::runtime_error`をスローします。

### メソッド
- `int ParseError() const`: パース結果を返し、エラーが発生した場合は`std::runtime_error`をスローします。
- `std::set<std::string> Sections() const`: INIファイル内のセクションのリストを返します。
- `std::set<std::string> Keys(const std::string& section) const`: 指定されたセクション内のキーのリストを返します。
- `std::unordered_map<std::string, std::string> Get(const std::string& section) const`: 指定されたセクションの値をマップとして返します。セクションが見つからない場合は`std::runtime_error`をスローします。
- `template <typename T = std::string> T Get(const std::string& section, const std::string& name) const`: 指定されたセクションとキーの値を取得します。型変換に失敗した場合は`std::runtime_error`をスローします。
- `template <typename T> T Get(const std::string& section, const std::string& name, T&& default_v) const`: 指定されたセクションとキーの値を取得し、見つからない場合はデフォルト値を返します。
- `template <typename T = std::string> std::vector<T> GetVector(const std::string& section, const std::string& name) const`: 指定されたセクションとキーの値をベクトルとして取得します。パースに失敗した場合は`std::runtime_error`をスローします。
- `template <typename T> std::vector<T> GetVector(const std::string& section, const std::string& name, const std::vector<T>& default_v) const`: 指定されたセクションとキーの値をベクトルとして取得し、見つからない場合はデフォルト値を返します。
- `template <typename T = std::string> void InsertEntry(const std::string& section, const std::string& name, const T& v)`: 指定されたセクションとキーに値を挿入します。既存のキーが存在する場合は`std::runtime_error`をスローします。
- `template <typename T = std::string> void InsertEntry(const std::string& section, const std::string& name, const std::vector<T>& vs)`: 指定されたセクションとキーにベクトルの値を挿入します。既存のキーが存在する場合は`std::runtime_error`をスローします。
- `template <typename T = std::string> void UpdateEntry(const std::string& section, const std::string& name, const T& v)`: 指定されたセクションとキーの値を更新します。キーが存在しない場合は`std::runtime_error`をスローします。
- `template <typename T = std::string> void UpdateEntry(const std::string& section, const std::string& name, const std::vector<T>& vs)`: 指定されたセクションとキーのベクトルの値を更新します。キーが存在しない場合は`std::runtime_error`をスローします。

## 入力
- INIファイル名 (`const std::string& filename`)
- ファイルポインタ (`std::FILE* file`)
- セクション名 (`const std::string& section`)
- キー名 (`const std::string& name`)
- 値 (`T v`, `const T& v`, `const std::vector<T>& vs`)

## 出力
- パース結果 (`int`)
- セクションのリスト (`std::set<std::string>`)
- キーのリスト (`std::set<std::string>`)
- 値のマップ (`std::unordered_map<std::string, std::string>`)
- 値 (`T`)
- ベクトルの値 (`std::vector<T>`)

## 状態
- `_error`: パース結果を表す整数値。0は成功、-1はファイルオープンエラー、それ以外は最初のエラーライン番号。
- `_values`: セクションとキーに対する値を保持するマップ。

## 処理手順
1. コンストラクタでINIファイルを読み込みます。ファイル名またはファイルポインタから内容を取得し、`Parse`メソッドに渡します。
2. `Parse`メソッドでは、INIファイルの文法に基づいて内容を解析し、セクションとキーに対する値をマップに格納します。
3. 各種getterメソッドで指定されたセクションやキーの値を取得します。型変換が必要な場合は適切なコンバータを使用します。
4. `InsertEntry`メソッドでは、新しいキーと値を挿入します。既存のキーが存在する場合はエラーをスローします。
5. `UpdateEntry`メソッドでは、既存のキーの値を更新します。キーが存在しない場合はエラーをスローします。

## 例外・失敗条件
- ファイルオープンに失敗した場合: `std::runtime_error`
- パース中にエラーが発生した場合: `std::runtime_error`
- セクションやキーが見つからない場合: `std::runtime_error`
- 値の型変換に失敗した場合: `std::runtime_error`
- 既存のキーを挿入しようとした場合: `std::runtime_error`
- 存在しないキーを更新しようとした場合: `std::runtime_error`

## 依存関係
- `<fstream>`: ファイルストリーム操作
- `<string>`: 文字列操作
- `<unordered_map>`: マップ操作
- `<set>`: セット操作
- `<vector>`: ベクトル操作
- `<sstream>`: ストリーム操作
- `<stdexcept>`: 例外処理
- `detail`名前空間: 文字列のトリムや検索などのユーティリティ関数

## 重要な不変条件
- `_values`は常に有効なセクションとキーに対する値を保持します。
- `_error`はパース結果を正確に反映し、エラーが発生した場合は適切なエラーコードを設定します。