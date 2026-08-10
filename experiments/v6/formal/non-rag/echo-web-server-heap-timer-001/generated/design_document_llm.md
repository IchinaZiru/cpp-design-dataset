# デザイン文書: heap-timerモジュール

## 責務
- タイマーシステムを提供する。
- タイマーの追加、調整、削除、および期限切れタイマーのコールバック呼び出しを行う。
- タイマーは最小ヒープ構造で管理され、期限が最も近いものから順に処理される。

## 公開インターフェース
- `HeapTimer(log::Logger::Ptr logger = log::RootLogger()) noexcept`: コンストラクタ。ロガーを設定する。
- `void Adjust(const Key& key, Clock::duration expiration)`: タイマーの期限時間を調整する（相対時間）。
- `void Adjust(const Key& key, Clock::time_point expiration)`: タイマーの期限時間を調整する（絶対時間）。
- `void Push(const Key& key, Clock::duration expiration, TimeOutCallback callback) noexcept`: 新しいタイマーを追加する（相対時間）。
- `void Push(const Key& key, Clock::time_point expiration, TimeOutCallback callback) noexcept`: 新しいタイマーを追加する（絶対時間）。
- `void Tick() noexcept`: 期限切れのタイマーを処理し、コールバックを呼び出す。
- `bool Remove(const Key& key) noexcept`: タイマーを削除する。
- `void Invoke(const Key& key)`: 指定したキーのタイマーのコールバックを呼び出し、タイマーを削除する。
- `Key Pop() noexcept`: 期限が最も近いタイマーを削除し、そのキーを返す。
- `void Clear() noexcept`: タイマーシステムをクリアする。
- `bool Contain(const Key& key) const noexcept`: 指定したキーのタイマーが存在するか確認する。
- `bool Empty() const noexcept`: タイマーシステムが空であるか確認する。
- `std::size_t Size() const noexcept`: タイマーシステム内のタイマー数を返す。
- `Clock::duration ToNextTick() noexcept`: 次のタイマーまでの残り時間を返す。

## 入力
- タイマーのキー (`Key`)
- 期限時間 (`Clock::duration`または`Clock::time_point`)
- コールバック関数 (`TimeOutCallback`)

