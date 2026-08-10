# Design-only A/B formal token preflight v1

Status: **PASS**  
Targets: 17  
Design num_ctx / num_predict: 32768 / 8192  
Code num_ctx / num_predict: 32768 / 16384  
LLM calls: 0

| Target | A input | A total | A remain | B input | B total | B remain | Code input upper | Code total | Code remain | Risk |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| echo-web-server-block-deque | 2023 | 10215 | 22553 | 4557 | 12749 | 20019 | 9525 | 25909 | 6859 | no |
| echo-web-server-buffer | 3189 | 11381 | 21387 | 6689 | 14881 | 17887 | 9525 | 25909 | 6859 | no |
| echo-web-server-config | 4612 | 12804 | 19964 | 8915 | 17107 | 15661 | 9525 | 25909 | 6859 | no |
| echo-web-server-heap-timer | 3723 | 11915 | 20853 | 11007 | 19199 | 13569 | 9525 | 25909 | 6859 | no |
| echo-web-server-http | 8374 | 16566 | 16202 | 15918 | 24110 | 8658 | 9525 | 25909 | 6859 | no |
| echo-web-server-io | 1840 | 10032 | 22736 | 7649 | 15841 | 16927 | 9525 | 25909 | 6859 | no |
| echo-web-server-ip | 1629 | 9821 | 22947 | 5932 | 14124 | 18644 | 9525 | 25909 | 6859 | no |
| echo-web-server-log | 11021 | 19213 | 13555 | 20580 | 28772 | 3996 | 9525 | 25909 | 6859 | no |
| echo-web-server-thread-pool | 1492 | 9684 | 23084 | 8776 | 16968 | 15800 | 9525 | 25909 | 6859 | no |
| echo-web-server-util | 3516 | 11708 | 21060 | 6050 | 14242 | 18526 | 9525 | 25909 | 6859 | no |
| ini-cpp-ini-writer | 690 | 8882 | 23886 | 3224 | 11416 | 21352 | 9525 | 25909 | 6859 | no |
| ini-cpp-inireader | 3879 | 12071 | 20697 | 6413 | 14605 | 18163 | 9525 | 25909 | 6859 | no |
| riscv-simulator-instruction | 2198 | 10390 | 22378 | 4956 | 13148 | 19620 | 9525 | 25909 | 6859 | no |
| riscv-simulator-memory | 760 | 8952 | 23816 | 3518 | 11710 | 21058 | 9525 | 25909 | 6859 | no |
| riscv-simulator-parser | 701 | 8893 | 23875 | 3809 | 12001 | 20767 | 9525 | 25909 | 6859 | no |
| riscv-simulator-register | 578 | 8770 | 23998 | 3112 | 11304 | 21464 | 9525 | 25909 | 6859 | no |
| riscv-simulator-registerfile | 840 | 9032 | 23736 | 4189 | 12381 | 20387 | 9525 | 25909 | 6859 | no |

Code-generation input is a conservative upper bound: the final design document is reserved up to num_predict tokens, plus the shared code prompt/system/template overhead. The model was not contacted.
