# Round-trip batch readiness

既存metadataから対象情報を抽出した結果である．
この段階ではLLM生成・ソース置換・テスト実行を行わない．

- 実験対象数: **17**
- 想定対象数: **17**
- metadata自動抽出完了: **12**
- 実行設定完了: **0**
- 除外対象: **1**

| repository | target | adoption | granularity | source files | direct tests | full tests | metadata | execution |
|---|---|---|---|---:|---:|---:|---|---|
| Echo-Web-Server | block-deque | 採用 | class_span | 1 | 4 | 63 | COMPLETE | DRAFT |
| Echo-Web-Server | buffer | 採用 | module_files | 2 | 6 | 63 | COMPLETE | DRAFT |
| Echo-Web-Server | config | 採用 | module_files | 2 | 10 | 63 | COMPLETE | DRAFT |
| Echo-Web-Server | heap-timer | 採用 | class_span | 1 | 8 | 63 | COMPLETE | DRAFT |
| Echo-Web-Server | http | 採用 | module_files | 6 | 9 | 63 | COMPLETE | DRAFT |
| Echo-Web-Server | io | 採用 | module_files | 2 | 2 | 63 | COMPLETE | DRAFT |
| Echo-Web-Server | ip | 採用 | module_files | 2 | 5 | 63 | COMPLETE | DRAFT |
| Echo-Web-Server | log | 採用 | module_files | 7 | 9 | 63 | COMPLETE | DRAFT |
| Echo-Web-Server | thread-pool | 採用 | class_span | 2 | 1 | 63 | COMPLETE | DRAFT |
| Echo-Web-Server | util | 採用 | module_files | 2 | 9 | 63 | COMPLETE | DRAFT |
| ini-cpp | INIReader | 採用 | class_span | 1 | 24 | 27 | COMPLETE | DRAFT |
| ini-cpp | INIWriter | 採用 | class_span | 1 | 3 | 27 | COMPLETE | DRAFT |
| RISCV-Simulator | Instruction | 条件付き採用 | N/A | 0 | N/A | 18 | INCOMPLETE | DRAFT |
| RISCV-Simulator | Memory | 条件付き採用 | N/A | 0 | N/A | 18 | INCOMPLETE | DRAFT |
| RISCV-Simulator | Parser | 条件付き採用 | N/A | 0 | N/A | 18 | INCOMPLETE | DRAFT |
| RISCV-Simulator | Register | 条件付き採用 | N/A | 0 | N/A | 18 | INCOMPLETE | DRAFT |
| RISCV-Simulator | RegisterFile | 条件付き採用 | N/A | 0 | N/A | 18 | INCOMPLETE | DRAFT |

## 除外対象

- `RISCV-Simulator/Session`: 除外

## 状態の意味

- `metadata COMPLETE`: レポートから対象・粒度・テスト数等を抽出できた．
- `execution DRAFT`: 置換境界と実行コマンドが未検証であり，まだ実験できない．
