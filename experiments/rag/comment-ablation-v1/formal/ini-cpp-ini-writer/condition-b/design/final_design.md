# 詳細設計仕様書

## 1. クラス図

```mermaid
classDiagram
    class INIWriter {
        +INIWriter()
        +static void write(filepath: string, reader: INIReader, overwrite: bool)
    }
```

## 2. クラス・メソッド・インターフェース詳細

| 完全な名前 | 属性     | 引数名と型                         | 戻り値型   | 可視性 | const | 参照/ポインタ | static | virtual | noexcept |
|------------|----------|------------------------------------|------------|--------|-------|---------------|--------|---------|----------|
| INIWriter  | コンストラクタ | -                                | void       | public | false | -             | true   | false   | false    |
| write      | メソッド   | filepath: string, reader: INIReader, overwrite: bool | void       | public | false | -             | true   | false   | false    |

## 3. シーケンス図

```mermaid
sequenceDiagram
    participant Caller
    participant INIWriter
    participant ifstream
    participant ofstream
    participant reader

    Caller->>INIWriter: write(filepath, reader, overwrite)
    alt overwrite is false
        INIWriter->>ifstream: ifstream{filepath}
        ifstream-->>INIWriter: exists?
        alt file exists
            INIWriter-->>Caller: throw runtime_error
        else file does not exist
            INIWriter->>ofstream: ofstream{filepath}
            ofstream-->>INIWriter: is_open?
            alt file opened
                INIWriter->>reader: Sections()
                reader-->>INIWriter: sections
                loop for each section in sections
                    INIWriter->>ofstream: << "[" + section + "]\n"
                    INIWriter->>reader: Keys(section)
                    reader-->>INIWriter: keys
                    loop for each key in keys
                        INIWriter->>reader: Get(section, key)
                        reader-->>INIWriter: value
                        INIWriter->>ofstream: << key + "=" + value + "\n"
                end
            else file not opened
                INIWriter-->>Caller: throw runtime_error
            end
        end
    else overwrite is true
        INIWriter->>ofstream: ofstream{filepath}
        ofstream-->>INIWriter: is_open?
        alt file opened
            INIWriter->>reader: Sections()
            reader-->>INIWriter: sections
            loop for each section in sections
                INIWriter->>ofstream: << "[" + section + "]\n"
                INIWriter->>reader: Keys(section)
                reader-->>INIWriter: keys
                loop for each key in keys
                    INIWriter->>reader: Get(section, key)
                    reader-->>INIWriter: value
                    INIWriter->>ofstream: << key + "=" + value + "\n"
                end
            end
        else file not opened
            INIWriter-->>Caller: throw runtime_error
        end
    end
```

## 4. メソッド仕様書

### write

#### 目的
INIファイルにデータを書き込む。

#### 引数
- `filepath`: 書き込み先のファイルパス (std::string)
- `reader`: INIデータを保持しているオブジェクト (INIReader&)
- `overwrite`: 既存ファイルを上書きするかどうか (bool, デフォルト: false)

#### 戻り値
なし

#### 動作
1. `overwrite`がfalseの場合、指定されたファイルパスにファイルが存在するか確認する。
2. 存在する場合、例外をスローする。
3. 存在しない場合、または`overwrite`がtrueの場合、ファイルを開く。
4. ファイルを開けない場合は例外をスローする。
5. `reader`からセクション名を取得し、各セクションに対して以下の処理を行う:
   - セクション名をファイルに書き込む。
   - セクション内のキー名を取得し、各キーに対して以下の処理を行う:
     - キーと値をファイルに書き込む。

#### 副作用
- ファイルの作成または上書き

#### エラー処理
- 指定されたファイルパスにファイルが存在する場合: `std::runtime_error`
- ファイルを開けない場合: `std::runtime_error`

## 5. 処理フロー図

```mermaid
graph TD
    A[開始] --> B{overwrite?}
    B -- true --> C[ファイルを開く]
    B -- false --> D[ファイルが存在するか確認]
    D -- 存在する --> E[例外スロー: ファイル既存]
    D -- 不存在する --> C
    C --> F{ファイル開けた?}
    F -- 開けた --> G[セクション取得]
    F -- 開けなかった --> H[例外スロー: ファイルオープン失敗]
    G --> I[セクションループ開始]
    I --> J[キー取得]
    J --> K[キー値書き込み]
    K --> L{次のキー?}
    L -- あり --> J
    L -- 無い --> M{次のセクション?}
    M -- あり --> I
    M -- 無い --> N[終了]
    E --> N
    H --> N
```

## 6. 状態遷移・副作用

| 更新前状態 | 遷移条件         | 変更対象   | 更新後状態 | 更新順序 | 副作用               |
|------------|------------------|------------|------------|----------|----------------------|
| -          | overwrite=true   | ファイル     | 上書き     | 1        | ファイルの上書き       |
| -          | overwrite=false  | ファイル     | 新規作成   | 2        | ファイルの新規作成     |
| -          | ファイル存在     | -          | -          | 3        | 例外スロー: ファイル既存 |
| -          | ファイル開けた   | ファイル     | 書き込み中 | 4        | ファイルへの書き込み   |

## 7. データ変換・制約

| 入力データ       | 出力データ       | 変換規則                     |
|------------------|------------------|------------------------------|
| filepath         | -                | ファイルパス文字列           |
| reader.Sections()| -                | セクション名のリスト         |
| reader.Keys(section)| -             | キー名のリスト               |
| reader.Get(section, key)| -          | キーに対応する値           |

## 8. 追加詳細設計情報

- **ファイルパス**: `std::string`型で指定される。
- **INIReaderクラス**: `Sections()`メソッドと`Keys(section)`メソッド、および`Get(section, key)`メソッドを提供している。
- **例外処理**: ファイルが既存である場合やファイルを開けない場合に`std::runtime_error`をスローする。

この設計仕様書は、与えられたC++ソースコードの詳細な情報をもとに作られ、別のLLMが再実装できるように設計されています。