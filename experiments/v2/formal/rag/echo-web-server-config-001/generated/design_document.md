# 設計文書

## 1. 概要と責務

### 概要
このモジュールは、YAML形式の設定ファイルを読み取り、内部データ構造に変換し、その値を管理するための機能を提供します。

### 責務
- YAML形式の設定ファイルから設定情報を読み取る。
- 設定情報を内部データ構造（`Var<T>`）に格納する。
- 格納された設定情報へのアクセスと変更を提供する。
- 変数値の変化に対するリスナー機能を提供する。

## 2. 構造図

```mermaid
classDiagram
    class VarConverter~From, To~ {
        +To operator()(const From& val) const noexcept
    }
    
    class VarBase {
        +std::string_view Name() const noexcept
        +std::string_view Description() const noexcept
        +virtual std::string ToString() const noexcept = 0
        +virtual void FromString(std::string_view str) = 0
        -std::string name_
        -std::string description_
    }
    
    class Var~T, FromStr, ToStr~ {
        +std::string ToString() const noexcept override
        +void FromString(const std::string_view str) override
        +T GetValue() const noexcept
        +void SetValue(const T& val) noexcept
        +std::string_view TypeName() const noexcept
        +void RemoveListener(const std::uint64_t key) noexcept
        +std::uint64_t AddListener(OnChange listener) noexcept
        +void ClearListeners() noexcept
        -mutable std::shared_mutex mtx_
        -T val_
        -std::unordered_map~std::uint64_t, OnChange~ listeners_
    }
    
    class Config {
        +std::string_view Name() const noexcept
        +typename Var~T~::Ptr Lookup(const std::string_view name, const T& default_val, const std::string_view description = "") 
        +typename Var~T~::Ptr Lookup(const std::string_view name) const 
        +VarBase::Ptr LookupBase(std::string_view name) const noexcept
        +void LoadYaml(const YAML::Node& root)
        +void Visit(std::function~void(VarBase::Ptr)~ visitor) const noexcept
        -mutable std::shared_mutex mtx_
        -std::string name_
        -VarMap vars_
    }
    
    VarConverter <|-- VarConverter~From, To~
    VarConverter <|-- VarConverter~From, std::string~
    VarConverter <|-- VarConverter~std::string, std::string~
    VarConverter <|-- VarConverter~std::string, To~
    VarConverter <|-- VarConverter~std::string, std::list~T~~
    VarConverter <|-- VarConverter~std::list~T~, std::string~
    VarConverter <|-- VarConverter~std::string, std::vector~T~~
    VarConverter <|-- VarConverter~std::vector~T~, std::string~
    VarConverter <|-- VarConverter~std::string, std::set~T~~
    VarConverter <|-- VarConverter~std::set~T~, std::string~
    VarConverter <|-- VarConverter~std::string, std::unordered_set~T~~
    VarConverter <|-- VarConverter~std::unordered_set~T~, std::string~
    VarConverter <|-- VarConverter~std::string, std::map~std::string, T~~
    VarConverter <|-- VarConverter~std::map~std::string, T~, std::string~
    VarConverter <|-- VarConverter~std::string, std::unordered_map~std::string, T~~
    VarConverter <|-- VarConverter~std::unordered_map~std::string, T~, std::string~
    
    VarBase <|-- Var
    
    Config --> VarMap : contains >
    Config --> VarBase : uses >
```

## 3. インターフェースと依存関係

### 公開インターフェース

#### `VarConverter<From, To>`
- **完全な名前**: `ws::cfg::VarConverter<From, To>`
- **引数**:
  - `val`: 変換元の値 (`const From&`)
- **戻り値**: 変換後の値 (`To`)
- **修飾**: `noexcept`
- **使用するメンバ・型**: 無し
- **呼び出す関数・メソッド**: 無し
- **継承元**: 無し

#### `VarBase`
- **完全な名前**: `ws::cfg::VarBase`
- **公開メソッド**:
  - `Name()`: 変数名を取得 (`std::string_view`)
  - `Description()`: 変数の説明を取得 (`std::string_view`)
  - `ToString()`: 変数値を文字列に変換 (`virtual std::string`)
  - `FromString(std::string_view str)`: 文字列から変数値を設定 (`virtual void`)

