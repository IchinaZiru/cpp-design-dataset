# デザイン文書: utilモジュール

## 概要
`util.h`と`util.cpp`は、ウェブサーバーのさまざまな部分で使用される一般的なユーティリティ関数やクラスを提供します。このモジュールは文字列操作、ファイルディスクリプタの管理、YAMLの読み込み、エラーハンドリング、シングルトンパターンの実装などを含みます。

## 責務
- 文字列変換と操作（小文字化、大文字化、部分文字列置換、分割）
- YAMLデータの読み込みと検証
- ファイルディスクリプタの有効性チェックと非ブロッキングモードへの設定
- システムエラーの例外送出
- スレッドIDの取得
- 呼び出し元プログラムのバックトレース情報の取得
- RAII（リソース獲得は初期化）パターンの実装

## 公開インターフェース

### 関数
1. **StringToLower**
   - `std::string StringToLower(std::string str) noexcept;`
2. **StringToUpper**
   - `std::string StringToUpper(std::string str) noexcept;`
3. **ReplaceAllSubstring**
   - `std::string ReplaceAllSubstring(std::string_view str, std::string_view from, std::string_view to) noexcept;`
4. **SplitString**
   - `std::vector<std::string> SplitString(const std::string& str, const std::regex& pattern) noexcept;`
5. **SplitStringToLines**
   - `std::vector<std::string> SplitStringToLines(const std::string& str) noexcept;`
6. **LoadYamlString**
   - `YAML::Node LoadYamlString(std::string_view str, std::initializer_list<std::string_view> required_fields = {});`
7. **ThrowIfYamlFieldIsNotScalar**
   - `void ThrowIfYamlFieldIsNotScalar(const YAML::Node& node, std::string_view field);`
8. **IsValidFileDescriptor**
   - `constexpr bool IsValidFileDescriptor(FileDescriptor fd) noexcept;`
9. **SetFileDescriptorAsNonblocking**
   - `void SetFileDescriptorAsNonblocking(FileDescriptor fd);`
10. **ThrowLastSystemError**
    - `[[noreturn]] void ThrowLastSystemError();`
11. **CurrentThreadId**
    - `std::uint32_t CurrentThreadId() noexcept;`
12. **Backtrace (オーバーロード版1)**
    - `void Backtrace(std::vector<std::string>& stack, std::size_t size, std::size_t skip = 0) noexcept;`
13. **Backtrace (オーバーロード版2)**
    - `std::string Backtrace(std::size_t size, std::size_t skip = 0, std::string_view prefix = "") noexcept;`

### クラス
1. **Singleton**
   - テンプレートクラスで、シングルトンパターンを実装します。
2. **SingletonPtr**
   - テンプレートクラスで、スマートポインタを使用したシングルトンパターンを実装します。
3. **RAII**
   - テンプレートクラスで、リソースの自動解放を提供します。
4. **MappedReadOnlyFile**
   - ファイルをメモリにマッピングし読み取り専用アクセスを提供するクラス。

## 入力
- 文字列操作関数: 変換や分割対象となる文字列、置換のための部分文字列など。
- YAMLデータ読み込み関数: YAML形式の文字列と必須フィールドリスト。
- ファイルディスクリプタ管理関数: 操作対象となるファイルディスクリプタ。

## 出力
- 文字列操作関数: 変換や分割後の文字列。
- YAMLデータ読み込み関数: 解析されたYAMLノード。
- ファイルディスクリプタ管理関数: 成功時にはvoid、失敗時には例外送出。

## 状態
- **MappedReadOnlyFile**
  - マッピング状態（マップされているか否か）
  - ファイルパス
  - ファイルサイズ
  - メモリ上のデータポインタ

## 処理手順
1. **文字列操作関数**
   - 文字列の変換や分割は、標準ライブラリのアルゴリズムを使用して行います。
2. **YAMLデータ読み込み関数**
   - YAML形式の文字列を解析し、必要なフィールドが存在することを確認します。存在しない場合は例外を送出します。
3. **ファイルディスクリプタ管理関数**
   - ファイルディスクリプタの有効性チェックを行い、非ブロッキングモードに設定します。失敗した場合は例外を送出します。
4. **MappedReadOnlyFile**
   - `Map`: ファイルをメモリにマッピングし、データへのポインタを返します。
   - `Unmap`: メモリからファイルのマッピングを解除します。

## 例外・失敗条件
- 文字列操作関数: 入力文字列が不正な場合でも通常は例外を送出しません（`noexcept`指定）。
- YAMLデータ読み込み関数: 必須フィールドが存在しない場合やスカラーでない場合は`std::invalid_argument`を送出します。
- ファイルディスクリプタ管理関数: ファイルディスクリプタの設定に失敗した場合は`std::system_error`を送出します。
- `MappedReadOnlyFile`: マッピングやファイルアクセスに失敗した場合、適切な例外（`std::invalid_argument`, `std::runtime_error`, `std::system_error`）を送出します。

## 依存関係
- **標準ライブラリ**
  - `<fmt/format.h>`
  - `<yaml-cpp/yaml.h>`
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
- **システムヘッダ**
  - `<execinfo.h>`
  - `<fcntl.h>`
  - `<sys/mman.h>`
  - `<sys/syscall.h>`
  - `<unistd.h>`

## 重要な不変条件
- `MappedReadOnlyFile`のインスタンスは、一度マッピングされたファイルをアンマップするまで有効なデータポインタを持ちます。
- 文字列操作関数は入力文字列に対して副作用を及ぼさず、新しい文字列を返します。
- YAMLデータ読み込み関数は、指定されたフィールドが存在しスカラーであることを保証します。
