# 設計文書

## 1. 概要と責務

### 概要
`util.h`と`util.cpp`は、様々なユーティリティ関数やクラスを提供するモジュールです。文字列操作、ファイルディスクリプタの管理、シングルトンパターンの実装、RAII（Resource Acquisition Is Initialization）パターンの実装などが含まれます。

### 責務
- 文字列変換と操作：大文字小文字変換、部分文字列置き換え、分割など。
- YAMLデータの読み込みと検証。
- ファイルディスクリプタの非ブロッキングモードへの設定。
- スレッドIDの取得。
- 呼び出し元プログラムのバックトレース情報の取得。
- シングルトンパターンの実装。
- RAIIパターンの実装。
- 読み取り専用ファイルのメモリマッピング。

## 2. 構造図

```mermaid
classDiagram
    class Singleton {
        +static T& Instance() noexcept
    }
    
    class SingletonPtr {
        +static std::shared_ptr<T> Instance() noexcept
    }

    class RAII {
        -T obj_
        -Cleaner cleaner_
        +RAII(T obj, Cleaner cleaner) noexcept
        +const T& Object() const noexcept
    }

    class MappedReadOnlyFile {
        -std::string path_
        -struct stat stat_ {}
        -std::byte* data_ {nullptr}
        +MappedReadOnlyFile() noexcept
        +MappedReadOnlyFile(MappedReadOnlyFile&&) noexcept
        +MappedReadOnlyFile& operator=(MappedReadOnlyFile&&) noexcept
        +~MappedReadOnlyFile() noexcept
        +std::byte* Map(std::string path)
        +void Unmap() noexcept
        +std::size_t Size() const noexcept
        +std::byte* Data() const noexcept
        +std::string_view Path() const noexcept
    }
```

## 3. インターフェースと依存関係

### 公開インターフェース

#### 文字列操作
- `StringToLower(std::string str) noexcept`
  - 引数: `str` (std::string, 変換したい文字列)
  - 戻り値: std::string (小文字に変換された文字列)

- `StringToUpper(std::string str) noexcept`
  - 引数: `str` (std::string, 変換したい文字列)
  - 戻り値: std::string (大文字に変換された文字列)

- `ReplaceAllSubstring(std::string_view str, std::string_view from, std::string_view to) noexcept`
  - 引数: 
    - `str` (std::string_view, 対象文字列)
    - `from` (std::string_view, 置き換え元の部分文字列)
    - `to` (std::string_view, 置き換え後の部分文字列)
  - 戻り値: std::string (置き換えた結果の文字列)

- `SplitString(const std::string& str, const std::regex& pattern) noexcept`
  - 引数: 
    - `str` (const std::string&, 対象文字列)
    - `pattern` (const std::regex&, 分割パターン)
  - 戻り値: std::vector<std::string> (分割された文字列のリスト)

- `SplitStringToLines(const std::string& str) noexcept`
  - 引数: `str` (const std::string&, 対象文字列)
  - 戻り値: std::vector<std::string> (行ごとに分割された文字列のリスト)

#### YAML操作
- `LoadYamlString(std::string_view str, std::initializer_list<std::string_view> required_fields = {})`
  - 引数: 
    - `str` (std::string_view, YAML形式の文字列)
    - `required_fields` (std::initializer_list<std::string_view>, 必須フィールドリスト)
  - 戻り値: YAML::Node (YAMLノード)

- `ThrowIfYamlFieldIsNotScalar(const YAML::Node& node, std::string_view field)`
  - 引数: 
    - `node` (const YAML::Node&, YAMLノード)
    - `field` (std::string_view, フィールド名)
  - 戻り値: void

#### ファイルディスクリプタ操作
- `IsValidFileDescriptor(FileDescriptor fd) noexcept`
  - 引数: `fd` (FileDescriptor, ファイルディスクリプタ)
  - 戻り値: bool (ファイルディスクリプタが有効かどうか)

