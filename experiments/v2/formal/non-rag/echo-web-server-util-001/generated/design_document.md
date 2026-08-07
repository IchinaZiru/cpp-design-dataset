# デザイン文書: utilモジュール

## 概要
`util`モジュールは、様々なユーティリティ関数とクラスを提供します。これには文字列操作、YAMLの読み込み、ファイルディスクリプタの管理、バックトレースの取得、シングルトンパターンの実装などが含まれます。

## ファイル構造
- `include/util.h`: 公開インターフェースとクラス定義を含むヘッダーファイル。
- `src/util/util.cpp`: 実装ファイルで、`util.h`に宣言された関数やクラスの実体を提供します。

## ファイル間の関係
- `include/util.h`は公開インターフェースを定義し、`src/util/util.cpp`がそれらを実装しています。
- 両ファイルは同じ名前空間`ws`を使用しており、モジュールとして統合されています。

## 公開インターフェース

### 関数
1. **文字列操作**
   - `std::string StringToLower(std::string str) noexcept;`
     - 文字列を小文字に変換します。
     - **入力**: 変換したい文字列。
     - **出力**: 小文字に変換された文字列。
   
   - `std::string StringToUpper(std::string str) noexcept;`
     - 文字列を大文字に変換します。
     - **入力**: 変換したい文字列。
     - **出力**: 大文字に変換された文字列。

   - `std::string ReplaceAllSubstring(std::string_view str, std::string_view from, std::string_view to) noexcept;`
     - 文字列内の特定の部分を別の文字列で置き換えます。
     - **入力**: 置換したい文字列、置換元の部分、置換後の部分。
     - **出力**: 置換後の文字列。

   - `std::vector<std::string> SplitString(const std::string& str, const std::regex& pattern) noexcept;`
     - 正規表現を使用して文字列を分割します。
     - **入力**: 分割したい文字列、正規表現パターン。
     - **出力**: 分割された文字列のリスト。

   - `std::vector<std::string> SplitStringToLines(const std::string& str) noexcept;`
     - 文字列を行ごとに分割します。
     - **入力**: 分割したい文字列。
     - **出力**: 行ごとに分割された文字列のリスト。

2. **YAML操作**
   - `YAML::Node LoadYamlString(std::string_view str, std::initializer_list<std::string_view> required_fields = {});`
     - YAML形式の文字列を読み込みます。
     - **入力**: YAML形式の文字列、必須フィールド（オプション）。
     - **出力**: YAMLノード。
     - **例外**: `std::invalid_argument` (必須フィールドが存在しない場合)。

   - `void ThrowIfYamlFieldIsNotScalar(const YAML::Node& node, std::string_view field);`
     - 指定されたフィールドがスカラーであることを確認し、そうでない場合は例外を投げます。
     - **入力**: YAMLノード、確認したいフィールド名。
     - **例外**: `std::invalid_argument` (指定したフィールドが存在しないかスカラーでない場合)。

3. **ファイルディスクリプタ操作**
   - `constexpr bool IsValidFileDescriptor(FileDescriptor fd) noexcept;`
     - ファイルディスクリプタの有効性を確認します。
     - **入力**: ファイルディスクリプタ。
     - **出力**: 有効な場合は`true`、それ以外は`false`。

   - `void SetFileDescriptorAsNonblocking(FileDescriptor fd);`
     - ファイルディスクリプタをノンブロッキングモードに設定します。
     - **入力**: ファイルディスクリプタ。
     - **例外**: `std::system_error` (設定に失敗した場合)。

   - `void ThrowLastSystemError();`
     - 最後のシステムエラーを含む例外を投げます。
     - **例外**: `std::system_error`。

4. **スレッド操作**
   - `std::uint32_t CurrentThreadId() noexcept;`
     - 現在のスレッドIDを取得します。
     - **出力**: スレッドID。

