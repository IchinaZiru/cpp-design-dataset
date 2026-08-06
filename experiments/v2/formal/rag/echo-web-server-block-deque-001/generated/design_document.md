# デザイン文書: block-dequeモジュール

## 1. 概要と責務
`block_deque.h`は、スレッドセーフなブロックデキュー（両端キュー）を提供するテンプレートクラス`BlockDeque`を定義しています。このクラスは、最大容量を超えた場合にプッシュ操作がブロッキングされ、消費者スレッドが通知される仕組みを持っています。

## 2. 構造図
```mermaid
classDiagram
    class BlockDeque {
        +Clock::duration Clock
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
        +std::optional<T> Pop(std::optional<Clock::duration> time_out = std::nullopt) noexcept
        +void Flush() noexcept
        +void Close() noexcept
        -void WaitForSpace(std::unique_lock<std::mutex>& locker) noexcept
        -void ClearNoLock() noexcept
        -mutable std::mutex mtx_
        -std::atomic_bool closed_ {false}
        -std::size_t capacity_
        -std::deque<T> deq_
        -std::condition_variable consumer_cond_
        -std::condition_variable producer_cond_
    }
```

## 3. インターフェースと依存関係

### 公開インターフェース
- **`BlockDeque(std::size_t capacity) noexcept`**
  - 引数: `capacity` (キューの最大容量)
  - 戻り値: 無し
  - 目的: キューを初期化する。
  - 使用するメンバ: `capacity_`
  - 呼び出す関数・メソッド: `assert`

- **`void Clear() noexcept`**
  - 引数: 無し
  - 戻り値: 無し
  - 目的: キュー内のすべての要素をクリアする。
  - 使用するメンバ: `mtx_`, `ClearNoLock`

- **`bool Empty() const noexcept`**
  - 引数: 無し
  - 戻り値: `bool` (キューが空かどうか)
  - 目的: キューが空であるかを確認する。
  - 使用するメンバ: `mtx_`, `deq_`

- **`bool Full() const noexcept`**
  - 引数: 無し
  - 戻り値: `bool` (キューが満杯かどうか)
  - 目的: キューが満杯であるかを確認する。
  - 使用するメンバ: `capacity_`, `deq_`

- **`std::size_t Size() const noexcept`**
  - 引数: 無し
  - 戻り値: `std::size_t` (キュー内の要素数)
  - 目的: キュー内の要素数を取得する。
  - 使用するメンバ: `mtx_`, `deq_`

- **`std::size_t Capacity() const noexcept`**
  - 引数: 無し
  - 戻り値: `std::size_t` (キューの最大容量)
  - 目的: キューの最大容量を取得する。
  - 使用するメンバ: `capacity_`

- **`void PushBack(T item) noexcept`**
  - 引数: `item` (追加する要素)
  - 戻り値: 無し
  - 目的: キューの末尾に要素を追加し、消費者スレッドに通知する。
  - 使用するメンバ: `mtx_`, `deq_`, `producer_cond_`, `consumer_cond_`
  - 呼び出す関数・メソッド: `WaitForSpace`, `Flush`

- **`void PushFront(T item) noexcept`**
  - 引数: `item` (追加する要素)
  - 戻り値: 無し
  - 目的: キューの先頭に要素を挿入し、消費者スレッドに通知する。
  - 使用するメンバ: `mtx_`, `deq_`, `producer_cond_`, `consumer_cond_`
  - 呼び出す関数・メソッド: `WaitForSpace`, `Flush`

- **`const T& Front() const noexcept`**
  - 引数: 無し
  - 戻り値: `const T&` (先頭要素への参照)
  - 目的: キューの先頭要素を取得する。
  - 使用するメンバ: `mtx_`, `deq_`

- **`const T& Back() const noexcept`**
  - 引数: 無し
  - 戻り値: `const T&` (末尾要素への参照)
  - 目的: キューの末尾要素を取得する。
  - 使用するメンバ: `mtx_`, `deq_`

