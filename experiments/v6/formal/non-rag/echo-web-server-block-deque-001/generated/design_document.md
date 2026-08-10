# デザイン文書: block-dequeモジュール

## 責務
`BlockDeque`クラスは、スレッドセーフなブロックデキューを提供します。最大容量を超えた場合の挿入操作は待機し、消費者が要素を取り出すまでブロックされます。

## 公開インターフェース
- `explicit BlockDeque(std::size_t capacity = 1000) noexcept;`
- `void Clear() noexcept;`
- `bool Empty() const noexcept;`
- `bool Full() const noexcept;`
- `std::size_t Size() const noexcept;`
- `std::size_t Capacity() const noexcept;`
- `void PushBack(T item) noexcept;`
- `void PushFront(T item) noexcept;`
- `const T& Front() const noexcept;`
- `const T& Back() const noexcept;`
- `T& Front() noexcept;`
- `T& Back() noexcept;`
- `std::optional<T> Pop(std::optional<Clock::duration> time_out = std::nullopt) noexcept;`
- `void Flush() noexcept;`
- `void Close() noexcept;`

## 入力
- コンストラクタ: 最大容量 (`capacity`)
- `PushBack`, `PushFront`: 追加する要素 (`item`)
- `Pop`: タイムアウト時間 (`time_out`)

## 出力
- `Empty`, `Full`: ブール値
- `Size`, `Capacity`: 要素数や容量を表すサイズ型
- `Front`, `Back`: コンテナ内の要素への参照
- `Pop`: オプションでラップされた要素

## 状態
- `mtx_`: ミューテックスオブジェクト (`std::mutex`)
- `closed_`: キューが閉じているかどうかを表すアトミックなブール値 (`std::atomic_bool`)
- `capacity_`: 最大容量 (`std::size_t`)
- `deq_`: 実際のデータ格納用デキュー (`std::deque<T>`)
- `consumer_cond_`, `producer_cond_`: コンシューマとプロデューサのための条件変数 (`std::condition_variable`)

## 処理手順
1. **コンストラクタ**: 最大容量を設定し、アサートで検証。
2. **PushBack, PushFront**: ミューテックスロックを取得し、必要に応じて待機してから要素を追加し、通知する。
3. **Pop**: タイムアウトオプションに基づいて待機し、要素を取り出す。キューが閉じている場合は空のオプションを返す。
4. **Clear, ClearNoLock**: データをクリアする。
5. **Close**: キューを閉じて通知する。

## 例外・失敗条件
- `PushBack`, `PushFront`: キューが閉じている場合、挿入操作は待機し続ける。
- `Pop`: タイムアウトまたはキューが閉じている場合、空のオプションを返す。
- `Front`, `Back`: キューが空の場合、アサートで検証。

## 依存関係
- `<cassert>`
- `<condition_variable>`
- `<deque>`
- `<mutex>`
- `<optional>`
- `<utility>`

## 重要な不変条件
- `capacity_`は常に正である。
- `deq_.size()`は常に`capacity_`以下である。

# 追加詳細設計情報

## クラス図
```mermaid
classDiagram
    class BlockDeque {
        +Clock Clock
        +BlockDeque(std::size_t capacity) noexcept
        +void Clear() noexcept
        +bool Empty() const noexcept
        +bool Full() const noexcept
        +std::size_t Size() const noexcept
        +std::size_t Capacity() const noexcept
        +void PushBack(T item) noexcept
        +void PushFront(T item) noexcept
        +const T& Front() const noexcept
        +const T& Back() const noexcept
        +T& Front() noexcept
        +T& Back() noexcept
        +std::optional~T~ Pop(std::optional~Clock::duration~ time_out = std::nullopt) noexcept
        +void Flush() noexcept
        +void Close() noexcept
        -void WaitForSpace(std::unique_lock~std::mutex~& locker) noexcept
        -void ClearNoLock() noexcept
        -mutable std::mutex mtx_
        -std::atomic_bool closed_
        -std::size_t capacity_
        -std::deque~T~ deq_
        -std::condition_variable consumer_cond_
        -std::condition_variable producer_cond_
    }
```

