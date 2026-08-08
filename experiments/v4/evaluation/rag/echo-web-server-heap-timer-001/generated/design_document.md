# デザイン文書: heap-timerモジュール

## 責務
- タイマーシステムを提供する。
- タイマーの追加、調整、削除、および期限切れ時のコールバック呼び出しを行う。
- 内部で最小ヒープを使用してタイマーを管理する。

## 公開インターフェース
| 関数名 | 説明 |
|--------|------|
| `HeapTimer(log::Logger::Ptr logger = log::RootLogger())` | タイマーシステムを作成する。 |
| `void Adjust(const Key& key, Clock::duration expiration)` | 指定したキーのタイマーの期限時間を調整する。 |
| `void Adjust(const Key& key, Clock::time_point expiration)` | 指定したキーのタイマーの期限時間を指定の時間点に設定する。 |
| `void Push(const Key& key, Clock::duration expiration, TimeOutCallback callback) noexcept` | タイマーを追加する（相対的な期限）。 |
| `void Push(const Key& key, Clock::time_point expiration, TimeOutCallback callback) noexcept` | タイマーを追加する（絶対的な期限）。 |
| `void Tick() noexcept` | 期限切れのタイマーを削除し、コールバックを呼び出す。 |
| `bool Remove(const Key& key) noexcept` | 指定したキーのタイマーを削除する。 |
| `void Invoke(const Key& key)` | 指定したキーのタイマーを削除し、コールバックを呼び出す。 |
| `Key Pop() noexcept` | 最も期限切れのタイマーを削除してそのキーを返す。 |
| `void Clear() noexcept` | タイマーシステムをクリアする。 |
| `bool Contain(const Key& key) const noexcept` | 指定したキーのタイマーが存在するか確認する。 |
| `bool Empty() const noexcept` | タイマーシステムが空であるか確認する。 |
| `std::size_t Size() const noexcept` | タイマーシステム内のタイマー数を返す。 |
| `Clock::duration ToNextTick() noexcept` | 次の期限切れまでの時間を返す。 |

## 入力
- キー (`Key`)
- 期限時間 (`Clock::duration`, `Clock::time_point`)
- コールバック関数 (`TimeOutCallback`)

## 出力
- タイマーのキー (`Key`)
- 次の期限切れまでの時間 (`Clock::duration`)

## 状態
- 内部ヒープ (`std::deque<Node> nodes_`)
- キーとインデックスのマップ (`std::unordered_map<Key, std::size_t> key_to_idx_`)
- ロガー (`log::Logger::Ptr logger_`)

## 処理手順
1. `Push`: 新しいタイマーを追加し、ヒープの適切な位置に配置する。
2. `Adjust`: 既存のタイマーの期限時間を変更し、ヒープの構造を再調整する。
3. `Tick`: 期限切れのタイマーを探し、コールバックを呼び出す。ヒープから削除する。
4. `Remove`: 指定したキーのタイマーを削除する。
5. `Invoke`: 指定したキーのタイマーを削除し、コールバックを呼び出す。
6. `Pop`: 最も期限切れのタイマーをヒープから削除してそのキーを返す。
7. `Clear`: すべてのタイマーをクリアする。

## 例外・失敗条件
- `Adjust`, `Invoke`: 指定したキーが存在しない場合、`std::out_of_range` をスローする。
- `Pop`: タイマーシステムが空の場合、未定義動作（元コードではアサートで検出される）。

## 依存関係
- `log::Logger`
- `util.h`
- `<algorithm>`
- `<cassert>`
- `<chrono>`
- `<compare>`
- `<deque>`
- `<functional>`
- `<optional>`
- `<stdexcept>`
- `<unordered_map>`

## 重要な不変条件
- `nodes_` のサイズと `key_to_idx_` のサイズは常に一致する。
- ヒープの構造が常に最小ヒープを維持している。

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