5. **バックトレース取得**
   - `void Backtrace(std::vector<std::string>& stack, std::size_t size, std::size_t skip = 0) noexcept;`
     - バックトレース情報を取得し、指定されたベクタに格納します。
     - **入力**: 格納先のベクタ、最大アドレス数、無視するアドレス数（オプション）。

   - `std::string Backtrace(std::size_t size, std::size_t skip = 0, std::string_view prefix = "") noexcept;`
     - バックトレース情報を取得し、指定されたプレフィックスを付加した文字列で返します。
     - **入力**: 最大アドレス数、無視するアドレス数（オプション）、プレフィックス（オプション）。
     - **出力**: バックトレース情報の文字列。

### クラス
1. **シングルトンパターン**
   - `template <typename T, typename... Args> class Singleton;`
     - 単一インスタンスを提供するためのシングルトンクラス。
     - **公開インターフェース**: 
       - `static T& Instance() noexcept;` インスタンスを取得します。

   - `template <typename T, typename... Args> class SingletonPtr;`
     - 単一インスタンスをスマートポインタとして提供するためのシングルトンクラス。
     - **公開インターフェース**: 
       - `static std::shared_ptr<T> Instance() noexcept;` インスタンスを取得します。

2. **RAII**
   - `template <typename T, typename Cleaner = std::function<void(T)>> class RAII;`
     - リソースの自動管理を行うためのRAIIクラス。
     - **公開インターフェース**: 
       - `explicit RAII(T obj, Cleaner cleaner) noexcept;` コンストラクタ。
       - `const T& Object() const noexcept;` 管理しているオブジェクトを取得します。

3. **ファイルマッピング**
   - `class MappedReadOnlyFile;`
     - ファイルをメモリにマップし、読み取り専用でアクセスするためのクラス。
     - **公開インターフェース**: 
       - `MappedReadOnlyFile() noexcept;` コンストラクタ。
       - `std::byte* Map(std::string path);` ファイルをメモリにマップします。
       - `void Unmap() noexcept;` メモリからファイルのマッピングを解除します。
       - `std::size_t Size() const noexcept;` マップされたファイルサイズを取得します。
       - `std::byte* Data() const noexcept;` マップされたデータへのポインタを取得します。
       - `std::string_view Path() const noexcept;` マップされたファイルのパスを取得します。

## 実装上の処理
- 文字列操作関数は、標準ライブラリのアルゴリズムを使用して実装されています。
- YAML読み込み関数は、`yaml-cpp`ライブラリを使用して実装されています。
- ファイルディスクリプタ操作関数は、POSIX API (`fcntl`, `open`, `mmap`, `munmap`) を使用して実装されています。
- スレッドID取得関数は、システムコール(`syscall(SYS_gettid)`)を使用して実装されています。
- バックトレース取得関数は、`execinfo.h`ライブラリの`backtrace`と`backtrace_symbols`を使用して実装されています。

## 例外・失敗条件
- `LoadYamlString`: 必須フィールドが存在しない場合に`std::invalid_argument`を投げます。
- `ThrowIfYamlFieldIsNotScalar`: 指定したフィールドがスカラーでない場合に`std::invalid_argument`を投げます。
- `SetFileDescriptorAsNonblocking`: ファイルディスクリプタの設定に失敗した場合に`std::system_error`を投げます。
- `MappedReadOnlyFile::Map`: ファイルがディレクトリである、アクセス権限がない、マッピングに失敗した場合に例外を投げます。

## 依存関係
- `fmt/format.h`
- `yaml-cpp/yaml.h`
- `<sys/stat.h>`
- `<concepts>`
- `<functional>`
- `<initializer_list>`
- `<memory>`
- `<regex>`
- `<string>`
- `<string_view>`
- `<utility>`
- `<vector>`
- `<execinfo.h>`
- `<fcntl.h>`
- `<sys/mman.h>`
- `<sys/syscall.h>`
- `<unistd.h>`

## 重要な不変条件
- `MappedReadOnlyFile`クラスのインスタンスは、一度に一つのファイルしかマップできません。
- `Singleton`と`SingletonPtr`クラスは、テンプレート引数として指定された型に対して常に同じインスタンスを提供します。