## 出力
- `bool`: 操作の成否（例：削除操作）
- `Key`: 削除されたタイマーのキー（`Pop()`メソッド）
- `std::size_t`: タイマーシステム内のタイマー数 (`Size()`メソッド）
- `Clock::duration`: 次のタイマーまでの残り時間 (`ToNextTick()`メソッド）

## 状態
- `nodes_`: タイマーを保持する最小ヒープ（`std::deque<Node>`）
- `key_to_idx_`: キーからノードインデックスへのマッピング（`std::unordered_map<Key, std::size_t>`）
- `logger_`: ロガー (`log::Logger::Ptr`)

## 処理手順
1. **Push**: 新しいタイマーを追加し、ヒープの適切な位置に配置する。
2. **Adjust**: 既存のタイマーの期限時間を変更し、ヒープの構造を再調整する。
3. **Tick**: 期限切れのタイマーを探し、コールバックを呼び出す。ヒープの構造を再調整する。
4. **Remove**: 指定したキーのタイマーを削除し、ヒープの構造を再調整する。
5. **Invoke**: 指定したキーのタイマーのコールバックを呼び出し、タイマーを削除する。
6. **Pop**: 期限が最も近いタイマーを削除し、そのキーを返す。ヒープの構造を再調整する。

## 例外・失敗条件
- `std::out_of_range`: 指定したキーのタイマーが存在しない場合（`Adjust`, `Invoke`メソッド）。
- コールバック関数内で例外が発生した場合は、例外はキャッチされログに記録される。

## 依存関係
- `log::Logger`: ロギング機能を提供する。
- `std::chrono`: 時間管理に使用される。
- `std::function`: コールバック関数の型として使用される。
- `std::optional`: オプショナルな値を扱うために使用される。
- `std::unordered_map`, `std::deque`: データ構造として使用される。

## 重要な不変条件
- `nodes_`と`key_to_idx_`のサイズは常に一致する。
- `nodes_`は最小ヒープ構造を保つ。
- タイマーが期限切れになった場合、そのコールバックは呼び出される。

# 追加詳細設計情報

## クラス図
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
        -struct Node {
            +Key key
            +Clock::time_point expiration
            +TimeOutCallback callback
            +bool Expired() const noexcept
            +void Swap(Node&) noexcept
            +friend std::weak_ordering operator<=>(const Node& lhs, const Node& rhs) noexcept
        }
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
```

## クラス・メソッド・インターフェース詳細

| 完全な名前 | 属性 | 引数名と型 | 戻り値型 | 可視性 | const | 参照/ポインタ | static | virtual | noexcept |
|------------|------|------------|----------|--------|-------|---------------|--------|---------|----------|
| `HeapTimer::HeapTimer` | コンストラクタ | log::Logger::Ptr logger = log::RootLogger() | void | public | なし | 参照 | なし | なし | あり |
| `HeapTimer::Adjust` | メソッド | const Key& key, Clock::duration expiration | void | public | なし | 値 | なし | なし | なし |
| `HeapTimer::Adjust` | メソッド | const Key& key, Clock::time_point expiration | void | public | なし | 値 | なし | なし | なし |
| `HeapTimer::Push` | メソッド | const Key& key, Clock::duration expiration, TimeOutCallback callback | void | public | なし | 値 | なし | なし | あり |
| `HeapTimer::Push` | メソッド | const Key& key, Clock::time_point expiration, TimeOutCallback callback | void | public | なし | 値 | なし | なし | あり |
| `HeapTimer::Tick` | メソッド | なし | void | public | なし | なし | なし | なし | あり |
| `HeapTimer::Remove` | メソッド | const Key& key | bool | public | なし | 値 | なし | なし | あり |
| `HeapTimer::Invoke` | メソッド | const Key& key | void | public | なし | 値 | なし | なし | なし |
| `HeapTimer::Pop` | メソッド | なし | Key | public | なし | なし | なし | なし | あり |
| `HeapTimer::Clear` | メソッド | なし | void | public | なし | なし | なし | なし | あり |
| `HeapTimer::Contain` | メソッド | const Key& key | bool | public | あり | 値 | なし | なし | あり |
| `HeapTimer::Empty` | メソッド | なし | bool | public | あり | なし | なし | なし | あり |
| `HeapTimer::Size` | メソッド | なし | std::size_t | public | あり | なし | なし | なし | あり |
| `HeapTimer::ToNextTick` | メソッド | なし | Clock::duration | public | なし | なし | なし | なし | あり |

## シーケンス図
```mermaid
sequenceDiagram
    participant Client
    participant HeapTimer
    participant Node
    participant Logger

    Client->>HeapTimer: Push(key, expiration, callback)
    HeapTimer->>Node: Create Node with key, expiration, callback
    HeapTimer->>HeapTimer: Add Node to nodes_
    HeapTimer->>HeapTimer: Update key_to_idx_
    HeapTimer->>HeapTimer: ShiftUp(idx)

    Client->>HeapTimer: Tick()
    loop Until no expired nodes
        alt Node is expired
            HeapTimer->>Node: Get callback and key
            HeapTimer->>Logger: Log if exception occurs in callback
            HeapTimer->>HeapTimer: RemoveByIndex(0)
            HeapTimer->>HeapTimer: ShiftDown(0)
        else Node is not expired
            break
        end
    end

    Client->>HeapTimer: Adjust(key, expiration)
    HeapTimer->>Node: Update expiration
    alt shift_up
        HeapTimer->>HeapTimer: ShiftUp(idx)
    else !shift_up
        HeapTimer->>HeapTimer: ShiftDown(idx)
    end

    Client->>HeapTimer: Remove(key)
    HeapTimer->>HeapTimer: RemoveByIndex(idx)
    HeapTimer->>Logger: Log if exception occurs in callback
```

## メソッド仕様書

### `Push`
- **目的**: 新しいタイマーを追加する。
- **引数**:
  - `key`: タイマーのキー (`const Key&`)
  - `expiration`: 期限時間 (`Clock::duration`または`Clock::time_point`)
  - `callback`: コールバック関数 (`TimeOutCallback`)
- **戻り値**: なし
- **動作**:
  - 新しいノードを作成し、ヒープに追加する。
  - キーからインデックスへのマッピングを更新する。
  - ヒープの構造を再調整する（`ShiftUp`）。
- **副作用**: `nodes_`と`key_to_idx_`が更新される。

### `Tick`
- **目的**: 期限切れのタイマーを処理し、コールバックを呼び出す。
- **引数**: なし
- **戻り値**: なし
- **動作**:
  - ヒープの先頭から期限切れのノードを探し、コールバックを呼び出す。
  - コールバック内で例外が発生した場合はログに記録する。
  - 呼び出し後、ヒープの構造を再調整する（`ShiftDown`）。
- **副作用**: `nodes_`と`key_to_idx_`が更新される。

### `Adjust`
- **目的**: タイマーの期限時間を調整する。
- **引数**:
  - `key`: タイマーのキー (`const Key&`)
  - `expiration`: 新しい期限時間 (`Clock::duration`または`Clock::time_point`)
- **戻り値**: なし
- **動作**:
  - 指定したキーのノードを見つけ、期限時間を更新する。
  - 更新後、ヒープの構造を再調整する（`ShiftUp`または`ShiftDown`）。
- **例外**: `std::out_of_range`: キーが存在しない場合。

### `Remove`
- **目的**: 指定したキーのタイマーを削除する。
- **引数**:
  - `key`: タイマーのキー (`const Key&`)
- **戻り値**: 削除に成功したかどうか (`bool`)
- **動作**:
  - 指定したキーのノードを見つけ、ヒープから削除する。
  - ヒープの構造を再調整する（`ShiftDown`）。
- **副作用**: `nodes_`と`key_to_idx_`が更新される。

### `Invoke`
- **目的**: 指定したキーのタイマーのコールバックを呼び出し、タイマーを削除する。
- **引数**:
  - `key`: タイマーのキー (`const Key&`)
- **戻り値**: なし
- **動作**:
  - 指定したキーのノードを見つけ、コールバックを呼び出す。
  - コールバック内で例外が発生した場合はログに記録する。
  - 呼び出し後、ヒープからノードを削除し、ヒープの構造を再調整する（`ShiftDown`）。
- **例外**: `std::out_of_range`: キーが存在しない場合。

## 処理フロー図
```mermaid
graph TD
    A[Push] --> B[Create Node]
    B --> C[Add to nodes_]
    C --> D[Update key_to_idx_]
    D --> E[ShiftUp(idx)]

    F[Tick] --> G{Empty?}
    G -- Yes --> H[End]
    G -- No --> I[Node Expired?]
    I -- Yes --> J[Get callback and key]
    J --> K[Log if exception occurs in callback]
    K --> L[RemoveByIndex(0)]
    L --> M[ShiftDown(0)]
    M --> F
    I -- No --> H

    N[Adjust] --> O{Find Node}
    O -- Found --> P[Update expiration]
    P --> Q{shift_up?}
    Q -- Yes --> R[ShiftUp(idx)]
    Q -- No --> S[ShiftDown(idx)]
    O -- Not Found --> T[throw std::out_of_range]

    U[Remove] --> V{Find Node}
    V -- Found --> W[RemoveByIndex(idx)]
    W --> X[Log if exception occurs in callback]
    V -- Not Found --> Y[return false]

    Z[Invoke] --> AA{Find Node}
    AA -- Found --> AB[Get callback and key]
    AB --> AC[Log if exception occurs in callback]
    AC --> AD[RemoveByIndex(idx)]
    AA -- Not Found --> AE[throw std::out_of_range]
```

## 状態遷移・副作用

| 更新前状態 | 遷移条件 | 変更対象 | 更新後状態 | 更新順序 | 副作用 |
|------------|----------|----------|------------|----------|--------|
| なし       | Push     | nodes_, key_to_idx_ | ノード追加, インデックスマッピング更新 | ShiftUp(idx) | ヒープ構造再調整 |
| 期限切れノードあり | Tick     | nodes_, key_to_idx_ | 期限切れノード削除, コールバック呼び出し | ShiftDown(0) | ヒープ構造再調整 |
| タイマー存在 | Adjust   | nodes_ | 期限時間更新 | ShiftUp(idx)/ShiftDown(idx) | ヒープ構造再調整 |
| タイマー存在 | Remove   | nodes_, key_to_idx_ | ノード削除 | ShiftDown(0) | ヒープ構造再調整 |
| タイマー存在 | Invoke   | nodes_, key_to_idx_ | コールバック呼び出し, ノード削除 | ShiftDown(0) | ヒープ構造再調整 |

## データ変換・制約

| 入力データ | 変換規則 | 出力データ |
|------------|----------|------------|
| expiration (duration) | 現在時刻 + duration | expiration (time_point) |
| expiration (time_point) | そのまま | expiration (time_point) |
| nodes_ | ヒープ構造維持 | nodes_ |
| key_to_idx_ | キーからインデックスへのマッピング更新 | key_to_idx_ |

- `expiration`は相対時間（duration）または絶対時間（time_point）で指定される。
- ヒープの構造が常に最小ヒープを維持する。
- タイマーのキーからノードのインデックスへのマッピングが正確に更新される。