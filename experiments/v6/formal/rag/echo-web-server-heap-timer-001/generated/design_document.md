# デザイン文書: heap-timerモジュール

## 責務
- タイマーシステムを提供し、指定されたキーを持つノードの有効期限を管理する。
- ノードが期限切れになったときにコールバック関数を呼び出す。
- ログ記録機能を備えている。

## 公開インターフェース
- `HeapTimer(log::Logger::Ptr logger = log::RootLogger()) noexcept`: コンストラクタ。ロガーを指定しない場合はデフォルトのルートロガーを使用する。
- `void Adjust(const Key& key, Clock::duration expiration)`: 指定されたキーを持つノードの有効期限を調整する（相対時間）。
- `void Adjust(const Key& key, Clock::time_point expiration)`: 指定されたキーを持つノードの有効期限を調整する（絶対時間）。
- `void Push(const Key& key, Clock::duration expiration, TimeOutCallback callback) noexcept`: ノードを追加する（相対時間）。
- `void Push(const Key& key, Clock::time_point expiration, TimeOutCallback callback) noexcept`: ノードを追加する（絶対時間）。
- `void Tick() noexcept`: 期限切れのノードを削除し、コールバック関数を呼び出す。
- `bool Remove(const Key& key) noexcept`: 指定されたキーを持つノードを削除する。
- `void Invoke(const Key& key)`: 指定されたキーを持つノードのコールバック関数を呼び出し、ノードを削除する。
- `Key Pop() noexcept`: 最も期限が近いノードを削除し、そのキーを返す。
- `void Clear() noexcept`: すべてのノードを削除する。
- `bool Contain(const Key& key) const noexcept`: 指定されたキーを持つノードが存在するかどうかを確認する。
- `bool Empty() const noexcept`: タイマーシステムが空であるかどうかを確認する。
- `std::size_t Size() const noexcept`: ノードの数を返す。
- `Clock::duration ToNextTick() noexcept`: 次に期限切れになるノードまでの残り時間を返す。

## 入力
- キー（`Key`型）
- 有効期限（相対時間または絶対時間）
- コールバック関数（`TimeOutCallback`型）

## 出力
- `bool`: 操作の成否（`Remove`, `Contain`, `Empty`メソッド）
- `Key`: 削除されたノードのキー（`Pop`メソッド）
- `std::size_t`: ノード数（`Size`メソッド）
- `Clock::duration`: 次に期限切れになるノードまでの残り時間（`ToNextTick`メソッド）

## 状態
- `nodes_`: ノードのリスト（`std::deque<Node>`型）
- `key_to_idx_`: キーからノードのインデックスへのマップ（`std::unordered_map<Key, std::size_t>`型）
- `logger_`: ロガー（`log::Logger::Ptr`型）

## 処理手順
1. **Push**: 新しいノードを追加し、ヒーププロパティを維持する。
2. **Adjust**: 既存のノードの有効期限を更新し、ヒーププロパティを維持する。
3. **Tick**: 期限切れのノードを削除し、コールバック関数を呼び出す。
4. **Remove**: 指定されたキーを持つノードを削除する。
5. **Invoke**: 指定されたキーを持つノードのコールバック関数を呼び出し、ノードを削除する。
6. **Pop**: 最も期限が近いノードを削除し、そのキーを返す。
7. **Clear**: すべてのノードを削除する。

## 例外・失敗条件
- `std::out_of_range`: 指定されたキーを持つノードが存在しない場合（`Adjust`, `Invoke`メソッド）。
- コールバック関数内で例外が発生した場合は、ログに記録されるが再スローされない。

## 依存関係
- `log::Logger`: ログ記録機能を提供する。
- `std::chrono::steady_clock`: 時間の測定と管理を行う。
- `std::function<void(const Key&)>`: コールバック関数の型として使用される。

## 重要な不変条件
- `nodes_`と`key_to_idx_`は常に同期されている。つまり、あるキーが`key_to_idx_`に存在する場合、そのインデックスは`nodes_`で有効な範囲内である。
- ヒーププロパティ: 任意のノードの有効期限は子ノードの有効期限以下である。

## 追加詳細設計情報

