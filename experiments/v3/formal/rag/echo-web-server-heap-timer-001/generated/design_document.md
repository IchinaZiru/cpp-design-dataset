# 対象
- target: heap-timer
- granularity: module_files
- source_files: ["include/containers/heap_timer.h"]

# 対象範囲
元コードとして示したsource_files全体を1つのモジュールとして扱ってください。
設計文書は、各ファイルの責務、ファイル間の関係、公開インターフェース、実装上の処理を含めて作成してください。
再実装ではsource_filesにある各ファイル全体を生成するため、ファイルごとの構造と責務を区別してください。

## 責務
`HeapTimer`クラスは、キーに基づいたタイマーを管理し、そのタイマーの有効期限が到来したときにコールバック関数を呼び出す機能を提供します。内部では最小ヒープを使用してタイマーを管理しています。

## 公開インターフェース
- `HeapTimer(log::Logger::Ptr logger = log::RootLogger()) noexcept`: コンストラクタ。
- `void Adjust(const Key& key, Clock::duration expiration)`: タイマーの有効期限を調整する。
- `void Adjust(const Key& key, Clock::time_point expiration)`: タイマーの有効期限を指定した時間に設定する。
- `void Push(const Key& key, Clock::duration expiration, TimeOutCallback callback) noexcept`: 新しいタイマーを追加する。
- `void Push(const Key& key, Clock::time_point expiration, TimeOutCallback callback) noexcept`: 新しいタイマーを指定した有効期限で追加する。
- `void Tick() noexcept`: 有効期限が到来したタイマーのコールバックを呼び出す。
- `bool Remove(const Key& key) noexcept`: 指定されたキーを持つタイマーを削除する。
- `void Invoke(const Key& key)`: 指定されたキーを持つタイマーのコールバックを呼び出し、その後タイマーを削除する。
- `Key Pop() noexcept`: 最も近い有効期限が到来したタイマーを削除し、そのキーを返す。
- `void Clear() noexcept`: すべてのタイマーをクリアする。
- `bool Contain(const Key& key) const noexcept`: 指定されたキーを持つタイマーが存在するかどうかを確認する。
- `bool Empty() const noexcept`: タイマーが空であるかどうかを確認する。
- `std::size_t Size() const noexcept`: 管理されているタイマーの数を返す。
- `Clock::duration ToNextTick() noexcept`: 次に有効期限が到来するタイマーまでの残り時間を返す。

## 入力
- タイマーのキー (`Key`)
- 有効期限 (`Clock::duration`または`Clock::time_point`)
- コールバック関数 (`TimeOutCallback`)

## 出力
- `bool`: 操作の成否（例：タイマーの削除）
- `Key`: 削除されたタイマーのキー
- `std::size_t`: 管理されているタイマーの数
- `Clock::duration`: 次に有効期限が到来するタイマーまでの残り時間

## 状態
- タイマーのリスト (`nodes_`)
- キーからインデックスへのマッピング (`key_to_idx_`)

## 処理手順
1. `Push`: 新しいノードを追加し、ヒーププロパティを維持する。
2. `Adjust`: 既存のノードの有効期限を更新し、ヒーププロパティを維持する。
3. `Tick`: 有効期限が到来したノードのコールバックを呼び出し、ヒープから削除する。
4. `Remove`: 指定されたキーを持つノードを削除し、ヒーププロパティを維持する。
5. `Invoke`: 指定されたキーを持つノードのコールバックを呼び出し、その後ノードを削除する。
6. `Pop`: 最も近い有効期限が到来したノードを削除し、そのキーを返す。

## 例外・失敗条件
- `std::out_of_range`: 指定されたキーを持つタイマーが存在しない場合に`Adjust`や`Invoke`が投げる。
- コールバック関数内で例外が発生した場合はキャッチされ、ログに記録される。

## 依存関係
- `log::Logger::Ptr`: ロギング機能
- `std::chrono`: 時間管理
- `std::function`: コールバック関数の型
- `std::optional`: オプショナルな値を扱う
- `std::unordered_map`: キーからインデックスへのマッピング
- `std::deque`: ノードのリスト

