以下は、与えられたC++ソースコードを基にした詳細な設計仕様書です。この仕様書は、別のLLMが再実装できるように作成されています。

---

# 設計仕様書: IPアドレスクラス

## 概要
この仕様書は、IPv4およびIPv6アドレスを扱うためのC++クラスライブラリの設計を記述します。このライブラリは、ネットワークプログラミングにおいてIPアドレスを扱うための抽象化と具体的な実装を提供します。

## 1. クラス構造

### 1.1 IPAddr (抽象基底クラス)
- **役割**: IPv4およびIPv6アドレスの共通インターフェースを定義する。
- **メソッド**:
  - `virtual ~IPAddr() noexcept = default;`: デストラクタ（仮想関数）。
  - `virtual int Version() const noexcept = 0;`: IPバージョンを返す（4または6）。
  - `virtual std::size_t Size() const noexcept = 0;`: ソケットアドレス構造体のサイズを返す。
  - `virtual const sockaddr* Raw() const noexcept = 0;`: 生のソケットアドレス構造体へのポインタを返す。
  - `virtual std::uint16_t Port() const noexcept = 0;`: ポート番号を返す（ネットワークバイトオーダーからホストバイトオーダーに変換）。
  - `virtual std::string IPAddress() const noexcept = 0;`: IPアドレス文字列を返す。

### 1.2 IPv4Addr (IPv4アドレスクラス)
- **役割**: IPv4アドレスの具体的な実装。
- **静的メンバー**:
  - `version {AF_INET}`: AF_INET（通常は2）。
  - `loop_back {"127.0.0.1"}`: Loopbackアドレス。
  - `any {"0.0.0.0"}`: Anyアドレス。
  - `max_length {15}`: IPv4アドレス文字列の最大長（例: "255.255.255.255"）。
- **型エイリアス**:
  - `RawType = sockaddr_in`: 生のソケットアドレス構造体。
- **コンストラクタ**:
  - `explicit IPv4Addr(sockaddr_in addr)`: sockaddr_inから初期化。
  - `explicit IPv4Addr(std::string ip, std::uint16_t port)`: IP文字列とポート番号から初期化。
- **メソッド**:
  - `Version()`: AF_INETを返す。
  - `Size()`: sizeof(sockaddr_in)を返す。
  - `Raw()`: reinterpret_cast<const sockaddr*>(&raw_)を返す。
  - `Port()`: ntohs(raw_.sin_port)を返す。
  - `IPAddress()`: ip_を返す。
- **メンバー変数**:
  - `ip_`: IPアドレス文字列（std::string）。
  - `raw_`: sockaddr_in構造体。

### 1.3 IPv6Addr (IPv6アドレスクラス)
- **役割**: IPv6アドレスの具体的な実装。
- **静的メンバー**:
  - `version {AF_INET6}`: AF_INET6（通常は10）。
  - `loop_back {"::1"}`: Loopbackアドレス。
  - `any {"::"}`: Anyアドレス。
  - `max_length {45}`: IPv6アドレス文字列の最大長（例: "ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff"）。
- **型エイリアス**:
  - `RawType = sockaddr_in6`: 生のソケットアドレス構造体。
- **コンストラクタ**:
  - `explicit IPv6Addr(sockaddr_in6 addr)`: sockaddr_in6から初期化。
  - `explicit IPv6Addr(std::string ip, std::uint16_t port)`: IP文字列とポート番号から初期化。
- **メソッド**:
  - `Version()`: AF_INET6を返す。
  - `Size()`: sizeof(sockaddr_in6)を返す。
  - `Raw()`: reinterpret_cast<const sockaddr*>(&raw_)を返す。
  - `Port()`: ntohs(raw_.sin6_port)を返す。
  - `IPAddress()`: ip_を返す。
- **メンバー変数**:
  - `ip_`: IPアドレス文字列（std::string）。
  - `raw_`: sockaddr_in6構造体。

### 1.4 ValidIPAddr (コンセプト)
- **役割**: IPv4AddrまたはIPv6Addrであることをチェックする。
- **定義**:
  ```cpp
  template <typename T>
  concept ValidIPAddr = std::same_as<T, IPv4Addr> || std::same_as<T, IPv6Addr>;
  ```

## 2. 実装詳細

### 2.1 コンストラクタの動作
- **sockaddr_in/sockaddr_in6からの初期化**:
  - `inet_ntop`を使用してIPアドレス文字列に変換し、エラーが発生した場合は`ThrowLastSystemError()`を呼び出す。
- **IP文字列とポート番号からの初期化**:
  - `raw_.sin_family`または`raw_.sin6_family`を設定する。
  - `raw_.sin_port`または`raw_.sin6_port`を`htons(port)`で設定する。
  - `inet_pton`を使用してIP文字列をソケットアドレス構造体に変換し、エラーが発生した場合は`ThrowLastSystemError()`を呼び出す。

### 2.2 メソッドの動作
- **Version()**: 静的メンバー`version`を返す。
- **Size()**: `sizeof(raw_)`を返す。
- **Raw()**: `reinterpret_cast<const sockaddr*>(&raw_)`を返す。
- **Port()**: `ntohs(raw_.sin_port)`または`ntohs(raw_.sin6_port)`を返す。
- **IPAddress()**: `ip_`を返す。

## 3. エラー処理
- `inet_ntop`および`inet_pton`のエラーは、`ThrowLastSystemError()`によって処理される。この関数は、システムエラーをスローすることを想定しているが、具体的な実装は別のモジュール（`util.h`）に委ねられる。

## 4. ネームスペース
- すべてのクラスおよびコンセプトは、`ws`ネームスペース内に配置される。

## 5. 依存関係
- **ヘッダ**:
  - `<concepts>`: コンセプトを使用するため。
  - `<cstdint>`: `std::uint16_t`を使用するため。
  - `<string>`: `std::string`を使用するため。
  - `<string_view>`: 静的メンバーに使用される。
  - `<netinet/in.h>`: `sockaddr_in`および`sockaddr_in6`を使用するため。
- **ソース**:
  - `util.h`: `ThrowLastSystemError()`を提供するため。
  - `<arpa/inet.h>`: `inet_ntop`および`inet_pton`を使用するため。

## 6. 注意事項
- **名前の保持**: Fxx/Uxx識別子は、再実装においても同じ名前で使用される必要がある。
- **型とシグネチャ**: 型および関数シグネチャは、再実装においても同じものを使用する必要がある。
- **置換境界**: 置換が必要なユニット（F01/U01およびF02/U02）のみが再実装される。

---

この仕様書に従って、別のLLMは与えられたC++ソースコードを再実装することができます。