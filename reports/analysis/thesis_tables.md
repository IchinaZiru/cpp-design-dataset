# 論文掲載用集計表

## 表A　対象別の主実験結果

| No. | Repository | Target | Granularity | Direct tests | Full tests | Result | Failure stage | Failure cause |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Echo-Web-Server | block-deque | module_files | 4 | 63 | FAIL | direct_test | ハング・外部停止（デッドロック疑い） |
| 2 | Echo-Web-Server | buffer | module_files | 6 | 63 | FAIL | build | 構文エラー |
| 3 | Echo-Web-Server | config | module_files | 10 | 63 | FAIL | build | 型・インタフェースの誤理解 |
| 4 | Echo-Web-Server | heap-timer | module_files | 8 | 63 | FAIL | build | 構文エラー |
| 5 | Echo-Web-Server | http | module_files | 9 | 63 | FAIL | build | 型・インタフェースの誤理解 |
| 6 | Echo-Web-Server | io | module_files | 2 | 63 | FAIL | build | 型・インタフェースの誤理解 |
| 7 | Echo-Web-Server | ip | module_files | 5 | 63 | PASS | — | — |
| 8 | Echo-Web-Server | log | module_files | 9 | 63 | FAIL | code_regeneration | 生成出力の打ち切り |
| 9 | Echo-Web-Server | thread-pool | module_files | 1 | 63 | FAIL | build | 定義・依存関係の欠落 |
| 10 | Echo-Web-Server | util | module_files | 9 | 63 | FAIL | build | 構文エラー |
| 11 | ini-cpp | INIWriter::write | function | 3 | 27 | PASS | — | — |
| 12 | ini-cpp | INIReader | class_span | 24 | 27 | FAIL | build | 型・インタフェースの誤理解 |
| 13 | RISCV-Simulator | Instruction | module_files | 7 | 18 | FAIL | build | 型・インタフェースの誤理解 |
| 14 | RISCV-Simulator | Memory | class_span | 4 | 18 | PASS | — | — |
| 15 | RISCV-Simulator | Parser | class_span | 3 | 18 | PASS | — | — |
| 16 | RISCV-Simulator | Register | class_span | 2 | 18 | PASS | — | — |
| 17 | RISCV-Simulator | RegisterFile | class_span | 1 | 18 | PASS | — | — |

## 表B　リポジトリ別結果

| Repository | N | PASS | FAIL | Pass rate |
| --- | --- | --- | --- | --- |
| Echo-Web-Server | 10 | 1 | 9 | 10.0% |
| RISCV-Simulator | 5 | 4 | 1 | 80.0% |
| ini-cpp | 2 | 1 | 1 | 50.0% |

## 表C　粒度別結果

| Granularity | N | PASS | FAIL | Pass rate |
| --- | --- | --- | --- | --- |
| class_span | 5 | 4 | 1 | 80.0% |
| function | 1 | 1 | 0 | 100.0% |
| module_files | 11 | 1 | 10 | 9.1% |

## 表D　粒度間の探索的比較

| Comparison | Group 1 PASS/FAIL | Group 2 PASS/FAIL | Fisher p (two-sided) |
| --- | --- | --- | --- |
| class_span vs module_files | 4/1 | 1/10 | 0.0128 |

## 表E　失敗原因別件数

| Failure cause | Count |
| --- | --- |
| 型・インタフェースの誤理解 | 5 |
| 構文エラー | 3 |
| ハング・外部停止（デッドロック疑い） | 1 |
| 定義・依存関係の欠落 | 1 |
| 生成出力の打ち切り | 1 |
