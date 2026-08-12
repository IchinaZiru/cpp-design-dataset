以下は、与えられたC++ソースコードを基にした詳細な設計仕様書です。この仕様書は、別のLLMが再実装できるように作成されています。

## 1. 概要

この仕様書は、`ws::ThreadPool`クラスの実装と宣言について記述しています。`ThreadPool`は、タスクを並行して実行するためのスレッドプールです。このクラスは、タスクの追加、スレッドプールの開始・終了、およびエラー処理を行うことができます。

## 2. クラス構造

### 2.1 クラス名
`ws::ThreadPool`

### 2.2 継承関係
なし

### 2.3 依存関係
- `std::function<void()>`
- `log::Logger::Ptr`
- `std::mutex`
- `std::condition_variable`
- `std::atomic_bool`
- `std::list<Task>`
- `std::list<std::thread>`

## 3. パブリックインターフェース

### 3.1 コンストラクタ
```cpp
explicit ThreadPool(std::optional<std::size_t> thread_count = std::nullopt,
                    log::Logger::Ptr logger = log::RootLogger()) noexcept;
```
- **パラメータ:**
  - `thread_count`: スレッドの数。指定されない場合は`std::thread::hardware_concurrency()`を使用します。
  - `logger`: ロガー。指定されない場合は`log::RootLogger()`を使用します。
- **例外:**
  - 投げません。

### 3.2 デストラクタ
```cpp
~ThreadPool() noexcept;
```
- **動作:**
  - `Close()`を呼び出し、すべてのスレッドを終了させます。
  - すべてのスレッドが`joinable()`であることを確認し、`join()`します。
- **例外:**
  - 投げません。

### 3.3 コピー・ムーブ禁止
```cpp
ThreadPool(const ThreadPool&) = delete;
ThreadPool(ThreadPool&&) = delete;
ThreadPool& operator=(const ThreadPool&) = delete;
ThreadPool& operator=(ThreadPool&&) = delete;
```

### 3.4 メソッド

#### 3.4.1 `Start()`
```cpp
void Start() noexcept;
```
- **動作:**
  - スレッドプールを開始し、指定された数のスレッドを生成します。
  - 各スレッドは`ExecProc()`を実行します。
- **前提条件:**
  - `closed_`が`true`であること。
- **例外:**
  - 投げません。

#### 3.4.2 `Push(Task task)`
```cpp
void Push(Task task) noexcept;
```
- **パラメータ:**
  - `task`: 実行するタスク。
- **動作:**
  - タスクをキューに追加し、1つのスレッドを通知します。
- **前提条件:**
  - `closed_`が`false`であること。
- **例外:**
  - 投げません。

#### 3.4.3 `Close()`
```cpp
void Close() noexcept;
```
- **動作:**
  - スレッドプールを閉じ、すべてのスレッドに終了を通知します。
- **例外:**
  - 投げません。

## 4. プライベートメンバー

### 4.1 メソッド

#### 4.1.1 `ExecProc()`
```cpp
void ExecProc() noexcept;
```
- **動作:**
  - タスクキューからタスクを取得し、実行します。
  - タスクが存在しない場合は、条件変数で待機します。
  - 例外が発生した場合は、ログに記録します。
- **例外:**
  - 投げません。

### 4.2 メンバ変数

| 名前 | 型 | 説明 |
|------|----|------|
| `logger_` | `log::Logger::Ptr` | ロガー。 |
| `mtx_` | `std::mutex` | ミューテックス。 |
| `closed_` | `std::atomic_bool` | スレッドプールが閉じているかどうかを示すフラグ。初期値は`true`です。 |
| `thread_count_` | `std::size_t` | スレッドの数。 |
| `cond_` | `std::condition_variable` | 条件変数。 |
| `tasks_` | `std::list<Task>` | タスクキュー。 |
| `threads_` | `std::list<std::thread>` | スレッドリスト。 |

## 5. 実装詳細

### 5.1 コンストラクタ
- `logger_`が指定されていない場合は、`log::RootLogger()`を使用します。
- `thread_count_`が0の場合は、`std::thread::hardware_concurrency()`を使用します。

### 5.2 `ExecProc()`
- タスクキューが空または閉じている場合に条件変数で待機します。
- タスクが存在する場合は、タスクを取得し、実行します。
- 例外が発生した場合は、ログに記録します。

### 5.3 `Close()`
- `closed_`を`true`に設定し、すべてのスレッドに終了を通知します。

## 6. 注意事項

- `Start()`は、`closed_`が`true`であることを前提としています。
- `Push()`は、`closed_`が`false`であることを前提としています。
- `ThreadPool`は、コピーおよびムーブが禁止されています。

## 7. 使用例

```cpp
#include "thread_pool.h"

int main() {
    ws::ThreadPool pool;
    pool.Start();

    for (int i = 0; i < 10; ++i) {
        pool.Push([i]() {
            std::cout << "Task " << i << " executed." << std::endl;
        });
    }

    pool.Close();
    return 0;
}
```

この仕様書を基に、別のLLMが`ws::ThreadPool`クラスを再実装することができます。