### クラス図
```mermaid
classDiagram
    class HeapTimer {
        +HeapTimer(log::Logger::Ptr logger = log::RootLogger()) noexcept
        +void Adjust(const Key& key, Clock::duration expiration)
        +void Adjust(const Key& key, Clock::time_point expiration)
        +void Push(const Key& key, Clock::duration expiration, TimeOutCallback callback) noexcept
        +void Push(const Key& key, Clock::time_point expiration, TimeOutCallback callback) noexcept
        +void Tick() noexcept
        +bool Remove(const Key& key) noexcept
        +void Invoke(const Key& key)
        +Key Pop() noexcept
        +void Clear() noexcept
        +bool Contain(const Key& key) const noexcept
        +bool Empty() const noexcept
        +std::size_t Size() const noexcept
        +Clock::duration ToNextTick() noexcept
        -struct Node
        -void Swap(std::size_t idx1, std::size_t idx2) noexcept
        -void Adjust(const Key& key, Clock::time_point expiration, std::optional<TimeOutCallback> callback)
        -Key RemoveByIndex(std::size_t idx) noexcept
        -void ShiftUp(std::size_t idx) noexcept
        -void ShiftDown(std::size_t idx) noexcept
        -bool ValidIndex(std::size_t idx) const noexcept
        -std::optional<std::size_t> Parent(std::size_t idx) const noexcept
        -std::optional<std::size_t> SmallChild(std::size_t idx) const noexcept
        -log::Logger::Ptr logger_
        -std::unordered_map<Key, std::size_t> key_to_idx_
        -std::deque<Node> nodes_
    }
    
    class Node {
        +Key key
        +Clock::time_point expiration
        +TimeOutCallback callback
        +bool Expired() const noexcept
        +void Swap(Node&) noexcept
        <<friend>> std::weak_ordering operator<=>(const Node& lhs, const Node& rhs) noexcept
    }
    
    HeapTimer --> Node : contains
    HeapTimer --> log::Logger : uses
```

### クラス・メソッド・インターフェース詳細

| クラス名 | メソッド名 | 完全な名前 | 属性 | 引数名と型 | 戻り値型 | 可視性 | const | `const` | `noexcept` | `static` | `virtual` | 型別名 | 列挙型 | 定数 | 直接依存 |
|----------|------------|--------------|------|------------|-----------|--------|-------|---------|------------|----------|-----------|--------|--------|------|------------|
| HeapTimer | HeapTimer | ws::HeapTimer<Key>::HeapTimer | コンストラクタ | log::Logger::Ptr logger = log::RootLogger() | void | public | - | - | はい | - | - | - | - | - | log::Logger |
| HeapTimer | Adjust | ws::HeapTimer<Key>::Adjust | メソッド | const Key& key, Clock::duration expiration | void | public | - | - | いいえ | - | - | - | - | - | - |
| HeapTimer | Adjust | ws::HeapTimer<Key>::Adjust | メソッド | const Key& key, Clock::time_point expiration | void | public | - | - | いいえ | - | - | - | - | - | - |
| HeapTimer | Push | ws::HeapTimer<Key>::Push | メソッド | const Key& key, Clock::duration expiration, TimeOutCallback callback | void | public | - | - | はい | - | - | - | - | - | - |
| HeapTimer | Push | ws::HeapTimer<Key>::Push | メソッド | const Key& key, Clock::time_point expiration, TimeOutCallback callback | void | public | - | - | はい | - | - | - | - | - | - |
| HeapTimer | Tick | ws::HeapTimer<Key>::Tick | メソッド | - | void | public | - | - | はい | - | - | - | - | - | - |
| HeapTimer | Remove | ws::HeapTimer<Key>::Remove | メソッド | const Key& key | bool | public | - | - | はい | - | - | - | - | - | - |
| HeapTimer | Invoke | ws::HeapTimer<Key>::Invoke | メソッド | const Key& key | void | public | - | - | いいえ | - | - | - | - | - | - |
| HeapTimer | Pop | ws::HeapTimer<Key>::Pop | メソッド | - | Key | public | - | - | はい | - | - | - | - | - | - |
| HeapTimer | Clear | ws::HeapTimer<Key>::Clear | メソッド | - | void | public | - | - | はい | - | - | - | - | - | - |
| HeapTimer | Contain | ws::HeapTimer<Key>::Contain | メソッド | const Key& key | bool | public | - | いいえ | いいえ | - | - | - | - | - | - |
| HeapTimer | Empty | ws::HeapTimer<Key>::Empty | メソッド | - | bool | public | - | いいえ | いいえ | - | - | - | - | - | - |
| HeapTimer | Size | ws::HeapTimer<Key>::Size | メソッド | - | std::size_t | public | - | いいえ | いいえ | - | - | - | - | - | - |
| HeapTimer | ToNextTick | ws::HeapTimer<Key>::ToNextTick | メソッド | - | Clock::duration | public | - | - | はい | - | - | - | - | - | - |

