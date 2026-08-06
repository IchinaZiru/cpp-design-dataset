# デザイン文書: block-deque モジュール

## 概要
`block_deque.h`は、スレッドセーフなブロックデキュー（両端キュー）を提供するヘッダファイルです。このデータ構造は、最大容量を超えた場合にプッシュ操作がブロッキングされ、消費者スレッドが通知されるように設計されています。

## モジュールの責務
- スレッドセーフなデキュー操作の提供。
- キューの空・満状態の確認。
- 要素の追加と削除（両端からの操作）。
- 消費者スレッドへの通知機能。
- タイムアウト付きのポップ操作。

## ファイル間の関係
このモジュールは単一ファイルで構成されており、他のファイルとの直接的な依存関係はありません。ただし、標準ライブラリ（`<cassert>`, `<condition_variable>`, `<deque>`, `<mutex>`, `<optional>`, `<utility>`）に依存しています。

## 公開インターフェース

### クラス: `BlockDeque<T>`
#### コンストラクタ
- `explicit BlockDeque(std::size_t capacity = 1000) noexcept;`
  - ブロックデキューを作成し、最大容量を設定します。

#### デストラクタ
- `~BlockDeque() noexcept;`
  - キューを閉じてリソースを解放します。

#### メンバ関数
- `void Clear() noexcept;`
  - キュー内のすべての要素をクリアします。
  
- `bool Empty() const noexcept;`
  - キューが空であるかどうかを返します。
  
- `bool Full() const noexcept;`
  - キューが満杯であるかどうかを返します。
  
- `std::size_t Size() const noexcept;`
  - キューサイズを返します。
  
- `std::size_t Capacity() const noexcept;`
  - キューの最大容量を返します。
  
- `void PushBack(T item) noexcept;`
  - 要素をキューの末尾に追加し、消費者スレッドに通知します。
  
- `void PushFront(T item) noexcept;`
  - 要素をキューの先頭に挿入し、消費者スレッドに通知します。
  
- `const T& Front() const noexcept;`
  - キューの最初の要素への参照を返します（キューが空でないことを保証する必要があります）。
  
- `const T& Back() const noexcept;`
  - キューの最後の要素への参照を返します（キューが空でないことを保証する必要があります）。
  
- `T& Front() noexcept;`
  - キューの最初の要素への非const参照を返します。
  
- `T& Back() noexcept;`
  - キューの最後の要素への非const参照を返します。
  
- `std::optional<T> Pop(std::optional<Clock::duration> time_out = std::nullopt) noexcept;`
  - タイムアウト付きで最初の要素を取り出します。タイムアウトが発生した場合やキューが閉じられた場合は`std::nullopt`を返します。
  
- `void Flush() noexcept;`
  - 消費者スレッドに通知します。
  
- `void Close() noexcept;`
  - キュー内のすべての要素をクリアし、キューを閉じます。

## 入力
- コンストラクタ: 最大容量（`std::size_t`）。
- `PushBack`, `PushFront`: 追加する要素（`T`型）。
- `Pop`: タイムアウト時間（`std::optional<Clock::duration>`）。

## 出力
- `Empty`, `Full`: ブーリアン値。
- `Size`, `Capacity`: サイズ（`std::size_t`）。
- `Front`, `Back`: 要素への参照（`const T&`または`T&`）。
- `Pop`: 取り出した要素（`std::optional<T>`）。

## 状態
- `closed_`: キューが閉じられているかどうかを示すフラグ（`std::atomic_bool`）。
- `capacity_`: キューの最大容量（`std::size_t`）。
- `deq_`: 実際のデータ格納用デキュー（`std::deque<T>`）。

## 処理手順
1. **コンストラクタ**: 最大容量を設定し、アサートで検証します。
2. **デストラクタ**: `Close()`メソッドを呼び出してリソースを解放します。
3. **Clear()**: ロックを取得して`deq_`をクリアします。
4. **Empty(), Full(), Size(), Capacity()**: ロックを取得してそれぞれの状態を返します。
5. **PushBack(), PushFront()**: ロックを取得し、必要に応じてスペース待ちを行ってから要素を追加し、消費者スレッドに通知します。
6. **Front(), Back()**: ロックを取得して先頭または末尾の要素への参照を返します。キューが空であることを保証する必要があります。
7. **Pop()**: ロックを取得し、必要に応じてタイムアウト付きで待機を行ってから最初の要素を取り出し、プロデューサースレッドに通知します。
8. **Flush()**: 消費者スレッドに通知します。
9. **Close()**: ロックを取得して`deq_`をクリアし、フラグを立てて両方の条件変数に通知します。

## 例外・失敗条件
- `Front()`や`Back()`がキューが空であるときに呼び出された場合: アサートで検証されます。
- `Pop()`がタイムアウトまたはキューが閉じられた場合: `std::nullopt`を返します。

## 依存関係
- 標準ライブラリのヘッダファイル（`<cassert>`, `<condition_variable>`, `<deque>`, `<mutex>`, `<optional>`, `<utility>`）。

## 重要な不変条件
- `capacity_`は常に正である。
- `deq_.size()`は常に`capacity_`以下である。
- `closed_`が`true`の場合、`deq_`は空である。