- `SetFileDescriptorAsNonblocking(FileDescriptor fd)`
  - 引数: `fd` (FileDescriptor, ファイルディスクリプタ)
  - 戻り値: void

#### スレッド操作
- `CurrentThreadId() noexcept`
  - 引数: 無し
  - 戻り値: std::uint32_t (現在のスレッドID)

#### バックトレース取得
- `Backtrace(std::vector<std::string>& stack, std::size_t size, std::size_t skip = 0) noexcept`
  - 引数: 
    - `stack` (std::vector<std::string>&, スタックトレースを格納するベクター)
    - `size` (std::size_t, 最大取得サイズ)
    - `skip` (std::size_t, 無視するスタックフレーム数)
  - 戻り値: void

- `Backtrace(std::size_t size, std::size_t skip = 0, std::string_view prefix = "") noexcept`
  - 引数: 
    - `size` (std::size_t, 最大取得サイズ)
    - `skip` (std::size_t, 無視するスタックフレーム数)
    - `prefix` (std::string_view, 各行のプレフィックス)
  - 戻り値: std::string (バックトレース情報)

#### シングルトンパターン
- `Singleton<T, Args...>::Instance<args...>() noexcept`
  - 引数: 無し（テンプレートパラメータとしてコンストラクタ引数）
  - 戻り値: T& (シングルトンインスタンスへの参照)

- `SingletonPtr<T, Args...>::Instance<args...>() noexcept`
  - 引数: 無し（テンプレートパラメータとしてコンストラクタ引数）
  - 戻り値: std::shared_ptr<T> (シングルトンインスタンスへのスマートポインタ)

#### RAIIパターン
- `RAII<T, Cleaner>::RAII(T obj, Cleaner cleaner) noexcept`
  - 引数: 
    - `obj` (T, 管理するオブジェクト)
    - `cleaner` (Cleaner, クリーナー関数)
  - 戻り値: void

- `RAII<T, Cleaner>::Object() const noexcept`
  - 引数: 無し
  - 戻り値: const T& (管理するオブジェクトへの参照)

#### メモリマップファイル操作
- `MappedReadOnlyFile::MappedReadOnlyFile() noexcept`
  - 引数: 無し
  - 戻り値: void

- `MappedReadOnlyFile::MappedReadOnlyFile(MappedReadOnlyFile&&) noexcept`
  - 引数: MappedReadOnlyFile (ムーブコンストラクタ)
  - 戻り値: void

- `MappedReadOnlyFile& MappedReadOnlyFile::operator=(MappedReadOnlyFile&&) noexcept`
  - 引数: MappedReadOnlyFile (ムーブ代入演算子)
  - 戻り値: MappedReadOnlyFile& (自分自身への参照)

- `MappedReadOnlyFile::~MappedReadOnlyFile() noexcept`
  - 引数: 無し
  - 戻り値: void

- `std::byte* MappedReadOnlyFile::Map(std::string path)`
  - 引数: `path` (std::string, マッピングするファイルパス)
  - 戻り値: std::byte* (マップされたデータへのポインタ)

- `void MappedReadOnlyFile::Unmap() noexcept`
  - 引数: 無し
  - 戻り値: void

- `std::size_t MappedReadOnlyFile::Size() const noexcept`
  - 引数: 無し
  - 戻り値: std::size_t (ファイルサイズ)

- `std::byte* MappedReadOnlyFile::Data() const noexcept`
  - 引数: 無し
  - 戻り値: std::byte* (マップされたデータへのポインタ)

- `std::string_view MappedReadOnlyFile::Path() const noexcept`
  - 引数: 無し
  - 戻り値: std::string_view (ファイルパス)

### 実装上の処理

#### 文字列操作
- `StringToLower`, `StringToUpper`: `std::ranges::transform`を使用して文字列の各要素を変換する。
- `ReplaceAllSubstring`: `std::ostringstream`と`std::string_view::find`を使用して部分文字列を置き換える。
- `SplitString`: `std::sregex_token_iterator`を使用して正規表現にマッチしない部分で分割する。
- `SplitStringToLines`: `\r*\n`のパターンで行ごとに分割する。