## 重要な不変条件
- `nodes_`と`key_to_idx_`は常に同期されている。
- `nodes_`は最小ヒープ構造を維持している。

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
        -struct Node {
            +Key key
            +Clock::time_point expiration
            +TimeOutCallback callback
            +bool Expired() const noexcept
            +void Swap(Node&) noexcept
            +operator<=>(const Node& lhs, const Node& rhs) noexcept
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

### クラス・メソッド・インターフェース詳細

| 完全な名前 | 属性 | 引数名と型 | 戻り値型 | 可視性 | const | noexcept | 依存 |
|------------|------|------------|----------|--------|-------|----------|------|
| HeapTimer::HeapTimer | コンストラクタ | log::Logger::Ptr logger = log::RootLogger() | void | public | - | yes | log::Logger::Ptr |
| HeapTimer::Adjust | メソッド | const Key& key, Clock::duration expiration | void | public | - | no | - |
| HeapTimer::Adjust | メソッド | const Key& key, Clock::time_point expiration | void | public | - | no | - |
| HeapTimer::Push | メソッド | const Key& key, Clock::duration expiration, TimeOutCallback callback | void | public | - | yes | TimeOutCallback |
| HeapTimer::Push | メソッド | const Key& key, Clock::time_point expiration, TimeOutCallback callback | void | public | - | yes | TimeOutCallback |
| HeapTimer::Tick | メソッド | - | void | public | - | yes | - |
| HeapTimer::Remove | メソッド | const Key& key | bool | public | - | yes | - |
| HeapTimer::Invoke | メソッド | const Key& key | void | public | - | no | - |
| HeapTimer::Pop | メソッド | - | Key | public | - | yes | - |
| HeapTimer::Clear | メソッド | - | void | public | - | yes | - |
| HeapTimer::Contain | メソッド | const Key& key | bool | public | yes | yes | - |
| HeapTimer::Empty | メソッド | - | bool | public | yes | yes | - |
| HeapTimer::Size | メソッド | - | std::size_t | public | yes | yes | - |
| HeapTimer::ToNextTick | メソッド | - | Clock::duration | public | - | yes | - |

### シーケンス図
該当なし

### メソッド仕様書

| メソッド名 | 目的 | 引数 | 戻り値 | 動作の説明 | 副作用 | 使用例 | エラー処理 |
|------------|------|------|--------|------------|--------|--------|------------|
| HeapTimer::Adjust | 指定されたキーを持つタイマーの有効期限を調整する | const Key& key, Clock::duration expiration | void | 有効期限を現在時刻から指定した時間後に設定し、ヒーププロパティを維持する | ヒープ構造が変更される | `timer.Adjust(key, std::chrono::seconds(10));` | 指定されたキーを持つタイマーが存在しない場合にstd::out_of_range例外を投げる |
| HeapTimer::Push | 新しいタイマーを追加する | const Key& key, Clock::duration expiration, TimeOutCallback callback | void | タイマーを追加し、ヒーププロパティを維持する | ヒープ構造が変更される | `timer.Push(key, std::chrono::seconds(10), [](const Key& k) { /* コールバック処理 */ });` | なし |
| HeapTimer::Tick | 有効期限が到来したタイマーのコールバックを呼び出す | - | void | 有効期限が現在時刻を超えたノードのコールバックを呼び出し、ヒープから削除する | ヒープ構造が変更される | `timer.Tick();` | コールバック内で例外が発生した場合はキャッチされ、ログに記録される |
| HeapTimer::Remove | 指定されたキーを持つタイマーを削除する | const Key& key | bool | タイマーを削除し、ヒーププロパティを維持する | ヒープ構造が変更される | `timer.Remove(key);` | なし |
| HeapTimer::Invoke | 指定されたキーを持つタイマーのコールバックを呼び出し、その後タイマーを削除する | const Key& key | void | タイマーのコールバックを呼び出し、ヒープから削除する | ヒープ構造が変更される | `timer.Invoke(key);` | 指定されたキーを持つタイマーが存在しない場合にstd::out_of_range例外を投げる |
| HeapTimer::Pop | 最も近い有効期限が到来したタイマーを削除し、そのキーを返す | - | Key | 最も近い有効期限が到来したノードのコールバックを呼び出し、ヒープから削除する | ヒープ構造が変更される | `Key key = timer.Pop();` | なし |
| HeapTimer::Clear | すべてのタイマーをクリアする | - | void | すべてのタイマーを削除する | ヒープ構造が変更される | `timer.Clear();` | なし |
| HeapTimer::Contain | 指定されたキーを持つタイマーが存在するかどうかを確認する | const Key& key | bool | キーに対応するノードが存在するか確認する | なし | `bool exists = timer.Contain(key);` | なし |
| HeapTimer::Empty | タイマーが空であるかどうかを確認する | - | bool | タイマーが空であるか確認する | なし | `bool isEmpty = timer.Empty();` | なし |
| HeapTimer::Size | 管理されているタイマーの数を返す | - | std::size_t | 管理されているタイマーの数を返す | なし | `std::size_t size = timer.Size();` | なし |
| HeapTimer::ToNextTick | 次に有効期限が到来するタイマーまでの残り時間を返す | - | Clock::duration | 次に有効期限が到来するタイマーまでの残り時間を計算し、返す | ヒープ構造が変更される | `Clock::duration duration = timer.ToNextTick();` | なし |

### 処理フロー図
該当なし

### 状態遷移・副作用

| 更新前状態 | 遷移条件 | 変更対象 | 更新後状態 | 更新順序 | 副作用 |
|------------|----------|----------|------------|----------|--------|
| タイマーが存在する | 有効期限が到来した | nodes_ | ノード削除 | - | コールバック呼び出し、ログ記録 |
| タイマーが存在する | 新しいタイマー追加 | nodes_, key_to_idx_ | ノード追加 | ShiftUp | ヒープ構造変更 |
| タイマーが存在する | 有効期限調整 | nodes_ | 有効期限更新 | ShiftUp/ShiftDown | ヒープ構造変更 |
| タイマーが存在する | タイマー削除 | nodes_, key_to_idx_ | ノード削除 | RemoveByIndex | ヒープ構造変更 |

### データ変換・制約

| 入力形式 | 出力形式 | 変換規則 | 値域 | 境界値 | 単位 | 精度 | エンコーディング | 検証条件 | 特殊値・欠損値の扱い |
|----------|----------|----------|------|--------|------|------|------------------|------------|--------------------|
| Clock::duration | Clock::time_point | 現在時刻 + duration | - | 0, 最大時間 | 時間単位 | ナノ秒 | - | 正の値 | なし |
| Clock::time_point | - | 直接使用 | - | 最小時間, 最大時間 | 時間単位 | ナノ秒 | - | 有効な時刻 | なし |
| TimeOutCallback | - | コールバック関数として保持 | - | - | - | - | - | 有効な関数オブジェクト | nullptrは許可されない |