# ラウンドトリップ実験の統合分析

生成日時（UTC）：2026-08-02T11:44:48.015463+00:00

## 1．全体結果

主実験の対象は17件であり，PASSは6件，FAILは11件であった．
通過率は35.3%であり，Wilson法による95%信頼区間は17.3%〜58.7%である．

| 総数 | PASS | FAIL | 通過率 | 95% CI |
| --- | --- | --- | --- | --- |
| 17 | 6 | 11 | 35.3% | 17.3%–58.7% |

## 2．対象別結果

| リポジトリ | 対象 | 粒度 | configure | build | 直接 | 全体 | 判定 | 失敗分類 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Echo-Web-Server | block-deque | module_files | passed | passed | failed | skipped | FAIL | ハング・外部停止（デッドロック疑い） |
| Echo-Web-Server | buffer | module_files | passed | failed | skipped | skipped | FAIL | 構文エラー |
| Echo-Web-Server | config | module_files | passed | failed | skipped | skipped | FAIL | 型・インタフェースの誤理解 |
| Echo-Web-Server | heap-timer | module_files | passed | failed | skipped | skipped | FAIL | 構文エラー |
| Echo-Web-Server | http | module_files | passed | failed | skipped | skipped | FAIL | 型・インタフェースの誤理解 |
| Echo-Web-Server | io | module_files | passed | failed | skipped | skipped | FAIL | 型・インタフェースの誤理解 |
| Echo-Web-Server | ip | module_files | passed | passed | passed | passed | PASS | — |
| Echo-Web-Server | log | module_files | not_recorded | not_recorded | not_recorded | not_recorded | FAIL | 生成出力の打ち切り |
| Echo-Web-Server | thread-pool | module_files | passed | failed | skipped | skipped | FAIL | 定義・依存関係の欠落 |
| Echo-Web-Server | util | module_files | passed | failed | skipped | skipped | FAIL | 構文エラー |
| ini-cpp | INIWriter::write | function | passed | passed | passed | passed | PASS | — |
| ini-cpp | INIReader | class_span | passed | failed | skipped | skipped | FAIL | 型・インタフェースの誤理解 |
| RISCV-Simulator | Instruction | module_files | passed | failed | skipped | skipped | FAIL | 型・インタフェースの誤理解 |
| RISCV-Simulator | Memory | class_span | passed | passed | passed | passed | PASS | — |
| RISCV-Simulator | Parser | class_span | passed | passed | passed | passed | PASS | — |
| RISCV-Simulator | Register | class_span | passed | passed | passed | passed | PASS | — |
| RISCV-Simulator | RegisterFile | class_span | passed | passed | passed | passed | PASS | — |

## 3．リポジトリ別・粒度別結果

| 分類軸 | 群 | 総数 | PASS | FAIL | 通過率 | 95% CI |
| --- | --- | --- | --- | --- | --- | --- |
| repository | Echo-Web-Server | 10 | 1 | 9 | 10.0% | 1.8%–40.4% |
| repository | RISCV-Simulator | 5 | 4 | 1 | 80.0% | 37.6%–96.4% |
| repository | ini-cpp | 2 | 1 | 1 | 50.0% | 9.5%–90.5% |
| granularity | class_span | 5 | 4 | 1 | 80.0% | 37.6%–96.4% |
| granularity | function | 1 | 1 | 0 | 100.0% | 20.7%–100.0% |
| granularity | module_files | 11 | 1 | 10 | 9.1% | 1.6%–37.7% |

## 4．失敗段階

| 段階 | 到達 | PASS | FAIL | SKIP | 未記録 |
| --- | --- | --- | --- | --- | --- |
| design_generation | 16 | 16 | 0 | 0 | 1 |
| code_regeneration | 16 | 15 | 1 | 0 | 1 |
| configure | 16 | 16 | 0 | 0 | 1 |
| build | 16 | 7 | 9 | 0 | 1 |
| direct_test | 7 | 6 | 1 | 9 | 1 |
| full_test | 6 | 6 | 0 | 10 | 1 |

## 5．失敗原因

| 失敗分類 | 件数 |
| --- | --- |
| 型・インタフェースの誤理解 | 5 |
| 構文エラー | 3 |
| ハング・外部停止（デッドロック疑い） | 1 |
| 定義・依存関係の欠落 | 1 |
| 生成出力の打ち切り | 1 |

