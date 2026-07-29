# Echo-Web-Server データセット適格性再評価

## 結論

固定専用環境で新規に全評価を実行した結果、10対象すべてを「採用」と判定した。置換単位は7対象がmodule、`block-deque`、`heap-timer`、`thread-pool`の3対象がclassである。全対象でベースラインと直接フィルタが3回安定し、公開interfaceを維持した置換境界があり、主要責務を壊す有効ミューテーションが少なくとも2件、対応付けた直接テストで検出された。

この判定は既存テストが観測する範囲での再生成コード評価への適格性を示す。未検証範囲を含む完全な意味的等価性は保証しない。

## 固定条件と履歴分離

- Commit: `fb2fadb7e7f4c340325b0a72847425f6e8b6367e`
- Docker tag: `cpp-roundtrip-env:echo-web-server-v2`
- Docker image ID: `sha256:f4983b70f6c2400cec7c8869810a8ec3e87f6966e2cc86e09598bdbbc4773c5c`
- Ubuntu 22.04.5 LTS、GCC 11.4.0、CMake 3.22.1、Git 2.34.1
- libfmt-dev 8.1.1+ds1-2、libgtest-dev/libgmock-dev 1.11.0-3、libyaml-cpp-dev 0.7.0+dfsg-8build1
- 新run: `logs/Echo-Web-Server/run_20260727T135730Z/`
- 旧runと`environment_setup/`は参照のみ。旧canonical metadataはSHA-256付きで`metadata/history/Echo-Web-Server/run_20260727T130931Z/`へ履歴化した。

## 調査・集計方法

- 実装ファイルのみを行計測し、空白のみを空行、commentのみをcomment行、末尾comment付きcodeをcode行とした。
- `method_count`はcommentを除去した固定commitのC++から、bodyを持つconstructor/destructor/operator/private/static/template/inlineを含むfunction definitionを字句的に再抽出した値である。署名一覧は`02_metrics.json`に保存した。
- `test_declaration_count`はcommentを除去後の`TEST/TEST_F/TEST_P`宣言、`discovered_test_count`は`--gtest_list_tests`と対象filterの照合による重複なし実名数である。
- CTest 3回、3本のGoogleTestを一巡とした全体実行3回、対象別直接filter 3回を独立実行した。
- 各ミューテーションは1件ずつ実装だけへ適用し、build、直接filter、全3実行ファイルの順で評価した。その後、元byte列、SHA-256、diff、再build、直接filterで復元を確認した。

## ベースライン

- Clean configure/build: 成功
- CTest: 63/63成功 × 3回。件数・test名・順序一致: `True`
- 全GoogleTest: 63/63成功 × 3回（test-bundle 58、log-test 2、http-test 3）。件数・test名・順序一致: `True`

