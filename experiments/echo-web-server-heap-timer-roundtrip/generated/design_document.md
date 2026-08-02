# デザイン文書: HeapTimer クラス

## 概要
`HeapTimer`クラスは、最小ヒープを基盤としたタイマーシステムを提供します。各タイマーは有効期限によって管理され、その有効期限が到来するとコールバック関数が呼び出されます。

## 責務
- タイマーの追加、調整、削除を行う。
- 有効期限が到来したタイマーのコールバックを実行する。
- ヒープ構造を維持し、効率的にタイマーオペレーションを処理する。

## 公開インターフェース
### コンストラクタ
```cpp
explicit HeapTimer(log::Logger::Ptr logger = log::RootLogger()) noexcept;
```
- ロガーを指定してタイマーシステムを作成します。ロガーが指定されない場合は、グローバルルートロガーを使用します。

### メソッド
#### Adjust
```cpp
void Adjust(const Key& key, Clock::duration expiration);
void Adjust(const Key& key, Clock::time_point expiration);
```
- 指定されたキーを持つノードの有効期限を調整します。
- 存在しないキーの場合、`std::out_of_range`例外がスローされます。

#### Push
```cpp
void Push(const Key& key, Clock::duration expiration, TimeOutCallback callback) noexcept;
void Push(const Key& key, Clock::time_point expiration, TimeOutCallback callback) noexcept;
```
- タイマーを追加します。キーが既に存在する場合は、有効期限とコールバックを更新します。

#### Tick
```cpp
void Tick() noexcept;
```
- 有効期限が到来したタイマーのコールバックを実行し、そのノードを削除します。
- コールバック内でスローされた例外は再スローされず、ロガーに記録されます。

#### Remove
```cpp
bool Remove(const Key& key) noexcept;
```
- 指定されたキーを持つノードを削除します。存在しないキーの場合は`false`を返し、それ以外は`true`を返します。

#### Invoke
```cpp
void Invoke(const Key& key);
```
- 指定されたキーを持つノードのコールバックを実行し、そのノードを削除します。
- 存在しないキーの場合、`std::out_of_range`例外がスローされます。
- コールバック内でスローされた例外は再スローされず、ロガーに記録されます。

#### Pop
```cpp
Key Pop() noexcept;
```
- ヒープの先頭ノードを削除し、そのキーを返します。ヒープが空の場合、このメソッドは呼び出せません。

#### Clear
```cpp
void Clear() noexcept;
```
- タイマーシステムをクリアします。

#### Contain
```cpp
bool Contain(const Key& key) const noexcept;
```
- 指定されたキーを持つノードが存在するかどうかを返します。

#### Empty
```cpp
bool Empty() const noexcept;
```
- タイマーシステムが空であるかどうかを返します。

#### Size
```cpp
std::size_t Size() const noexcept;
```
- タイマーシステム内のノード数を返します。

#### ToNextTick
```cpp
Clock::duration ToNextTick() noexcept;
```
- 有効期限が最も近いタイマーまでの残り時間を返します。ヒープが空の場合、ゼロの間隔を返します。
- コールバック内でスローされた例外は再スローされず、ロガーに記録されます。

## 入力
- タイマーキー (`Key`)
- 有効期限 (`Clock::duration`または`Clock::time_point`)
- コールバック関数 (`TimeOutCallback`)

## 出力
- `Push`, `Adjust`: なし
- `Tick`, `Invoke`: なし
- `Remove`: 削除されたノードのキーを返す
- `Pop`: ヒープの先頭ノードのキーを返す
- `Clear`: なし
- `Contain`: 存在するかどうかを表すブール値
- `Empty`: 空であるかどうかを表すブール値
- `Size`: タイマーシステム内のノード数
- `ToNextTick`: 次のタイマーまでの残り時間

## 状態
- ヒープ構造 (`std::deque<Node> nodes_`)
- キーとインデックスのマッピング (`std::unordered_map<Key, std::size_t> key_to_idx_`)

## 処理手順
1. **Push**: 新しいノードを追加し、ヒーププロパティを維持するためにShiftUpを呼び出す。
2. **Adjust**: 指定されたキーを持つノードの有効期限を更新し、必要に応じてShiftUpまたはShiftDownを呼び出す。
3. **Tick**: 有効期限が到来したノードのコールバックを実行し、ヒープから削除する。このプロセスは繰り返される。
4. **Remove**: 指定されたキーを持つノードをヒープから削除し、ShiftDownを呼び出してヒーププロパティを維持する。
5. **Invoke**: 指定されたキーを持つノードのコールバックを実行し、ヒープから削除する。このメソッドはRemoveと似ていますが、コールバックの実行も含みます。

## 例外・失敗条件
- `Adjust`: 存在しないキーの場合、`std::out_of_range`例外がスローされます。
- `Invoke`: 存在しないキーの場合、`std::out_of_range`例外がスローされます。
- `Pop`: ヒープが空の場合、このメソッドは呼び出せません。

## 依存関係
- `log::Logger`
- `util.h`

## 重要な不変条件
- `nodes_`と`key_to_idx_`のサイズは常に一致する。
- `nodes_`は最小ヒープ構造を維持している。