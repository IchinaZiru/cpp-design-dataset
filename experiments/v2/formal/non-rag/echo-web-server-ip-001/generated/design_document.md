# デザイン文書

## 概要
この設計文書は、`include/ip.h`と`src/ip/ip.cpp`に含まれるIPアドレス処理モジュールの再実装に必要な情報を提供します。各ファイルの責務、公開インターフェース、入力、出力、状態、処理手順、例外・失敗条件、依存関係、重要な不変条件について記載します。

## モジュール構造

### ファイル間の関係
- `include/ip.h`: クラス定義と公開インターフェースを含むヘッダーファイル。
- `src/ip/ip.cpp`: 実装ファイルで、`ip.h`に定義されたクラスのメンバ関数を実装しています。

## ファイル詳細

### include/ip.h
#### 責務
IPアドレスを抽象化したインターフェースとその派生クラス（IPv4Addr, IPv6Addr）を提供します。
#### 公開インターフェース
- `class IPAddr`: IPアドレスの基底クラスで、純粋仮想関数として以下のメソッドを持ちます。
  - `int Version() const noexcept`
  - `std::size_t Size() const noexcept`
  - `const sockaddr* Raw() const noexcept`
  - `std::uint16_t Port() const noexcept`
  - `std::string IPAddress() const noexcept`

- `class IPv4Addr`: IPAddrを継承し、IPv4アドレスの具体的な実装を行います。
  - コンストラクタ: 
    - `explicit IPv4Addr(sockaddr_in addr)`
    - `explicit IPv4Addr(std::string ip, std::uint16_t port)`

- `class IPv6Addr`: IPAddrを継承し、IPv6アドレスの具体的な実装を行います。
  - コンストラクタ: 
    - `explicit IPv6Addr(sockaddr_in6 addr)`
    - `explicit IPv6Addr(std::string ip, std::uint16_t port)`

- `template <typename T> concept ValidIPAddr`: IPv4AddrまたはIPv6Addrの型を制約するためのコンセプト。

#### 入力
- IPアドレス文字列とポート番号（`std::string`, `std::uint16_t`）
- `sockaddr_in` または `sockaddr_in6`

#### 出力
- IPバージョン (`int`)
- ソケットアドレス構造体のサイズ (`std::size_t`)
- ソケットアドレスへのポインタ (`const sockaddr*`)
- ポート番号 (`std::uint16_t`)
- IPアドレス文字列 (`std::string`)

#### 状態
- IPv4Addr: `ip_`, `raw_`
- IPv6Addr: `ip_`, `raw_`

#### 処理手順
- コンストラクタでIPアドレスとポート番号を設定し、内部状態を初期化します。
- 各メンバ関数は内部状態から情報を抽出して返却します。

#### 例外・失敗条件
- `inet_pton`が1以外の値を返した場合（無効なIPアドレス文字列）
- `inet_ntop`がnullptrを返した場合（システムエラー）

#### 依存関係
- `<concepts>`
- `<cstdint>`
- `<string>`
- `<string_view>`
- `<netinet/in.h>`
- `<arpa/inet.h>`

#### 重要な不変条件
- IPv4Addr: `raw_.sin_family`は常に`AF_INET`
- IPv6Addr: `raw_.sin6_family`は常に`AF_INET6`

### src/ip/ip.cpp
#### 責務
`include/ip.h`で定義されたクラスのメンバ関数を実装します。
#### 公開インターフェース
- 各コンストラクタと純粋仮想関数のオーバーライド

#### 処理手順
- コンストラクタ:
  - IPアドレス文字列から`sockaddr_in`または`sockaddr_in6`への変換（`inet_pton`）
  - `sockaddr_in`または`sockaddr_in6`からIPアドレス文字列への変換（`inet_ntop`）

- 各メンバ関数:
  - 内部状態から情報を抽出して返却

#### 例外・失敗条件
- `inet_pton`が1以外の値を返した場合（無効なIPアドレス文字列）
- `inet_ntop`がnullptrを返した場合（システムエラー）

## 注意事項
- 再実装では、元コードに存在しない機能や変更は行わないでください。
- 依存関係にあるヘッダーファイルとライブラリの使用は必須です。