| target | 選択数 | 3回実行数 | 名前・順序一致 | 選択テスト名 |
|---|---:|---|---|---|
| util | 9 | 9/9/9 | yes | StringTest.LetterCaseConversion, StringTest.ReplaceString, StringTest.SplitString, StringTest.SplitStringToLines, RAIITest.Destroy, LoadYamlStringTest.RequiredField, YamlNodeTest.ThrowIfFieldIsNotScalar, ConceptTest.Addable, MappedReadOnlyFileTest.Map |
| buffer | 6 | 6/6/6 | yes | BufferTest.Construction, BufferTest.Copy, BufferTest.ReadWriteOffset, BufferTest.ReadWrite, BufferTest.Clear, IOBufferTest.ReadWrite |
| io | 2 | 2/2/2 | yes | StringStreamIOTest.ReadWrite, FileDescriptorIOTest.ReadWrite |
| config | 10 | 10/10/10 | yes | ConfigurationVariableConverterTest.Number, ConfigurationVariableConverterTest.String, ConfigurationVariableConverterTest.List, ConfigurationVariableConverterTest.Set, ConfigurationVariableConverterTest.Map, ConfigurationVariableTest.Construction, ConfigurationVariableTest.ConvertedFromString, ConfigurationVariableTest.Listen, ConfigurationTest.Lookup, ConfigurationTest.Visit |
| block-deque | 4 | 4/4/4 | yes | BlockDequeTest.Construction, BlockDequeTest.SingleThreadPushPop, BlockDequeTest.MultiThreadPushPop, BlockDequeTest.Close |
| log | 9 | 9/9/9 | yes | LoggerTest.SynchronousLog, LoggerTest.AsynchronousLog, LogManagementTest.LoggerManager, LogManagementTest.LevelEnumConversion, LogManagementTest.AppenderTypeEnumConversion, LogFormatterTest.Construction, LogFormatterTest.Format, LogFormatFieldTest.ParsePattern, LoggerConfigurationTest.Construction |
| heap-timer | 8 | 8/8/8 | yes | HeapTimerTest.Construction, HeapTimerTest.PushPop, HeapTimerTest.Adjust, HeapTimerTest.Remove, HeapTimerTest.Invoke, HeapTimerTest.Tick, HeapTimerTest.ToNextTick, HeapTimerTest.Clear |
| thread-pool | 1 | 1/1/1 | yes | ThreadPoolTest.Execution |
| ip | 5 | 5/5/5 | yes | ConceptTest.ValidIPAddr, IPAddrTest.MaximumLength, IPAddrTest.LoopBack, IPAddrTest.Any, IPAddrTest.Construction |
| http | 9 | 9/9/9 | yes | HTTPTest.StatusCodeEnumConversion, HTTPTest.MethodEnumConversion, HTTPTest.ContentType, HTTPTest.URLEncoding, HTTPTest.HTMLPlaceholder, HTTPTest.PutParameterIntoHTML, HTTPRequestTest.Parse, HTTPResponseTest.BuiltByFile, HTTPResponseTest.BuiltByPredefinedErrorContent |

全対象でfilter実行数は1件以上であり、0件正常終了はなかった。静的宣言名とdiscovered名は全10対象で完全一致し、欠落・重複はなかった。

## 実装・テスト対応、規模、置換境界

| target | granularity | 宣言・実装 | 対応test | total/blank/comment/code | methods | tests decl/discovered | 主なAPI・型 | 置換 |
|---|---|---|---|---:|---:|---:|---|---|
| util | module | include/util.h;src/util/util.cpp | tests/util_test.cpp | 466/81/110/275 | 38 | 9/9 | 自由関数 StringToLower/ReplaceAllSubstring/LoadYamlString、RAII補助、MappedReadOnlyFile、YAML node補助 | yes: hpp/cpp分離の自由関数・補助型モジュール |
| buffer | module | include/containers/buffer.h;src/containers/buffer/buffer.cpp | tests/containers/buffer_test.cpp | 421/99/80/242 | 40 | 6/6 | Buffer、IOBuffer；append/retrieve/clear、read/write領域・offset管理 | yes: hpp/cpp分離のBuffer/IOBufferクラス群 |
| io | module | include/io.h;src/io/io.cpp | tests/io_test.cpp | 217/48/59/110 | 7 | 2/2 | Stream、StringStream、FileDescriptor；BufferとのReadFrom/WriteTo | yes: hpp/cpp分離のStream抽象とStringStream/FileDescriptor実装 |
| config | module | include/config.h;src/config/config.cpp | tests/config_test.cpp | 622/89/126/407 | 47 | 10/10 | VarBase、VarConverter、Var<T>、Config；型変換、lookup、listener、YAML load | yes: template実装を含むheader + cppの設定モジュール |
| block-deque | class | include/containers/block_deque.h | tests/containers/block_deque_test.cpp | 261/51/54/156 | 20 | 4/4 | BlockDeque<T>；両端push/pop、capacity、flush、close | yes: header-only template class |
| log | module | include/log.h;src/log/log.cpp;src/log/appender.cpp;src/log/field.h;src/log/field.cpp;src/log/config_init.h;src/log/config_init.cpp | tests/log_test.cpp;src/log/field_test.cpp;src/log/config_init_test.cpp | 1636/357/235/1044 | 127 | 9/9 | Event、Logger、Manager、Formatter、Appender群、field parser、LoggerConfig listener | yes: 公開header + 複数cpp/internal headerの複合モジュール |
| heap-timer | class | include/containers/heap_timer.h | tests/containers/heap_timer_test.cpp | 500/78/135/287 | 40 | 8/8 | HeapTimer<Key>；push/adjust/remove/pop/tick/次回期限 | yes: header-only template class |
| thread-pool | class | include/containers/thread_pool.h;src/containers/thread_pool/thread_pool.cpp | tests/containers/thread_pool_test.cpp | 175/33/42/100 | 10 | 1/1 | ThreadPool；start/close/push/worker execution | yes: hpp/cpp分離のThreadPool class |
| ip | module | include/ip.h;src/ip/ip.cpp | tests/ip_test.cpp | 198/59/16/123 | 14 | 5/5 | Addr interface、IPv4Addr、IPv6Addr；構築、port/address/raw socket access | yes: hpp/cpp分離のAddr/IPv4Addr/IPv6Addrクラス群 |
| http | module | include/http.h;src/http/http.cpp;src/http/request.h;src/http/request.cpp;src/http/response.h;src/http/response.cpp | tests/http_test.cpp;src/http/request_test.cpp;src/http/response_test.cpp | 1192/223/233/736 | 86 | 9/9 | StatusCode/ContentType変換、Header/Body、Request、Response；parse/build/keep-alive | yes: 公開header + request/response内部クラスの複合モジュール |

