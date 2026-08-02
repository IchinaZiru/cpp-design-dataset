# デザイン文書

## 概要
この設計文書は、与えられたC++のログシステムのコードを基に再実装するための詳細な仕様を記載しています。各クラスや関数の責務、公開インターフェース、入力・出力、状態、処理手順、例外・失敗条件、依存関係、重要な不変条件について説明します。

## クラス設計

### 1. `Level`
- **責務**: ログレベルを定義し、文字列と列挙型の相互変換を行う。
- **公開インターフェース**:
    - `std::string_view LevelToString(Level level) noexcept;`
    - `std::string to_string(Level level) noexcept;`
    - `Level StringToLevel(std::string str);`
- **例外・失敗条件**: `StringToLevel` で無効な文字列が渡された場合、`std::invalid_argument` をスローする。

### 2. `AppenderType`
- **責務**: アペンダーの種類を定義し、文字列と列挙型の相互変換を行う。
- **公開インターフェース**:
    - `std::string_view AppenderTypeToString(AppenderType type) noexcept;`
    - `std::string to_string(AppenderType type) noexcept;`
    - `AppenderType StringToAppenderType(std::string str);`
- **例外・失敗条件**: `StringToAppenderType` で無効な文字列が渡された場合、`std::invalid_argument` をスローする。

### 3. `Event`
- **責務**: ログイベントを表す。イベントのレベル、発生場所、スレッドID、時間、メッセージなどを保持する。
- **公開インターフェース**:
    - `static Ptr Create(log::Level level, std::experimental::source_location location = std::experimental::source_location::current(), std::uint32_t thread_id = CurrentThreadId(), Clock::time_point time = Clock::now()) noexcept;`
    - `log::Level Level() const noexcept;`
    - `std::string_view FileName() const noexcept;`
    - `std::size_t LineNum() const noexcept;`
    - `std::uint32_t ThreadId() const noexcept;`
    - `Clock::time_point Time() const noexcept;`
    - `std::string Message() const noexcept;`
    - `std::ostringstream& MessageStream() noexcept;`
- **例外・失敗条件**: なし

### 4. `Formatter`
- **責務**: ログイベントを指定されたフォーマットに従って文字列化する。
- **公開インターフェース**:
    - `static Formatter::Ptr Default() noexcept;`
    - `explicit Formatter(std::string_view pattern);`
    - `std::string Format(const Logger& logger, const Event& event) const noexcept;`
    - `std::string_view Pattern() const noexcept;`
- **例外・失敗条件**: コンストラクタで無効なパターンが渡された場合、`std::invalid_argument` をスローする。

### 5. `Formatter::Field`
- **責務**: フォーマットの各フィールドを表す。具体的なフォーマッティングロジックを持つ。
- **公開インターフェース**:
    - `explicit Field(std::string_view format = "") noexcept;`
    - `virtual void Format(std::ostream& out, const Logger& logger, const Event& event) noexcept = 0;`
    - `virtual std::string_view Tag() const noexcept = 0;`

### 6. `Appender`
- **責務**: ログイベントを特定の場所に書き込む。
- **公開インターフェース**:
    - `explicit Appender(std::string_view pattern);`
    - `explicit Appender(Formatter::Ptr formatter = Formatter::Default()) noexcept;`
    - `virtual void Log(const Logger& logger, const Event& event) noexcept = 0;`
    - `virtual std::string ToYamlString() const noexcept = 0;`
    - `Formatter::Ptr GetFormatter() const noexcept;`
    - `void SetFormatter(Formatter::Ptr formatter) noexcept;`
    - `void SetFormatter(std::string_view pattern);`
- **例外・失敗条件**: `SetFormatter` で無効なパターンが渡された場合、`std::invalid_argument` をスローする。

### 7. `StdOutAppender`
- **責務**: ログイベントを標準出力に書き込む。
- **公開インターフェース**:
    - `void Log(const Logger& logger, const Event& event) noexcept override;`
    - `std::string ToYamlString() const noexcept override;`

### 8. `FileAppender`
- **責務**: ログイベントをファイルに書き込む。
- **公開インターフェース**:
    - `explicit FileAppender(std::string_view file_name, Formatter::Ptr formatter = Formatter::Default());`
    - `void Log(const Logger& logger, const Event& event) noexcept override;`
    - `std::string ToYamlString() const noexcept override;`
- **例外・失敗条件**: コンストラクタでファイル作成に失敗した場合、`std::system_error` をスローする。