### シーケンス図
```mermaid
sequenceDiagram
    participant Client
    participant HeapTimer
    participant Logger

    Client->>HeapTimer: Push(key, expiration, callback)
    HeapTimer->>HeapTimer: ValidIndex(idx)
    alt Node exists?
        HeapTimer->>HeapTimer: Adjust(key, expiration, callback)
        HeapTimer->>HeapTimer: ShiftUp(idx) or ShiftDown(idx)
    else Node does not exist
        HeapTimer->>HeapTimer: nodes_.push_back({key, expiration, callback})
        HeapTimer->>HeapTimer: key_to_idx_.emplace(key, idx)
        HeapTimer->>HeapTimer: ShiftUp(Size() - 1)
    end

    Client->>HeapTimer: Tick()
    loop While not empty and front node is expired
        HeapTimer->>HeapTimer: nodes_.front().Expired()
        alt Node is expired?
            HeapTimer->>Logger: Log(event)
            HeapTimer->>HeapTimer: RemoveByIndex(0)
        else Node is not expired
            break
        end
    end

    Client->>HeapTimer: Adjust(key, expiration)
    HeapTimer->>HeapTimer: key_to_idx_.at(key)
    HeapTimer->>HeapTimer: nodes_[idx].expiration = expiration
    alt shift_up?
        HeapTimer->>HeapTimer: ShiftUp(idx)
    else not shift_up
        HeapTimer->>HeapTimer: ShiftDown(idx)
    end

    Client->>HeapTimer: Remove(key)
    HeapTimer->>HeapTimer: key_to_idx_.at(key)
    HeapTimer->>HeapTimer: RemoveByIndex(idx)

    Client->>HeapTimer: Invoke(key)
    HeapTimer->>HeapTimer: key_to_idx_.at(key)
    HeapTimer->>Logger: Log(event)
    HeapTimer->>HeapTimer: RemoveByIndex(idx)

    Client->>HeapTimer: Pop()
    HeapTimer->>HeapTimer: RemoveByIndex(0)

    Client->>HeapTimer: ToNextTick()
    HeapTimer->>HeapTimer: Tick()
    alt nodes_ is not empty?
        HeapTimer->>HeapTimer: nodes_.front().expiration - Clock::now()
        HeapTimer->>Client: interval
    else nodes_ is empty
        HeapTimer->>Client: Clock::duration::zero()
    end

    Client->>HeapTimer: Clear()
    HeapTimer->>HeapTimer: nodes_.clear()
    HeapTimer->>HeapTimer: key_to_idx_.clear()
```

### メソッド仕様書

#### Push
- **目的**: 新しいノードを追加する。
- **引数**:
  - `key`: ユニークなキー（`Key`型）
  - `expiration`: 有効期限（相対時間または絶対時間）
  - `callback`: コールバック関数（`TimeOutCallback`型）
- **戻り値**: 無し
- **動作**:
  - 指定されたキーを持つノードが存在しない場合、新しいノードを作成しヒープに追加する。
  - 存在する場合は、そのノードの有効期限とコールバック関数を更新する。
- **副作用**: ヒーププロパティを維持するためにノードの位置が変更される可能性がある。

#### Adjust
- **目的**: 指定されたキーを持つノードの有効期限を調整する。
- **引数**:
  - `key`: ユニークなキー（`Key`型）
  - `expiration`: 新しい有効期限（相対時間または絶対時間）
- **戻り値**: 無し
- **動作**:
  - 指定されたキーを持つノードの有効期限を更新する。
  - ヒーププロパティを維持するためにノードの位置が変更される可能性がある。