`log`と`http`は複数classを含むが、公開contractと内部実装が単一CMake library内で密結合するためmodule単位を1データ候補とした。`block-deque`と`heap-timer`は単一のheader-only template classを、`thread-pool`は単一のThreadPool classとその分離実装を置換対象とするためclass単位とした。その他はmodule単位で、公開headerのsignatureを固定し、対応cpp/internal headerを置換境界とする。

## ミューテーション結果

| target | attempted | compile | test | direct | indirect | runtime | survived | execution | 判定 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| util | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | 採用 |
| buffer | 3 | 0 | 2 | 2 | 0 | 1 | 0 | 0 | 採用 |
| io | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | 採用 |
| config | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | 採用 |
| block-deque | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | 採用 |
| log | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | 採用 |
| heap-timer | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | 採用 |
| thread-pool | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | 採用 |
| ip | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | 採用 |
| http | 3 | 0 | 2 | 2 | 0 | 1 | 0 | 0 | 採用 |

有効30件の合計は`test_killed=28`（`direct_test_killed=28`、`indirect_test_killed=0`）、`runtime_killed=2`、`compile_killed=0`、`survived=0`、`execution_error=0`である。

- `buffer_01_append_noop`: assertion失敗を出した後、直接test-bundleと全test-bundleがSIGABRT相当のexit 134。分類優先順位により`runtime_killed`とし、採用根拠には使用しなかった。
- `http_01_status_message_empty`: test-bundleでは通常のassertion失敗、http-testはexit 134。必須processの異常終了を優先して`runtime_killed`とし、採用根拠には使用しなかった。
- `ip_03_ipv4_sockaddr_text_empty`: 初回の広いconstructor markerがbraced member initializerをbodyと誤認した。この無効な初回差分・compile logは`adjustments/ip_03_initial_invalid_marker_attempt/`へ隔離し、initializer末尾までmarkerを限定した最小body変更へ調整した。有効変更は`IPAddrTest.Construction`が直接検出した。

全30件の正確なdiff、失敗test名、直接/間接、runtime情報、build結果、復元hashは`mutation_results.csv`と`mutation_results.json`に記録した。

## 対象別の観測範囲と未検証範囲

