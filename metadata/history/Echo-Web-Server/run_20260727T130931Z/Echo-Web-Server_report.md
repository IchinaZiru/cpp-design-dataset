# Echo-Web-Server データセット適格性評価報告

## 結論

固定Dockerイメージ `cpp-roundtrip-env:ubuntu22.04` では、元コードをクリーンconfigureできなかった。`src/util/CMakeLists.txt` の `find_package(yaml-cpp REQUIRED)` が `yaml-cppConfig.cmake` または `yaml-cpp-config.cmake` を発見できず、終了コード1で停止した。

イメージ内を確認した結果、GTest 1.11.0は導入済みだった一方、`libyaml-cpp-dev`と`libfmt-dev`は導入されていなかった。リポジトリのDockerfileには両パッケージを導入する記述があるが、指定された固定イメージの実状態には反映されていない。

計画のベースラインゲートに従い、ビルド設定の変更、依存パッケージの後付け、別イメージの利用は行わず、ミューテーションは1件も開始していない。固定環境で元コードをビルドできることが採用条件であるため、10対象はいずれも暫定的な「保留」ではなく「除外」とした。

これは実装品質や既存テストの感度を否定する結果ではない。テスト感度は実行できておらず、固定環境でのベースライン不成立だけを根拠とする判定である。

## 固定コミットと実行環境

- リポジトリ: `repos/Echo-Web-Server`
- 固定コミット: `fb2fadb7e7f4c340325b0a72847425f6e8b6367e`
- Dockerイメージ: `cpp-roundtrip-env:ubuntu22.04`
- イメージID: `sha256:81e23cc94a387697d7979c847d81bf557543fece913065fbdbd329bf194f62cd`
- Ubuntu: 22.04.5 LTS
- GCC: 11.4.0
- CMake: 3.22.1
- Git: 2.34.1
- GTest: 1.11.0
- `libyaml-cpp-dev`: 未導入
- `libfmt-dev`: 未導入
- run-id: `run_20260727T130931Z`

環境と依存確認の生ログは `commands/0006_environment.*` と、コマンド台帳中の `diagnostic_missing_dependencies` に保存した。

## 調査方法と集計規則

評価単位は、公開インターフェースとCMakeライブラリ境界を維持して置換する10モジュールとした。`log`と`http`は複数クラス・複数実装ファイルを含むが、単一ライブラリとして相互依存しているため今回のCSVでは分割していない。

行数は宣言・実装ファイルを対象に、空白だけの行、コメントだけの行、実コード行へ排他的に分類した。末尾コメントを含むコード行は実コード行である。

`method_count`は、実装本体または明示的な`= default`定義を持つ呼び出し可能要素を数えた。コンストラクタ、デストラクタ、演算子、private、static、ネスト型、template、inlineを含み、pure declarationと`= delete`は除外した。対象別の算定根拠は `03_method_inventory.json` に保存した。

`test_declaration_count`はコメントアウトされたマクロを除外した既存の`TEST`、`TEST_F`、`TEST_P`宣言数である。`discovered_test_count`は本来`--gtest_list_tests`を優先するが、テスト実行ファイルが生成されなかったため`NOT_AVAILABLE`とした。0件とみなしたわけではない。

## 実装とテストの対応・規模

| target | 実装方式 | total | blank | comment | code | methods | TEST宣言 |
|---|---|---:|---:|---:|---:|---:|---:|
| util | hpp/cpp＋inline template | 466 | 81 | 110 | 275 | 28 | 9 |
| buffer | hpp/cpp | 421 | 99 | 80 | 242 | 38 | 6 |
| io | hpp/cpp | 217 | 48 | 59 | 110 | 10 | 2 |
| config | header template＋cpp | 622 | 89 | 126 | 407 | 38 | 10 |
| block-deque | header-only template | 261 | 51 | 54 | 156 | 18 | 4 |
| log | 複数hpp/cpp | 1636 | 357 | 235 | 1044 | 101 | 9 |
| heap-timer | header-only template | 500 | 78 | 135 | 287 | 25 | 8 |
| thread-pool | hpp/cpp | 175 | 33 | 42 | 100 | 6 | 1 |
| ip | hpp/cpp | 198 | 59 | 16 | 123 | 15 | 5 |
| http | 複数hpp/cpp | 1192 | 223 | 233 | 736 | 62 | 9 |