- **例外**: `std::out_of_range` - 指定されたキーを持つノードが存在しない場合。

#### Tick
- **目的**: 期限切れのノードを削除し、コールバック関数を呼び出す。
- **引数**: 無し
- **戻り値**: 無し
- **動作**:
  - ヒープの先頭から期限切れのノードを探し、そのコールバック関数を呼び出す。
  - コールバック関数内で例外が発生した場合はログに記録されるが再スローされない。

#### Remove
- **目的**: 指定されたキーを持つノードを削除する。
- **引数**:
  - `key`: ユニークなキー（`Key`型）
- **戻り値**: 削除に成功したかどうか（`bool`型）
- **動作**:
  - 指定されたキーを持つノードをヒープから削除する。
- **例外**: 無し

#### Invoke
- **目的**: 指定されたキーを持つノードのコールバック関数を呼び出し、ノードを削除する。
- **引数**:
  - `key`: ユニークなキー（`Key`型）
- **戻り値**: 無し
- **動作**:
  - 指定されたキーを持つノードのコールバック関数を呼び出し、その後ノードをヒープから削除する。
- **例外**: `std::out_of_range` - 指定されたキーを持つノードが存在しない場合。

#### Pop
- **目的**: 最も期限が近いノードを削除し、そのキーを返す。
- **引数**: 無し
- **戻り値**: 削除されたノードのキー（`Key`型）
- **動作**:
  - ヒープの先頭から最も期限が近いノードを削除し、そのキーを返す。
- **例外**: 無し

#### Clear
- **目的**: すべてのノードを削除する。
- **引数**: 無し
- **戻り値**: 無し
- **動作**:
  - ヒープ内のすべてのノードとキーからインデックスへのマップをクリアする。

#### Contain
- **目的**: 指定されたキーを持つノードが存在するかどうかを確認する。
- **引数**:
  - `key`: ユニークなキー（`Key`型）
- **戻り値**: 存在するかどうか（`bool`型）
- **動作**:
  - 指定されたキーを持つノードが存在するかどうかを確認する。

#### Empty
- **目的**: タイマーシステムが空であるかどうかを確認する。
- **引数**: 無し
- **戻り値**: 空であるかどうか（`bool`型）
- **動作**:
  - タイマーシステムが空であるかどうかを確認する。

#### Size
- **目的**: ノードの数を返す。
- **引数**: 無し
- **戻り値**: ノードの数（`std::size_t`型）
- **動作**:
  - タイマーシステム内のノードの数を返す。

#### ToNextTick
- **目的**: 次に期限切れになるノードまでの残り時間を返す。
- **引数**: 無し
- **戻り値**: 残り時間（`Clock::duration`型）
- **動作**:
  - `Tick()`を呼び出し、次に期限切れになるノードまでの残り時間を計算して返す。

### 処理フロー図
```mermaid
graph TD
    A[Push] --> B{Node exists?}
    B -- Yes --> C[Adjust node]
    B -- No --> D[Create new node]
    C --> E[ShiftUp or ShiftDown]
    D --> F[Add to nodes_]
    F --> G[Update key_to_idx_]
    G --> H[ShiftUp]
    E --> I[End]
    H --> I

    J[Tick] --> K{Empty?}
    K -- Yes --> L[Return]
    K -- No --> M[Front node expired?]
    M -- Yes --> N[Log event]
    N --> O[RemoveByIndex(0)]
    O --> P[End]
    M -- No --> Q[Break]
    Q --> R[End]

    S[Adjust] --> T{Node exists?}
    T -- Yes --> U[Update expiration and callback]
    T -- No --> V[Throw std::out_of_range]
    U --> W[ShiftUp or ShiftDown]
    W --> X[End]
    V --> Y[End]

    Z[Remove] --> AA{Node exists?}
    AA -- Yes --> AB[RemoveByIndex(idx)]
    AA -- No --> AC[Return false]
    AB --> AD[Return true]
    AC --> AE[End]
    AD --> AF[End]

    AG[Invoke] --> AH{Node exists?}
    AH -- Yes --> AI[Log event]
    AI --> AJ[RemoveByIndex(idx)]
    AH -- No --> AK[Throw std::out_of_range]
    AK --> AL[End]
    AJ --> AM[End]

    AN[Pop] --> AO[RemoveByIndex(0)]
    AO --> AP[Return key]
    AP --> AQ[End]

    AR[Clear] --> AS[Clear nodes_ and key_to_idx_]
    AS --> AT[End]

    AU[Contain] --> AV{Node exists?}
    AV -- Yes --> AW[Return true]
    AV -- No --> AX[Return false]
    AW --> AY[End]
    AX --> AZ[End]

    BA[Empty] --> BB{Empty?}
    BB -- Yes --> BC[Return true]
    BB -- No --> BD[Return false]
    BC --> BE[End]
    BD --> BF[End]

    BG[Size] --> BH[Return size of nodes_]
    BH --> BI[End]

    BJ[ToNextTick] --> BK[Tick()]
    BK --> BL{Empty?}
    BL -- Yes --> BM[Return zero duration]
    BL -- No --> BN[Calculate interval]
    BN --> BO[Return interval]
    BO --> BP[End]
```