- **`T& Front() noexcept`**
  - 引数: 無し
  - 戻り値: `T&` (先頭要素への参照)
  - 目的: キューの先頭要素を取得する。
  - 使用するメンバ: `mtx_`, `deq_`

- **`T& Back() noexcept`**
  - 引数: 無し
  - 戻り値: `T&` (末尾要素への参照)
  - 目的: キューの末尾要素を取得する。
  - 使用するメンバ: `mtx_`, `deq_`

- **`std::optional<T> Pop(std::optional<Clock::duration> time_out = std::nullopt) noexcept`**
  - 引数: `time_out` (タイムアウト時間)
  - 戻り値: `std::optional<T>` (取得した要素または空)
  - 目的: キューから先頭要素をポップする。タイムアウト時間を指定できる。
  - 使用するメンバ: `mtx_`, `deq_`, `consumer_cond_`, `producer_cond_`

- **`void Flush() noexcept`**
  - 引数: 無し
  - 戻り値: 無し
  - 目的: 消費者スレッドに通知する。
  - 使用するメンバ: `consumer_cond_`

- **`void Close() noexcept`**
  - 引数: 無し
  - 戻り値: 無し
  - 目的: キューを閉じ、すべての要素をクリアし、プロデューサーと消費者スレッドに通知する。
  - 使用するメンバ: `mtx_`, `closed_`, `deq_`, `producer_cond_`, `consumer_cond_`
  - 呼び出す関数・メソッド: `ClearNoLock`

### 実装上の処理
- **`void WaitForSpace(std::unique_lock<std::mutex>& locker) noexcept`**
  - 引数: `locker` (ミューテックスロック)
  - 戻り値: 無し
  - 目的: キューに空きができるまで待つ。
  - 使用するメンバ: `producer_cond_`, `deq_`

- **`void ClearNoLock() noexcept`**
  - 引数: 無し
  - 戻り値: 無し
  - 目的: キュー内のすべての要素をクリアする。ロックは取得済みと仮定。
  - 使用するメンバ: `deq_`

## 4. 処理フロー図

### PushBackメソッド
```mermaid
flowchart TD
    A[PushBack] --> B{mtx_.lock()}
    B --> C[WaitForSpace]
    C --> D[deq_.push_back(item)]
    D --> E[Flush]
    E --> F[mtx_.unlock()]
```

### Popメソッド
```mermaid
flowchart TD
    A[Pop] --> B{mtx_.lock()}
    B --> C{time_out.has_value()?}
    C -- Yes --> D[consumer_cond_.wait_for(locker, *time_out, not_empty_or_closed)]
    C -- No --> E[consumer_cond_.wait(locker, not_empty_or_closed)]
    D --> F{closed_?}
    E --> F
    F -- Yes --> G[return std::nullopt]
    F -- No --> H[deq_.pop_front()]
    H --> I[producer_cond_.notify_one()]
    I --> J[mtx_.unlock()]
    J --> K[return item]
```

## 5. シーケンス図
該当なし。元コードから複数の関数、メソッド、オブジェクト間の呼び出し順序を直接確認できない。

## 6. 関数・メソッド仕様書

### `BlockDeque(std::size_t capacity) noexcept`
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::BlockDeque<T>::BlockDeque` |
| 目的 | キューを初期化する。 |
| 引数 | `capacity` (キューの最大容量) |
| 戻り値 | 無し |
| 前提条件 | `capacity > 0` |
| 事後条件 | `capacity_ == capacity`, `deq_.empty() == true` |
| 動作の説明 | コンストラクタで最大容量を設定し、内部デキューを初期化する。 |
| 状態変更・副作用 | `capacity_`, `deq_` |
| 依存関係 | `assert` |
| 境界条件 | `capacity == 1`, `capacity == 最大値` |
| エラー処理 | `capacity <= 0` の場合、アサートが発生する。 |
| 不変条件 | 無し |

### `void Clear() noexcept`
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::BlockDeque<T>::Clear` |
| 目的 | キュー内のすべての要素をクリアする。 |
| 引数 | 無し |
| 戻り値 | 無し |
| 前提条件 | 無し |
| 事後条件 | `deq_.empty() == true` |
| 動作の説明 | ロックを取得して内部デキューをクリアする。 |
| 状態変更・副作用 | `deq_` |
| 依存関係 | `mtx_`, `ClearNoLock` |
| 境界条件 | キューが空の場合、何もしない。 |
| エラー処理 | 明示的なエラー処理は確認できない |
| 不変条件 | 無し |