#### YAML操作
- `LoadYamlString`: `YAML::Load`を使用して文字列からYAMLノードを作成し、必須フィールドが存在することを確認する。
- `ThrowIfYamlFieldIsNotScalar`: 指定されたフィールドがスカラーであることを確認し、そうでない場合は例外を投げる。

#### ファイルディスクリプタ操作
- `SetFileDescriptorAsNonblocking`: `fcntl`を使用してファイルディスクリプタを非ブロッキングモードに設定する。
- `ThrowLastSystemError`: 最後のシステムエラー情報を元に`std::system_error`を投げる。

#### スレッド操作
- `CurrentThreadId`: `syscall(SYS_gettid)`を使用して現在のスレッドIDを取得する。

#### バックトレース取得
- `Backtrace(std::vector<std::string>&, std::size_t, std::size_t)`: `backtrace`と`backtrace_symbols`を使用してバックトレース情報を取得し、指定された数だけスタックフレームを無視する。
- `Backtrace(std::size_t, std::size_t, std::string_view)`: バックトレース情報を文字列として返す。

#### シングルトンパターン
- `Singleton<T, Args...>::Instance<args...>()`: 静的ローカル変数を使用してシングルトンインスタンスを作成する。
- `SingletonPtr<T, Args...>::Instance<args...>()`: スマートポインタを使用してシングルトンインスタンスを作成する。

#### RAIIパターン
- `RAII<T, Cleaner>::RAII(T obj, Cleaner cleaner)`: オブジェクトとクリーナー関数を保持し、デストラクタでクリーナー関数を呼び出す。
- `RAII<T, Cleaner>::Object()`: 保持しているオブジェクトへの参照を返す。

#### メモリマップファイル操作
- `MappedReadOnlyFile::Map(std::string)`: ファイルの存在とアクセス権限を確認し、`mmap`を使用してファイルをメモリにマッピングする。
- `MappedReadOnlyFile::Unmap()`: マッピングされたデータを解放する。

## 4. 処理フロー図

### ReplaceAllSubstring
```mermaid
flowchart TD
    A[開始] --> B{str.empty()?}
    B --はい--> C[return ss.str()]
    B --いいえ--> D[str.find(from)]
    D --> E[ss << str.substr(0, begin)]
    F[begin != std::string_view::npos?] --> G[ss << to]
    F --いいえ--> H[break]
    F --はい--> I[str = str.substr(begin + from.length())]
    G --> J[D]
    H --> C
    I --> D
```

### LoadYamlString
```mermaid
flowchart TD
    A[開始] --> B[YAML::Load(str.data())]
    B --> C[node]
    D[required_fieldsの各要素に対して]
    E{node[field.data()]?}
    F{node[field.data()].IsScalar()?}
    G[throw std::invalid_argument]
    H[return node]
    D --> E
    E --いいえ--> G
    E --はい--> F
    F --いいえ--> G
    F --はい--> D
    D --> H
```

### SetFileDescriptorAsNonblocking
```mermaid
flowchart TD
    A[開始] --> B{IsValidFileDescriptor(fd)?}
    C[fcntl(fd, F_SETFL, fcntl(fd, F_GETFD) | O_NONBLOCK)]
    D{C < 0?}
    E[ThrowLastSystemError()]
    F[return]
    B --いいえ--> G[assert(false)]
    B --はい--> C
    C --> D
    D --いいえ--> F
    D --はい--> E
```

### Backtrace(std::vector<std::string>&, std::size_t, std::size_t)
```mermaid
flowchart TD
    A[開始] --> B[std::unique_ptr<VoidPtr[]> buffer {new VoidPtr[size]}]
    C[backtrace(buffer.get(), size)]
    D{ret_size > 0?}
    E[backtrace_symbols(buffer.get(), ret_size)]
    F[stack.push_back(stack_strs[i])]
    G[free(stack_strs)]
    H[return]
    C --> D
    D --いいえ--> H
    D --はい--> E
    E --> F
    F --> F
    F --> G
    G --> H
```

