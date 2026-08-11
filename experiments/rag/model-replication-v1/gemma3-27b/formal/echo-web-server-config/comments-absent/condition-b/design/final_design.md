## 設計仕様書

### 全体概要

この設計仕様書は、`include/config.h` と `src/config/config.cpp` のソースコードを再実装するためのものです。これらのファイルは、設定値の管理と変換のための機能を提供します。特に、YAML形式の設定ファイルを読み込み、様々な型に変換する機能が中心です。

### 1. 正確な定義

| 名前 | 種別 | 実体 |
|---|---|---|
| `FileDescriptor` | 型名 | `int` |
| `invalid_file_descriptor` | 定数 | `-1` |
| `ws::cfg::Singleton<T, Args...>::Instance()` | 関数 | 静的メソッド、テンプレート関数 |
| `ws::cfg::SingletonPtr<T, Args...>::Instance()` | 関数 | 静的メソッド、テンプレート関数 |
| `ws::cfg::RAII<T, Cleaner>` | クラス | テンプレートクラス |

### 2. 直接依存インターフェースと利用方法

*   **`fmt/format.h`**: 文字列フォーマット機能を提供します。`fmt::format()` 関数が使用されます。
*   **`yaml-cpp/yaml.h`**: YAMLの解析機能を提供します。`YAML::Node` クラスが使用され、YAMLファイルの読み込みと操作に使用されます。
*   **`<sys/stat.h>`**: ファイル情報の取得に使用されます。`struct stat` が使用されます。
*   **`<concepts>`**: C++20のコンセプト機能を使用します。
*   **`<functional>`**: 関数オブジェクト（ファンクタ）を扱います。`std::function`が使用されます。
*   **`<initializer_list>`**: 初期化リストを使用します。
*   **`<memory>`**: スマートポインタ(`std::shared_ptr`)を使用します。
*   **`<regex>`**: 正規表現を使用します。
*   **`<string>`**, **`<string_view>`**: 文字列操作に使用されます。
*   **`<utility>`**: `std::move`などのユーティリティ関数を提供します。
*   **`<vector>`**: 動的配列(`std::vector`)を使用します。

### 3. 結果を決める式・具体値

*   `IsValidFileDescriptor(fd)`:  `fd >= 0` の場合にtrueを返します。
*   `Singleton<T>::Instance()`: 静的メンバ変数 `ins` を初期化し、その参照を返します。
*   `SingletonPtr<T>::Instance()`: 静的メンバ変数 `ins` を初期化し、その共有ポインタを返します。

### 4. 使用データ・更新データ

*   `Var::val_`: 設定値を保持するプライベートメンバ変数です。`SetValue()` メソッドで更新されます。
*   `Config::vars_`:  設定変数のマップを保持するプライベートメンバ変数です。`Lookup()` メソッドで検索、追加されます。
*   `MappedReadOnlyFile::data_`: マッピングされたファイルのデータを指すポインタです。`Map()`メソッドで割り当てられ、`Unmap()`メソッドで解放されます。

### 5. 状態・副作用・不変条件

*   `Var::SetValue()`: 値が変更された場合に、登録されているリスナーに通知します。
*   `Config::Lookup()`:  設定変数が存在しない場合、新しい設定変数を作成し、マップに追加します。
*   `MappedReadOnlyFile`: ファイルをメモリマップするため、ファイルの内容は読み取り専用です。

### 6. クラス図

```mermaid
classDiagram
    class VarBase {
        - std::string name_
        - std::string description_
        + std::string_view Name()
        + std::string_view Description()
        + virtual std::string ToString() = 0
        + virtual void FromString(std::string_view str) = 0
    }

    class Var<T> {
        - T val_
        + std::string ToString()
        + void FromString(std::string_view str)
        + T GetValue()
        + void SetValue(const T& val)
    }

    class Config {
        - std::string name_
        - std::unordered_map<std::string, VarBase::Ptr> vars_
        + typename Var<T>::Ptr Lookup(const std::string_view name, const T& default_val, const std::string_view description = "")
        + typename Var<T>::Ptr Lookup(const std::string_view name) const
        + VarBase::Ptr LookupBase(std::string_view name) const
    }

    Var --|> VarBase
    Config o-- Var : has-a
```

### 7. クラス・メソッド・インターフェース詳細

| クラス/メソッド | 名前 | 引数 | 戻り値型 | 可視性 | その他 |
|---|---|---|---|---|---|
| `VarBase` | `Name()` | なし | `std::string_view` | public | const |
| `VarBase` | `Description()` | なし | `std::string_view` | public | const |
| `VarBase` | `ToString()` | なし | `std::string` | virtual public | abstract |
| `VarBase` | `FromString()` | `std::string_view str` | void | virtual public | abstract |
| `Var<T>` | `GetValue()` | なし | `T` | public | const |
| `Var<T>` | `SetValue()` | `const T& val` | void | public |  |
| `Config` | `Name()` | なし | `std::string_view` | public | const |
| `Config` | `Lookup(name, default_val, description)` | `std::string_view name`, `T default_val`, `std::string_view description` | `typename Var<T>::Ptr` | public | template |
| `Config` | `Lookup(name)` | `std::string_view name` | `typename Var<T>::Ptr` | public | template, const |
| `Config` | `LookupBase()` | `std::string_view name` | `VarBase::Ptr` | private | const |

### 8. シーケンス図

YAMLファイルの読み込みと設定値の取得のシーケンス:

```mermaid
sequenceDiagram
    participant Config
    participant YAMLNode
    participant Var<T>

    Config->>YAMLNode: LoadYamlString(str)
    activate YAMLNode
    YAMLNode-->>Config: YAML::Node
    deactivate YAMLNode
    loop for each node in root
        Config->>Config: LookupBase(key)
        activate Config
        Config-->>Config: VarBase::Ptr
        deactivate Config
        alt var is not null
            Config->>Var<T>: FromString(node.second.str())
        end
    end
```

### 9. メソッド仕様書

**`Var::SetValue()`**:

*   目的: 設定値を更新し、リスナーに通知します。
*   引数: `val`: 新しい設定値。
*   戻り値: なし。
*   副作用: リスナーが登録されている場合、リスナー関数が呼び出されます。

### 10. 処理フロー図

YAMLファイルの読み込み処理:

```mermaid
graph TD
    A[LoadYamlString(str)] --> B{IsMap()?};
    B -- Yes --> C{Iterate through nodes};
    C --> D[LookupBase(key)];
    D --> E{Var exists?};
    E -- Yes --> F[FromString(node.second.str())];
    E -- No --> G[Create new Var instance];
    G --> F;
    B -- No --> H[Throw exception];
```

### 11. 状態遷移・副作用

`Config`クラスは、内部の`vars_`マップの状態を保持します。`Lookup()`メソッドによって新しい変数が作成され、マップに追加されます。`LoadYaml()`メソッドは、YAMLファイルから読み込んだ値に基づいて既存または新規の変数の値を更新します。

### 12. データ変換・制約

*   YAML文字列 -> `std::string`
*   `std::string` -> `T` (VarConverterを使用)
*   型変換エラーが発生した場合、`std::invalid_argument`例外がスローされます。
*   YAMLファイルの形式が不正な場合、YAMLライブラリによって例外がスローされます。