静的な既存テスト宣言は合計63件だった。テスト実行ファイルはCMake上では`test-bundle`、`log-test`、`http-test`の3本だが、configure失敗によりいずれも生成されなかった。

## 対象別の構造と依存

### util

文字列操作、YAML補助、RAII、Singleton、Linuxファイルマッピング、ファイルディスクリプタ操作、スレッドID、backtraceを含む。`fmt`、`yaml-cpp`、`execinfo`、`fcntl`、`mmap`、`syscall`へ依存する。公開APIを保ったモジュール置換は静的には可能だが、今回の固定環境ではビルド確認できていない。

### buffer

`Buffer`と`IOBuffer`を含み、`io`と相互に連携する。可変バイト列、read/write offset、拡張、append/retrieveを担当する。外部サービス依存はなく、標準コンテナとatomicを使用する。

### io

`IReader`、`IWriter`、`IReadWriter`、`Null`、`StringStream`、`FileDescriptor`を含む。POSIXの`readv`、`write`、ファイルディスクリプタへ依存する。ファイルシステムを利用するテストが宣言されている。

### config

各種`VarConverter`、`VarBase`、`Var<T>`、`Config`、root configを含む。テンプレート実装の多くが公開ヘッダにある。`yaml-cpp`と`fmt`へ直接または`util`経由で依存し、今回のconfigure失敗箇所と密接に関連する。

### block-deque

condition variableを用いるheader-onlyのblocking dequeである。スレッド、待機、容量、closeの状態を扱う。GUI、ネットワーク、乱数、ハードウェアへの直接依存はない。

### log

Event、Formatter、Appender、Logger、Manager、format field、YAML設定初期化を一つのライブラリに含む。`util`、`block-deque`、`config`、時刻、スレッド、標準出力、ファイル出力へ依存する。同期・非同期処理および実ファイル出力が環境依存要素である。

### heap-timer

steady clockとmin-heapを利用するheader-only timerで、callback、adjust、remove、tickを提供する。テストソースは`std::random_shuffle`と時刻を利用するため、実行できた場合は3回反復で安定性を確認する予定だった。

### thread-pool

condition variableと`std::thread`を利用するworker poolである。デフォルトworker数は`hardware_concurrency()`に依存する。既存テストソースは10msの待機を使うため、環境負荷に対する再現性確認が必要だが、今回は実行できていない。

### ip

抽象`IPAddr`、IPv4Addr、IPv6Addrを含み、`inet_pton`、`inet_ntop`、sockaddr、byte-order変換へ依存する。実ネットワーク通信は不要だが、Linux/POSIXネットワークAPI依存である。

### http

HTTP補助関数、Request state parser、Response builder、ConnectionImpl、型付きConnectionを含む。`buffer`、`io`、`ip`、`util`、filesystem、socket、ファイルマッピングへ依存する。テストソース上、補助変換、URL decode、POST解析、レスポンス構築は対象だが、実Connectionのreceive/send/processを直接検証するテストは確認できない。

## ベースライン実行結果

指定どおり、次をクリーン状態で実行した。

```text
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug -DECHO_WEB_SERVER_BUILD_TESTS=ON
cmake --build build -j2
```

最初のconfigureは終了コード1で失敗した。続けて実行されたbuildは有効なMakefileがないため終了コード2だった。

最終確認時には`build/`をもう一度削除し、同じconfigureとbuildを再実行した。同じ依存欠落が再現し、3つのGoogleTest実行ファイルが存在しないことを確認した。

