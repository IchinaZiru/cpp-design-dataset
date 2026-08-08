# 対象
- target: INIReader
- granularity: target_span
- target_kind: class
- target_symbol: INIReader

# 対象範囲
元コード全体は対象部分を理解するための文脈として参照してください。
設計文書はtarget_symbolで指定した対象部分だけについて作成してください。
対象外の関数やクラスは、対象部分との関係を説明する場合に限って記載してください。

# 基本設計項目の出力構成（全条件共通・固定）

## 責務
INIファイルを読み込み、セクションとキーに対応する値を提供し、必要に応じて新しいエントリを挿入または既存のエントリを更新します。

## 公開インターフェース
- `INIReader()`: 空のコンストラクタ。
- `INIReader(const std::string& filename)`: ファイル名からINIファイルを読み込むコンストラクタ。パースエラーが発生した場合は例外をスローします。
- `INIReader(std::FILE* file)`: ファイルポインタからINIファイルを読み込むコンストラクタ。パースエラーが発生した場合は例外をスローします。
- `int ParseError() const`: パース結果を返す。エラーが発生した場合は例外をスローします。
- `std::set<std::string> Sections() const`: INIファイルに含まれるセクションのリストを返します。
- `std::set<std::string> Keys(const std::string& section) const`: 指定されたセクション内のキーのリストを返します。
- `std::unordered_map<std::string, std::string> Get(const std::string& section) const`: 指定されたセクションの値を表すマップを返します。セクションが見つからない場合は例外をスローします。
- `template <typename T = std::string> T Get(const std::string& section, const std::string& name) const`: 指定されたセクションとキーの値を返します。セクションやキーが見つからない、または値を型Tにパースできない場合は例外をスローします。
- `template <typename T> T Get(const std::string& section, const std::string& name, T&& default_v) const`: 指定されたセクションとキーの値を返します。見つからない場合はデフォルト値を返します。
- `template <typename T = std::string> std::vector<T> GetVector(const std::string& section, const std::string& name) const`: 指定されたセクションとキーの値をベクトルとして返します。パースに失敗した場合は例外をスローします。
- `template <typename T> std::vector<T> GetVector(const std::string& section, const std::string& name, const std::vector<T>& default_v) const`: 指定されたセクションとキーの値をベクトルとして返します。見つからない場合はデフォルト値を返します。
- `template <typename T = std::string> void InsertEntry(const std::string& section, const std::string& name, const T& v)`: 指定されたセクションとキーにエントリを挿入します。既存のキーが存在する場合は例外をスローします。
- `template <typename T = std::string> void InsertEntry(const std::string& section, const std::string& name, const std::vector<T>& vs)`: 指定されたセクションとキーにベクトルエントリを挿入します。既存のキーが存在する場合は例外をスローします。
- `template <typename T = std::string> void UpdateEntry(const std::string& section, const std::string& name, const T& v)`: 指定されたセクションとキーのエントリを更新します。キーが見つからない場合は例外をスローします。
- `template <typename T = std::string> void UpdateEntry(const std::string& section, const std::string& name, const std::vector<T>& vs)`: 指定されたセクションとキーのベクトルエントリを更新します。キーが見つからない場合は例外をスローします。

## 入力
- INIファイル名またはファイルポインタ。
- セクション名、キー名、値（文字列や他の型）。

## 出力
- パース結果（成功時は0、失敗時はエラーコード）。
- 指定されたセクションのリスト。
- 指定されたセクション内のキーのリスト。
- 指定されたセクションとキーの値（文字列や他の型）。
- 指定されたセクションとキーの値を含むマップ。

## 状態
- `_error`: パース結果を示す整数。0は成功、-1はファイルオープンエラー、それ以外は最初のエラーライン番号。
- `_values`: セクションとキーに対応する値を保持するマップ。

## 処理手順
1. コンストラクタでINIファイルを読み込み、内容を文字列として取得します。
2. `Parse`メソッドを使用してINIファイルの内容をパースし、セクションとキーに対応する値をマップに格納します。
3. 各公開インターフェースを通じてセクションやキーの値へのアクセスや更新を行います。

## 例外・失敗条件
- ファイルが開けない場合、メモリ確保エラー、またはパース中に構文エラーが発生した場合は`std::runtime_error`をスローします。
- セクションやキーが見つからない場合、値の型変換に失敗した場合も`std::runtime_error`をスローします。

## 依存関係
- `std::ifstream`, `std::ofstream`: ファイル入出力操作。
- `std::unordered_map`, `std::set`, `std::vector`: コレクションの管理。
- `std::string`, `std::string_view`: 文字列操作。
- `std::istringstream`, `std::ostringstream`: ストリームベースの文字列変換。

## 重要な不変条件
- `_values`は常に有効なセクションとキーに対応する値を保持します。
- `_error`が0以外の場合、パースに失敗したことを示し、その他の操作は未定義動作となる可能性があります。