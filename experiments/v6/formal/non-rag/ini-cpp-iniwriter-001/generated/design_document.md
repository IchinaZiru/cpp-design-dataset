# 設計文書: `INIWriter::write`

## 基本設計項目

### 責務
`INIWriter::write` 関数は、与えられた `INIReader` オブジェクトの内容を指定されたファイルパスに INI 形式で書き出す責任があります。

### 公開インターフェース
- **関数名**: `write`
- **修飾子**: `inline static`
- **引数**:
  - `const std::string& filepath`: 出力ファイルのパス。
  - `const INIReader& reader`: 書き出す内容を保持している `INIReader` オブジェクト。
  - `const bool overwrite = false`: 既存ファイルを上書きするかどうかを指定するフラグ。
- **戻り値**: `void`
- **例外**:
  - `std::runtime_error`: 出力ファイルが既に存在する場合、または出力ファイルを開くことができない場合。

### 入力
- `filepath`: 書き出すファイルのパスを表す文字列。
- `reader`: INI ファイルの内容を保持している `INIReader` オブジェクト。
- `overwrite`: 既存ファイルを上書きするかどうかを指定する論理値。

### 出力
- 指定されたファイルパスに `INIReader` オブジェクトの内容が INI 形式で書き出されます。

### 状態
- `filepath`: 書き出すファイルのパス。
- `reader`: 書き出す内容を保持している `INIReader` オブジェクト。
- `overwrite`: 既存ファイルを上書きするかどうかを指定する論理値。

### 処理手順
1. `overwrite` フラグが `false` の場合、指定されたファイルパスにファイルが存在するか確認します。存在する場合は例外をスローします。
2. 指定されたファイルパスに新しいファイルを開きます。開けない場合は例外をスローします。
3. `INIReader` オブジェクトからセクション名のリストを取得し、各セクションに対して以下の処理を行います:
   - セクション名をファイルに出力します。
   - 各セクション内のキー名と値のペアを取得し、キー名と値を `key=value` 形式でファイルに出力します。

### 例外・失敗条件
- 指定されたファイルパスにファイルが既存であり、`overwrite` フラグが `false` の場合。
- 出力ファイルを開くことができない場合。

### 依存関係
- `INIReader`: INI ファイルの内容を保持しているオブジェクト。
- `std::ifstream`: ファイルの存在確認に使用される。
- `std::ofstream`: ファイルへの書き出しに使用される。

### 重要な不変条件
- 出力ファイルが既存であり、`overwrite` フラグが `false` の場合、例外をスローする。
- 出力ファイルを開くことができない場合は例外をスローする。
- 各セクションとキーのペアは `key=value` 形式で出力される。

## RAGによる追加詳細設計

### クラス図
```mermaid
classDiagram
    class INIWriter {
        +static void write(filepath: string, reader: INIReader, overwrite: bool)
    }
    
    class INIReader {
        +set Sections() const
        +set Keys(section: string) const
        +T Get~T~(section: string, name: string) const
    }

    INIWriter --> INIReader : uses
```

### クラス・メソッド・インターフェース詳細

| クラス名 | メソッド名 | 修飾子 | 引数 | 戻り値型 |
|----------|------------|--------|------|-----------|
| INIWriter | write      | inline static | const std::string& filepath, const INIReader& reader, const bool overwrite = false | void |

### シーケンス図
```mermaid
sequenceDiagram
    participant Caller
    participant INIWriter
    participant INIReader
    participant ifstream
    participant ofstream

    Caller->>INIWriter: write(filepath, reader, overwrite)
    alt overwrite is false
        INIWriter->>ifstream: ifstream(filepath)
        alt ifstream.is_open()
            ifstream-->>INIWriter: true
            INIWriter-->>Caller: throw std::runtime_error
        else !ifstream.is_open()
            ifstream-->>INIWriter: false
        end
    end
    INIWriter->>ofstream: ofstream(filepath)
    alt ofstream.is_open()
        ofstream-->>INIWriter: true
        INIWriter->>INIReader: Sections()
        INIReader-->>INIWriter: sections
        loop for each section in sections
            INIWriter->>ofstream: << "[" + section + "]\n"
            INIWriter->>INIReader: Keys(section)
            INIReader-->>INIWriter: keys
            loop for each key in keys
                INIWriter->>INIReader: Get(section, key)
                INIReader-->>INIWriter: value
                INIWriter->>ofstream: << key + "=" + value + "\n"
            end
        end
    else !ofstream.is_open()
        ofstream-->>INIWriter: false
        INIWriter-->>Caller: throw std::runtime_error
    end
```

