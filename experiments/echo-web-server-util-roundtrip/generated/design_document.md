# デザイン文書: utilモジュール

## 概要
`util`モジュールは、一般的なユーティリティ関数とクラスを提供します。これには文字列操作、YAMLの読み込み、ファイルディスクリプタの管理、バックトレースの取得、シングルトンパターンの実装などが含まれます。

## 責務
- 文字列変換（大文字小文字変換、部分文字列置換）
- YAMLデータの解析と検証
- ファイルディスクリプタの操作（非ブロッキングモードへの設定）
- スレッド情報の取得
- バックトレースの生成
- シングルトンパターンの実装
- RAII（リソース獲得は初期化）の提供

## 公開インターフェース

### 関数
1. **StringToLower**
   - 説明: 文字列を小文字に変換します。
   - 引数: `std::string str`
   - 戻り値: `std::string`

2. **StringToUpper**
   - 説明: 文字列を大文字に変換します。
   - 引数: `std::string str`
   - 戻り値: `std::string`

3. **ReplaceAllSubstring**
   - 説明: 文字列内の指定された部分文字列を別の文字列で置き換えます。
   - 引数: `std::string_view str`, `std::string_view from`, `std::string_view to`
   - 戻り値: `std::string`

4. **SplitString**
   - 説明: 正規表現を使用して文字列を分割します。
   - 引数: `const std::string& str`, `const std::regex& pattern`
   - 戻り値: `std::vector<std::string>`

5. **SplitStringToLines**
   - 説明: 文字列を行ごとに分割します。
   - 引数: `const std::string& str`
   - 戻り値: `std::vector<std::string>`

6. **LoadYamlString**
   - 説明: YAML文字列を解析し、必要なフィールドが存在することを確認します。
   - 引数: `std::string_view str`, `std::initializer_list<std::string_view> required_fields`
   - 戻り値: `YAML::Node`

7. **ThrowIfYamlFieldIsNotScalar**
   - 説明: YAMLノードの指定されたフィールドがスカラーであることを確認し、そうでない場合は例外を投げます。
   - 引数: `const YAML::Node& node`, `std::string_view field`
   - 戻り値: なし

8. **IsValidFileDescriptor**
   - 説明: ファイルディスクリプタが有効であるかを確認します。
   - 引数: `FileDescriptor fd`
   - 戻り値: `bool`

9. **SetFileDescriptorAsNonblocking**
   - 説明: ファイルディスクリプタを非ブロッキングモードに設定します。
   - 引数: `FileDescriptor fd`
   - 戻り値: なし

10. **ThrowLastSystemError**
    - 説明: 最後のシステムエラーを含む例外を投げます。
    - 引数: なし
    - 戻り値: なし

11. **CurrentThreadId**
    - 説明: 現在のスレッドIDを取得します。
    - 引数: なし
    - 戻り値: `std::uint32_t`

12. **Backtrace**
    - 説明: 呼び出し元プログラムのバックトレースを生成します。
    - 引数: `std::vector<std::string>& stack`, `std::size_t size`, `std::size_t skip`
    - 戻り値: なし

13. **Backtrace**
    - 説明: 呼び出し元プログラムのバックトレースを生成し、それを文字列として返します。
    - 引数: `std::size_t size`, `std::size_t skip`, `std::string_view prefix`
    - 戻り値: `std::string`

### クラス
1. **Singleton**
   - 説明: 単一のインスタンスを提供するシングルトンパターンのインターフェースです。
   - メンバ関数:
     - `Instance()`: シングルトンインスタンスを取得します。

2. **SingletonPtr**
   - 説明: スマートポインタを使用したシングルトンパターンのインターフェースです。
   - メンバ関数:
     - `Instance()`: シングルトンインスタンスをスマートポインタとして取得します。

3. **RAII**
   - 説明: RAII（リソース獲得は初期化）のためのクラステンプレートです。
   - メンバ関数:
     - コンストラクタ: オブジェクトとクリーナーを設定します。
     - `Object()`: 管理しているオブジェクトへの参照を返します。

