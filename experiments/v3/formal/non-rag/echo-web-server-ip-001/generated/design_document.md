## 責務
`ip.h`と`ip.cpp`は、IPv4アドレスとIPv6アドレスを表す抽象クラス`IPAddr`とその派生クラス`IPv4Addr`、`IPv6Addr`の定義と実装を提供します。これらのクラスは、IPアドレスのバージョン、ソケットアドレスのサイズ、生のソケットアドレス、ポート番号、およびIPアドレス文字列を取得する機能を提供します。

## 公開インターフェース
- `class IPAddr`
  - `virtual ~IPAddr() noexcept = default;`
  - `virtual int Version() const noexcept = 0;`
  - `virtual std::size_t Size() const noexcept = 0;`
  - `virtual const sockaddr* Raw() const noexcept = 0;`
  - `virtual std::uint16_t Port() const noexcept = 0;`
  - `virtual std::string IPAddress() const noexcept = 0;`

- `class IPv4Addr : public IPAddr`
  - `explicit IPv4Addr(sockaddr_in addr);`
  - `explicit IPv4Addr(std::string ip, std::uint16_t port);`
  - `int Version() const noexcept override;`
  - `std::size_t Size() const noexcept override;`
  - `const sockaddr* Raw() const noexcept override;`
  - `std::uint16_t Port() const noexcept override;`
  - `std::string IPAddress() const noexcept override;`

- `class IPv6Addr : public IPAddr`
  - `explicit IPv6Addr(sockaddr_in6 addr);`
  - `explicit IPv6Addr(std::string ip, std::uint16_t port);`
  - `int Version() const noexcept override;`
  - `std::size_t Size() const noexcept override;`
  - `const sockaddr* Raw() const noexcept override;`
  - `std::uint16_t Port() const noexcept override;`
  - `std::string IPAddress() const noexcept override;`

- `template <typename T> concept ValidIPAddr = std::same_as<T, IPv4Addr> || std::same_as<T, IPv6Addr>;`

## 入力
- `IPv4Addr`のコンストラクタ:
  - `sockaddr_in addr`
  - `std::string ip`, `std::uint16_t port`
  
- `IPv6Addr`のコンストラクタ:
  - `sockaddr_in6 addr`
  - `std::string ip`, `std::uint16_t port`

## 出力
- IPアドレスのバージョン (`int`)
- ソケットアドレスのサイズ (`std::size_t`)
- 生のソケットアドレス (`const sockaddr*`)
- ポート番号 (`std::uint16_t`)
- IPアドレス文字列 (`std::string`)

## 状態
- `IPv4Addr`
  - `ip_`: IPv4アドレスを表す文字列
  - `raw_`: IPv4アドレスを表す`sockaddr_in`構造体

- `IPv6Addr`
  - `ip_`: IPv6アドレスを表す文字列
  - `raw_`: IPv6アドレスを表す`sockaddr_in6`構造体

## 処理手順
1. **IPv4Addrのコンストラクタ処理**:
   - `sockaddr_in addr`を受け取り、内部メンバ変数`raw_`に設定する。
   - `inet_ntop`を使用して、`raw_.sin_addr`からIPアドレス文字列を生成し、`ip_`に設定する。失敗した場合は例外を投げる。

2. **IPv4Addrのコンストラクタ処理 (IPアドレスとポート番号)**:
   - `std::string ip`, `std::uint16_t port`を受け取り、内部メンバ変数`ip_`に設定する。
   - `raw_.sin_family`を`AF_INET`に設定し、`raw_.sin_port`をネットワークバイトオーダーに変換して設定する。
   - `inet_pton`を使用して、`ip_`から`raw_.sin_addr`にIPv4アドレスを設定する。失敗した場合は例外を投げる。

3. **IPv6Addrのコンストラクタ処理**:
   - `sockaddr_in6 addr`を受け取り、内部メンバ変数`raw_`に設定する。
   - `inet_ntop`を使用して、`raw_.sin6_addr`からIPアドレス文字列を生成し、`ip_`に設定する。失敗した場合は例外を投げる。

4. **IPv6Addrのコンストラクタ処理 (IPアドレスとポート番号)**:
   - `std::string ip`, `std::uint16_t port`を受け取り、内部メンバ変数`ip_`に設定する。
   - `raw_.sin6_family`を`AF_INET6`に設定し、`raw_.sin6_port`をネットワークバイトオーダーに変換して設定する。
   - `inet_pton`を使用して、`ip_`から`raw_.sin6_addr`にIPv6アドレスを設定する。失敗した場合は例外を投げる。

## 例外・失敗条件
- `inet_ntop`または`inet_pton`が失敗した場合、`ThrowLastSystemError()`関数を呼び出して例外を投げる。

## 依存関係
- `<concepts>`
- `<cstdint>`
- `<string>`
- `<string_view>`
- `<netinet/in.h>`
- `"util.h"`
- `<arpa/inet.h>`

## 重要な不変条件
- `IPv4Addr`と`IPv6Addr`のインスタンスは、それぞれ有効なIPアドレスとポート番号を持つこと。
- `ip_`が設定された場合、`raw_`も適切に初期化されていること。