| target | 既存testが観測した機能 | 今回確認できない主な範囲 | 依存・再現性 |
|---|---|---|---|
| util | 大小文字変換、substring置換、YAML必須field、RAII、YAML node、concept、read-only mmap | locale依存Unicode case、mmap権限/巨大file/OS error、全YAML例外形 | STL; yaml-cpp; POSIX mmap/stat/open/close; file I/O; yes（3回一致） |
| buffer | 構築、append/retrieve/clear、offset、read/write、IOBuffer | 極端な容量、allocation失敗、高競合下の全offset/interleaving | STL; util; memory allocation; network/time/random/thread/GUI/hardwareなし; yes（3回一致） |
| io | StringStreamとBuffer間の双方向転送、FileDescriptorへの書き込み | EINTR/EAGAIN、partial I/O、実socket/device、fd失効 | Buffer; STL streams; POSIX fd read/write; file/device descriptor I/O; yes（固定local fdテストで3回一致） |
| config | scalar/list/map/set変換、値更新/listener、lookup、YAMLからの設定 | 高競合更新、listener例外、全不正YAML/type mismatch | util; yaml-cpp; STL containers/locks; file-backed YAML load; yes（3回一致） |
| block-deque | 単一/複数thread push/pop、両端順序、close | 長時間高競合、公平性、spurious wakeupの全interleaving | STL deque/mutex/condition_variable; thread scheduling; yes（3回一致；scheduler依存余地あり） |
| log | 同期/非同期log、management、format、pattern parse、configuration listener | permission不足、rotation/reopen失敗、時刻境界、高並行時の完全順序 | fmt; yaml-cpp/config; STL threads/locks; filesystem; system time; yes（3回一致；時刻・thread・filesystem依存あり） |
| heap-timer | push/pop/adjust/remove/clear、callback invoke、tick、次回期限 | clock境界、callback例外、高並行更新 | STL heap/map/function; steady_clock time; yes（3回一致；steady_clock依存あり） |
| thread-pool | worker開始、task投入、task実行 | shutdown競合、task例外、飽和負荷、公平性 | STL thread/mutex/condition_variable; scheduler; yes（3回一致；scheduler依存余地あり） |
| ip | IPv4/IPv6構築、port/address/raw表現、valid address concept | 全不正address、IPv6 scope、OS API失敗、live network | POSIX sockets, sockaddr, inet_ntop/inet_pton; OS networking API; yes（固定OS APIで3回一致） |
| http | status/content-type変換、request parse、URL encoded POST、response build、keep-alive | chunked/巨大/malformed入力の全組合せ、escaping境界、live network integration | buffer/io/config/util; fmt; filesystem; HTTP text parsing; no live network in direct tests; yes（固定local fixtureで3回一致） |

未検証範囲の存在は単独では除外理由にしていない。採用根拠は、対応filter内で主要責務の変更を直接検出した事実に限定した。今回`indirect_test_killed`だけに依存する対象はない。

## 採用判定

- **util — 採用**: 固定環境のbaselineが3回安定し、置換可能。主要責務のdirect_test_killedを3件確認。
- **buffer — 採用**: 固定環境のbaselineが3回安定し、置換可能。主要責務のdirect_test_killedを2件確認。
- **io — 採用**: 固定環境のbaselineが3回安定し、置換可能。主要責務のdirect_test_killedを3件確認。
- **config — 採用**: 固定環境のbaselineが3回安定し、置換可能。主要責務のdirect_test_killedを3件確認。
- **block-deque — 採用**: 固定環境のbaselineが3回安定し、置換可能。主要責務のdirect_test_killedを3件確認。
- **log — 採用**: 固定環境のbaselineが3回安定し、置換可能。主要責務のdirect_test_killedを3件確認。
- **heap-timer — 採用**: 固定環境のbaselineが3回安定し、置換可能。主要責務のdirect_test_killedを3件確認。
- **thread-pool — 採用**: 固定環境のbaselineが3回安定し、置換可能。主要責務のdirect_test_killedを3件確認。
- **ip — 採用**: 固定環境のbaselineが3回安定し、置換可能。主要責務のdirect_test_killedを3件確認。
- **http — 採用**: 固定環境のbaselineが3回安定し、置換可能。主要責務のdirect_test_killedを2件確認。

## 最終検証

- 通常実装での最終build/CTest/全GoogleTest/10対象filter: すべて成功
- HEAD: `fb2fadb7e7f4c340325b0a72847425f6e8b6367e`（固定commit一致）
- `git diff`: 空
- `git status --short --untracked-files=no`: 空
- `git status --short`: 空
- 非ignore未追跡: なし
- `build/`は存在し、`.gitignore:51:/build/`でignoreされることを確認した。

## 人間が最終判断すべき事項

- module単位、とくに複合的な`log`/`http`の規模と、class単位の3対象を同一データセットで扱うことがLLM設計書生成・再生成のtoken予算・比較設計に適するか。
- header-only template対象を、cpp分離対象と同一の難易度群として扱うか。
- thread/time/filesystem/POSIX networking依存を含む対象に、別host・別schedulerで追加再現性確認を要求するか。
- 未検証のerror path・高競合・live network機能を研究上の意味的同等性範囲へ含めるか。
