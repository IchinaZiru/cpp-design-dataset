# 対象
- target: RegisterFile
- granularity: target_span
- target_kind: class
- target_symbol: RegisterFile

# 対象範囲
元コード全体は対象部分を理解するための文脈として参照してください。
設計文書はtarget_symbolで指定した対象部分だけについて作成してください。
対象外の関数やクラスは、対象部分との関係を説明する場合に限って記載してください。

# 基本設計項目の出力構成（全条件共通・固定）

## 責務
RegisterFileクラスはRISC-Vシミュレータにおいてレジスタファイルを管理します。32個のレジスタを保持し、各レジスタへの読み書き操作を行います。

## 公開インターフェース
- `Immediate read(int id)`: 指定されたIDのレジスタ値を読み取ります。
- `void write(int id, Immediate val)`: 指定されたIDのレジスタに値を書き込みます。
- `void tick()`: レジスタファイルの状態を更新します。`next`配列の内容を`prev`配列にコピーします。
- `void debug()`: レジスタファイルの現在の状態をデバッグ用に出力します。

## 入力
- `read(int id)`: レジスタID (`int`)
- `write(int id, Immediate val)`: レジスタID (`int`) と書き込む値 (`Immediate`)

## 出力
- `read(int id)`: 指定されたレジスタの値 (`Immediate`)

## 状態
- `prev[REG_NUM]`: 前回のクロックサイクルでのレジスタ値を保持する配列。
- `next[REG_NUM]`: 現在のクロックサイクルでのレジスタ値を保持する配列。

## 処理手順
1. コンストラクタで`prev`と`next`配列を初期化します。
2. `write(int id, Immediate val)`メソッドが呼び出されると、指定されたIDの`next`配列に値を書き込みます。
3. `tick()`メソッドが呼び出されると、`next`配列の内容を`prev`配列にコピーします。
4. `read(int id)`メソッドが呼び出されると、指定されたIDの`prev`配列から値を読み取ります。ただし、レジスタIDが0の場合には常に0を返します。

## 例外・失敗条件
- レジスタIDが範囲外（0から31以外）である場合の動作は未定義です。
- `Immediate`型の定義や制約については元コードからは不明瞭です。

## 依存関係
- `Common.h`: シミュレータ全体で使用される共通ヘッダファイルを想定しています。
- `Register.hpp`: `Immediate`型が定義されていると推測されます。
- `utils.h`: `debug_immediate()`関数が定義されていると推測されます。

## 重要な不変条件
- レジスタID0は常に0を保持します。
- `tick()`メソッド呼び出し後、`prev`配列は直前のクロックサイクルの`next`配列の値を持ちます。