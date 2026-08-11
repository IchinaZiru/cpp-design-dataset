# 設計仕様書

## 1. 概要
この設計仕様書は、`INIWriter` クラスの再実装を目的としています。元のソースコードから得られる情報に基づき、クラスの機能とインターフェースを詳細に定義します。

## 2. 対象範囲
- **ファイルパス**: `ini/ini.h`
- **役割**: INIWriter クラスの完全な定義
- **再実装対象**: `replacement_required=true` のユニットのみ

## 3. 命名規則と識別子
- **Fxx/Uxx 識別子**: 不透明であり、その名前、型、シグネチャ、名前空間、置換境界は保持される。
- **再実装対象ユニット**: `F01/U01`
- **参照のみの入力**: なし

## 4. クラス定義: INIWriter
### 4.1 概要
`INIWriter` クラスは、INIファイルを書き出すための機能を提供します。このクラスは `INIReader` オブジェクトからデータを取り出し、指定されたファイルパスにINI形式で保存します。

### 4.2 コンストラクタ
- **シグネチャ**: `INIWriter() = default;`
- **説明**: デフォルトコンストラクタ。特に初期化処理は必要としない。

### 4.3 静的メソッド: write
- **シグネチャ**: 
  ```cpp
  inline static void write(const std::string& filepath,
                          const INIReader& reader,
                          const bool overwrite = false);
  ```
- **パラメータ**:
  - `filepath`: 書き出すINIファイルのパスを指定する文字列。
  - `reader`: データを提供する `INIReader` オブジェクト。
  - `overwrite`: 既存のファイルを上書きするかどうかを示す論理値。デフォルトは `false`。
- **例外処理**:
  - 指定されたファイルパスにファイルが存在し、かつ `overwrite=false` の場合、`std::runtime_error` をスローします。
  - ファイルを開くことができない場合、`std::runtime_error` をスローします。
- **機能詳細**:
  1. `overwrite` パラメータが `false` で、指定されたファイルパスにファイルが存在する場合は例外をスローします。
  2. 指定されたファイルパスにファイルを開きます。開くことができない場合は例外をスローします。
  3. `INIReader` オブジェクトからセクション名のリストを取得し、各セクションに対して以下の処理を行います:
     - セクション名をファイルに出力します（例: `[section]`）。
     - 各セクション内のキー名のリストを取得し、各キーに対して以下の処理を行います:
       - キーと値を `key=value` の形式でファイルに出力します。

## 5. 注意事項
- **Fxx/Uxx 識別子**: 不透明な識別子であるため、名前や型、シグネチャは変更しないこと。
- **参照のみの入力**: このドキュメントでは参照のみの入力が存在しないため、特に考慮する必要はありません。

## 6. 付録
### 6.1 クラス定義全体
```cpp
class INIWriter {
   public:
    INIWriter() = default;

    inline static void write(const std::string& filepath,
                             const INIReader& reader,
                             const bool overwrite = false) {
        if (!overwrite && std::ifstream{filepath}) {
            throw std::runtime_error("file: " + filepath + " already exists.");
        }
        std::ofstream out{filepath};
        if (!out.is_open()) {
            throw std::runtime_error("cannot open output file: " + filepath);
        }
        for (const auto& section : reader.Sections()) {
            out << "[" << section << "]\n";
            for (const auto& key : reader.Keys(section)) {
                out << key << "=" << reader.Get(section, key) << "\n";
            }
        }
    }
};
```

この仕様書に基づき、`INIWriter` クラスを再実装することが可能です。