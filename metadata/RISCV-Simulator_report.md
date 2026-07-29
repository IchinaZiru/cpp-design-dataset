# RISCV-Simulator 研究データセット適格性評価

## 結論

固定コミット上のクリーンビルドと既存18テストは安定して成功した。ただし、代表ミューテーション18件のうち `test_killed` は10件、`survived` は8件だった。`compile_killed` と最終分類が `execution_error` になったミューテーションはない。

暫定判定は次のとおり。

| 対象 | 判定 | 主な理由 |
|---|---|---|
| Memory | 条件付き採用 | word/shortの基本操作は検出するが、範囲上限の破壊を検出せず、実装にendianness・alignment・aliasing依存がある |
| Parser | 条件付き採用 | 16進変換とバイト進行は検出するが、複数wordの配置進行を検出しない |
| Instruction | 条件付き採用 | 6形式のデコードと符号拡張は強いが、nop sentinelと複数の公開helperが未検証 |
| Register | 条件付き採用 | write・tick・stallは検出するが、`current()` の意味反転を検出しない |
| RegisterFile | 条件付き採用 | tick・readは検出するが、レジスタ2～31への書き込み停止を検出しない |
| Session | 除外 | 既存テストは構築・破棄だけで、主要動作を壊す3件がすべて生存 |

## 実行環境

- 対象: `cpp-design-dataset/repos/RISCV-Simulator`
- 固定コミット: `8989a09c357a69b68612f653380d60816f5176c2`
- Dockerイメージ: `cpp-roundtrip-env:ubuntu22.04`
- イメージID: `sha256:81e23cc94a387697d7979c847d81bf557543fece913065fbdbd329bf194f62cd`
- OS: Ubuntu 22.04.5 LTS
- GCC: 11.4.0
- CMake: 3.22.1
- Git: 2.34.1
- GoogleTest: 1.11.0
- C++規格: C++14
- 実行ログ: `logs/RISCV-Simulator/run_20260727T120348Z/`

ネットワーク、時計、乱数、GUI、専用ハードウェアを実際に利用する対象はない。`Session.cpp` は `<random>` と `<thread>` をincludeするが、この実装内では使用していない。`Session` はファイル入力と標準入出力に依存する。

## 調査方法

実装ファイルの総行数、空行、コメント専用行、実コード行を集計した。コードと同じ行にある末尾コメントは実コード行とした。メソッド数にはコンストラクタ、デストラクタ、演算子、staticメソッド、対象内のネスト型メソッドを含めた。

テスト数はソース上の `TEST` 宣言数と、ビルド後の `--gtest_list_tests` による発見数を分けて取得した。全対象で両者は一致したため、最終的な `test_count` には発見数を使用した。

各ミューテーションは1件ずつ適用し、対象テスト実行ファイルをビルドした。分類規則は以下である。

- `compile_killed`: 一時変更後のコンパイルまたはリンクが失敗
- `test_killed`: ビルド成功後、GoogleTestが正常完走し、既存対象テストが1件以上失敗
- `survived`: ビルド成功後、対象テストがすべて成功
- `execution_error`: 有効なビルド・テスト判定を取得できない実行障害

テスト検出率は `test_killed / ビルド成功ミューテーション数` とした。コンパイル失敗はテスト検出数に含めていない。

変更後は毎回逆パッチを適用し、元ファイルのSHA-256、対象ファイルの差分、追跡status、再ビルド、対象テスト成功を確認した。18件すべてで復元に成功した。

## ベースラインと再現性

クリーンconfigureと全ターゲットのビルドは成功した。ビルド時には `LoadStoreUnit.cpp` の3メソッドについて「non-void functionの末尾に到達する可能性」の警告が出たが、ビルド失敗ではなく、今回の6対象への一時変更が原因でもない。

CTestと全GoogleTestの反復結果は以下のとおり。

| 実行 | 1回目 | 2回目 | 3回目 | 名前・結果の一致 |
|---|---:|---:|---:|---|
| CTest | 1/1成功、0.445秒 | 1/1成功、0.460秒 | 1/1成功、0.435秒 | 一致 (`AllTestsInMain`) |
| 全GoogleTest | 18/18成功、0.431秒 | 18/18成功、0.450秒 | 18/18成功、0.404秒 | 18テストの名前・順序・結果が一致 |

