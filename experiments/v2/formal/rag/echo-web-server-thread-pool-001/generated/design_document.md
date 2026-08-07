# 設計文書

## 1. 概要と責務

### 概要
`ThreadPool`クラスは、タスクを並列に処理するためのスレッドプールを提供します。タスクは関数オブジェクトとしてプッシュされ、スレッドプール内のワーカースレッドによって非同期に実行されます。

### 責務
- 指定された数のワーカースレッドを作成し管理する。
- タスクをキューに追加し、ワーカースレッドがタスクを処理できるように通知する。
- スレッドプールを終了させ、残っているタスクは実行せずにクリーンアップを行う。

## 2. 構造図

```mermaid
classDiagram
    class ThreadPool {
        +using Task = std::function<void()>
        +ThreadPool(std::optional<std::size_t> thread_count, log::Logger::Ptr logger) noexcept
        +~ThreadPool(const ThreadPool&) 
        +~ThreadPool(ThreadPool&&) 
        +~ThreadPool& operator=(const ThreadPool&)
        +~ThreadPool& operator=(ThreadPool&&)
        +void Start() noexcept
        +void Push(Task task) noexcept
        +void Close() noexcept
        -void ExecProc() noexcept
        -log::Logger::Ptr logger_
        -mutable std::mutex mtx_
        -std::atomic_bool closed_ {true}
        -std::size_t thread_count_
        -std::condition_variable cond_
        -std::list<Task> tasks_
        -std::list<std::thread> threads_
    }
```

## 3. インターフェースと依存関係

### 公開インターフェース
| 完全な名前 | 引数名, 型, 意味 | 戻り値の型と意味 | 修飾 | 使用するメンバ, 型, 定数, 列挙型, 型別名 | 呼び出す関数・メソッドとその目的 | 継承元, テンプレート型などの直接依存 |
|---|---|---|---|---|---|---|
| `ThreadPool::ThreadPool` | `thread_count`, `std::optional<std::size_t>`<br>スレッド数<br>`logger`, `log::Logger::Ptr`<br>ロガー | なし | `noexcept` | `logger_`, `thread_count_`, `closed_` | `log::RootLogger()` | `log::Logger::Ptr` |
| `ThreadPool::~ThreadPool` | なし | なし | `noexcept` | `threads_` | `Close()`, `std::thread::join` | なし |
| `ThreadPool::Start` | なし | なし | `noexcept` | `closed_`, `thread_count_`, `threads_` | `std::thread::emplace_back` | なし |
| `ThreadPool::Push` | `task`, `Task`<br>タスク | なし | `noexcept` | `mtx_`, `tasks_`, `cond_` | `std::lock_guard`, `std::move`, `std::condition_variable::notify_one` | なし |
| `ThreadPool::Close` | なし | なし | `noexcept` | `mtx_`, `closed_`, `cond_` | `std::lock_guard`, `std::condition_variable::notify_all` | なし |

### 実装上の処理
| 完全な名前 | 引数名, 型, 意味 | 戻り値の型と意味 | 修飾 | 使用するメンバ, 型, 定数, 列挙型, 型別名 | 呼び出す関数・メソッドとその目的 | 継承元, テンプレート型などの直接依存 |
|---|---|---|---|---|---|---|
| `ThreadPool::ExecProc` | なし | なし | `noexcept` | `mtx_`, `cond_`, `tasks_`, `closed_`, `logger_` | `std::unique_lock`, `std::condition_variable::wait`, `std::move`, `log::Event::Create`, `fmt::format`, `log::Logger::Log` | なし |

## 4. 処理フロー図

### `ThreadPool::Start`
```mermaid
flowchart TD
    A[開始] --> B{closed_?}
    B -- true --> C[assert(closed_)]
    B -- false --> D[closed_=false]
    D --> E[for i=0 to thread_count_-1]
    E --> F[threads_.emplace_back(&ThreadPool::ExecProc, this)]
    F --> G[i++]
    G --> H{終了条件?}
    H -- true --> I[終了]
    H -- false --> E
```

### `ThreadPool::Push`
```mermaid
flowchart TD
    A[開始] --> B{closed_?}
    B -- true --> C[assert(!closed_)]
    B -- false --> D[std::lock_guard locker {mtx_}]
    D --> E[tasks_.push_back(std::move(task))]
    E --> F[cond_.notify_one()]
    F --> G[終了]
```

### `ThreadPool::ExecProc`
```mermaid
flowchart TD
    A[開始] --> B[not_empty_or_closed = [&this]() noexcept {...}]
    B --> C[while (true)]
    C --> D[std::unique_lock locker {mtx_}]
    D --> E[cond_.wait(locker, not_empty_or_closed)]
    E --> F{closed_?}
    F -- true --> G[return]
    F -- false --> H[task = std::move(tasks_.front())]
    H --> I[tasks_.pop_front()]
    I --> J[try { task(); }]
    J --> K{catch (const std::exception& err)?}
    K -- true --> L[logger_->Log(...)]
    K -- false --> M[終了]
    M --> C
```

## 5. シーケンス図

該当なし。元コードから複数の関数、メソッド、オブジェクト間の呼び出し順序を直接確認できない。

## 6. 関数・メソッド仕様書