## クラス・メソッド・インターフェース詳細
| 名前 | 完全な名前 | 属性 | 引数名と型 | 戻り値型 | 可視性 | const | 参照/ポインタ | static | virtual | noexcept |
|------|------------|------|------------|----------|--------|-------|---------------|--------|---------|----------|
| コンストラクタ | `BlockDeque(std::size_t capacity)` | - | `capacity` / `std::size_t` | - | public | - | - | - | - | はい |
| Clear | `void Clear()` | - | - | - | public | - | - | - | - | はい |
| Empty | `bool Empty() const` | - | - | `bool` | public | はい | - | - | - | はい |
| Full | `bool Full() const` | - | - | `bool` | public | はい | - | - | - | はい |
| Size | `std::size_t Size() const` | - | - | `std::size_t` | public | はい | - | - | - | はい |
| Capacity | `std::size_t Capacity() const` | - | - | `std::size_t` | public | はい | - | - | - | はい |
| PushBack | `void PushBack(T item)` | - | `item` / `T` | - | public | - | - | - | - | はい |
| PushFront | `void PushFront(T item)` | - | `item` / `T` | - | public | - | - | - | - | はい |
| Front (const) | `const T& Front() const` | - | - | `const T&` | public | はい | - | - | - | はい |
| Back (const) | `const T& Back() const` | - | - | `const T&` | public | はい | - | - | - | はい |
| Front (non-const) | `T& Front()` | - | - | `T&` | public | - | - | - | - | はい |
| Back (non-const) | `T& Back()` | - | - | `T&` | public | - | - | - | - | はい |
| Pop | `std::optional<T> Pop(std::optional<Clock::duration> time_out)` | - | `time_out` / `std::optional<Clock::duration>` | `std::optional<T>` | public | - | - | - | - | はい |
| Flush | `void Flush()` | - | - | - | public | - | - | - | - | はい |
| Close | `void Close()` | - | - | - | public | - | - | - | - | はい |
| WaitForSpace | `void WaitForSpace(std::unique_lock<std::mutex>& locker)` | - | `locker` / `std::unique_lock<std::mutex>&` | - | private | - | 参照 | - | - | はい |
| ClearNoLock | `void ClearNoLock()` | - | - | - | private | - | - | - | - | はい |

## シーケンス図
```mermaid
sequenceDiagram
    participant Producer as プロデューサ
    participant BlockDeque as BlockDeque
    participant Consumer as コンシューマ

    Producer->>BlockDeque: PushBack(item)
    alt deq_.size() < capacity_
        BlockDeque->>deq_: push_back(item)
        BlockDeque->>Consumer: notify_one()
    else deq_.size() == capacity_
        Producer->>BlockDeque: WaitForSpace(locker)
        Consumer->>BlockDeque: Pop(time_out)
        alt !deq_.empty() || closed_
            Consumer->>deq_: pop_front()
            Consumer->>Producer: notify_one()
            BlockDeque->>Consumer: return item
        else closed_
            BlockDeque->>Consumer: return std::nullopt
        end
    end

    Producer->>BlockDeque: Close()
    BlockDeque->>deq_: clear()
    BlockDeque->>closed_: true
    BlockDeque->>Producer: notify_all()
    BlockDeque->>Consumer: notify_all()
```

## メソッド仕様書
### PushBack
- **目的**: 要素をデキューの末尾に追加し、消費者に通知する。
- **引数**: `item` / `T`
- **戻り値**: なし
- **動作**: ミューテックスロックを取得し、必要に応じて待機してから要素を追加し、通知する。
- **副作用**: データの追加と条件変数への通知。

