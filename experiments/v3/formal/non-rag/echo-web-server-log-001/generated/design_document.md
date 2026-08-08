# 対象
- target: log
- granularity: module_files
- source_files: ["include/log.h", "src/log/log.cpp", "src/log/appender.cpp", "src/log/field.h", "src/log/field.cpp", "src/log/config_init.h", "src/log/config_init.cpp"]

# 対象範囲
元コードとして示したsource_files全体を1つのモジュールとして扱ってください。
設計文書は、各ファイルの責務、ファイル間の関係、公開インターフェース、実装上の処理を含めて作成してください。
再実装ではsource_filesにある各ファイル全体を生成するため、ファイルごとの構造と責務を区別してください。

## 責務
ログイベントの作成、フォーマット、および出力を行う。複数のロガーとアペンダーを管理し、設定に基づいてログの動作を調整します。

## 公開インターフェース
- `log::LevelToString(Level level)`: ログレベルを文字列に変換する。
- `log::StringToLevel(std::string str)`: 文字列からログレベルを取得する。
- `log::AppenderTypeToString(AppenderType type)`: アペンダータイプを文字列に変換する。
- `log::StringToAppenderType(std::string str)`: 文字列からアペンダータイプを取得する。
- `Event::Create(...)`: ログイベントを作成する。
- `Formatter::Default()`: デフォルトのフォーマッタを作成する。
- `Logger::Logger(...)`: ロガーを作成する。
- `Manager::Manager(...)`: ロガーマネージャーを作成する。
- `Manager::InitConfig()`: ログ設定を初期化する。

## 入力
- ログレベル、アペンダータイプ、フォーマットパターン、イベントメッセージなどの文字列データ。
- YAML形式のログ設定ファイル。

## 出力
- フォーマットされたログメッセージ。
- YAML形式のロガー設定。

## 状態
- ログレベル、キャパシティ、アペンダーリスト、フォーマッタなど。
- ロガーマネージャー内のロガー集合。

## 処理手順
1. `Logger::Log(Event::Ptr event)`: イベントをログに記録する。非同期モードではイベントキューに追加し、同期モードでは直接出力する。
2. `Formatter::Format(...)`: フォーマットパターンに基づいてイベント情報をフォーマットする。
3. `Appender::Log(...)`: フォーマットされたメッセージを指定の場所に出力する（標準出力やファイルなど）。
4. `Manager::FindLogger(...)`: 指定した名前のロガーを探す。存在しない場合は新しく作成する。

## 例外・失敗条件
- 不正なログレベルまたはアペンダータイプの文字列が与えられた場合、`std::invalid_argument`をスローする。
- ファイルアペンダーでファイルの作成に失敗した場合、`std::system_error`をスローする。
- フォーマットパターンが不正な場合、`std::invalid_argument`をスローする。

## 依存関係
- `log.h`: 公開インターフェースとクラス定義。
- `log.cpp`: イベント作成、フォーマッタ処理、ロガー操作の実装。
- `appender.cpp`: アペンダーの具体的な動作（標準出力やファイルへの書き込み）を実装。
- `field.h`: フォーマットフィールドの定義。
- `field.cpp`: 各フォーマットフィールドの具体的なフォーマット処理を実装。
- `config_init.h`: YAML形式の設定ファイルの読み書きとロガー設定の初期化インターフェース。
- `config_init.cpp`: YAML形式の設定ファイルからロガー設定を読み取り、マネージャーに反映する。

## 重要な不変条件
- ログレベルは常に有効な値である。
- キューが使用される場合、そのキャパシティは正の整数である。
- アペンダーとフォーマッタは適切に初期化され、イベントを処理する準備ができている。