### `bool Empty() const noexcept`
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::BlockDeque<T>::Empty` |
| 目的 | キューが空であるかを確認する。 |
| 引数 | 無し |
| 戻り値 | `bool` (キューが空かどうか) |
| 前提条件 | 無し |
| 事後条件 | 無し |
| 動作の説明 | ロックを取得して内部デキューが空であるか確認する。 |
| 状態変更・副作用 | 無し |
| 依存関係 | `mtx_`, `deq_` |
| 境界条件 | キューが空の場合、`true` を返す。 |
| エラー処理 | 明示的なエラー処理は確認できない |
| 不変条件 | 無し |

### `bool Full() const noexcept`
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::BlockDeque<T>::Full` |
| 目的 | キューが満杯であるかを確認する。 |
| 引数 | 無し |
| 戻り値 | `bool` (キューが満杯かどうか) |
| 前提条件 | 無し |
| 事後条件 | 無し |
| 動作の説明 | キューのサイズと最大容量を比較して満杯であるか確認する。 |
| 状態変更・副作用 | 無し |
| 依存関係 | `capacity_`, `deq_` |
| 境界条件 | キューが満杯の場合、`true` を返す。 |
| エラー処理 | 明示的なエラー処理は確認できない |
| 不変条件 | 無し |

### `std::size_t Size() const noexcept`
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::BlockDeque<T>::Size` |
| 目的 | キュー内の要素数を取得する。 |
| 引数 | 無し |
| 戻り値 | `std::size_t` (キュー内の要素数) |
| 前提条件 | 無し |
| 事後条件 | 無し |
| 動作の説明 | ロックを取得して内部デキューのサイズを返す。 |
| 状態変更・副作用 | 無し |
| 依存関係 | `mtx_`, `deq_` |
| 境界条件 | キューが空の場合、`0` を返す。 |
| エラー処理 | 明示的なエラー処理は確認できない |
| 不変条件 | 無し |

### `std::size_t Capacity() const noexcept`
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::BlockDeque<T>::Capacity` |
| 目的 | キューの最大容量を取得する。 |
| 引数 | 無し |
| 戻り値 | `std::size_t` (キューの最大容量) |
| 前提条件 | 無し |
| 事後条件 | 無し |
| 動作の説明 | 最大容量を返す。 |
| 状態変更・副作用 | 無し |
| 依存関係 | `capacity_` |
| 境界条件 | 無し |
| エラー処理 | 明示的なエラー処理は確認できない |
| 不変条件 | 無し |

### `void PushBack(T item) noexcept`
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::BlockDeque<T>::PushBack` |
| 目的 | キューの末尾に要素を追加し、消費者スレッドに通知する。 |
| 引数 | `item` (追加する要素) |
| 戻り値 | 無し |
| 前提条件 | 無し |
| 事後条件 | キューの末尾に要素が追加され、消費者スレッドに通知される。 |
| 動作の説明 | ロックを取得して空きがあるまで待つ。その後、要素を追加し、消費者スレッドに通知する。 |
| 状態変更・副作用 | `deq_`, `producer_cond_`, `consumer_cond_` |
| 依存関係 | `mtx_`, `WaitForSpace`, `Flush` |
| 境界条件 | キューが満杯の場合、空きができるまで待つ。 |
| エラー処理 | 明示的なエラー処理は確認できない |
| 不変条件 | 無し |

### `void PushFront(T item) noexcept`
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::BlockDeque<T>::PushFront` |
| 目的 | キューの先頭に要素を挿入し、消費者スレッドに通知する。 |
| 引数 | `item` (追加する要素) |
| 戻り値 | 無し |
| 前提条件 | 無し |
| 事後条件 | キューの先頭に要素が挿入され、消費者スレッドに通知される。 |
| 動作の説明 | ロックを取得して空きがあるまで待つ。その後、要素を挿入し、消費者スレッドに通知する。 |
| 状態変更・副作用 | `deq_`, `producer_cond_`, `consumer_cond_` |
| 依存関係 | `mtx_`, `WaitForSpace`, `Flush` |
| 境界条件 | キューが満杯の場合、空きができるまで待つ。 |
| エラー処理 | 明示的なエラー処理は確認できない |
| 不変条件 | 無し |