| 関数名 | 完全な名前 | 属性 | 引数名と型 | 戻り値型 | 可視性 | const | noexcept | static | virtual |
|--------|------------|------|------------|----------|--------|-------|----------|--------|---------|
| `HeapTimer` | `ws::HeapTimer<Key>::HeapTimer(log::Logger::Ptr logger)` | コンストラクタ | `logger`: log::Logger::Ptr | なし | public | いいえ | はい | いいえ | いいえ |
| `Adjust` | `void ws::HeapTimer<Key>::Adjust(const Key& key, Clock::duration expiration)` | メソッド | `key`: const Key&, `expiration`: Clock::duration | なし | public | いいえ | いいえ | いいえ | いいえ |
| `Adjust` | `void ws::HeapTimer<Key>::Adjust(const Key& key, Clock::time_point expiration)` | メソッド | `key`: const Key&, `expiration`: Clock::time_point | なし | public | いいえ | いいえ | いいえ | いいえ |
| `Push` | `void ws::HeapTimer<Key>::Push(const Key& key, Clock::duration expiration, TimeOutCallback callback)` | メソッド | `key`: const Key&, `expiration`: Clock::duration, `callback`: TimeOutCallback | なし | public | いいえ | はい | いいえ | いいえ |
| `Push` | `void ws::HeapTimer<Key>::Push(const Key& key, Clock::time_point expiration, TimeOutCallback callback)` | メソッド | `key`: const Key&, `expiration`: Clock::time_point, `callback`: TimeOutCallback | なし | public | いいえ | はい | いいえ | いいえ |
| `Tick` | `void ws::HeapTimer<Key>::Tick()` | メソッド | なし | なし | public | いいえ | はい | いいえ | いいえ |
| `Remove` | `bool ws::HeapTimer<Key>::Remove(const Key& key)` | メソッド | `key`: const Key& | bool | public | いいえ | はい | いいえ | いいえ |
| `Invoke` | `void ws::HeapTimer<Key>::Invoke(const Key& key)` | メソッド | `key`: const Key& | なし | public | いいえ | いいえ | いいえ | いいえ |
| `Pop` | `Key ws::HeapTimer<Key>::Pop()` | メソッド | なし | Key | public | いいえ | はい | いいえ | いいえ |
| `Clear` | `void ws::HeapTimer<Key>::Clear()` | メソッド | なし | なし | public | いいえ | はい | いいえ | いいえ |
| `Contain` | `bool ws::HeapTimer<Key>::Contain(const Key& key) const` | メソッド | `key`: const Key& | bool | public | いいえ | はい | いいえ | いいえ |
| `Empty` | `bool ws::HeapTimer<Key>::Empty() const` | メソッド | なし | bool | public | いいえ | はい | いいえ | いいえ |
| `Size` | `std::size_t ws::HeapTimer<Key>::Size() const` | メソッド | なし | std::size_t | public | いいえ | はい | いいえ | いいえ |
| `ToNextTick` | `Clock::duration ws::HeapTimer<Key>::ToNextTick()` | メソッド | なし | Clock::duration | public | いいえ | はい | いいえ | いいえ |

## シーケンス図
```mermaid
sequenceDiagram
    participant Client
    participant HeapTimer
    participant Node

    Client->>HeapTimer: Push(key, expiration, callback)
    HeapTimer->>Node: Create Node with key, expiration, callback
    HeapTimer->>HeapTimer: Add Node to nodes_
    HeapTimer->>HeapTimer: Update key_to_idx_
    HeapTimer->>HeapTimer: ShiftUp(idx)

    Client->>HeapTimer: Adjust(key, new_expiration)
    HeapTimer->>Node: Find Node by key
    HeapTimer->>Node: Update expiration
    alt shift_up
        true
            HeapTimer->>HeapTimer: ShiftUp(idx)
        false
            HeapTimer->>HeapTimer: ShiftDown(idx)
    end

    Client->>HeapTimer: Tick()
    loop while not Empty()
        alt nodes_.front().Expired()
            true
                HeapTimer->>Node: Invoke callback
                HeapTimer->>HeapTimer: RemoveByIndex(0)
            false
                break
        end
    end

    Client->>HeapTimer: Remove(key)
    HeapTimer->>Node: Find Node by key
    alt Contain(key)
        true
            HeapTimer->>HeapTimer: RemoveByIndex(idx)
            return true
        false
            return false
    end

    Client->>HeapTimer: Invoke(key)
    HeapTimer->>Node: Find Node by key
    HeapTimer->>Node: Invoke callback
    HeapTimer->>HeapTimer: RemoveByIndex(idx)

    Client->>HeapTimer: Pop()
    alt not Empty()
        true
            HeapTimer->>HeapTimer: RemoveByIndex(0)
            return key
        false
            throw std::out_of_range
    end

    Client->>HeapTimer: Clear()
    HeapTimer->>nodes_: clear()
    HeapTimer->>key_to_idx_: clear()

    Client->>HeapTimer: Contain(key)
    HeapTimer->>key_to_idx_: contains(key)
    return bool

    Client->>HeapTimer: Empty()
    HeapTimer->>nodes_: empty()
    return bool

    Client->>HeapTimer: Size()
    HeapTimer->>nodes_: size()
    return std::size_t

    Client->>HeapTimer: ToNextTick()
    HeapTimer->>HeapTimer: Tick()
    alt not Empty()
        true
            HeapTimer->>Node: Calculate interval
            return interval
        false
            return Clock::duration::zero()
    end
```