対象別ベースラインもすべて成功した。

| 対象 | 宣言数 | 発見数 | 成功/失敗 | GoogleTest内部時間 | Docker呼出し壁時計 |
|---|---:|---:|---:|---:|---:|
| Memory | 4 | 4 | 4/0 | 1 ms | 0.423秒 |
| Parser | 3 | 3 | 3/0 | 1 ms | 0.391秒 |
| Instruction | 7 | 7 | 7/0 | 0 ms | 0.410秒 |
| Register | 2 | 2 | 2/0 | 0 ms | 0.424秒 |
| RegisterFile | 1 | 1 | 1/0 | 0 ms | 0.465秒 |
| Session | 1 | 1 | 1/0 | 6 ms | 0.497秒 |

## 構造と規模

| 対象 | 実装方式 | 総行 | 空行 | コメント | 実コード | メソッド | テスト |
|---|---|---:|---:|---:|---:|---:|---:|
| Memory | `Memory.hpp` header-only | 64 | 14 | 6 | 44 | 8 | 4 |
| Parser | `Parser.hpp` header-only | 52 | 7 | 3 | 42 | 3 | 3 |
| Instruction | `Instruction.hpp` header-only型群 | 183 | 24 | 3 | 156 | 18 | 7 |
| Register | `Register.hpp` header-only template | 34 | 13 | 3 | 18 | 9 | 2 |
| RegisterFile | `RegisterFile.hpp` header-only | 55 | 11 | 3 | 41 | 5 | 1 |
| Session | `Session.h` / `Session.cpp` 分離 | 133 | 35 | 6 | 92 | 9 | 1 |

### Memory

- 型・メソッド: `Memory`、constructor、`check_addr`、word/ushort read/write、`operator[]`、`debug`
- 内部依存: `Common.h` の `Immediate`
- 標準依存: `<cstring>`, `<iostream>`, `<cassert>`
- 外部依存: 実装には第三者ライブラリなし。テストのみGoogleTest
- 注意点: 4 MiBの配列を公開し、word/shortアクセスにchar配列上のポインタキャストを使う。endianness、alignment、strict aliasingの影響を受ける。アドレス検査はアクセス開始位置だけを確認し、multi-byteアクセス終端は確認しない。

### Parser

- メソッド: 文字列版`parse_hex`、バイト形式`parse`、word形式のストリーム版`parse_hex`
- 内部依存: `Memory`
- 標準依存: stream、string、stringstream、`strtol`
- 外部依存: 実装には第三者ライブラリなし。テストのみGoogleTest
- 注意点: 空行でも`line[0]`を読む経路、無効なstreamで処理を継続する経路、`strtol`エラー・overflowは未処理。word配置はMemoryのbyte orderを継承する。

### Instruction

- 型: `Instruction` alias、`InstructionBase`、`InstructionR/I/S/B/U/J`
- メソッド: base constructor 2件、`nop`、`is_nop`、bit helper 3件、validity helper 2件、`debug`、operand helper 2件、派生constructor 6件
- 内部依存: `Common.h` の`Immediate`
- 標準依存: string、iostream、utility
- 外部依存: 実装には第三者ライブラリなし。テストのみGoogleTest
- 注意点: public fieldとenum値が他モジュールの契約である。デフォルトconstructorは`InstructionBase::t`を初期化しない。

### Register

- 型: `template<typename T> Register`
- メソッド: constructor 2件、`read`、`current`、`write`、`tick`、`stall`、変換演算子、代入演算子
- 内部・外部依存: C++言語機能以外なし。テストのみGoogleTest
- 注意点: `prev`、`next`、`_stall`がpublicであり、他モジュールが直接操作する。再生成時はこの公開状態とtick semanticsの保持が必要。

### RegisterFile

- 型・メソッド: `RegisterFile`、constructor、`tick`、`read`、`write`、`debug`
- 内部依存: `Common.h`、`Register.hpp`、`utils.h`
- 標準依存: iostream、iomanip、vector、およびCメモリ・書式関数
- 外部依存: 実装には第三者ライブラリなし。テストのみGoogleTest
- 注意点: IDの範囲検査はない。x0へのwriteは`next[0]`へ格納されるが、`read(0)`だけが0を強制する。`prev`と`next`はpublic。

