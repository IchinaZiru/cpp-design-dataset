## デザイン文書: YAML::Node クラス

### 責務
`YAML::Node`クラスは、YAMLドキュメント内のノードを表すオブジェクトとして機能します。このクラスは、ノードの種類（スカラー、シーケンス、マップ）、値、タグ、スタイルなどの情報を保持し、それらに対するアクセスと操作を提供します。

### 公開インターフェース

#### コンストラクタ
- `Node()`: デフォルトコンストラクタ。未定義のノードを作成する。
- `explicit Node(NodeType::value type)`: 指定されたタイプを持つノードを作成する。
- `template <typename T> explicit Node(const T& rhs)`: 与えられた値からノードを作成する。
- `explicit Node(const detail::iterator_value& rhs)`: イテレータの値からノードを作成する。
- `Node(const Node& rhs)`: コピーコンストラクタ。

#### デストラクタ
- `~Node()`: ノードを破棄する。

#### アクセサメソッド
- `YAML::Mark Mark() const`: マーク情報を取得する。
- `NodeType::value Type() const`: ノードのタイプを取得する。
- `bool IsDefined() const`: ノードが定義されているか確認する。
- `bool IsNull() const`: ノードがnullであるか確認する。
- `bool IsScalar() const`: ノードがスカラーであるか確認する。
- `bool IsSequence() const`: ノードがシーケンスであるか確認する。
- `bool IsMap() const`: ノードがマップであるか確認する。

#### 型変換演算子
- `explicit operator bool() const`: ノードが定義されているかを真偽値として返す。
- `bool operator!() const`: ノードが未定義であるかを真偽値として返す。

#### 値アクセスメソッド
- `template <typename T> T as() const`: ノードの値を指定された型に変換して取得する。
- `template <typename T, typename S> T as(const S& fallback) const`: ノードの値を指定された型に変換できなければ、デフォルト値を返す。
- `const std::string& Scalar() const`: スカラー値を取得する。
- `const std::string& UninstrumentedScalarForTesting() const`: テスト用のスカラー値を取得する。

#### タグ操作メソッド
- `const std::string& Tag() const`: タグ情報を取得する。
- `void SetTag(const std::string& tag)`: タグ情報を設定する。

#### スタイル操作メソッド
- `EmitterStyle::value Style() const`: ノードのスタイルを取得する。
- `void SetStyle(EmitterStyle::value style)`: ノードのスタイルを設定する。

#### 代入演算子
- `bool is(const Node& rhs) const`: 2つのノードが同じであるか確認する。
- `template <typename T> Node& operator=(const T& rhs)`: 値を代入する。
- `Node& operator=(const Node& rhs)`: ノードを代入する。
- `void reset(const Node& rhs = Node())`: ノードの値をリセットする。

#### サイズとイテレータ
- `std::size_t size() const`: ノードのサイズ（シーケンスやマップの場合）を取得する。
- `const_iterator begin() const`: 開始イテレータを取得する。
- `iterator begin()`: 開始イテレータを取得する。
- `const_iterator end() const`: 終了イテレータを取得する。
- `iterator end()`: 終了イテレータを取得する。

#### シーケンス操作メソッド
- `template <typename T> void push_back(const T& rhs)`: シーケンスに要素を追加する。
- `void push_back(const Node& rhs)`: シーケンスにノードを追加する。

#### インデックス操作メソッド
- `template <typename Key> const Node operator[](const Key& key) const`: 指定されたキーのノードを取得する。
- `template <typename Key> Node operator[](const Key& key)`: 指定されたキーのノードを取得または作成する。
- `template <typename Key> bool remove(const Key& key)`: 指定されたキーのノードを削除する。

#### マップ操作メソッド
- `template <typename Key, typename Value> void force_insert(const Key& key, const Value& value)`: キーと値のペアを強制的に挿入する。
- `template <typename Key> bool contains(const Key& key) const`: 指定されたキーが存在するか確認する。

### 入力
- ノードのタイプ、値、タグ、スタイルなどの初期化パラメータ。
- イテレータの値や他のノードからの代入。

### 出力
- ノードのタイプ、値、タグ、スタイルなどの情報。
- イテレータを通じてアクセス可能な子ノード。

### 状態
- `m_isValid`: ノードが有効であるかを示すフラグ。
- `m_invalidKey`: ノードが無効な場合のキー情報を保持する文字列。
- `m_pMemory`: メモリ管理用のオブジェクトへのポインタ。
- `m_pNode`: 実際のノードデータへのポインタ。

### 処理手順
1. コンストラクタでノードを初期化し、必要に応じて値やタイプを設定する。
2. アクセサメソッドを通じてノードの情報を取得する。
3. 値アクセスメソッドを使用してノードの値を特定の型に変換して取得する。
4. タグ操作メソッドとスタイル操作メソッドを使用してノードのタグやスタイルを設定・取得する。
5. 代入演算子を使用してノードの値を更新する。
6. サイズとイテレータを使用してノードの内容を反復処理する。
7. シーケンス操作メソッドを使用してシーケンスに要素を追加する。
8. インデックス操作メソッドを使用してマップからキーに対応する値を取得・設定・削除する。

### 例外・失敗条件
- `as<T>()`や`operator[]`などのメソッドで型変換に失敗した場合、例外がスローされる可能性がある。
- ノードが未定義であるときに特定の操作（例：値へのアクセス）を行った場合、未定義動作となる。

### 依存関係
- `YAML::Mark`: マーク情報を保持する構造体。
- `NodeType::value`: ノードのタイプを表す列挙型。
- `EmitterStyle::value`: エミッタースタイルを表す列挙型。
- `detail::iterator_value`: イテレータが参照する値を保持する構造体。
- `detail::node`: 実際のノードデータを管理するクラス。
- `detail::shared_memory_holder`: メモリ管理用のオブジェクト。

### 重要な不変条件
- `m_isValid`フラグがfalseの場合、`m_pNode`はnullであるべきである。
- タイプが`NodeType::Undefined`でない場合、`m_pNode`は有効なノードデータを指しているべきである。