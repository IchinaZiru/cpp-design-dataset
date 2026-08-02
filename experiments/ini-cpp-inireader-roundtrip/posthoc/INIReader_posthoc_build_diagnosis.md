# INIReader再生成コードの事後ビルド診断

## 1．位置付け

本記録は，`ini-cpp-inireader`に対する主実験終了後に実施した補足的な事後診断である．

主実験では，再生成されたクラス定義にMarkdownコードフェンスが含まれていたため，`regenerate_code`段階の形式検証で停止した．そのため，主実験中にはソースコードの置換，ビルドおよびテストを実行していない．

本診断では，保存済みの再生成出力から最外部のMarkdownコードフェンスのみを除去し，一時的に`INIReader`クラスを置換してビルド可否を確認した．LLMへの再問い合わせ，再生成，コード内容の修正および自動修復は行っていない．

## 2．主実験結果

| 項目 | 結果 |
|---|---|
| 設計文書生成 | 正常終了 |
| コード再生成API応答 | 正常終了 |
| コード生成終了理由 | `stop` |
| 形式検証 | FAIL |
| 失敗段階 | `regenerate_code` |
| 直接原因 | 再生成出力にMarkdownコードフェンスが含まれていた |
| 再試行 | なし |
| 自動修復 | なし |
| ソース置換 | 未実行 |
| ビルド | 未実行 |
| テスト | 未実行 |

主実験の正式な判定は`FAIL_PIPELINE`のままであり，本事後診断の結果によって変更しない．

## 3．事後診断の操作

再生成出力の先頭にある外側の` ```cpp `と，出力末尾にある外側の` ``` `のみを除去した．クラス内部のDoxygenコメントに含まれるコードフェンスは，C++のコメント内にあるため除去していない．

その後，生成された`INIReader`クラスを一時的に`repos/ini-cpp/ini/ini.h`へ置換し，正式実験と同じDockerイメージを使用してconfigureおよびbuildを実行した．

## 4．事後診断結果

| 段階 | 結果 |
|---|---|
| configure | PASS（exit code 0） |
| build | FAIL（exit code 2） |
| 直接テスト | 未実行 |
| 全体テスト | 未実行 |
| ソース復元 | 成功 |

復元前後のSHA-256は次のとおりであり，一致した．

```text
original_sha256 : 30dfffabdda27182ddf2351193c9224b533b42349e9186a4cecf40f781b0c7f1
restored_sha256 : 30dfffabdda27182ddf2351193c9224b533b42349e9186a4cecf40f781b0c7f1
restored         : True
```

## 5．確認されたコンパイルエラー

### 5.1 `std::string_view`の誤用

ファイルストリームの入力イテレータ2つを，`std::string_view`のコンストラクタへ渡していた．

```cpp
Parse(std::string_view(
    std::istreambuf_iterator<char>(file),
    std::istreambuf_iterator<char>()
));
```

`std::string_view`は文字列を所有する型ではなく，入力イテレータの範囲から文字列を構築することはできない．一度`std::string`へ読み込む必要がある．

### 5.2 `FILE*`とC++ストリームAPIの混同

`FILE*`を`std::istreambuf_iterator<char>`のコンストラクタへ渡していた．

```cpp
std::istreambuf_iterator<char>(file)
```

`std::istreambuf_iterator`は`std::istream`または`std::streambuf`を受け取るため，C標準ライブラリの`FILE*`とは互換性がない．

### 5.3 `const`不整合

`const`メンバ関数から変更可能な`std::string&`を返そうとしていた．

```cpp
std::string& FindEntry(
    const std::string& section,
    const std::string& name
) const;
```

`const`メンバ関数から取得される要素は`const`として扱われるため，非`const`参照として返すことはできない．

### 5.4 Most Vexing Parse

次の記述が，変数初期化ではなく関数宣言として解釈された．

```cpp
std::istringstream iss(std::string(content));
```

このため，後続の`std::getline(iss, line)`にストリームオブジェクトを渡すことができなかった．

## 6．考察

今回の主実験は，Markdownコードフェンスを含む出力形式違反によって，ビルド前に停止した．しかし，事後的に最外部のコードフェンスのみを除去しても，生成コードには複数のコンパイルエラーが残っており，ビルドは成功しなかった．

したがって，本対象は「形式上のコードフェンスだけを削除すれば成功する生成結果」ではない．出力形式の問題に加えて，C++の型，ストリーム処理，const correctnessおよび構文解釈に関する実装上の誤りが含まれていた．

なお，これらの誤りを人手で修正した場合のビルド・テスト結果は，本診断では評価していない．

## 7．証拠ファイル

主実験の記録：

```text
experiments/ini-cpp-inireader-roundtrip/evaluation/pipeline_failure.json
experiments/ini-cpp-inireader-roundtrip/raw_output/code_regeneration_response.json
experiments/ini-cpp-inireader-roundtrip/raw_output/code_regeneration_metadata.json
```

事後診断のローカルログ：

```text
logs/posthoc/ini-cpp-inireader-fence-strip-build/build.stdout.txt
logs/posthoc/ini-cpp-inireader-fence-strip-build/build.stderr.txt
logs/posthoc/ini-cpp-inireader-fence-strip-build/generated_class_without_fences.cpp
```

ローカルログは詳細確認用であり，主実験の正式な評価結果は`evaluation/pipeline_failure.json`に保存されている．