### 状態遷移・副作用
| 更新前状態 | 遷移条件 | 変更対象 | 更新後状態 | 更新順序 | 副作用 |
|------------|----------|----------|------------|----------|--------|
| ノードが存在しない | Pushメソッド呼び出し | nodes_, key_to_idx_ | 新しいノード追加, インデックスマップ更新 | 1. nodes_.push_back<br>2. key_to_idx_.emplace<br>3. ShiftUp | ヒーププロパティ維持 |
| ノードが存在する | Adjustメソッド呼び出し | nodes_ | 有効期限とコールバック関数更新 | 1. nodes_[idx].expiration = expiration<br>2. ShiftUp or ShiftDown | ヒーププロパティ維持 |
| 期限切れのノードあり | Tickメソッド呼び出し | nodes_, key_to_idx_ | 期限切れノード削除, コールバック関数実行 | 1. RemoveByIndex(0)<br>2. callback(key) | ヒーププロパティ維持, ログ記録 |
| 指定されたキーを持つノードあり | Removeメソッド呼び出し | nodes_, key_to_idx_ | 指定されたノード削除 | 1. RemoveByIndex(idx) | ヒーププロパティ維持 |
| 指定されたキーを持つノードあり | Invokeメソッド呼び出し | nodes_, key_to_idx_ | 指定されたノードのコールバック関数実行, 削除 | 1. callback(key)<br>2. RemoveByIndex(idx) | ヒーププロパティ維持, ログ記録 |
| - | Clearメソッド呼び出し | nodes_, key_to_idx_ | 全てのノード削除 | 1. nodes_.clear()<br>2. key_to_idx_.clear() | 無し |

### データ変換・制約
| 変換元 | 変換先 | 型変換 | 加工規則 | 値域 | 境界値 | 単位 | 精度 | encoding | 検証条件 | 特殊値・欠損値の扱い |
|--------|--------|--------|----------|------|--------|------|--------|----------|------------|---------------------|
| Clock::duration | Clock::time_point | - | 現在時刻に加算 | - | - | 時間単位 | ナノ秒 | - | - | - |
| Clock::time_point | bool | - | 有効期限と現在時刻の比較 | true/false | - | - | - | - | - | - |
| Key | std::size_t | - | キーからインデックスへのマッピング | - | - | - | - | - | - | - |
| TimeOutCallback | void | - | コールバック関数の実行 | - | - | - | - | - | - | - |

これらの設計情報は、`heap-timer`モジュールを再実装する際に必要な詳細な情報を提供します。

# Machine-extracted Source-local Implementation Contract

This appendix is deterministic evidence extracted from the target source.
It is not an LLM summary and it does not contain complete function bodies.

During regeneration:
- preserve the exact local declaration types, containers, initializers, and literals listed below;
- preserve the exact call targets and argument expressions listed below;
- do not substitute a different representation or accessor merely because it looks similar;
- treat these items as exact constraints, not as pseudocode suggestions.

## Exact local declarations

- `const auto idx {key_to_idx_.at(key)};`
- `const auto shift_up {expiration < nodes_[idx].expiration};`
- `const auto idx {Size()};`
- `auto parent {Parent(idx)};`
- `auto child {SmallChild(idx)};`
- `const auto left {idx * 2 + 1};`
- `const auto right {left + 1};`
- `auto smaller {left};`
- `auto& node {nodes_.front()};`
- `const auto callback {std::move(node.callback)};`
- `const auto key {node.key};`
- `const auto interval {nodes_.front().expiration - Clock::now()};`
- `const auto key {nodes_[idx].key};`