### MappedReadOnlyFile::Map(std::string)
```mermaid
flowchart TD
    A[開始] --> B[Unmap()]
    C[path_ = std::move(path)]
    D[Check()]
    E{open(path_.c_str(), O_RDONLY)}
    F{IsValidFileDescriptor(fd)?}
    G[mmap(nullptr, stat_.st_size, PROT_READ, MAP_PRIVATE, fd.Object(), 0)]
    H{map_base != MAP_FAILED?}
    I[data_ = static_cast<std::byte*>(map_base)]
    J[return data_]
    K[ThrowLastSystemError()]
    L[return nullptr]
    A --> C
    C --> D
    D --> E
    E --> F
    F --いいえ--> K
    F --はい--> G
    G --> H
    H --いいえ--> K
    H --はい--> I
    I --> J
```

## 5. シーケンス図

該当なし  
理由: 元コードから複数の関数、メソッド、オブジェクト間の呼び出し順序を直接確認できない。

## 6. 関数・メソッド仕様書

### StringToLower
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::StringToLower` |
| 目的 | 文字列を小文字に変換する。 |
| 引数 | `str` (std::string, 変換したい文字列) |
| 戻り値 | std::string (小文字に変換された文字列) |
| 前提条件 | 無し |
| 事後条件 | 返される文字列はすべて小文字である。 |
| 動作の説明 | `std::ranges::transform`を使用して各要素を小文字に変換する。 |
| 状態変更・副作用 | 入力文字列が変更されない。 |
| 依存関係 | std::string, std::ranges::transform, std::tolower |
| 境界条件 | 空文字列の場合は空文字列を返す。 |
| エラー処理 | 明示的なエラー処理は確認できない。 |
| 不変条件 | 入力文字列の長さが変わらない。 |

### StringToUpper
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::StringToUpper` |
| 目的 | 文字列を大文字に変換する。 |
| 引数 | `str` (std::string, 変換したい文字列) |
| 戻り値 | std::string (大文字に変換された文字列) |
| 前提条件 | 無し |
| 事後条件 | 返される文字列はすべて大文字である。 |
| 動作の説明 | `std::ranges::transform`を使用して各要素を大文字に変換する。 |
| 状態変更・副作用 | 入力文字列が変更されない。 |
| 依存関係 | std::string, std::ranges::transform, std::toupper |
| 境界条件 | 空文字列の場合は空文字列を返す。 |
| エラー処理 | 明示的なエラー処理は確認できない。 |
| 不変条件 | 入力文字列の長さが変わらない。 |

### ReplaceAllSubstring
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::ReplaceAllSubstring` |
| 目的 | 文字列内の部分文字列を指定された文字列に置き換える。 |
| 引数 | 
  - `str` (std::string_view, 対象文字列)
  - `from` (std::string_view, 置き換え元の部分文字列)
  - `to` (std::string_view, 置き換え後の部分文字列) |
| 戻り値 | std::string (置き換えた結果の文字列) |
| 前提条件 | 無し |
| 事後条件 | 返される文字列は指定された部分文字列が置き換えられたものである。 |
| 動作の説明 | `std::ostringstream`と`std::string_view::find`を使用して部分文字列を置き換える。 |
| 状態変更・副作用 | 入力文字列が変更されない。 |
| 依存関係 | std::string, std::string_view, std::ostringstream, std::string_view::find, std::string_view::substr |
| 境界条件 | 
  - `from`が空文字列の場合は元の文字列を返す。
  - `str`が空文字列の場合は空文字列を返す。 |
| エラー処理 | 明示的なエラー処理は確認できない。 |
| 不変条件 | 入力文字列の長さが変わらない。 |

### SplitString
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::SplitString` |
| 目的 | 文字列を指定された正規表現パターンで分割する。 |
| 引数 | 
  - `str` (const std::string&, 対象文字列)
  - `pattern` (const std::regex&, 分割パターン) |
