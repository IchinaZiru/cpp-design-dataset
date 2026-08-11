## util.h 詳細設計仕様書 (F01/U01)

### 1. 正確な定義

| 型名 / 種別 / 実体 | 説明 |
|---|---|
| `FileDescriptor` / `typedef` / `int` | ファイルディスクリプタの型。 |
| `invalid_file_descriptor` / `constexpr` / `int {-1}` | 無効なファイルディスクリプタを示す定数。 |

### 2. 直接依存インターフェースと利用方法

#### ヘッダーファイル

*   `<fmt/format.h>`: フォーマット済み出力機能を提供。
*   `<yaml-cpp/yaml.h>`: YAMLパーサライブラリ。
*   `<sys/stat.h>`: ファイルステータス関連の関数と型を提供。
*   `<concepts>`: C++20 conceptsをサポート。
*   `<functional>`: 関数オブジェクト、`std::function`などを提供。
*   `<initializer_list>`: 初期化リストをサポート。
*   `<memory>`: スマートポインタ (`std::shared_ptr`) を提供。
*   `<regex>`: 正規表現をサポート。
*   `<string>`: 文字列操作機能を提供。
*   `<string_view>`: 文字列への軽量な参照を提供。
*   `<utility>`: `std::pair`、`std::move`などを提供。
*   `<vector>`: 動的配列 (`std::vector`) を提供。

#### 関数・メソッド

| qualified name | 引数 | 戻り値型 | 可視性 | const | noexcept | 説明 |
|---|---|---|---|---|---|---|
| `ws::StringToLower(std::string str)` | `str` (std::string) | std::string | public |  | yes | 文字列を小文字に変換。 |
| `ws::StringToUpper(std::string str)` | `str` (std::string) | std::string | public |  | yes | 文字列を大文字に変換。 |
| `ws::ReplaceAllSubstring(std::string_view str, std::string_view from, std::string_view to)` | `str`, `from`, `to` (std::string_view) | std::string | public |  | yes | 文字列内のすべての部分文字列を置換。 |
| `ws::SplitString(const std::string& str, const std::regex& pattern)` | `str` (const std::string&), `pattern` (const std::regex&) | std::vector<std::string> | public |  | yes | 正規表現パターンで文字列を分割。 |
| `ws::SplitStringToLines(const std::string& str)` | `str` (const std::string&) | std::vector<std::string> | public |  | yes | 文字列を行に分割。 |
| `ws::LoadYamlString(std::string_view str, std::initializer_list<std::string_view> required_fields)` | `str` (std::string_view), `required_fields` (std::initializer_list<std::string_view>) | YAML::Node | public |  |  | YAML文字列をロードし、必須フィールドが存在するか確認。 |
| `ws::ThrowIfYamlFieldIsNotScalar(const YAML::Node& node, std::string_view field)` | `node` (const YAML::Node&), `field` (std::string_view) | void | public |  |  | YAMLノードのフィールドがスカラーでない場合に例外をスロー。 |
| `ws::IsValidFileDescriptor(FileDescriptor fd)` | `fd` (FileDescriptor) | bool | public / constexpr |  | yes | ファイルディスクリプタが有効かどうかを確認。 |
| `ws::SetFileDescriptorAsNonblocking(FileDescriptor fd)` | `fd` (FileDescriptor) | void | public |  |  | ファイルディスクリプタをノンブロッキングに設定。 |
| `ws::ThrowLastSystemError()` | なし | void | public / noreturn |  |  | 最後のシステムエラーで例外をスロー。 |
| `ws::CurrentThreadId()` | なし | std::uint32_t | public / noexcept |  | yes | 現在のスレッドIDを取得。 |
| `ws::Backtrace(std::vector<std::string>& stack, std::size_t size, std::size_t skip)` | `stack` (std::vector<std::string>&), `size` (std::size_t), `skip` (std::size_t) | void | public / noexcept |  | yes | コールスタックを取得。 |
| `ws::Backtrace(std::size_t size, std::size_t skip, std::string_view prefix)` | `size` (std::size_t), `skip` (std::size_t), `prefix` (std::string_view) | std::string | public / noexcept |  | yes | コールスタックを取得し、文字列として返す。 |

