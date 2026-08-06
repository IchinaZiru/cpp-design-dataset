# デザイン文書: HeapTimer クラス

## 責務
HeapTimerクラスは、キーと関連付けられたタイムアウトコールバックを管理するための最小ヒープベースのタイマーシステムを提供します。各ノードは有効期限を持つもので、その有効期限が到来すると登録されたコールバックが呼び出されます。

## 公開インターフェース
- `HeapTimer(log::Logger::Ptr logger = log::RootLogger()) noexcept`
- `void Adjust(const Key& key, Clock::duration expiration)`
- `void Adjust(const Key& key, Clock::time_point expiration)`
- `void Push(const Key& key, Clock::duration expiration, TimeOutCallback callback) noexcept`
- `void Push(const Key& key, Clock::time_point expiration, TimeOutCallback callback) noexcept`
- `void Tick() noexcept`
- `bool Remove(const Key& key) noexcept`
- `void Invoke(const Key& key)`
- `Key Pop() noexcept`
- `void Clear() noexcept`
- `bool Contain(const Key& key) const noexcept`
- `bool Empty() const noexcept`
- `std::size_t Size() const noexcept`
- `Clock::duration ToNextTick() noexcept`

## 入力
- キー（`Key`型）
- 有効期限（`Clock::duration`または`Clock::time_point`型）
- タイムアウトコールバック（`TimeOutCallback`型）

## 出力
- `bool`: 操作の成功/失敗を示す論理値
- `Key`: ノードのキー
- `std::size_t`: ノード数
- `Clock::duration`: 次のタイマーイベントまでの間隔

## 状態
- 内部ヒープ構造（`std::deque<Node>`）
- キーとノードインデックスのマッピング（`std::unordered_map<Key, std::size_t>`）

## 処理手順
1. **コンストラクタ**: ロガーを初期化します。ロガーが指定されていない場合は、グローバルルートロガーを使用します。
2. **Adjustメソッド**:
   - キーに対応するノードの有効期限を更新します。
   - 有効期限が短くなった場合、ヒープを上にシフト（ShiftUp）します。それ以外の場合、ヒープを下にシフト（ShiftDown）します。
3. **Pushメソッド**:
   - 新しいノードを追加し、キーとインデックスのマッピングを作成します。
   - ヒープを上にシフトして新しいノードを適切な位置に配置します。
4. **Tickメソッド**:
   - 有効期限が到来したノードを取り出し、そのコールバックを呼び出します。
   - コールバックの例外はキャッチされ、ログに記録されます。
5. **Removeメソッド**: 指定されたキーを持つノードをヒープから削除します。
6. **Invokeメソッド**:
   - 指定されたキーを持つノードのコールバックを呼び出します。
   - コールバックの例外はキャッチされ、ログに記録されます。
7. **Popメソッド**: ヒープの先頭（最も早い有効期限）からノードを取り出し、そのキーを返します。
8. **Clearメソッド**: すべてのノードとマッピングをクリアします。
9. **Containメソッド**: 指定されたキーを持つノードが存在するかどうかを確認します。
10. **Emptyメソッド**: ヒープが空であるかどうかを確認します。
11. **Sizeメソッド**: 現在のヒープ内のノード数を返します。
12. **ToNextTickメソッド**:
    - 有効期限が最も近いノードまでの間隔を計算します。
    - `Tick`メソッドを呼び出して古いノードを処理し、次のタイマーイベントまでの間隔を返します。

## 例外・失敗条件
- **Adjust, Invoke**: 指定されたキーを持つノードが存在しない場合、`std::out_of_range`例外がスローされます。
- **Pop**: ヒープが空の場合、未定義動作となるため、呼び出し前に`Empty()`メソッドで確認する必要があります。

## 依存関係
- `log::Logger`: ログ出力に使用します。
- `std::chrono`: 時間管理に使用します。
- `std::deque`, `std::unordered_map`: 内部データ構造として使用します。
- `std::function`: コールバックの型として使用します。

## 重要な不変条件
1. **ヒーププロパティ**: ヒープ内の各ノードは、その子ノードよりも有効期限が短い（または等しい）必要があります。
2. **キーとインデックスのマッピング**: `key_to_idx_`は常に`nodes_`と同期され、同じキーを持つノードが存在する場合のみエントリを含む必要があります。
3. **ロガーの有効性**: ロガーが設定されていない場合は、グローバルルートロガーを使用します。