| 戻り値 | std::vector<std::string> (分割された文字列のリスト) |
| 前提条件 | 無し |
| 事後条件 | 返されるベクターは指定されたパターンで分割された文字列を含む。 |
| 動作の説明 | `std::sregex_token_iterator`を使用して正規表現にマッチしない部分で分割する。 |
| 状態変更・副作用 | 入力文字列が変更されない。 |
| 依存関係 | std::string, std::vector, std::regex, std::sregex_token_iterator, std::back_inserter |
| 境界条件 | 
  - `pattern`にマッチしない部分がない場合は、元の文字列を含むベクターが返される。
  - `str`が空文字列の場合は空のベクターが返される。 |
| エラー処理 | 明示的なエラー処理は確認できない。 |
| 不変条件 | 入力文字列の長さが変わらない。 |

### SplitStringToLines
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::SplitStringToLines` |
| 目的 | 文字列を行ごとに分割する。 |
| 引数 | `str` (const std::string&, 対象文字列) |
| 戻り値 | std::vector<std::string> (行ごとに分割された文字列のリスト) |
| 前提条件 | 無し |
| 事後条件 | 返されるベクターは改行コードで分割された文字列を含む。 |
| 動作の説明 | `\r*\n`のパターンで行ごとに分割する。 |
| 状態変更・副作用 | 入力文字列が変更されない。 |
| 依存関係 | std::string, std::vector, std::regex, ws::SplitString |
| 境界条件 | 
  - 改行コードがない場合は、元の文字列を含むベクターが返される。
  - `str`が空文字列の場合は空のベクターが返される。 |
| エラー処理 | 明示的なエラー処理は確認できない。 |
| 不変条件 | 入力文字列の長さが変わらない。 |

### LoadYamlString
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::LoadYamlString` |
| 目的 | YAML形式の文字列からノードを作成し、必須フィールドが存在することを確認する。 |
| 引数 | 
  - `str` (std::string_view, YAML形式の文字列)
  - `required_fields` (std::initializer_list<std::string_view>, 必須フィールドリスト) |
| 戻り値 | YAML::Node (YAMLノード) |
| 前提条件 | 無し |
| 事後条件 | 返されるノードは指定された必須フィールドを含む。 |
| 動作の説明 | `YAML::Load`を使用して文字列からYAMLノードを作成し、必須フィールドが存在することを確認する。 |
| 状態変更・副作用 | 入力文字列が変更されない。 |
| 依存関係 | std::string_view, YAML::Node, YAML::Load, std::initializer_list, std::ranges::for_each, fmt::format, std::invalid_argument |
| 境界条件 | 
  - `required_fields`が空の場合は、YAMLノードが返される。
  - `str`が空文字列の場合は例外を投げる。 |
| エラー処理 | 必須フィールドが存在しない場合やスカラーでない場合は`std::invalid_argument`を投げる。 |
| 不変条件 | 入力文字列の長さが変わらない。 |