| 対象 | 失敗段階 | 失敗分類 | 代表的なエラー |
| --- | --- | --- | --- |
| echo-web-server-block-deque | direct_test | ハング・外部停止（デッドロック疑い） | 直接テスト中に処理の進行が停止し、外部から終了された。デッドロックの可能性があるが、スレッドダンプ等による厳密な確定はしていない（exit_code=137, elapsed_seconds=56279.41479750001） |
| echo-web-server-buffer | build | 構文エラー | /workspace/repos/Echo-Web-Server/src/containers/buffer/buffer.cpp:83:50: error: stray '\' in program |
| echo-web-server-config | build | 型・インタフェースの誤理解 | /workspace/repos/Echo-Web-Server/src/config/config.cpp:305:25: error: no matching function for call to 'std::unordered_map<std::__cxx11::basic_string<char>, std::shared_ptr<ws::cfg::VarBase> >::find(const string_view&)' |
| echo-web-server-heap-timer | build | 構文エラー | /workspace/repos/Echo-Web-Server/include/containers/heap_timer.h:47:61: error: expected ';' before 'gt' |
| echo-web-server-http | build | 型・インタフェースの誤理解 | /workspace/repos/Echo-Web-Server/src/http/request.cpp:8:26: error: invalid use of incomplete type 'class ws::http::Request::State' |
| echo-web-server-io | build | 型・インタフェースの誤理解 | /workspace/repos/Echo-Web-Server/src/io/io.cpp:14:20: error: cannot convert 'std::span<std::byte>' to 'std::size_t' {aka 'long unsigned int'} |
| echo-web-server-log | code_regeneration | 生成出力の打ち切り | code regeneration ended with done_reason=length |
| echo-web-server-thread-pool | build | 定義・依存関係の欠落 | /workspace/repos/Echo-Web-Server/src/containers/thread_pool/thread_pool.cpp:57:31: error: 'ws::log::LogLevel' has not been declared |
| echo-web-server-util | build | 構文エラー | /workspace/repos/Echo-Web-Server/include/util.h:239:38: error: expected '{' before ';' token |
| ini-cpp-inireader | build | 型・インタフェースの誤理解 | /workspace/repos/ini-cpp/ini/ini.h:129:104: error: no matching function for call to 'std::basic_string_view<char>::basic_string_view(std::istreambuf_iterator<char, std::char_traits<char> >, std::istreambuf_iterator<char, std::char_traits<char> >)' |
| riscv-simulator-instruction | build | 型・インタフェースの誤理解 | /workspace/repos/RISCV-Simulator/src/Common/Instruction.hpp:65:173: error: request for member 'value' in '((InstructionBase*)this)->InstructionBase::imm', which is of non-class type 'Immediate' {aka 'unsigned int'} |

## 6．コード規模・テスト数との関係

相関係数は探索的な記述値である．対象数が17件と少なく，各対象も独立同分布とは限らないため，因果関係や一般的傾向の証明としては扱わない．
また，コード規模，テスト数，生成トークン数はリポジトリおよび粒度と交絡している．特に全体テスト数はリポジトリごとにほぼ固定されているため，その相関をテスト数単独の効果とは解釈しない．

| 指標 | n | PASS平均 | FAIL平均 | PASS中央値 | FAIL中央値 | 点双列相関 | Spearman ρ |
| --- | --- | --- | --- | --- | --- | --- | --- |
| original_loc | 17 | 59.500 | 553.545 | 36.500 | 421.000 | -0.555 | -0.779 |
| original_chars | 17 | 1517.500 | 15479.636 | 1214.000 | 12758.000 | -0.565 | -0.804 |
| generated_loc | 16 | 66.333 | 401.300 | 47.500 | 393.500 | -0.675 | -0.784 |
| expected_direct_tests | 17 | 3.000 | 8.091 | 3.000 | 8.000 | -0.458 | -0.543 |
| expected_full_tests | 17 | 27.000 | 55.636 | 18.000 | 63.000 | -0.650 | -0.658 |
| code_eval_count | 16 | 506.400 | 3682.364 | 355.000 | 3274.000 | -0.627 | -0.775 |

### 粒度間の探索的比較

class_spanとmodule_filesのPASS／FAIL分布についてFisherの正確確率検定（両側）を行った．ただし，粒度とリポジトリ構成が強く対応しているため，粒度そのものの因果効果を示す検定ではない．

| 比較 | class_span PASS/FAIL | module_files PASS/FAIL | Fisher p（両側） |
| --- | --- | --- | --- |
| class_span vs module_files | 4/1 | 1/10 | 0.0128 |

## 7．出力形式・正規化

| メタデータあり | 正規化実施 | 正規化後PASS | strict format失敗 | length終了 |
| --- | --- | --- | --- | --- |
| 6 | 5 | 4 | 5 | 1 |

## 8．解釈上の注意

- テスト通過は既存テストスイートが観測する範囲での正当性を示すものであり，未検証機能を含む完全な意味的等価性を保証しない．
- リポジトリ別・粒度別の対象数は均等ではなく，対象選定にも条件があるため，群間差は探索的に解釈する．
- 粒度とリポジトリは独立ではない．class_spanの大部分はRISCV-Simulator，module_filesの大部分はEcho-Web-Serverであるため，両者の通過率差を粒度だけに帰属させない．
- original_locとgenerated_locは置換粒度をそろえて測定する．module_filesは対象ファイル全体，class_spanは抽出したクラス定義，旧形式のfunctionは対象関数本体を数える．
- generated_locは完全なコード再生成が得られた対象だけを測定し，done_reason=lengthの不完全出力は除外する．
- BlockDequeは直接テスト中にハングして外部停止した．デッドロックの可能性はあるが，スレッドダンプ等で厳密に確定していないため，『ハング・外部停止（デッドロック疑い）』と記録する．
- 旧形式のINIWriter実験は標準ハーネス外であるため，利用できるメタデータが他の16対象より少ない可能性がある．
- 感度分析やpilot-failuresは主実験の17件には含めていない．

## 9．データ品質

検証上の問題件数：0
