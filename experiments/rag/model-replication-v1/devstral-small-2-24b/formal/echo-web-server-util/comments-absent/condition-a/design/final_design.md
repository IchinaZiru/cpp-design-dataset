# 設計仕様書: `ws` ユーティリティライブラリ

## 概要
この設計仕様書は、C++のユーティリティ関数とクラスを提供する `ws` 名前空間の実装を記述します。このライブラリには文字列操作、YAML処理、ファイルマッピング、システムインターフェースなどの機能が含まれています。

## 1. 一般的な要件

### 1.1 名前空間
すべての宣言は `ws` 名前空間内に配置されます。

```cpp
namespace ws {
    // 宣言...
}
```

### 1.2 ヘッダ依存関係
- `<fmt/format.h>`: フォーマット文字列サポート
- `<yaml-cpp/yaml.h>`: YAML処理
- `<sys/stat.h>`: ファイル状態情報
- C++標準ライブラリヘッダ: `<concepts>`, `<functional>`, `<initializer_list>`, `<memory>`, `<regex>`, `<string>`, `<string_view>`, `<utility>`, `<vector>`
- 実装で使用されるシステムヘッダ:
  - `<execinfo.h>`: バックトレース
  - `<fcntl.h>`: ファイル制御
  - `<sys/mman.h>`: メモリマッピング
  - `<sys/syscall.h>`: システムコール
  - `<unistd.h>`: POSIX API

## 2. 型定義

### 2.1 `FileDescriptor`
```cpp
using FileDescriptor = int;
```
- ファイルディスクリプタを表す整数型
- `invalid_file_descriptor` 定数と共に使用されます

### 2.2 `invalid_file_descriptor`
```cpp
inline constexpr FileDescriptor invalid_file_descriptor {-1};
```
- 無効なファイルディスクリプタを示す定数

## 3. 関数

### 3.1 文字列操作関数

#### `StringToLower`
```cpp
std::string StringToLower(std::string str) noexcept;
```
- 入力文字列を小文字に変換します
- 非破壊的で、新しい文字列を返します

#### `StringToUpper`
```cpp
std::string StringToUpper(std::string str) noexcept;
```
- 入力文字列を大文字に変換します
- 非破壊的で、新しい文字列を返します

#### `ReplaceAllSubstring`
```cpp
std::string ReplaceAllSubstring(std::string_view str, std::string_view from,
                               std::string_view to) noexcept;
```
- 文字列内のすべての`from`サブストリングを`to`で置き換えます
- `str`は変更されず、新しい文字列が返されます

#### `SplitString`
```cpp
std::vector<std::string> SplitString(const std::string& str,
                                    const std::regex& pattern) noexcept;
```
- 正規表現パターンで文字列を分割します
- 分割結果のベクトルを返します

#### `SplitStringToLines`
```cpp
std::vector<std::string> SplitStringToLines(const std::string& str) noexcept;
```
- 改行で文字列を分割します（`\r*\n`パターン）
- 分割結果のベクトルを返します

### 3.2 YAML処理関数

#### `LoadYamlString`
```cpp
YAML::Node LoadYamlString(
    std::string_view str,
    std::initializer_list<std::string_view> required_fields = {});
```
- YAML文字列をパースし、必要なフィールドが存在するか確認します
- 要求されたフィールドが見つからない場合は例外をスローします

#### `ThrowIfYamlFieldIsNotScalar`
```cpp
void ThrowIfYamlFieldIsNotScalar(const YAML::Node& node,
                                std::string_view field);
```
- 指定されたフィールドがスカラー値でない場合に例外をスローします

### 3.3 ファイル操作関数

#### `IsValidFileDescriptor`
```cpp
constexpr bool IsValidFileDescriptor(FileDescriptor fd) noexcept;
```
- ファイルディスクリプタが有効かどうかを判定します

#### `SetFileDescriptorAsNonblocking`
```cpp
void SetFileDescriptorAsNonblocking(FileDescriptor fd);
```
- ファイルディスクリプタを非ブロッキングモードに設定します
- 無効なファイルディスクリプタが渡された場合はアサートされます

