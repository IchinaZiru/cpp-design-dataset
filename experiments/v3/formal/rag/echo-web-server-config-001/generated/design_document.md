# 対象
- target: config
- granularity: module_files
- source_files: ["include/config.h", "src/config/config.cpp"]

# 責務
`config` モジュールは、YAML形式の設定ファイルを読み取り、内部データ構造に変換し、その値を管理・提供する。また、設定値の変更イベントに対するリスナー機能も提供する。

# 公開インターフェース
- `VarConverter` クラステンプレート: 値の型変換を行う。
- `VarBase` クラス: 設定変数の基本情報を保持し、文字列との相互変換を提供する。
- `Var` クラステンプレート: 特定の型の設定変数を管理し、値の取得・設定、リスナー機能を提供する。
- `Config` クラス: 設定全体を管理し、設定変数の検索、YAMLからの読み込み、全変数へのアクセスを提供する。
- `RootConfig` 関数: ルート設定インスタンスを取得する。

# 入力
- YAML形式の設定データ（文字列）
- 設定変数名とデフォルト値

# 出力
- 文字列形式の設定値
- `Var` オブジェクトへのポインタ
- 例外 (`std::invalid_argument`)

# 状態
- 設定変数の現在値
- リスナー関数のリスト

# 処理手順
1. YAML形式の設定データを読み取り、内部データ構造に変換する。
2. 設定変数名で検索し、存在しない場合は新規作成する。
3. 文字列形式の設定値から型変換を行い、設定変数に値を設定する。
4. 値が変更された場合、登録されているリスナー関数を呼び出す。

# 例外・失敗条件
- YAMLデータが期待される形式でない場合 (`std::invalid_argument`)
- 設定変数の型が一致しない場合 (`std::invalid_argument`)

# 依存関係
- `YAML` ライブラリ: YAMLデータの読み取りと操作
- `fmt` ライブラリ: 文字列フォーマット

# 重要な不変条件
- 設定変数名は一意である。
- リスナー関数は登録・削除が適切に行われる。

## 追加詳細設計情報

### クラス図
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
        +void FromString(std::string_view str) override
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
    
    VarConverter <|-- VarConverter~From, std::string~
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
    
    VarBase <|-- Var~T, FromStr, ToStr~
    
    Config --> VarMap : contains >