## メソッド仕様書

### `Push`
- **目的**: タイマーを追加する。
- **引数**:
  - `key`: タイマーのキー (`const Key&`)
  - `expiration`: 期限時間 (`Clock::duration` または `Clock::time_point`)
  - `callback`: 期限切れ時に呼び出すコールバック関数 (`TimeOutCallback`)
- **戻り値**: なし
- **動作**:
  - タイマーが存在しない場合、新しいノードを作成しヒープに追加する。
  - 存在する場合は、そのタイマーの期限時間を調整する。
- **副作用**: ヒープ構造を再調整する。

### `Adjust`
- **目的**: 指定したキーのタイマーの期限時間を変更する。
- **引数**:
  - `key`: タイマーのキー (`const Key&`)
  - `expiration`: 新しい期限時間 (`Clock::duration` または `Clock::time_point`)
- **戻り値**: なし
- **動作**:
  - 指定したキーのタイマーを見つけ、その期限時間を変更する。
  - 必要に応じてヒープ構造を再調整する。
- **例外**: `std::out_of_range` (指定したキーが存在しない場合)

### `Tick`
- **目的**: 期限切れのタイマーを探し、コールバックを呼び出す。ヒープから削除する。
- **引数**: なし
- **戻り値**: なし
- **動作**:
  - ヒープが空でない限り、最も期限切れのノードを取り出し、そのコールバックを呼び出す。
  - コールバック呼び出し中に例外が発生した場合はログに記録する。

### `Remove`
- **目的**: 指定したキーのタイマーを削除する。
- **引数**:
  - `key`: タイマーのキー (`const Key&`)
- **戻り値**: 削除が成功したかどうか (`bool`)
- **動作**:
  - 指定したキーのタイマーを見つけ、ヒープから削除する。
- **例外**: 無し

### `Invoke`
- **目的**: 指定したキーのタイマーを削除し、コールバックを呼び出す。
- **引数**:
  - `key`: タイマーのキー (`const Key&`)
- **戻り値**: なし
- **動作**:
  - 指定したキーのタイマーを見つけ、そのコールバックを呼び出す。
  - コールバック呼び出し中に例外が発生した場合はログに記録する。
  - タイマーをヒープから削除する。
- **例外**: `std::out_of_range` (指定したキーが存在しない場合)

### `Pop`
- **目的**: 最も期限切れのタイマーをヒープから削除してそのキーを返す。
- **引数**: なし
- **戻り値**: タイマーのキー (`Key`)
- **動作**:
  - ヒープが空でない場合、最も期限切れのノードを取り出し、そのキーを返す。
- **例外**: `std::out_of_range` (ヒープが空の場合)

### `Clear`
- **目的**: タイマーシステムをクリアする。
- **引数**: なし
- **戻り値**: なし
- **動作**:
  - ヒープとキーインデックスマップをクリアする。

### `Contain`
- **目的**: 指定したキーのタイマーが存在するか確認する。
- **引数**:
  - `key`: タイマーのキー (`const Key&`)
- **戻り値**: 存在するかどうか (`bool`)

### `Empty`
- **目的**: タイマーシステムが空であるか確認する。
- **引数**: なし
- **戻り値**: 空であるかどうか (`bool`)

### `Size`
- **目的**: タイマーシステム内のタイマー数を返す。
- **引数**: なし
- **戻り値**: タイマー数 (`std::size_t`)

### `ToNextTick`
- **目的**: 次の期限切れまでの時間を返す。
- **引数**: なし
- **戻り値**: 次の期限切れまでの時間 (`Clock::duration`)
- **動作**:
  - `Tick()` を呼び出し、ヒープが空でない場合、最も期限切れのノードとの間隔を計算して返す。
  - ヒープが空の場合、`Clock::duration::zero()` を返す。

