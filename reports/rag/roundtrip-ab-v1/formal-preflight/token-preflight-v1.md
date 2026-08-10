# Design-only A/B formal token preflight v1

Status: **PASS**  
Targets: 17  
Design num_ctx / num_predict: 32768 / 8192  
Code num_ctx / num_predict: 32768 / 16384  
LLM calls: 0

| Target | A input | A total | A remain | B input | B total | B remain | Code input upper | Code total | Code remain | Risk |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| echo-web-server-block-deque | 4532 | 12724 | 20044 | 4555 | 12747 | 20021 | 9525 | 25909 | 6859 | no |
| echo-web-server-buffer | 5698 | 13890 | 18878 | 6687 | 14879 | 17889 | 9525 | 25909 | 6859 | no |
| echo-web-server-config | 7121 | 15313 | 17455 | 8913 | 17105 | 15663 | 9525 | 25909 | 6859 | no |
| echo-web-server-heap-timer | 6232 | 14424 | 18344 | 11005 | 19197 | 13571 | 9525 | 25909 | 6859 | no |
| echo-web-server-http | 10883 | 19075 | 13693 | 15916 | 24108 | 8660 | 9525 | 25909 | 6859 | no |
| echo-web-server-io | 4349 | 12541 | 20227 | 7647 | 15839 | 16929 | 9525 | 25909 | 6859 | no |
| echo-web-server-ip | 4138 | 12330 | 20438 | 5930 | 14122 | 18646 | 9525 | 25909 | 6859 | no |
| echo-web-server-log | 13530 | 21722 | 11046 | 20578 | 28770 | 3998 | 9525 | 25909 | 6859 | no |
| echo-web-server-thread-pool | 4001 | 12193 | 20575 | 8774 | 16966 | 15802 | 9525 | 25909 | 6859 | no |
| echo-web-server-util | 6025 | 14217 | 18551 | 6048 | 14240 | 18528 | 9525 | 25909 | 6859 | no |
| ini-cpp-ini-writer | 3184 | 11376 | 21392 | 3207 | 11399 | 21369 | 9525 | 25909 | 6859 | no |
| ini-cpp-inireader | 6388 | 14580 | 18188 | 6411 | 14603 | 18165 | 9525 | 25909 | 6859 | no |
| riscv-simulator-instruction | 4707 | 12899 | 19869 | 4954 | 13146 | 19622 | 9525 | 25909 | 6859 | no |
| riscv-simulator-memory | 3269 | 11461 | 21307 | 3516 | 11708 | 21060 | 9525 | 25909 | 6859 | no |
| riscv-simulator-parser | 3210 | 11402 | 21366 | 3807 | 11999 | 20769 | 9525 | 25909 | 6859 | no |
| riscv-simulator-register | 3087 | 11279 | 21489 | 3110 | 11302 | 21466 | 9525 | 25909 | 6859 | no |
| riscv-simulator-registerfile | 3349 | 11541 | 21227 | 4187 | 12379 | 20389 | 9525 | 25909 | 6859 | no |

Code-generation input is a conservative upper bound: the final design document is reserved up to num_predict tokens, plus the shared code prompt/system/template overhead. The model was not contacted.