### Session

- 型・メソッド: `Session`、nested `Stat`、constructor/destructor、`tick`、`load_memory` 2 overload、`load_hex`、`debug`、`report`
- 内部依存: `Memory`、`RegisterFile`、`Parser`、`Issue`、`OoOExecute`、`BranchPrediction`
- 標準依存: file/stream出力。`thread`、`random`、`functional`はincludeされるが未使用
- 外部依存: 実装には第三者ライブラリなし。テストのみGoogleTest
- 注意点: ownershipをraw pointerで管理し、pipeline全体へ強く結合する。構築以外の既存テストがない。

## ミューテーション実行結果

全18件で変更後ビルドに成功したため、`compile_killed=0` である。

| 対象 | ID | 変更 | 分類 | 失敗した既存テスト／未検証機能 |
|---|---|---|---|---|
| Memory | M01 | `read_word`を常に0 | test_killed | `Memory.StoreWord` |
| Memory | M02 | `write_ushort`をno-op | test_killed | `Memory.StoreShort` |
| Memory | M03 | 上限判定を`<`から`<=` | survived | `MEMORY_SIZE`ちょうどの範囲外境界 |
| Parser | P01 | 文字列版`parse_hex`を常に0 | test_killed | `Parser.Hex`, `Parser.Parse`, `Parser.ParseHex` |
| Parser | P02 | byte格納先のincrementを除去 | test_killed | `Parser.Parse` |
| Parser | P03 | word格納後の`+4`を除去 | survived | 2個以上のword入力 |
| Instruction | I01 | `get_digits`を常に0 | test_killed | R/I/S/B/U/J constructorテスト |
| Instruction | I02 | `expand_digit`を常に0 | test_killed | I/S/B/J constructorテスト |
| Instruction | I03 | `nop()`が通常default instanceを返す | survived | nop sentinelと`is_nop` |
| Register | R01 | `tick`からstall条件を除去 | test_killed | `Register.ReadWrite`, `Register.ReadWriteOperator` |
| Register | R02 | `write`をno-op | test_killed | 同上 |
| Register | R03 | `current`が`prev`を返す | survived | next-stateの直接観測 |
| RegisterFile | RF01 | `tick`をno-op | test_killed | `RegisterFile.ReadWrite` |
| RegisterFile | RF02 | `read`を常に0 | test_killed | `RegisterFile.ReadWrite` |
| RegisterFile | RF03 | ID 2以上へのwriteを無視 | survived | レジスタ2～31 |
| Session | S01 | `tick`全体をno-op | survived | cycle、issue、execute、register commit |
| Session | S02 | stream版`load_memory`をno-op | survived | stream入力 |
| Session | S03 | `load_hex`をno-op | survived | hexファイル入力 |

集計は以下のとおり。

| 対象 | attempted | build成功 | compile_killed | test_killed | survived | execution_error | テスト検出率 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Memory | 3 | 3 | 0 | 2 | 1 | 0 | 2/3 = 66.7% |
| Parser | 3 | 3 | 0 | 2 | 1 | 0 | 2/3 = 66.7% |
| Instruction | 3 | 3 | 0 | 2 | 1 | 0 | 2/3 = 66.7% |
| Register | 3 | 3 | 0 | 2 | 1 | 0 | 2/3 = 66.7% |
| RegisterFile | 3 | 3 | 0 | 2 | 1 | 0 | 2/3 = 66.7% |
| Session | 3 | 3 | 0 | 0 | 3 | 0 | 0/3 = 0.0% |

この値は網羅的mutation scoreではなく、候補選定用の代表的感度である。

## テストが確認している機能

- Memory: word/shortの基本read-after-write、`operator[]`による3 byte、ホストのsigned-char変換
- Parser: 00～FFの大文字16進変換、`@address`を含むbyte入力、空白区切り、単一wordのlittle-endian配置
- Instruction: `Instruction`が4 byteであること、固定bit patternに対するR/I/S/B/U/Jの主要fieldとnegative immediate
- Register: staged write、tick commit、stall保持、代入・変換演算子
- RegisterFile: x0 readが0、x1のwrite/tick/read
- Session: constructorとdestructorが通常経路で完了することだけ

## テストが確認していない機能