そのため、以下はすべて`NOT_RUN`である。

- CTest 3回
- 全GoogleTest 3回
- `--gtest_list_tests`
- 対象別GoogleTest
- 最終CTest、全GoogleTest、対象別GoogleTest

未実行を成功や0件として扱っていない。ベースラインの成功・失敗数、テスト名、反復一致性は`NOT_ASSESSABLE`である。

## ミューテーション結果

ミューテーション試行数は全対象で0件である。

| target | attempted | compile_killed | test_killed | direct | indirect | runtime_killed | survived | execution_error |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 全10対象共通 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

ベースライン失敗後にミューテーションを開始しないという計画上のゲートを適用した結果であり、ミューテーション自体の`execution_error`ではない。したがって`execution_error`も0件とした。

`direct_test_killed`、`indirect_test_killed`、`runtime_killed`のいずれも観測されていない。各対象の採用根拠となる直接検出は存在しない。

## テストが観測した機能

実行された既存テストはないため、実行結果として観測済みと主張できる機能はない。

テストソースの静的調査からは、文字列/YAML、buffer、stream/file descriptor I/O、configuration、blocking deque、logging、heap timer、thread pool、IPv4/IPv6、HTTP helper/request/responseを意図したテスト宣言が確認できる。ただし、これは実行結果ではなくテストコードからの推測である。

## 未検証機能

全対象のランタイム挙動が未検証である。加えて静的調査上、次はテスト宣言が限定的または見当たらない。

- utilのnonblocking設定、thread ID、backtrace、Singleton
- ioのNull、partial I/O、EINTR/EAGAIN
- block-dequeのproducer blockingとtimeout精度
- logの実StdOut/FileAppender、負荷時の非同期shutdown、時刻format
- heap-timerのcallback再入と時刻境界
- thread-poolのclose/start競合、例外処理、再起動
- IPの不正アドレス、IPv6 scope
- HTTP ConnectionImplのsocket receive/send/process、path traversal等

これらの未検証範囲は本来、採用可否と分けて扱う予定だった。しかし今回は、それ以前に固定環境でベースラインが成立していない。

## 採用・除外判定

10対象すべてを「除外」とした。

共通根拠は次のとおりである。

1. 固定Docker環境で元コードのconfigureが失敗した。
2. 既存テスト実行ファイルが生成されなかった。
3. ベースラインの3回安定成功を確認できない。
4. 主要責務の`direct_test_killed`を確認できない。

「保留」にしなかった理由は、環境障害が一時的で原因不明なのではなく、指定された固定イメージに必要な開発パッケージが存在しないことを実行結果で確認でき、研究上の固定環境ビルド条件を明確に満たさないためである。

## 最終復元・Git確認

実装ファイルへのミューテーションは一度も適用していない。テスト、CMake、設定ファイルも変更していない。

最終結果は次のとおり。

- `git rev-parse HEAD`: `fb2fadb7e7f4c340325b0a72847425f6e8b6367e`
- `git diff`: 空
- `git status --short --untracked-files=no`: 空
- `git status --short`: 空
- `git ls-files --others --exclude-standard`: 空
- `build/`: 存在するが`.gitignore:51:/build/`により無視される
- `build/`以外の未追跡ファイル: なし

## 人間が最終判断すべき事項

- `cpp-roundtrip-env:ubuntu22.04`を、同じタグのまま依存追加して上書きすると固定環境が変わる。再評価する場合は、新しいイメージIDを明示して別実験として扱うべきか。
- リポジトリのDockerfileが要求する`libfmt-dev`と`libyaml-cpp-dev`を含む新しい固定イメージを正式な実験環境にするか。
- 環境を更新した場合、本報告のミューテーション未実行結果を引き継がず、クリーンビルド、3回反復、30件のミューテーションを最初から再実行するか。
- 今回の除外を「実装・テスト品質による除外」ではなく「指定環境との依存不整合による除外」としてデータセット選定記録に残すか。
