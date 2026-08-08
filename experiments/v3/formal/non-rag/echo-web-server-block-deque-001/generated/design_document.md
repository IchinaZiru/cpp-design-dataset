## 責務
`BlockDeque`クラスは、スレッドセーフなブロッキングデキューを提供します。最大容量を超える要素の追加は待機させ、消費者が要素を取り出すまでプロデューサーをブロックします。

## 公開インターフェース
- `BlockDeque(std::size_t capacity = 1000) noexcept`: コンストラクタで初期容量を設定します。
- `void Clear() noexcept`: キュー内のすべての要素をクリアします。
- `bool Empty() const noexcept`: キューが空かどうかを返します。
- `bool Full() const noexcept`: キューが満杯かどうかを返します。
- `std::size_t Size() const noexcept`: 現在のキュー内の要素数を返します。
- `std::size_t Capacity() const noexcept`: キューサイズの最大容量を返します。
- `void PushBack(T item) noexcept`: 要素をキューの末尾に追加し、消費者に通知します。
- `void PushFront(T item) noexcept`: 要素をキューの先頭に挿入し、消費者に通知します。
- `const T& Front() const noexcept`: キューの最初の要素への参照を返します（キューが空でないことを保証）。
- `const T& Back() const noexcept`: キューの最後の要素への参照を返します（キューが空でないことを保証）。
- `T& Front() noexcept`: キューの最初の要素への非const参照を返します（キューが空でないことを保証）。
- `T& Back() noexcept`: キューの最後の要素への非const参照を返します（キューが空でないことを保証）。
- `std::optional<T> Pop(std::optional<Clock::duration> time_out = std::nullopt) noexcept`: キューから最初の要素を取り出し、それを返します。タイムアウトまたはキューが閉じられたら`std::nullopt`を返します。
- `void Flush() noexcept`: 消費者に通知します。
- `void Close() noexcept`: キュー内のすべての要素をクリアし、キューを閉じます。

## 入力
- コンストラクタ: 初期容量（デフォルトは1000）
- `PushBack`, `PushFront`: 追加または挿入する要素
- `Pop`: オプションのタイムアウト値

## 出力
- `Empty`, `Full`: ブーリアン値
- `Size`, `Capacity`: サイズ（`std::size_t`）
- `Front`, `Back`: 要素への参照または非const参照
- `Pop`: 取り出した要素または`std::nullopt`

## 状態
- `closed_`: キューが閉じられているかどうかを示すブーリアン値（アトミック）
- `capacity_`: キューサイズの最大容量
- `deq_`: 実際の要素を保持する`std::deque`
- `mtx_`: スレッドセーフな操作のために使用されるミューテックス
- `consumer_cond_`, `producer_cond_`: コンシューマーとプロデューサーの間で同期するために使用される条件変数

## 処理手順
1. **PushBack, PushFront**: 要素を追加または挿入する前に、キューに空きがあることを確認します。なければ待機します。
2. **Pop**: キューが空でないかチェックし、要素を取り出します。タイムアウトやキューのクローズにより取り出しできない場合は`std::nullopt`を返します。
3. **Close**: キュー内のすべての要素をクリアし、プロデューサーと消費者に通知します。

## 例外・失敗条件
- `Front`, `Back`: キューが空の場合、未定義動作となるため呼び出し前に`Empty()`でチェックが必要です。
- `PushBack`, `PushFront`: キューが閉じられている場合、待機せずに終了します。

## 依存関係
- C++標準ライブラリ: `assert`, `condition_variable`, `deque`, `mutex`, `optional`, `utility`

## 重要な不変条件
- `capacity_`は常に正の値である。
- `deq_.size()`は常に`capacity_`以下である。