#### テンプレートクラス

*   `ws::Singleton<T, Args...>`: シングルトンパターンを実装するためのインターフェース。
    *   `Instance()`: シングルトンインスタンスを取得。
*   `ws::SingletonPtr<T, Args...>`: スマートポインタを使用したシングルトンパターンを実装するためのインターフェース。
    *   `Instance()`: シングルトンインスタンスの `std::shared_ptr` を取得。
*   `ws::RAII<T, Cleaner>`: リソース管理のための RAII クラス。
    *   コンストラクタ: オブジェクトとクリーンアップ関数を受け取り、オブジェクトを初期化する。
    *   デストラクタ: クリーンアップ関数を実行してリソースを解放する。
    *   `Object()`: 管理対象のオブジェクトへのアクセスを提供する。
*   `ws::MappedReadOnlyFile`: メモリマップされた読み取り専用ファイルのためのクラス。
    *   コンストラクタ、ムーブコンストラクタ、代入演算子、デストラクタ
    *   `Map(std::string path)`: ファイルをメモリマップする。
    *   `Unmap()`: ファイルのマッピングを解除する。
    *   `Size()`: ファイルサイズを取得する。
    *   `Data()`: マップされたファイルデータへのポインタを取得する。
    *   `Path()`: ファイルパスを取得する。

### 3. 結果を決める式・具体値

*   `invalid_file_descriptor = -1`
*   `IsValidFileDescriptor(fd)` は `fd >= 0` を返す。
*   `Singleton::Instance()` は静的初期化によってインスタンスを作成。
*   `RAII` デストラクタは、クリーンアップ関数を呼び出してオブジェクトを解放。

### 4. 使用データ・更新データ

*   `MappedReadOnlyFile`: ファイルパス、ファイルステータス、マップされたメモリ領域。
    *   `Map()`: ファイルパスを受け取り、ファイルステータスとメモリ領域を初期化する。
    *   `Unmap()`: メモリ領域を解放し、ファイルステータスとファイルパスをクリアする。

### 5. 状態・副作用・不変条件

*   `SetFileDescriptorAsNonblocking()` はファイルディスクリプタの状態を変更する。
*   `ThrowLastSystemError()` は例外をスローするため、呼び出し元で適切なエラー処理が必要。
*   シングルトンクラスは、インスタンスのライフサイクル全体を通じて一貫した状態を維持する必要がある。

### 6. クラス図

```mermaid
classDiagram
    class ws::Singleton {
        +static T& Instance()
    }
    class ws::SingletonPtr {
        +static std::shared_ptr<T> Instance()
    }
    class ws::RAII {
        -T obj_
        -Cleaner cleaner_
        +RAII(T, Cleaner)
        +const T& Object()
    }
    class ws::MappedReadOnlyFile {
        -std::string path_
        -struct stat stat_
        -std::byte* data_
        +MappedReadOnlyFile()
        +MappedReadOnlyFile(MappedReadOnlyFile&&)
        +MappedReadOnlyFile& operator=(MappedReadOnlyFile&&)
        ~MappedReadOnlyFile()
        +std::byte* Map(std::string path)
        +void Unmap()
        +std::size_t Size()
        +std::byte* Data()
        +std::string_view Path()
    }
```

### 7. クラス・メソッド・インターフェース詳細

上記「2. 直接依存インターフェースと利用方法」の表を参照。

### 8. シーケンス図

該当なし (複雑な相互作用がないため)。

### 9. メソッド仕様書

上記「2. 直接依存インターフェースと利用方法」の表を参照。各メソッドについて、引数、戻り値、動作、副作用を記述。