- Memory: 無効アドレス、上限境界、終端付近multi-byteアクセス、debug、invalid access時のplaceholder参照
- Parser: 複数word、空行・不正token・overflow・無効stream、lowercaseやprefixの仕様
- Instruction: nop、validity/exception、operand helper、debug、default state、多様なencoding、R形式`funct7`の個別正当性
- Register: `current()`、value constructor、unsigned以外のtemplate型、public stateの直接操作
- RegisterFile: ID 2～31、範囲外ID、debug、x0の内部next状態
- Session: tick、load、report、debug、pipeline coordination、file error、全シミュレーション結果

## データセット候補としての長所と問題点

### 長所

- 5対象が小規模なheader-only実装で、公開インターフェースを固定した実装置換が容易
- 全テストが短時間で実行でき、3回反復で結果が安定
- Instructionは6命令形式を個別に検証し、主要bit extractionとsign extensionの破壊を検出
- Registerは少ないテストながらwrite/tick/stall/operatorの中心的な状態遷移を検証

### 問題点

- すべての対象で少なくとも1件の主要変更が生存し、Sessionは感度が0%
- Memory/Parserにはホストbyte orderやraw pointer castに関する移植性条件がある
- header-only型は他モジュールへ広く展開される一方、対象別テストはproduction利用方法の一部しか覆わない
- RegisterFileは32 entry中、実質x0とx1だけを検証
- Sessionは強結合で置換範囲が大きいのに、既存テストはlifetime smoke testだけ

## 実行上の失敗・補正

結果を隠さないため、評価制御上の問題も記録する。

1. Windows側の再帰削除コマンドは安全ポリシーにより実行前に拒否された。対象を固定したDocker内の `/workspace/repos/RISCV-Simulator/build` 削除へ切り替え、元ファイルは削除していない。
2. 最初のtest discovery集計はPowerShell正規表現の過剰escapeと混在encodingにより0件と誤集計した。最初のログを保持し、GoogleTest列挙を再実行して18件を取得した。宣言数とも一致した。
3. M01の最初の補助実行はGitのCRLF警告をPowerShell例外として扱い、ビルド前に停止した。同じミューテーション状態のまま補助処理を修正し、ビルド・テストを有効に再実行した。
4. `apply_patch`で触れたhunkだけがLFになるため、最初のM01復元ハッシュ確認が失敗した。固定コミットの対象ファイルが全てCRLFであることと期待hashを確認し、以後は逆パッチ後にCRLFへ機械正規化してからhash・diffを検証した。
5. 成果物manifestの最終再生成時に`Get-FileHash`へ無効な位置引数を渡し、一度空のmanifestを生成した。評価結果には影響しておらず、明示的な`-Algorithm`と`-LiteralPath`で再生成し、210行すべてのhashが非空であることを確認した。

これらは最終ミューテーション分類の `execution_error` にはしていない。いずれも有効なビルド・テスト判定前の制御上の問題であり、補正後に同一変更を再評価できたためである。詳細は `command_control_errors.log` と関連ログに保存した。予定した18変更はすべて実装と一致し、機能目的を変える代替ミューテーションへの調整はなかった。

## 最終復元確認

- 最終全ビルド: 成功
- 最終CTest: 1/1成功
- 最終全GoogleTest: 18/18成功
- 最終対象別GoogleTest: 全6 suite成功
- `git rev-parse HEAD`: `8989a09c357a69b68612f653380d60816f5176c2`
- `git diff`: 出力なし
- `git status --short --untracked-files=no`: 出力なし
- `git status --short`: `?? build/`
- `build/`以外の未追跡ファイル: なし

既存のMemory関連ログは削除・上書きしていない。

## 人間が最終判断すべき事項

1. 66.7%という代表感度と各survivorを、研究データセットの合格基準として許容するか。
2. Memory/Parserのendianness・alignment・aliasing条件を設計書へ明示すれば採用可能とするか。
3. Instructionのnop/helper、Registerの`current()`、RegisterFileのID 2～31を既存テストが検証しない状態で、round-tripの同等性評価として十分か。
4. Sessionを除外するか、別の既存integration testが発見できる場合だけ再評価するか。
5. 公開配列・fieldを含むABI／layoutまで再生成対象の設計契約に含めるか。