### ThrowIfYamlFieldIsNotScalar
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::ThrowIfYamlFieldIsNotScalar` |
| 目的 | 指定されたフィールドがスカラーであることを確認し、そうでない場合は例外を投げる。 |
| 引数 | 
  - `node` (const YAML::Node&, YAMLノード)
  - `field` (std::string_view, フィールド名) |
| 戻り値 | void |
| 前提条件 | 無し |
| 事後条件 | 指定されたフィールドがスカラーである。 |
| 動作の説明 | 指定されたフィールドがスカラーであることを確認し、そうでない場合は例外を投げる。 |
| 状態変更・副作用 | 入力ノードやフィールド名が変更されない。 |
| 依存関係 | YAML::Node, std::string_view, fmt::format, std::invalid_argument |
| 境界条件 | 
  - 指定されたフィールドが存在しない場合は例外を投げる。
  - 指定されたフィールドがスカラーでない場合は例外を投げる。 |
| エラー処理 | フィールドが存在しない場合やスカラーでない場合は`std::invalid_argument`を投げる。 |
| 不変条件 | 入力ノードやフィールド名の状態が変わらない。 |

### IsValidFileDescriptor
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::IsValidFileDescriptor` |
| 目的 | ファイルディスクリプタが有効かどうかを確認する。 |
| 引数 | `fd` (FileDescriptor, ファイルディスクリプタ) |
| 戻り値 | bool (ファイルディスクリプタが有効かどうか) |
| 前提条件 | 無し |
| 事後条件 | 返されるブール値は指定されたファイルディスクリプタの有効性を表す。 |
| 動作の説明 | ファイルディスクリプタが0以上であることを確認する。 |
| 状態変更・副作用 | 入力ファイルディスクリプタが変更されない。 |
| 依存関係 | FileDescriptor, int |
| 境界条件 | 
  - ファイルディスクリプタが0以上の場合は`true`を返す。
  - ファイルディスクリプタが負の場合は`false`を返す。 |
| エラー処理 | 明示的なエラー処理は確認できない。 |
| 不変条件 | 入力ファイルディスクリプタの値が変わらない。 |

### SetFileDescriptorAsNonblocking
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::SetFileDescriptorAsNonblocking` |
| 目的 | ファイルディスクリプタを非ブロッキングモードに設定する。 |
| 引数 | `fd` (FileDescriptor, ファイルディスクリプタ) |
| 戻り値 | void |
| 前提条件 | 指定されたファイルディスクリプタが有効である。 |
| 事後条件 | 指定されたファイルディスクリプタは非ブロッキングモードに設定される。 |
| 動作の説明 | `fcntl`を使用してファイルディスクリプタを非ブロッキングモードに設定する。 |
| 状態変更・副作用 | 指定されたファイルディスクリプタが非ブロッキングモードに設定される。 |
| 依存関係 | FileDescriptor, fcntl, F_SETFL, F_GETFD, O_NONBLOCK, ws::ThrowLastSystemError |
| 境界条件 | 
  - 指定されたファイルディスクリプタが有効でない場合は`assert(false)`が発生する。
  - `fcntl`の呼び出しが失敗した場合は例外を投げる。 |
| エラー処理 | `fcntl`の呼び出しが失敗した場合は`ws::ThrowLastSystemError`を呼び出す。 |
| 不変条件 | 入力ファイルディスクリプタの値が変わらない。 |

### ThrowLastSystemError
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::ThrowLastSystemError` |
| 目的 | 最後のシステムエラー情報を元に例外を投げる。 |
| 引数 | 無し |
| 戻り値 | void |
| 前提条件 | 無し |
| 事後条件 | `std::system_error`が投げられる。 |
| 動作の説明 | 最後のシステムエラー情報を元に`std::system_error`を投げる。 |
| 状態変更・副作用 | 入力パラメータは変更されない。 |
| 依存関係 | std::system_error, errno, std::system_category |
| 境界条件 | 無し |
| エラー処理 | `std::system_error`を投げる。 |
| 不変条件 | 入力パラメータの状態が変わらない。 |

### CurrentThreadId
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::CurrentThreadId` |
| 目的 | 現在のスレッドIDを取得する。 |
| 引数 | 無し |
| 戻り値 | std::uint32_t (現在のスレッドID) |
| 前提条件 | 無し |
| 事後条件 | 返されるスレッドIDは現在のスレッドのものである。 |
| 動作の説明 | `syscall(SYS_gettid)`を使用して現在のスレッドIDを取得する。 |
| 状態変更・副作用 | 入力パラメータは変更されない。 |
| 依存関係 | std::uint32_t, syscall, SYS_gettid |
| 境界条件 | 無し |
| エラー処理 | 明示的なエラー処理は確認できない。 |
| 不変条件 | 入力パラメータの状態が変わらない。 |

### Backtrace(std::vector<std::string>&, std::size_t, std::size_t)
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::Backtrace` |
| 目的 | 呼び出し元プログラムのバックトレース情報を取得し、指定された数だけスタックフレームを無視する。 |
| 引数 | 
  - `stack` (std::vector<std::string>&, スタックトレースを格納するベクター)
  - `size` (std::size_t, 最大取得サイズ)
  - `skip` (std::size_t, 無視するスタックフレーム数) |
