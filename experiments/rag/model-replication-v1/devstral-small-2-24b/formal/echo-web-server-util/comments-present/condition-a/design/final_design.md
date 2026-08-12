以下は、与えられたC++ソースコードを解析し、別のLLMが再実装できるように設計仕様書を作成したものです。この仕様書では、入力から確認できない情報は推測せず、Fxx/Uxx識別子や名前空間などの構造を保持しています。

---

# 設計仕様書

## 1. 概要
この仕様書は、`util.h`と`util.cpp`からなるユーティリティライブラリの再実装のための設計仕様です。このライブラリには、文字列操作、YAMLパース、ファイルディスクリプタ操作、スレッドID取得、バックトレース取得、シンギルトンパターン、RAII管理などの機能が含まれています。

## 2. 名前空間
すべての関数とクラスは`ws`名前空間内に定義されます。

```cpp
namespace ws {
    // 関数とクラスの定義
}
```

## 3. 型定義
### FileDescriptor
ファイルディスクリプタを表す型です。`int`型を使用します。

```cpp
using FileDescriptor = int;
```

### invalid_file_descriptor
無効なファイルディスクリプタを表す定数です。

```cpp
inline constexpr FileDescriptor invalid_file_descriptor {-1};
```

## 4. 関数仕様

### 文字列操作関数
#### StringToLower
入力文字列を小文字に変換します。

```cpp
std::string StringToLower(std::string str) noexcept;
```

#### StringToUpper
入力文字列を大文字に変換します。

```cpp
std::string StringToUpper(std::string str) noexcept;
```

#### ReplaceAllSubstring
文字列内の特定の部分文字列を置き換えます。

```cpp
std::string ReplaceAllSubstring(std::string_view str, std::string_view from,
                                std::string_view to) noexcept;
```

#### SplitString
正規表現パターンで文字列を分割します。

```cpp
std::vector<std::string> SplitString(const std::string& str,
                                     const std::regex& pattern) noexcept;
```

#### SplitStringToLines
改行コードで文字列を分割します。

```cpp
std::vector<std::string> SplitStringToLines(const std::string& str) noexcept;
```

### YAML操作関数
#### LoadYamlString
YAML文字列をパースし、必要なフィールドが存在するか確認します。

```cpp
YAML::Node LoadYamlString(
    std::string_view str,
    std::initializer_list<std::string_view> required_fields = {});
```

#### ThrowIfYamlFieldIsNotScalar
YAMLノード内のフィールドがスカラー値であるか確認し、そうでない場合は例外を投げます。

```cpp
void ThrowIfYamlFieldIsNotScalar(const YAML::Node& node,
                                 std::string_view field);
```

### ファイルディスクリプタ操作関数
#### IsValidFileDescriptor
ファイルディスクリプタが有効か確認します。

```cpp
constexpr bool IsValidFileDescriptor(FileDescriptor fd) noexcept;
```

#### SetFileDescriptorAsNonblocking
ファイルディスクリプタを非ブロックモードに設定します。

```cpp
void SetFileDescriptorAsNonblocking(FileDescriptor fd);
```

### システム関数
#### ThrowLastSystemError
最後のシステムエラーを`std::system_error`として投げます。

```cpp
[[noreturn]] void ThrowLastSystemError();
```

#### CurrentThreadId
現在のスレッドIDを取得します。

```cpp
std::uint32_t CurrentThreadId() noexcept;
```

### バックトレース関数
#### Backtrace (vector版)
バックトレース情報を`std::vector<std::string>`に格納します。

```cpp
void Backtrace(std::vector<std::string>& stack, std::size_t size,
               std::size_t skip = 0) noexcept;
```

#### Backtrace (string版)
バックトレース情報を文字列として取得します。

```cpp
std::string Backtrace(std::size_t size, std::size_t skip = 0,
                      std::string_view prefix = "") noexcept;
```

## 5. クラス仕様

### Singleton
シンギルトンパターンの実装です。参照を返します。

```cpp
template <typename T, typename... Args>
class Singleton {
public:
    template <Args... args>
    static T& Instance() noexcept;
};
```

### SingletonPtr
シンギルトンパターンの実装です。スマートポインタを返します。

```cpp
template <typename T, typename... Args>
class SingletonPtr {
public:
    template <Args... args>
    static std::shared_ptr<T> Instance() noexcept;
};
```

### RAII
リソース管理のためのRAIIクラスです。

```cpp
template <typename T, typename Cleaner = std::function<void(T)>>
requires std::is_invocable_v<Cleaner, T>
class RAII {
public:
    explicit RAII(T obj, Cleaner cleaner) noexcept;
    ~RAII() noexcept;
    const T& Object() const noexcept;
private:
    T obj_;
    Cleaner cleaner_;
};
```

### MappedReadOnlyFile
ファイルをメモリにマップするためのRAIIクラスです。

```cpp
class MappedReadOnlyFile {
public:
    MappedReadOnlyFile() noexcept;
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

## 6. コンセプト
### Addable
二つの型が加算可能かを確認するコンセプトです。

```cpp
template <typename T, typename U, typename Ret = T>
concept Addable = requires(T t, U u) {
    { t + u } -> std::convertible_to<Ret>;
};
```

## 7. 依存関係
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

## 8. 注意事項
- `fmt`は将来的にC++20の`format`に置き換える予定です。
- `MappedReadOnlyFile`クラスはLinuxシステムコールを使用しています。

---

この仕様書を基に、別のLLMが再実装を行うことができます。必要な場合は、具体的な実装例も提供できます。