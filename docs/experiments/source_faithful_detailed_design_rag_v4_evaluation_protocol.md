# Source-faithful Detailed-design RAG v4 Evaluation Protocol

## 位置付け

v4は、v3正式結果とその失敗分析を見た後に設計したpost-hoc refinementである。
したがって、v4をv3とは独立なconfirmatory formal experimentとは扱わない。
v3 formal 34 runsおよび旧固定non-RAG main studyは変更・再実行・再分類しない。

目的は、v3で確認された「設計書は詳細化したが、再実装に必要な正確な実装事実が十分に保持されない」「Markdown見出し階層違反だけでコード再生成へ進めない」という問題を一般的なルールで改善し、同じ17対象でpost-hocに再生成成功率を確認することである。

## v4 treatment

condition: `full_source_source_faithful_detailed_design_rag_v4`

設計文書生成時に、v3と同じfull-source observation scopeへ `knowledge/detailed-design/general-v4.md` を追加する。

v4で重視する内容は次の5群である。

1. 正確な定義: type alias / enum / concept / constant / nested type
2. 直接依存インターフェースと実際の利用方法
3. 条件・bit・byte・index・offset・literal等の結果決定情報
4. 使用データ・更新データ
5. 状態・副作用・ownership・lifetime・同期不変条件

ソース全文コピーは要求しない。表、短い式、疑似コード、図、自然言語へ変換しつつ、再実装結果に影響する事実は抽象化で失わない。

## 見出し・形式ポリシー

基本9項目と詳細7項目の内容は要求するが、Markdownの見出しlevel、順序、追加見出しの有無はterminal failure条件にしない。

- `# 責務` / `## 責務` / `### 責務` の差だけで停止しない。
- 順序違いだけで停止しない。
- 追加見出しがあっても停止しない。
- named sectionの欠落やMermaid欠落はadvisory warningとして保存する。
- validatorは生成設計書を自動修正しない。
- validatorは設計書本文を一文字も書き換えない。

設計文書そのものが取得できない、LLM generationが正常終了しない等の場合のみdesign-generation failureとする。

## 実行条件

v3と同じ17 target inventoryを使用し、v4 treatmentだけを新しいrun/experiment IDで1回ずつ実行する。
比較の参考には凍結済みv3 non-RAG 17 runsを使用するが、v4はpost-hoc refinementなのでMcNemar等をconfirmatory primary testとして扱わない。

固定条件:

- model: `qwen2.5-coder:32b`
- temperature: 0
- seed: 42
- num_ctx: 32768
- num_predict: 16384
- generations per stage: 1
- retry: false
- automatic repair: false
- generated-code manual edit: false
- original source in code regeneration: false
- retrieved/design knowledge in code regeneration: false

コード再生成時の入力はv3と同じくgenerated design document + fixed scaffold + dependency/include contextのみとする。

## pilot方針

LLMを用いた反復pilotは実施しない。
formal対象外pilot結果でpromptを繰り返し調整する代わりに、実行前は機械的preflightのみ行う。

機械的preflightで確認する:

- config 17件がすべてdisabledで生成される
- run/experiment IDがv2/v3と重複しない
- knowledge pathが存在する
- model/context/generation count/retry/repairが固定値である
- output pathが未使用である
- v3 artifactを参照のみとし上書きしない

## batch方針

17件を1回ずつ直列実行する。
個別runがpipeline failureになっても、そのrunを保存した上で次targetへ進む。
同じrun IDのretry、repair、手修正は行わない。

最終的に17件すべてについて、design generation、code regeneration、configure、build、direct test、full testの到達状態を保存する。

## 解釈

v4の主要な問いは「post-hocに導入したsource-fidelity規則で、設計文書の実装情報保持とdownstream PASSが改善するか」である。

v4の結果が良くても、v3正式対象を見て設計した改善なので独立な一般化性能の証明とはしない。
必要なら将来、別repository/hold-out targetで独立検証する。