| 戻り値 | void |
| 前提条件 | 無し |
| 事後条件 | 指定されたベクターはバックトレース情報を含む。 |
| 動作の説明 | `backtrace`と`backtrace_symbols`を使用してバックトレース情報を取得し、指定された数だけスタックフレームを無視する。 |
| 状態変更・副作用 | 指定されたベクターが更新される。 |
| 依存関係 | std::vector, std::string, backtrace, backtrace_symbols, free |
| 境界条件 | 
  - `size`が0の場合はスタックトレース情報は取得されない。
  - `skip`がスタックフレーム数以上の場合はスタックトレース情報は取得されない。 |
| エラー処理 | 明示的なエラー処理は確認できない。 |
| 不変条件 | 入力パラメータの状態が変わらない。 |

### Backtrace(std::size_t, std::size_t, std::string_view)
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::Backtrace` |
| 目的 | 呼び出し元プログラムのバックトレース情報を文字列として返す。 |
| 引数 | 
  - `size` (std::size_t, 最大取得サイズ)
  - `skip` (std::size_t, 無視するスタックフレーム数)
  - `prefix` (std::string_view, 各行のプレフィックス) |
| 戻り値 | std::string (バックトレース情報) |
| 前提条件 | 無し |
| 事後条件 | 返される文字列はバックトレース情報を含む。 |
| 動作の説明 | `ws::Backtrace`を使用してバックトレース情報を取得し、指定されたプレフィックスを各行に付加する。 |
| 状態変更・副作用 | 入力パラメータは変更されない。 |
| 依存関係 | std::size_t, std::string_view, ws::Backtrace, std::ostringstream |
| 境界条件 | 
  - `size`が0の場合は空文字列を返す。
  - `skip`がスタックフレーム数以上の場合は空文字列を返す。 |
| エラー処理 | 明示的なエラー処理は確認できない。 |
| 不変条件 | 入力パラメータの状態が変わらない。 |

### Singleton<T, Args...>::Instance<args...>()
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::Singleton<T, Args...>::Instance<args...>()` |
| 目的 | シングルトンインスタンスを取得する。 |
| 引数 | 無し（テンプレートパラメータとしてコンストラクタ引数） |
| 戻り値 | T& (シングルトンインスタンスへの参照) |
| 前提条件 | 無し |
| 事後条件 | 返される参照はシングルトンインスタンスである。 |
| 動作の説明 | 静的ローカル変数を使用してシングルトンインスタンスを作成する。 |
| 状態変更・副作用 | シングルトンインスタンスが作成される場合がある。 |
| 依存関係 | T, Args... |
| 境界条件 | 無し |
| エラー処理 | 明示的なエラー処理は確認できない。 |
| 不変条件 | シングルトンインスタンスの状態が変わらない。 |

### SingletonPtr<T, Args...>::Instance<args...>()
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::SingletonPtr<T, Args...>::Instance<args...>()` |
| 目的 | シングルトンインスタンスをスマートポインタとして取得する。 |
| 引数 | 無し（テンプレートパラメータとしてコンストラクタ引数） |
| 戻り値 | std::shared_ptr<T> (シングルトンインスタンスへのスマートポインタ) |
| 前提条件 | 無し |
| 事後条件 | 返されるスマートポインタはシングルトンインスタンスを指す。 |
| 動作の説明 | スマートポインタを使用してシングルトンインスタンスを作成する。 |
| 状態変更・副作用 | シングルトンインスタンスが作成される場合がある。 |
| 依存関係 | T, Args..., std::shared_ptr, std::make_shared |
| 境界条件 | 無し |
| エラー処理 | 明示的なエラー