### 9. `Logger`
- **責務**: ロガーを表す。複数のアペンダーを持つことができ、同期的にも非同期的にログイベントを処理できる。
- **公開インターフェース**:
    - `explicit Logger(std::string_view name, log::Level level = Level::Info, std::optional<std::size_t> capacity = std::nullopt) noexcept;`
    - `void Log(Event::Ptr event) noexcept;`
    - `void AddAppender(Appender::Ptr appender) noexcept;`
    - `void RemoveAppender(Appender::Ptr appender) noexcept;`
    - `void ClearAppenders() noexcept;`
    - `log::Level GetLevel() const noexcept;`
    - `void SetLevel(log::Level level) noexcept;`
    - `Formatter::Ptr GetDefaultFormatter() const noexcept;`
    - `void SetDefaultFormatter(Formatter::Ptr formatter) noexcept;`
    - `void SetDefaultFormatter(std::string_view pattern);`
    - `std::string_view Name() const noexcept;`
    - `std::size_t Capacity() const noexcept;`
    - `std::string ToYamlString() const noexcept;`
- **例外・失敗条件**: `SetDefaultFormatter` で無効なパターンが渡された場合、`std::invalid_argument` をスローする。

### 10. `EventWriter`
- **責務**: ログイベントを自動的にロガーに書き込むためのヘルパークラス。
- **公開インターフェース**:
    - `explicit EventWriter(Logger& logger, Event::Ptr event) noexcept;`
    - `std::ostringstream& MessageStream() noexcept;`

### 11. `Manager`
- **責務**: ロガーのコレクションを管理する。ロガーの追加、削除、検索を行う。
- **公開インターフェース**:
    - `static void InitConfig() noexcept;`
    - `explicit Manager(std::string_view name) noexcept;`
    - `std::string_view Name() const noexcept;`
    - `Logger::Ptr FindLogger(std::string_view name, log::Level level = Level::Info, std::optional<std::size_t> capacity = std::nullopt) noexcept;`
    - `void RemoveLogger(std::string_view name) noexcept;`
    - `std::string ToYamlString() const noexcept;`

### 12. `AppenderConfig` / `LoggerConfig`
- **責務**: ロガーとアペンダーの設定を表す構造体。
- **公開インターフェース**:
    - 比較演算子 (`==`, `!=`)
- **例外・失敗条件**: なし

### 13. `SetListener`
- **責務**: ロガーの設定変更時にコールバックを呼び出すための関数。
- **公開インターフェース**:
    - `cfg::Var<std::unordered_set<LoggerConfig>>::Ptr SetListener(cfg::Var<std::unordered_set<LoggerConfig>>::Ptr loggers, Manager::Ptr manager) noexcept;`

## 重要な不変条件
1. `Level` と `AppenderType` の文字列変換関数は、有効な値に対してのみ呼び出される。
2. `Formatter` のパターンは、コンストラクタで検証され、無効なパターンが渡された場合は例外をスローする。
3. `FileAppender` はファイルの作成に失敗した場合、例外をスローする。
4. `Logger` のデフォルトフォーマッター設定時に無効なパターンが渡された場合は例外をスローする。

## 依存関係
- `log.h`: 全てのクラスと構造体の宣言。
- `log.cpp`: `Logger`, `EventWriter`, `Manager` の実装。
- `appender.cpp`: `Appender`, `StdOutAppender`, `FileAppender` の実装。
- `field.h`: 各フィールドフォーマッタの宣言。
- `field.cpp`: 各フィールドフォーマッタの実装。
- `config_init.h`: ロガーとアペンダーの設定構造体と変換関数の宣言。
- `config_init.cpp`: 設定構造体の比較演算子とリスナー設定関数の実装。

## 処理手順
1. **初期化**:
    - `Manager::InitConfig()` を呼び出して、ロガーの設定管理を初期化する。
2. **ロガー作成**:
    - `Manager::FindLogger(name)` で指定された名前のロガーを作成または取得する。
3. **アペンダー追加**:
    - `Logger::AddAppender(appender)` でロガーにアペンダーを追加する。
4. **ログイベント作成と書き込み**:
    - `Event::Create(level, location, thread_id, time)` でログイベントを作成し、`Logger::Log(event)` でロガーにイベントを書き込む。

## 状態
- 各クラスの内部状態は適切なミューテックス (`std::mutex`) を使用してスレッドセーフに管理される。
- `Logger` の非同期モードでは、イベントキューが使用され、別スレッドでログイベントを処理する。

## 例外・失敗条件
- 各関数の例外・失敗条件は前述の通りです。特に文字列変換やファイル操作に関連する関数は、無効な入力やシステムエラーに対して例外をスローします。

この設計文書に基づいて再実装を行うことで、元コードと同じ機能と動作を提供できることが期待されます。