## Exact top-level call expressions

- `log::RootLogger()`
- `Clock::now()`
- `swap(key, o.key)`
- `swap(expiration, o.expiration)`
- `swap(callback, o.callback)`
- `std::move(logger)`
- `nodes_.clear()`
- `key_to_idx_.clear()`
- `Contain(key)`
- `RemoveByIndex(key_to_idx_[key])`
- `Size()`
- `key_to_idx_.contains(key)`
- `Adjust(key, Clock::now() + expiration)`
- `Adjust(key, expiration, std::nullopt)`
- `key_to_idx_.at(key)`
- `callback.has_value()`
- `ShiftUp(idx)`
- `ShiftDown(idx)`
- `Push(key, Clock::now() + expiration, std::move(callback))`
- `key_to_idx_.emplace(key, idx)`
- `nodes_.push_back({key, expiration, std::move(callback)})`
- `Adjust(key, expiration, std::move(callback))`
- `assert(nodes_.empty() == key_to_idx_.empty())`
- `assert(nodes_.size() == key_to_idx_.size())`
- `assert(ValidIndex(idx))`
- `Parent(idx)`
- `parent.has_value()`
- `assert(*parent < idx)`
- `Swap(*parent, idx)`
- `SmallChild(idx)`
- `child.has_value()`
- `assert(*child > idx)`
- `Swap(*child, idx)`
- `ValidIndex(left)`
- `ValidIndex(right)`
- `assert(ValidIndex(idx1) && ValidIndex(idx2))`
- `nodes_[idx1].Swap(nodes_[idx2])`
- `Empty()`
- `nodes_.front()`
- `node.Expired()`
- `std::move(node.callback)`
- `Pop()`
- `assert(callback)`
- `callback(key)`
- `logger_->Log( log::Event::Create(log::Level::Error) << fmt::format("Exception raised in timer's callback: {}", err.what()))`
- `Tick()`
- `Clock::duration::zero()`
- `assert(!Empty())`
- `RemoveByIndex(0)`
- `assert(nodes_[idx].callback)`
- `nodes_[idx].callback(key)`
- `logger_->Log(log::Event::Create(log::Level::Error) << fmt::format("Exception raised in timer's callback: {}", err.what()))`
- `RemoveByIndex(idx)`
- `assert(!Contain(key))`
- `Clear()`
- `assert(nodes_.front().key == key)`
- `nodes_.front().Swap(nodes_.back())`
- `std::swap(key_to_idx_[nodes_.front().key], key_to_idx_[nodes_.back().key])`
- `nodes_.pop_back()`
- `key_to_idx_.erase(key)`
- `ShiftDown(0)`
- `assert(key_to_idx_.size() == nodes_.size())`

# Machine-extracted Dependency API Contract

This appendix is deterministic evidence derived from the selected repository context and target-source usages.
It is not an LLM summary.

During regeneration:
- preserve the exact dependency declarations and call patterns listed below;
- do not invent replacement APIs, member functions, overloads, or adapters;
- preserve return types, parameter types, defaults, qualifiers, and argument expressions as written;
- do not consume a void return value as a value.

## `Create`

### Exact declarations

- `static Ptr Create(log::Level level, std::experimental::source_location location = std::experimental::source_location::current(), std::uint32_t thread_id = CurrentThreadId(), Clock::time_point time = Clock::now()) noexcept;`

### Exact target-source usages

- `log::Event::Create(log::Level::Error)`

## `Log`

### Exact declarations

- `void Log(Event::Ptr event) noexcept;`

### Exact target-source usages

- `logger_->Log( log::Event::Create(log::Level::Error) << fmt::format("Exception raised in timer's callback: {}", err.what()))`
- `logger_->Log(log::Event::Create(log::Level::Error) << fmt::format("Exception raised in timer's callback: {}", err.what()))`

## `RootLogger`

### Exact declarations

- `Logger::Ptr RootLogger() noexcept;`

### Exact target-source usages

- `log::RootLogger()`