#### `ThrowLastSystemError`
```cpp
[[noreturn]] void ThrowLastSystemError();
```
- 最後のシステムエラーを例外としてスローします
- この関数は戻りません

### 3.4 システム関数

#### `CurrentThreadId`
```cpp
std::uint32_t CurrentThreadId() noexcept;
```
- 現在のスレッドIDを取得します

#### `Backtrace` (オーバーロード)
```cpp
void Backtrace(std::vector<std::string>& stack, std::size_t size,
              std::size_t skip = 0) noexcept;

std::string Backtrace(const std::size_t size, const std::size_t skip,
                     std::string_view prefix = "") noexcept;
```
- バックトレース情報を取得します
- 第1形式は結果をベクトルに格納します
- 第2形式はフォーマットされた文字列を返します

## 4. クラス

### 4.1 `Singleton`
```cpp
template <typename T, typename... Args>
class Singleton {
public:
    template <Args... args>
    static T& Instance() noexcept;
};
```
- シングルトンオブジェクトを管理するテンプレートクラス
- `Instance()` メソッドは静的なインスタンスにアクセスします

### 4.2 `SingletonPtr`
```cpp
template <typename T, typename... Args>
class SingletonPtr {
public:
    template <Args... args>
    static std::shared_ptr<T> Instance() noexcept;
};
```
- シングルトンオブジェクトを `std::shared_ptr` で管理するテンプレートクラス

### 4.3 `RAII`
```cpp
template <typename T, typename Cleaner = std::function<void(T)>>
requires std::is_invocable_v<Cleaner, T>
class RAII {
public:
    explicit RAII(T obj, Cleaner cleaner) noexcept;
    // コピーとムーブを禁止
    ~RAII() noexcept;

    const T& Object() const noexcept;
private:
    T obj_;
    Cleaner cleaner_;
};
```
- リソース管理のためのRAIIクラス
- オブジェクトが破棄されるときにクリーンアップ関数が呼び出されます

### 4.4 `MappedReadOnlyFile`
```cpp
class MappedReadOnlyFile {
public:
    MappedReadOnlyFile() noexcept;
    // コピーを禁止、ムーブをサポート
    ~MappedReadOnlyFile() noexcept;

    std::byte* Map(std::string path);
    void Unmap() noexcept;

    std::size_t Size() const noexcept;
    std::byte* Data() const noexcept;
    std::string_view Path() const noexcept;

private:
    void Check();
    std::string path_;
    struct stat stat_ {};
    std::byte* data_ {nullptr};
};
```
- ファイルを読み取り専用でメモリにマッピングするクラス
- `Map()` でファイルをマップし、`Unmap()` で解放します

## 5. コンセプト

### 5.1 `Addable`
```cpp
template <typename T, typename U, typename Ret = T>
concept Addable = requires(T t, U u) {
    { t + u } -> std::convertible_to<Ret>;
};
```
- 二つの型が加算可能かどうかを判定するコンセプト

## 6. 実装注意事項

1. **例外安全性**: 関数は適切な例外処理を行います
2. **非破壊操作**: 文字列操作関数は入力を変更せず、新しい文字列を返します
3. **リソース管理**: RAII原則に従い、リソースの適切な解放が行われます
4. **システムエラー**: システムコールの失敗は `ThrowLastSystemError()` で処理されます

## 7. エラーハンドリング

- システムエラー: `std::system_error` をスローします
- YAMLパースエラー: `std::invalid_argument` をスローします
- ファイルアクセスエラー: `std::runtime_error` または `std::invalid_argument` をスローします

## 8. 非推奨機能

このライブラリには明示的な非推奨機能はありませんが、将来のバージョンで変更される可能性があります。

## 9. 互換性要件

- C++20以上を要求します
- POSIXシステムコールに依存しています（Linux/Unix環境で動作します）

この設計仕様書は、与えられたソースコードの完全な再実装を行うためのガイドラインとして使用できます。