#### `Var<T, FromStr, ToStr>`
- **完全な名前**: `ws::cfg::Var<T, FromStr, ToStr>`
- **公開メソッド**:
  - `ToString()`: 変数値を文字列に変換 (`std::string`)
  - `FromString(std::string_view str)`: 文字列から変数値を設定 (`void`)
  - `GetValue()`: 変数値を取得 (`T`)
  - `SetValue(const T& val)`: 変数値を設定 (`void`)
  - `TypeName()`: 型名を取得 (`std::string_view`)
  - `RemoveListener(const std::uint64_t key)`: リスナーを削除 (`void`)
  - `AddListener(OnChange listener)`: リスナーを追加 (`std::uint64_t`)
  - `ClearListeners()`: 全てのリスナーをクリア (`void`)

#### `Config`
- **完全な名前**: `ws::cfg::Config`
- **公開メソッド**:
  - `Name()`: 設定名を取得 (`std::string_view`)
  - `Lookup(const std::string_view name, const T& default_val, const std::string_view description = "")`: 変数を探すまたは作成 (`typename Var<T>::Ptr`)
  - `Lookup(const std::string_view name) const`: 変数を探す (`typename Var<T>::Ptr`)
  - `LookupBase(std::string_view name) const`: 基本情報の変数を探す (`VarBase::Ptr`)
  - `LoadYaml(const YAML::Node& root)`: YAMLノードから設定を読み込む (`void`)
  - `Visit(std::function<void(VarBase::Ptr)> visitor) const`: 全ての変数を訪問 (`void`)

### 実装上の処理

#### `VarConverter<From, To>`
- **完全な名前**: `ws::cfg::VarConverter<From, To>`
- **引数**:
  - `val`: 変換元の値 (`const From&`)
- **戻り値**: 変換後の値 (`To`)
- **修飾**: `noexcept`
- **使用するメンバ・型**: 無し
- **呼び出す関数・メソッド**: 無し
- **継承元**: 無し

#### `VarBase`
- **完全な名前**: `ws::cfg::VarBase`
- **公開メソッド**:
  - `Name()`: 変数名を取得 (`std::string_view`)
  - `Description()`: 変数の説明を取得 (`std::string_view`)
  - `ToString()`: 変数値を文字列に変換 (`virtual std::string`)
  - `FromString(std::string_view str)`: 文字列から変数値を設定 (`virtual void`)

#### `Var<T, FromStr, ToStr>`
- **完全な名前**: `ws::cfg::Var<T, FromStr, ToStr>`
- **公開メソッド**:
  - `ToString()`: 変数値を文字列に変換 (`std::string`)
  - `FromString(std::string_view str)`: 文字列から変数値を設定 (`void`)
  - `GetValue()`: 変数値を取得 (`T`)
  - `SetValue(const T& val)`: 変数値を設定 (`void`)
  - `TypeName()`: 型名を取得 (`std::string_view`)
  - `RemoveListener(const std::uint64_t key)`: リスナーを削除 (`void`)
  - `AddListener(OnChange listener)`: リスナーを追加 (`std::uint64_t`)
  - `ClearListeners()`: 全てのリスナーをクリア (`void`)

#### `Config`
- **完全な名前**: `ws::cfg::Config`
- **公開メソッド**:
  - `Name()`: 設定名を取得 (`std::string_view`)
  - `Lookup(const std::string_view name, const T& default_val, const std::string_view description = "")`: 変数を探すまたは作成 (`typename Var<T>::Ptr`)
  - `Lookup(const std::string_view name) const`: 変数を探す (`typename Var<T>::Ptr`)
  - `LookupBase(std::string_view name) const`: 基本情報の変数を探す (`VarBase::Ptr`)
  - `LoadYaml(const YAML::Node& root)`: YAMLノードから設定を読み込む (`void`)
  - `Visit(std::function<void(VarBase::Ptr)> visitor) const`: 全ての変数を訪問 (`void`)

## 4. 処理フロー図

### `Config::LoadYaml`

```mermaid
flowchart TD
    A[開始] --> B{root.IsMap()?}
    B -- 是 --> C[ExtractMembers(root)]
    B -- 否 --> D[終了]
    C --> E[for each node in members]
    E --> F[node.first.empty()?]
    F -- はい --> G[スキップ]
    F -- いいえ --> H[LookupBase(node.first)]
    H --> I{var != nullptr?}
    I -- はい --> J[std::ostringstream ss; ss << node.second]
    I -- いいえ --> K[スキップ]
    J --> L[var->FromString(ss.str())]
    G --> M[次のnodeへ]
    K --> M
    L --> M
    M --> E
    D --> N[終了]
```