```

### クラス・メソッド・インターフェース詳細
| クラス/構造体 | 名前 | 完全な名前 | 属性 | 引数名と型 | 戻り値型 | 可視性 | const | noexcept | static | virtual |
|---------------|------|------------|------|------------|----------|--------|-------|----------|--------|---------|
| VarConverter~From, To~ | operator() | VarConverter~From, To~::operator() | - | val: From& | To | public | 〇 | 〇 | × | × |
| VarBase | VarBase | ws::cfg::VarBase::VarBase | - | name: std::string_view, description: std::string_view = "" | void | public | 〇 | 〇 | × | × |
| VarBase | ~VarBase | ws::cfg::VarBase::~VarBase | - | - | void | public | 〇 | 〇 | × | 〇 |
| VarBase | Name | ws::cfg::VarBase::Name | - | - | std::string_view | public | 〇 | 〇 | × | × |
| VarBase | Description | ws::cfg::VarBase::Description | - | - | std::string_view | public | 〇 | 〇 | × | × |
| VarBase | ToString | ws::cfg::VarBase::ToString | - | - | std::string | public | × | 〇 | × | 〇 |
| VarBase | FromString | ws::cfg::VarBase::FromString | - | str: std::string_view | void | public | × | × | × | 〇 |
| Var~T, FromStr, ToStr~ | Var | ws::cfg::Var~T, FromStr, ToStr~::Var | - | name: std::string_view, default_val: T&, description: std::string_view = "" | void | public | 〇 | 〇 | × | × |
| Var~T, FromStr, ToStr~ | ToString | ws::cfg::Var~T, FromStr, ToStr~::ToString | - | - | std::string | public | 〇 | 〇 | × | 〇 |
| Var~T, FromStr, ToStr~ | FromString | ws::cfg::Var~T, FromStr, ToStr~::FromString | - | str: std::string_view | void | public | 〇 | × | × | 〇 |
| Var~T, FromStr, ToStr~ | GetValue | ws::cfg::Var~T, FromStr, ToStr~::GetValue | - | - | T | public | 〇 | 〇 | × | × |
| Var~T, FromStr, ToStr~ | SetValue | ws::cfg::Var~T, FromStr, ToStr~::SetValue | - | val: const T& | void | public | 〇 | 〇 | × | × |
| Var~T, FromStr, ToStr~ | TypeName | ws::cfg::Var~T, FromStr, ToStr~::TypeName | - | - | std::string_view | public | 〇 | 〇 | × | × |
| Var~T, FromStr, ToStr~ | RemoveListener | ws::cfg::Var~T, FromStr, ToStr~::RemoveListener | - | key: const std::uint64_t | void | public | 〇 | 〇 | × | × |
| Var~T, FromStr, ToStr~ | AddListener | ws::cfg::Var~T, FromStr, ToStr~::AddListener | - | listener: OnChange | std::uint64_t | public | 〇 | 〇 | × | × |
| Var~T, FromStr, ToStr~ | ClearListeners | ws::cfg::Var~T, FromStr, ToStr~::ClearListeners | - | - | void | public | 〇 | 〇 | × | × |
| Config | Config | ws::cfg::Config::Config | - | name: std::string_view | void | public | 〇 | 〇 | × | × |
| Config | Name | ws::cfg::Config::Name | - | - | std::string_view | public | 〇 | 〇 | × | × |
| Config | Lookup~T~ | ws::cfg::Config::Lookup~T~ | - | name: std::string_view, default_val: T&, description: std::string_view = "" | typename Var~T~::Ptr | public | × | × | × | × |
| Config | Lookup~T~ | ws::cfg::Config::Lookup~T~ | - | name: std::string_view | typename Var~T~::Ptr | public | 〇 | × | × | × |
| Config | LookupBase | ws::cfg::Config::LookupBase | - | name: std::string_view | VarBase::Ptr | public | 〇 | 〇 | × | × |
| Config | LoadYaml | ws::cfg::Config::LoadYaml | - | root: const YAML::Node& | void | public | × | × | × | × |
| Config | Visit | ws::cfg::Config::Visit | - | visitor: std::function~void(VarBase::Ptr)~ | void | public | 〇 | 〇 | × | × |

### シーケンス図
該当なし

### メソッド仕様書
| 完全な名前 | 目的 | 引数 | 戻り値 | 動作の説明 | 副作用 | 使用例 | エラー処理 |
|------------|------|------|--------|------------|--------|--------|------------|
| VarConverter~From, To~::operator() | 値を変換する | val: From& | To | `static_cast<To>(val)` を使用して値を変換する | なし | 確認不能 | なし |
| ws::cfg::VarBase::Name | 変数名を取得する | - | std::string_view | 内部メンバ変数 `name_` を返す | なし | 確認不能 | なし |
| ws::cfg::VarBase::Description | 説明文を取得する | - | std::string_view | 内部メンバ変数 `description_` を返す | なし | 確認不能 | なし |
| ws::cfg::Var~T, FromStr, ToStr~::ToString | 変数値を文字列に変換する | - | std::string | `ToStr {}(GetValue())` を使用して値を変換する | なし | 確認不能 | なし |
| ws::cfg::Var~T, FromStr, ToStr~::FromString | 文字列から変数値に設定する | str: std::string_view | void | `FromStr {}(str)` を使用して文字列を変換し、`SetValue()` を呼び出す | なし | 確認不能 | なし |
| ws::cfg::Var~T, FromStr, ToStr~::GetValue | 変数値を取得する | - | T | 内部メンバ変数 `val_` を返す | なし | 確認不能 | なし |
| ws::cfg::Var~T, FromStr, ToStr~::SetValue | 変数値を設定する | val: const T& | void | 値が異なる場合、リスナー関数を呼び出し、内部メンバ変数 `val_` を更新する | リスナー関数の例外処理 | 確認不能 | なし |
| ws::cfg::Var~T, FromStr, ToStr~::TypeName | 変数型名を取得する | - | std::string_view | `typeid(T).name()` を使用して型名を返す | なし | 確認不能 | なし |
| ws::cfg::Config::Lookup~T~ | 変数を検索または作成する | name: std::string_view, default_val: T&, description: std::string_view = "" | typename Var~T~::Ptr | 指定された名前の変数が存在しない場合、新規作成し返す | なし | 確認不能 | なし |
| ws::cfg::Config::LoadYaml | YAMLノードから設定値を読み込む | root: const YAML::Node& | void | YAMLノードの各メンバーに対して `FromString()` を呼び出す | なし | 確認不能 | なし |

### 処理フロー図
```mermaid
flowchart TD
    A[LoadYaml] --> B{node.IsMap()?}
    B -- Yes --> C[ExtractMembers(node)]
    B -- No --> D[End]
    C --> E[for each member in members]
    E --> F{key.empty()?}
    F -- Yes --> G[continue]
    F -- No --> H[LookupBase(key)]
    H --> I{var != nullptr?}
    I -- Yes --> J[std::ostringstream ss]
    J --> K[ss << node.second]
    K --> L[var->FromString(ss.str())]
    I -- No --> M[End]
    G --> E
    D --> N[End]
```

### 状態遷移・副作用
| 更新前状態 | 遷移条件 | 変更対象 | 更新後状態 | 更新順序 | 副作用 |
|------------|----------|----------|------------|----------|--------|
| なし       | 初期化   | Config::vars_ | 空のマップ | -        | なし   |
| あり       | SetValue()呼び出し、値が異なる | Var::val_, リスナー関数 | 新しい値, リスナー関数実行 | 値更新 -> リスナー関数実行 | リスナー関数の例外処理 |

### データ変換・制約
| 入力形式 | 出力形式 | 変換方法 | 値域 | 境界値 | 単位 | 精度 | エンコーディング | 検証条件 | 特殊値・欠損値の扱い |
|----------|----------|----------|------|--------|------|------|--------------|------------|-----------------------|
| From     | To       | static_cast | 確認不能 | 確認不能 | 確認不能 | 確認不能 | 確認不能 | 確認不能 | 確認不能 |
| std::string | T | std::istringstreamを使用 | 確認不能 | 確認不能 | 確認不能 | 確認不能 | 確認不能 | 変換失敗時例外スロー | 確認不能 |
| T | std::string | to_string使用 | 確認不能 | 確認不能 | 確認不能 | 確認不能 | 確認不能 | 確認不能 | 確認不能 |
| YAML::Node | VarBase::Ptr | LookupBase()を使用 | 確認不能 | 確認不能 | 確認不能 | 確認不能 | 確認不能 | 存在しない場合nullptr | 確認不能 |