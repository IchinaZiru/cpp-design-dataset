# ラウンドトリップ実験 総合レポート

- target: `log`
- target_id: `echo-web-server-log`
- run_id: `echo-web-server-log-qwen25coder32b-001`
- repository: `Echo-Web-Server`
- granularity: `module_files`
- model: `qwen2.5-coder:32b`
- overall: **FAIL**
- failure_category: `code_regeneration_output_truncation`

## パイプライン結果

| stage | result | detail |
|---|---|---|
| design_generation | PASS | 設計文書を生成（done_reason=stop，eval_count=2478） |
| code_regeneration | FAIL | 出力上限8192トークンに到達して生成が途中終了（done_reason=length） |
| output_parsing | FAIL | 打ち切られた応答が未完了のJSONとなり解析失敗（line=21，column=18） |
| configure | SKIPPED | 再生成ファイルを抽出できなかったため未実行 |
| build | SKIPPED | 再生成ファイルを抽出できなかったため未実行 |
| direct_test | SKIPPED | 再生成ファイルを抽出できなかったため未実行 |
| full_test | SKIPPED | 再生成ファイルを抽出できなかったため未実行 |

## 判定

設計文書の生成には成功したが，コード再生成では設定した出力上限である
8192トークンに到達し，応答が途中で終了した．その結果，要求されたJSONが
完結せず，生成ファイルを抽出できなかった．生成1回，再試行なし，
自動修復なしの実験条件に従い，出力打ち切りによるFAILとして記録した．

元ソースへの置換は実施されておらず，対象7ファイルのハッシュはバックアップと
一致している．また，対象リポジトリはcleanな状態である．

## 今後の追加分析

本実験のFAILは，`num_predict=8192`の上限到達による
コード再生成出力の途中終了である．したがって，この結果だけでは，
設計文書からログモジュールを再構成する能力が不足していたのか，
単に出力可能なトークン数が不足していたのかを分離できない．

全対象の主実験完了後，`num_predict=16384`へ拡大した追加実験を，
主実験とは異なるrun_idで1回実施する予定である．
追加実験は感度分析として扱い，本主実験のFAILを上書きしない．