### メソッド仕様書

#### 目的
`INIReader` オブジェクトの内容を指定されたファイルパスに INI 形式で書き出す。

#### 引数
- `filepath`: 書き出すファイルのパス。
- `reader`: INI ファイルの内容を保持している `INIReader` オブジェクト。
- `overwrite`: 既存ファイルを上書きするかどうかを指定する論理値。

#### 戻り値
なし

#### 動作
1. `overwrite` フラグが `false` の場合、指定されたファイルパスにファイルが存在するか確認します。存在する場合は例外をスローします。
2. 指定されたファイルパスに新しいファイルを開きます。開けない場合は例外をスローします。
3. `INIReader` オブジェクトからセクション名のリストを取得し、各セクションに対して以下の処理を行います:
   - セクション名をファイルに出力します。
   - 各セクション内のキー名と値のペアを取得し、キー名と値を `key=value` 形式でファイルに出力します。

#### 副作用
- 指定されたファイルパスに新しいファイルが作成される。
- 既存ファイルが上書きされる場合がある。

#### エラー処理
- 出力ファイルが既存であり、`overwrite` フラグが `false` の場合、例外をスローする。
- 出力ファイルを開くことができない場合は例外をスローする。

### 処理フロー図
```mermaid
graph TD
    A[開始] --> B{overwrite?}
    B -- false --> C{ifstream(filepath).is_open()?}
    C -- true --> D[throw std::runtime_error]
    C -- false --> E[ofstream(filepath)]
    E --> F{ofstream.is_open()?}
    F -- false --> G[throw std::runtime_error]
    F -- true --> H[sections = reader.Sections()]
    H --> I[foreach section in sections]
    I --> J[ofstream << "[" + section + "]\n"]
    J --> K[keys = reader.Keys(section)]
    K --> L[foreach key in keys]
    L --> M[value = reader.Get(section, key)]
    M --> N[ofstream << key + "=" + value + "\n"]
    N --> O[end foreach key]
    O --> P[end foreach section]
    P --> Q[終了]
```

### 状態遷移・副作用

| 更新前状態 | 遷移条件 | 変更対象 | 更新後状態 | 更新順序 | 副作用 |
|------------|----------|----------|------------|----------|--------|
| ファイルが存在しない | overwrite が false | - | - | - | - |
| ファイルが存在する | overwrite が false | - | - | - | throw std::runtime_error |
| ofstream が開けない | - | - | - | - | throw std::runtime_error |
| ofstream が開ける | - | ofstream | ofstream が開かれている状態 | - | ファイルに書き出し |

### データ変換・制約

| 入力データ | 変換規則 | 出力データ |
|------------|----------|------------|
| filepath   | 文字列としてそのまま使用 | 出力ファイルのパス |
| reader     | INIReader オブジェクトからセクションとキーを取得し、値を文字列に変換 | key=value 形式の文字列 |

- `filepath`: ファイルパスは文字列としてそのまま使用されます。
- `reader`: `INIReader` オブジェクトからセクション名とキー名を取得し、各キーの値を文字列に変換してファイルに出力します。

# Machine-extracted Source-local Implementation Contract

This appendix is deterministic evidence extracted from the target source.
It is not an LLM summary and it does not contain complete function bodies.

During regeneration:
- preserve the exact local declaration types, containers, initializers, and literals listed below;
- preserve the exact call targets and argument expressions listed below;
- do not substitute a different representation or accessor merely because it looks similar;
- treat these items as exact constraints, not as pseudocode suggestions.

## Exact local declarations

- `std::ofstream out{filepath};`

## Exact top-level call expressions

- `std::runtime_error("file: " + filepath + " already exists.")`
- `out.is_open()`
- `std::runtime_error("cannot open output file: " + filepath)`
- `reader.Sections()`
- `reader.Keys(section)`
- `reader.Get(section, key)`