## 5. シーケンス図

該当なし  
理由: 元コードから複数の関数、メソッド、オブジェクト間の呼び出し順序を直接確認できない。

## 6. 関数・メソッド仕様書

### `VarConverter<From, To>::operator()`

| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::cfg::VarConverter<From, To>::operator()` |
| 目的 | 変数値を別の型に変換する。デフォルト実装は`static_cast`を使用する。 |
| 引数 | `val`: 変換元の値 (`const From&`) |
| 戻り値 | 変換後の値 (`To`) |
| 前提条件 | 無し |
| 事後条件 | 変換が成功した場合、変換後の値を返す。 |
| 動作の説明 | `static_cast`を使用して変換を行う。 |
| 状態変更・副作用 | 無し |
| 依存関係 | 無し |
| 境界条件 | 無し |
| エラー処理 | 無し |

### `VarBase::Name`

| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::cfg::VarBase::Name` |
| 目的 | 変数名を取得する。 |
| 引数 | 無し |
| 戻り値 | 変数名 (`std::string_view`) |
| 前提条件 | 無し |
| 事後条件 | 変数名が返される。 |
| 動作の説明 | `name_`を返す。 |
| 状態変更・副作用 | 無し |
| 依存関係 | 無し |
| 境界条件 | 無し |
| エラー処理 | 無し |

### `VarBase::Description`

| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::cfg::VarBase::Description` |
| 目的 | 変数の説明を取得する。 |
| 引数 | 無し |
| 戻り値 | 変数の説明 (`std::string_view`) |
| 前提条件 | 無し |
| 事後条件 | 変数の説明が返される。 |
| 動作の説明 | `description_`を返す。 |
| 状態変更・副作用 | 無し |
| 依存関係 | 無し |
| 境界条件 | 無し |
| エラー処理 | 無し |

### `Var<T, FromStr, ToStr>::ToString`

| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::cfg::Var<T, FromStr, ToStr>::ToString` |
| 目的 | 変数値を文字列に変換する。 |
| 引数 | 無し |
| 戻り値 | 文字列 (`std::string`) |
| 前提条件 | 無し |
| 事後条件 | 変数値が文字列に変換され、返される。 |
| 動作の説明 | `ToStr {}(GetValue())`を呼び出す。 |
| 状態変更・副作用 | 無し |
| 依存関係 | `VarConverter<T, std::string>` |
| 境界条件 | 無し |
| エラー処理 | 無し |

### `Var<T, FromStr, ToStr>::FromString`

| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::cfg::Var<T, FromStr, ToStr>::FromString` |
| 目的 | 文字列から変数値を設定する。 |
| 引数 | `str`: 変換元の文字列 (`std::string_view`) |
| 戻り値 | 無し |
| 前提条件 | 無し |
| 事後条件 | 文字列が変数値に設定される。 |
| 動作の説明 | `SetValue(FromStr {}(str))`を呼び出す。 |
| 状態変更・副作用 | 変数値が更新される。 |
| 依存関係 | `VarConverter<std::string, T>` |
| 境界条件 | 無し |
| エラー処理 | 無し |

### `Config::LoadYaml`

| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::cfg::Config::LoadYaml` |
| 目的 | YAMLノードから設定を読み込む。 |
| 引数 | `root`: YAMLノード (`const YAML::Node&`) |
| 戻り値 | 無し |
| 前提条件 | 無し |
| 事後条件 | YAMLノードの内容が設定に反映される。 |
| 動作の説明 | `ExtractMembers(root)`を呼び出し、各メンバーに対して`LookupBase(node.first)`を行い、存在する変数に対して`var->FromString(ss.str())`を呼び出す。 |
| 状態変更・副作用 | 設定値が更新される。 |
| 依存関係 | `ExtractMembers`, `VarBase::Ptr`, `VarConverter<std::string, T>` |
| 境界条件 | 無し |
| エラー処理 | 無し |

## 7. 状態遷移と重要な条件

該当なし  
理由: このモジュールは状態を保持するクラスが存在せず、状態の変更や更新順序が明確に定義されていない。

## 8. 確認不能事項

- YAMLノードの具体的な構造や内容。
- `RootConfig`が呼び出されるタイミングと目的。
- `VarConverter`の特殊化についての詳細な要件。