### `ThreadPool::ThreadPool`
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::ThreadPool::ThreadPool` |
| 目的 | スレッドプールを作成する。 |
| 引数 | `thread_count`, `std::optional<std::size_t>`<br>スレッド数<br>`logger`, `log::Logger::Ptr`<br>ロガー |
| 戻り値 | なし |
| 前提条件 | なし |
| 事後条件 | スレッドプールが初期化され、タスクキューとワーカースレッドリストが空になる。 |
| 動作の説明 | `thread_count`が指定されていない場合や0の場合、ハードウェアがサポートする並列スレッド数を使用する。<br>`logger`が指定されていない場合は、グローバルルートロガーを使用する。 |
| 状態変更・副作用 | `logger_`, `thread_count_`, `closed_`の初期化 |
| 依存関係 | `log::Logger::Ptr`, `std::optional<std::size_t>`, `std::move`, `std::thread::hardware_concurrency` |
| 境界条件 | `thread_count`が0または指定されていない場合、ハードウェアの並列スレッド数を使用する。 |
| エラー処理 | 明示的なエラー処理は確認できない |
| 不変条件 | なし |

### `ThreadPool::~ThreadPool`
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::ThreadPool::~ThreadPool` |
| 目的 | スレッドプールを破棄する。 |
| 引数 | なし |
| 戻り値 | なし |
| 前提条件 | なし |
| 事後条件 | 全てのワーカースレッドが終了し、リソースが解放される。 |
| 動作の説明 | `Close()`を呼び出してタスクキューをクリアし、ワーカースレッドを終了させる。<br>各スレッドがjoin可能であることを確認し、joinする。 |
| 状態変更・副作用 | `threads_`の各スレッドが終了される |
| 依存関係 | `Close()`, `std::thread::join`, `assert` |
| 境界条件 | なし |
| エラー処理 | 明示的なエラー処理は確認できない |
| 不変条件 | なし |

### `ThreadPool::Start`
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::ThreadPool::Start` |
| 目的 | スレッドプールを開始する。 |
| 引数 | なし |
| 戻り値 | なし |
| 前提条件 | `closed_`がtrueである |
| 事後条件 | `closed_`がfalseになり、指定された数のワーカースレッドが作成される。 |
| 動作の説明 | `closed_`をfalseに設定し、指定された数のワーカースレッドを作成する。<br>各ワーカースレッドは`ExecProc()`を実行する。 |
| 状態変更・副作用 | `closed_`, `threads_`の更新 |
| 依存関係 | `std::thread::emplace_back` |
| 境界条件 | なし |
| エラー処理 | 明示的なエラー処理は確認できない |
| 不変条件 | なし |

### `ThreadPool::Push`
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::ThreadPool::Push` |
| 目的 | タスクをスレッドプールに追加する。 |
| 引数 | `task`, `Task`<br>タスク |
| 戻り値 | なし |
| 前提条件 | `closed_`がfalseである |
| 事後条件 | タスクキューにタスクが追加され、ワーカースレッドに通知される。 |
| 動作の説明 | `mtx_`でロックを取得し、タスクキューにタスクを追加する。<br>ワーカースレッドにタスクが追加されたことを通知する。 |
| 状態変更・副作用 | `tasks_`, `cond_`の更新 |
| 依存関係 | `std::lock_guard`, `std::move`, `std::condition_variable::notify_one` |
| 境界条件 | なし |
| エラー処理 | 明示的なエラー処理は確認できない |
| 不変条件 | なし |

### `ThreadPool::Close`
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::ThreadPool::Close` |
| 目的 | スレッドプールを終了する。 |
| 引数 | なし |
| 戻り値 | なし |
| 前提条件 | なし |
| 事後条件 | `closed_`がtrueになり、ワーカースレッドに終了通知される。 |
| 動作の説明 | `mtx_`でロックを取得し、`closed_`をtrueに設定する。<br>ワーカースレッドに終了通知を送る。 |
| 状態変更・副作用 | `closed_`, `cond_`の更新 |
| 依存関係 | `std::lock_guard`, `std::condition_variable::notify_all` |
| 境界条件 | なし |
| エラー処理 | 明示的なエラー処理は確認できない |
| 不変条件 | なし |

### `ThreadPool::ExecProc`
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::ThreadPool::ExecProc` |
| 目的 | タスクキューからタスクを取得し実行する。 |
| 引数 | なし |
| 戻り値 | なし |
| 前提条件 | なし |
| 事後条件 | タスクキューが空になるまでタスクが処理される。<br>`closed_`がtrueになると終了する。 |
| 動作の説明 | `not_empty_or_closed`ラムダ式を定義し、タスクキューが空でないか、またはスレッドプールが閉じているかをチェックする。<br>タスクキューからタスクを取得し実行する。<br>例外が発生した場合はロガーに記録する。 |
| 状態変更・副作用 | `tasks_`の更新, 例外発生時のログ出力 |
| 依存関係 | `std::unique_lock`, `std::condition_variable::wait`, `std::move`, `log::Event::Create`, `fmt::format`, `log::Logger::Log` |
| 境界条件 | なし |
| エラー処理 | 例外が発生した場合はロガーに記録する。 |
| 不変条件 | なし |

## 7. 状態遷移と重要な条件

### `closed_`
- 更新前の状態: true
- 更新条件: `Start()`メソッド呼び出し時
- 更新対象と更新値: `closed_=false`
- 更新されない条件: `Start()`が呼ばれていない場合
- 更新順序: `closed_`をfalseに設定する前にワーカースレッドを作成しない。
- 処理後に成立する条件: `closed_`がfalseである。

### `tasks_`
- 更新前の状態: 空
- 更新条件: `Push()`メソッド呼び出し時
- 更新対象と更新値: タスクキューにタスクを追加する。
- 更新されない条件: `Push()`が呼ばれていない場合
- 更新順序: ロックを取得してからタスクキューにタスクを追加し、通知を行う。
- 処理後に成立する条件: タスクキューにタスクが追加される。

## 8. 確認不能事項

確認不能事項なし