### `const T& Front() const noexcept`
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::BlockDeque<T>::Front` |
| 目的 | キューの先頭要素を取得する。 |
| 引数 | 無し |
| 戻り値 | `const T&` (先頭要素への参照) |
| 前提条件 | キューが空でない |
| 事後条件 | 無し |
| 動作の説明 | ロックを取得して先頭要素を返す。 |
| 状態変更・副作用 | 無し |
| 依存関係 | `mtx_`, `deq_` |
| 境界条件 | キューが空の場合、アサートが発生する。 |
| エラー処理 | 明示的なエラー処理は確認できない |
| 不変条件 | 無し |

### `const T& Back() const noexcept`
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::BlockDeque<T>::Back` |
| 目的 | キューの末尾要素を取得する。 |
| 引数 | 無し |
| 戻り値 | `const T&` (末尾要素への参照) |
| 前提条件 | キューが空でない |
| 事後条件 | 無し |
| 動作の説明 | ロックを取得して末尾要素を返す。 |
| 状態変更・副作用 | 無し |
| 依存関係 | `mtx_`, `deq_` |
| 境界条件 | キューが空の場合、アサートが発生する。 |
| エラー処理 | 明示的なエラー処理は確認できない |
| 不変条件 | 無し |

### `T& Front() noexcept`
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::BlockDeque<T>::Front` |
| 目的 | キューの先頭要素を取得する。 |
| 引数 | 無し |
| 戻り値 | `T&` (先頭要素への参照) |
| 前提条件 | キューが空でない |
| 事後条件 | 無し |
| 動作の説明 | 先頭要素を取得する。 |
| 状態変更・副作用 | 無し |
| 依存関係 | `mtx_`, `deq_` |
| 境界条件 | キューが空の場合、アサートが発生する。 |
| エラー処理 | 明示的なエラー処理は確認できない |
| 不変条件 | 無し |

### `T& Back() noexcept`
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::BlockDeque<T>::Back` |
| 目的 | キューの末尾要素を取得する。 |
| 引数 | 無し |
| 戻り値 | `T&` (末尾要素への参照) |
| 前提条件 | キューが空でない |
| 事後条件 | 無し |
| 動作の説明 | 末尾要素を取得する。 |
| 状態変更・副作用 | 無し |
| 依存関係 | `mtx_`, `deq_` |
| 境界条件 | キューが空の場合、アサートが発生する。 |
| エラー処理 | 明示的なエラー処理は確認できない |
| 不変条件 | 無し |

### `std::optional<T> Pop(std::optional<Clock::duration> time_out = std::nullopt) noexcept`
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::BlockDeque<T>::Pop` |
| 目的 | キューから先頭要素をポップする。タイムアウト時間を指定できる。 |
| 引数 | `time_out` (タイムアウト時間) |
| 戻り値 | `std::optional<T>` (取得した要素または空) |
| 前提条件 | 無し |
| 事後条件 | キューから要素がポップされ、プロデューサースレッドに通知される。 |
| 動作の説明 | ロックを取得してタイムアウト時間を考慮して待つ。その後、要素をポップし、プロデューサースレッドに通知する。 |
| 状態変更・副作用 | `deq_`, `producer_cond_` |
| 依存関係 | `mtx_`, `consumer_cond_` |
| 境界条件 | タイムアウト時間が指定されない場合、要素が追加されるまで待つ。 |
| エラー処理 | 明示的なエラー処理は確認できない |
| 不変条件 | 無し |

### `void Flush() noexcept`
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::BlockDeque<T>::Flush` |
| 目的 | 消費者スレッドに通知する。 |
| 引数 | 無し |
| 戻り値 | 無し |
| 前提条件 | 無し |
| 事後条件 | 消費者スレッドが通知される。 |
| 動作の説明 | 消費者スレッドに通知する。 |
| 状態変更・副作用 | `consumer_cond_` |
| 依存関係 | `consumer_cond_` |
| 境界条件 | 無し |
| エラー処理 | 明示的なエラー処理は確認できない |
| 不変条件 | 無し |