## 処理フロー図
```mermaid
graph TD
    A[Push] --> B{Contain(key)?}
    B -- Yes --> C[Adjust]
    B -- No --> D[Create Node]
    D --> E[Add to nodes_]
    E --> F[Update key_to_idx_]
    F --> G[ShiftUp(idx)]
    G --> H[Return]

    I[Adjust] --> J{Contain(key)?}
    J -- Yes --> K[Find Node]
    K --> L[Update expiration]
    L --> M{shift_up?}
    M -- Yes --> N[ShiftUp(idx)]
    M -- No --> O[ShiftDown(idx)]
    N --> H
    O --> H
    J -- No --> P[Throw std::out_of_range]

    Q[Tick] --> R{Empty()?}
    R -- No --> S[Find front node]
    S --> T{Expired()?}
    T -- Yes --> U[Invoke callback]
    U --> V[RemoveByIndex(0)]
    V --> W[Continue loop]
    T -- No --> X[Break loop]
    R -- Yes --> H

    Y[Remove] --> Z{Contain(key)?}
    Z -- Yes --> AA[Find Node]
    AA --> AB[RemoveByIndex(idx)]
    AB --> AC[Return true]
    Z -- No --> AD[Return false]

    AE[Invoke] --> AF{Contain(key)?}
    AF -- Yes --> AG[Find Node]
    AG --> AH[Invoke callback]
    AH --> AI[RemoveByIndex(idx)]
    AI --> H
    AF -- No --> AJ[Throw std::out_of_range]

    AK[Pop] --> AL{Empty()?}
    AL -- No --> AM[RemoveByIndex(0)]
    AM --> AN[Return key]
    AL -- Yes --> AO[Throw std::out_of_range]

    AP[Clear] --> AQ[Clear nodes_]
    AQ --> AR[Clear key_to_idx_]
    AR --> H

    AS[Contain] --> AT{key_to_idx_.contains(key)?}
    AT -- Yes --> AU[Return true]
    AT -- No --> AV[Return false]

    AW[Empty] --> AX[nodes_.empty()?]
    AX -- Yes --> AY[Return true]
    AX -- No --> AZ[Return false]

    BA[Size] --> BB[nodes_.size()]
    BB --> H

    BC[ToNextTick] --> BD[Tick()]
    BD --> BE{Empty()?}
    BE -- No --> BF[Calculate interval]
    BF --> BG[Return interval]
    BE -- Yes --> BH[Return Clock::duration::zero()]
```

## 状態遷移・副作用
| 更新前状態 | 遷移条件 | 変更対象 | 更新後状態 | 更新順序 | 外部資源への副作用 |
|------------|----------|----------|------------|----------|----------------------|
| 任意       | Push     | nodes_   | ノード追加 | 1        | 無し                 |
|            |          | key_to_idx_| キー追加   | 2        | 無し                 |
|            |          | nodes_   | ShiftUp    | 3        | 無し                 |
| 任意       | Adjust   | nodes_   | 期限変更   | 1        | 無し                 |
|            |          | nodes_   | ShiftUp/ShiftDown | 2      | 無し               |
| 任意       | Tick     | nodes_   | ノード削除 | 1        | コールバック呼び出し   |
|            |          | key_to_idx_| キー削除   | 2        | 無し                 |
| 任意       | Remove   | nodes_   | ノード削除 | 1        | 無し                 |
|            |          | key_to_idx_| キー削除   | 2        | 無し                 |
| 任意       | Invoke   | nodes_   | コールバック呼び出し | 1    | コールバック呼び出し |
|            |          | nodes_   | ノード削除 | 2        | 無し                 |
|            |          | key_to_idx_| キー削除   | 3        | 無し                 |
| 任意       | Pop      | nodes_   | ノード削除 | 1        | 無し                 |
|            |          | key_to_idx_| キー削除   | 2        | 無し                 |
| 任意       | Clear    | nodes_   | クリア     | 1        | 無し                 |
|            |          | key_to_idx_| クリア     | 2        | 無し                 |

## データ変換・制約
| 入力データ | 出力データ | 変換規則 | 値域 | 境界値 | 単位 | 精度 | encoding |
|------------|------------|----------|------|--------|------|------|----------|
| key        | key        | そのまま | 任意 | なし   | なし | なし | なし     |
| expiration | expiration | 相対時間→絶対時間 | 任意 | なし | 時間単位 | なし | なし |
| callback   | callback   | そのまま | 任意 | なし   | なし | なし | なし     |
| interval   | interval   | 絶対時間→相対時間 | 0以上 | 0    | 時間単位 | なし | なし |

これらの設計情報は、元コードから確認できる事実に基づいて記述されています。再実装に必要な詳細な情報を提供します。