### Pop
- **目的**: デキューの先頭から要素を取り出す。タイムアウトオプションに基づいて待機する。
- **引数**: `time_out` / `std::optional<Clock::duration>`
- **戻り値**: オプションでラップされた要素 (`std::optional<T>`)
- **動作**: タイムアウトオプションに基づいて待機し、要素を取り出す。キューが閉じている場合は空のオプションを返す。
- **副作用**: データの取り出しと条件変数への通知。

## 処理フロー図
```mermaid
graph TD
    A[PushBack] --> B{deq_.size() < capacity_?}
    B -- はい --> C[deq_.push_back(item)]
    C --> D[consumer_cond_.notify_one()]
    B -- いいえ --> E[WaitForSpace(locker)]
    E --> F{!deq_.empty() || closed_?}
    F -- はい --> G[deq_.pop_front()]
    G --> H[producer_cond_.notify_one()]
    F -- いいえ --> I[return std::nullopt]
    D --> J[return]
    H --> K[return item]
```

## 状態遷移・副作用
| 更新前状態 | 遷移条件 | 変更対象 | 更新後状態 | 更新順序 | 副作用 |
|------------|----------|----------|------------|----------|--------|
| 任意       | PushBack | deq_     | 要素追加   | -        | consumer_cond_.notify_one() |
| 任意       | Pop      | deq_     | 要素取り出し | -        | producer_cond_.notify_one() |
| 任意       | Close    | closed_  | true       | -        | producer_cond_.notify_all(), consumer_cond_.notify_all() |

## データ変換・制約
| 入力データ | 出力データ | 変換規則 | 値域 | 境界値 |
|------------|------------|----------|------|--------|
| item       | deq_       | 追加     | -    | -      |
| time_out   | std::optional<T> | 待機と取り出し | -    | -      |

この設計文書は、`block_deque.h`ファイルの内容を基に再実装に必要な詳細情報を提供します。

# Machine-extracted Source-local Implementation Contract

This appendix is deterministic evidence extracted from the target source.
It is not an LLM summary and it does not contain complete function bodies.

During regeneration:
- preserve the exact local declaration types, containers, initializers, and literals listed below;
- preserve the exact call targets and argument expressions listed below;
- do not substitute a different representation or accessor merely because it looks similar;
- treat these items as exact constraints, not as pseudocode suggestions.

## Exact local declarations

- `const std::lock_guard locker {mtx_};`
- `const auto size {this->Size()};`
- `std::unique_lock locker {mtx_};`
- `const auto not_empty_or_closed {[this]() noexcept { // Consumer threads may not have started to wait when closing the deque. // If a close notification has been sent before they wait, // the condition variable will permanently block the thread. // So we should check if the queue has been closed when waiting. return !deq_.empty() || closed_; }};`
- `const auto item {deq_.front()};`

## Exact top-level call expressions

- `assert(capacity > 0)`
- `Close()`
- `deq_.empty()`
- `this->Size()`
- `assert(size <= capacity_)`
- `deq_.size()`
- `ClearNoLock()`
- `producer_cond_.notify_all()`
- `consumer_cond_.notify_all()`
- `deq_.clear()`
- `consumer_cond_.notify_one()`
- `WaitForSpace(locker)`
- `deq_.push_back(std::move(item))`
- `Flush()`
- `deq_.push_front(std::move(item))`
- `assert(!deq_.empty())`
- `deq_.front()`
- `deq_.back()`
- `const_cast<T&>(std::as_const(*this).Front())`
- `const_cast<T&>(std::as_const(*this).Back())`
- `time_out.has_value()`
- `consumer_cond_.wait_for(locker, *time_out, not_empty_or_closed)`
- `consumer_cond_.wait(locker, not_empty_or_closed)`
- `deq_.pop_front()`
- `producer_cond_.notify_one()`
- `producer_cond_.wait(locker, [this]() { return deq_.size() < capacity_; })`