### `void Close() noexcept`
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::BlockDeque<T>::Close` |
| 目的 | キューを閉じ、すべての要素をクリアし、プロデューサーと消費者スレッドに通知する。 |
| 引数 | 無し |
| 戻り値 | 無し |
| 前提条件 | 無し |
| 事後条件 | キューが閉じられ、すべての要素がクリアされ、プロデューサーと消費者スレッドに通知される。 |
| 動作の説明 | ロックを取得してキューを閉じ、すべての要素をクリアし、プロデューサーと消費者スレッドに通知する。 |
| 状態変更・副作用 | `closed_`, `deq_`, `producer_cond_`, `consumer_cond_` |
| 依存関係 | `mtx_`, `ClearNoLock` |
| 境界条件 | キューが既に閉じている場合、何もしない。 |
| エラー処理 | 明示的なエラー処理は確認できない |
| 不変条件 | 無し |

### `void WaitForSpace(std::unique_lock<std::mutex>& locker) noexcept`
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::BlockDeque<T>::WaitForSpace` |
| 目的 | キューに空きができるまで待つ。 |
| 引数 | `locker` (ミューテックスロック) |
| 戻り値 | 無し |
| 前提条件 | ロックが取得されている |
| 事後条件 | キューに空きがある。 |
| 動作の説明 | キューに空きができるまで待つ。 |
| 状態変更・副作用 | `producer_cond_` |
| 依存関係 | `producer_cond_`, `deq_` |
| 境界条件 | キューが満杯の場合、空きができるまで待つ。 |
| エラー処理 | 明示的なエラー処理は確認できない |
| 不変条件 | 無し |

### `void ClearNoLock() noexcept`
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::BlockDeque<T>::ClearNoLock` |
| 目的 | キュー内のすべての要素をクリアする。ロックは取得済みと仮定。 |
| 引数 | 無し |
| 戻り値 | 無し |
| 前提条件 | ロックが取得されている |
| 事後条件 | キュー内のすべての要素がクリアされる。 |
| 動作の説明 | 内部デキューをクリアする。 |
| 状態変更・副作用 | `deq_` |
| 依存関係 | `deq_` |
| 境界条件 | キューが空の場合、何もしない。 |
| エラー処理 | 明示的なエラー処理は確認できない |
| 不変条件 | 無し |

## 7. 状態遷移と重要な条件

- **`closed_`**
  - 更新前の状態: `false`
  - 更新条件: `Close()` メソッドが呼び出される。
  - 更新対象と更新値: `closed_ = true`
  - 更新されない条件: `Close()` メソッドが呼び出されていない。
  - 更新順序: `mtx_` をロックしてから更新する。
  - 処理後に成立する条件: `closed_ == true`

- **`deq_`**
  - 更新前の状態: 空または要素を含む
  - 更新条件: `PushBack()`, `PushFront()`, `Pop()`, `Clear()`, `Close()` メソッドが呼び出される。
  - 更新対象と更新値: `deq_.push_back(item)`, `deq_.push_front(item)`, `deq_.pop_front()`, `deq_.clear()`
  - 更新されない条件: 上記のメソッドが呼び出されていない。
  - 更新順序: ロックを取得してから更新する。
  - 処理後に成立する条件: キューの状態が適切に更新される。

## 8. 確認不能事項
確認不能事項なし