4. **MappedReadOnlyFile**
   - 説明: ファイルをメモリにマッピングするためのクラスです。
   - メンバ関数:
     - コンストラクタ/デストラクタ: デフォルトコンストラクタとムーブセマンティクスをサポートします。
     - `Map()`: ファイルをメモリにマッピングします。
     - `Unmap()`: メモリからファイルのマッピングを解除します。
     - `Size()`: マップされたファイルサイズを返します。
     - `Data()`: マップされたデータへのポインタを返します。
     - `Path()`: ファイルパスを返します。

## 入力
- 文字列操作関数: 文字列や部分文字列、正規表現パターンなどのテキストデータ。
- YAML解析関数: YAML形式の文字列と必要なフィールド名リスト。
- ファイルディスクリプタ操作関数: ファイルディスクリプタの値。

## 出力
- 文字列操作関数: 変換後の文字列や分割された文字列配列。
- YAML解析関数: 解析されたYAMLノード。
- バックトレース生成関数: スタックトレース情報の文字列表現。

## 状態
- **MappedReadOnlyFile**: ファイルパス、ファイルステータス構造体、マッピングされたデータへのポインタ。

## 処理手順
1. **StringToLower, StringToUpper**
   - 文字列の各文字を指定した関数（`std::tolower`, `std::toupper`）で変換します。
2. **ReplaceAllSubstring**
   - 指定された部分文字列を探し、それを新しい文字列に置き換えます。
3. **SplitString, SplitStringToLines**
   - 正規表現を使用して文字列を分割し、結果を配列として返します。
4. **LoadYamlString**
   - YAML文字列を解析し、必要なフィールドが存在することを確認します。
5. **ThrowIfYamlFieldIsNotScalar**
   - 指定されたフィールドがスカラーであることを確認し、そうでない場合は例外を投げます。
6. **SetFileDescriptorAsNonblocking**
   - ファイルディスクリプタのフラグを変更して非ブロッキングモードに設定します。
7. **ThrowLastSystemError**
   - 最後のシステムエラー番号から`std::system_error`例外を作成し、それを投げます。
8. **CurrentThreadId**
   - システムコールを使用して現在のスレッドIDを取得します。
9. **Backtrace**
   - `backtrace`と`backtrace_symbols`を使用してバックトレース情報を収集し、必要に応じて文字列として整形します。
10. **MappedReadOnlyFile::Map**
    - ファイルのステータスを確認し、メモリにマッピングします。
11. **MappedReadOnlyFile::Unmap**
    - メモリからファイルのマッピングを解除します。

## 例外・失敗条件
- **LoadYamlString**: 必要なフィールドが存在しない場合、`std::invalid_argument`例外を投げます。
- **ThrowIfYamlFieldIsNotScalar**: 指定されたフィールドがスカラーでない場合、`std::invalid_argument`例外を投げます。
- **SetFileDescriptorAsNonblocking**: ファイルディスクリプタの設定に失敗した場合、`std::system_error`例外を投げます。
- **MappedReadOnlyFile::Map**: ファイルがディレクトリである場合やアクセス権限がない場合、またはマッピングに失敗した場合は適切な例外を投げます。

## 依存関係
- `fmt/format.h`: 文字列フォーマット用。
- `yaml-cpp/yaml.h`: YAMLデータの解析用。
- `<sys/stat.h>`: ファイルステータス情報取得用。
- `<concepts>`, `<functional>`, `<initializer_list>`, `<memory>`, `<regex>`, `<string>`, `<string_view>`, `<utility>`, `<vector>`: 標準ライブラリ機能の利用。

## 重要な不変条件
- **MappedReadOnlyFile**: ファイルがマッピングされている場合、`data_`は有効なポインタでなければなりません。また、ファイルがマッピングされていない場合は`data_`はnullptrであるべきです。
- **RAII**: オブジェクトとクリーナーのペアが正しく設定され、デストラクタ呼び出し時にクリーナーが適切に実行されるべきです。