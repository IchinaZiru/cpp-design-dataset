# Formal RAG context build plan v1

- Status: `ready_for_remote_audit_before_context_generation`
- Mode: `plan-only`
- Branch: `agent/rag-protocol-v0-9`
- Project HEAD: `b9de59a6bb9fe23ed9f2b8480d9c307cb9043253`
- Protocol: `1.0` / `post-pilot formal freeze`
- Common config: `configs/rag/formal_retrieval_pipeline_v1.json` (`0640b24e8b9d5454aa4838fa30b27fb80f83cffd44fd286b78c5fe68416e85c1`)
- Targets: `17` (enabled: `0`)
- Retrieval/context generation: not executed
- LLM/Ollama/Docker/build/test/source replacement: not executed

## Planned targets

| Target | Repository commit | Query SHA-256 | Index validation SHA-256 | Planned context |
|---|---|---|---|---|
| `echo-web-server-block-deque` | `fb2fadb7e7f4c340325b0a72847425f6e8b6367e` | `3a90daae83ce2b4dba74942ef19be8746dcb44d011d2750d6b07df82f92b008d` | `e9933f750f2b93363682ac7f981c07758075693c63f25841c915a67bfcbf14a1` | `rag/retrieval/formal/echo-web-server-block-deque/context.txt` |
| `echo-web-server-buffer` | `fb2fadb7e7f4c340325b0a72847425f6e8b6367e` | `26f44d2b6d66c8cb6684eef7ca5a691907a4fabb6fe3f806fe1f54bbe9622161` | `e9933f750f2b93363682ac7f981c07758075693c63f25841c915a67bfcbf14a1` | `rag/retrieval/formal/echo-web-server-buffer/context.txt` |
| `echo-web-server-config` | `fb2fadb7e7f4c340325b0a72847425f6e8b6367e` | `78c6684bb752294daa2cd2554e8692fc2261a2dc3093ec3a5947fb47bbb66e13` | `e9933f750f2b93363682ac7f981c07758075693c63f25841c915a67bfcbf14a1` | `rag/retrieval/formal/echo-web-server-config/context.txt` |
| `echo-web-server-heap-timer` | `fb2fadb7e7f4c340325b0a72847425f6e8b6367e` | `3de9c98ff50a0a5dc8a8a8a8616bb6d76a653502b421e19e34d23b69ebf984a8` | `e9933f750f2b93363682ac7f981c07758075693c63f25841c915a67bfcbf14a1` | `rag/retrieval/formal/echo-web-server-heap-timer/context.txt` |
| `echo-web-server-http` | `fb2fadb7e7f4c340325b0a72847425f6e8b6367e` | `cbd94f066782653e5063a83fe5de1e6db5e146e134755db6c5ca26bd386b55a4` | `e9933f750f2b93363682ac7f981c07758075693c63f25841c915a67bfcbf14a1` | `rag/retrieval/formal/echo-web-server-http/context.txt` |
| `echo-web-server-io` | `fb2fadb7e7f4c340325b0a72847425f6e8b6367e` | `4312d8ed3432aabfb3f023119415b57b3ec746463cd74f3709cd7959d14f82a4` | `e9933f750f2b93363682ac7f981c07758075693c63f25841c915a67bfcbf14a1` | `rag/retrieval/formal/echo-web-server-io/context.txt` |
| `echo-web-server-ip` | `fb2fadb7e7f4c340325b0a72847425f6e8b6367e` | `51e0ed49fc7998406bc79b81c30f5a3803504c16cc652fedab4721e6e38b9298` | `e9933f750f2b93363682ac7f981c07758075693c63f25841c915a67bfcbf14a1` | `rag/retrieval/formal/echo-web-server-ip/context.txt` |
| `echo-web-server-log` | `fb2fadb7e7f4c340325b0a72847425f6e8b6367e` | `1372e8ca59b81629b6393ad565d0394403550e8e7ed4c5f5f71e398479e437fc` | `e9933f750f2b93363682ac7f981c07758075693c63f25841c915a67bfcbf14a1` | `rag/retrieval/formal/echo-web-server-log/context.txt` |
| `echo-web-server-thread-pool` | `fb2fadb7e7f4c340325b0a72847425f6e8b6367e` | `c8ebf32a61d8fd19196972ae54a7eba17a1b55e6347fcdb11a99a4d6e6c98df1` | `e9933f750f2b93363682ac7f981c07758075693c63f25841c915a67bfcbf14a1` | `rag/retrieval/formal/echo-web-server-thread-pool/context.txt` |
| `echo-web-server-util` | `fb2fadb7e7f4c340325b0a72847425f6e8b6367e` | `be3f8b739e7772d067f27672cdd01a68981b56cf2b2ee66a3507d70ecbf18f0f` | `e9933f750f2b93363682ac7f981c07758075693c63f25841c915a67bfcbf14a1` | `rag/retrieval/formal/echo-web-server-util/context.txt` |
| `ini-cpp-ini-writer` | `e1779b837274de8be2051bef579c3b9ec3483522` | `51ab8768bf58614770badb7db4e1b56f8152c72175f2b881c5a05ae79cac8c14` | `a076f9a66052f438ad662bb906061092d96b15db298ef23db3c38dfd187b69ed` | `rag/retrieval/formal/ini-cpp-ini-writer/context.txt` |
| `ini-cpp-inireader` | `e1779b837274de8be2051bef579c3b9ec3483522` | `f9bdafc19c8e29b77a429d108d6721f984a8e99299285cbc943d1f7ff4924dfb` | `a076f9a66052f438ad662bb906061092d96b15db298ef23db3c38dfd187b69ed` | `rag/retrieval/formal/ini-cpp-inireader/context.txt` |
| `riscv-simulator-instruction` | `8989a09c357a69b68612f653380d60816f5176c2` | `e7bd88ae88fc2495a70153bfde2f45626142ac44ddc13fc5e85f2e2ae7c37fa0` | `9d047f142bc72e2ad7da961f1307fb95dda889537b856b1e82f5dbfb9b9e631a` | `rag/retrieval/formal/riscv-simulator-instruction/context.txt` |
| `riscv-simulator-memory` | `8989a09c357a69b68612f653380d60816f5176c2` | `0c98198b8b69f6473037a5dac7e79368004d7219da9ccc220cf5d826dec11b91` | `9d047f142bc72e2ad7da961f1307fb95dda889537b856b1e82f5dbfb9b9e631a` | `rag/retrieval/formal/riscv-simulator-memory/context.txt` |
| `riscv-simulator-parser` | `8989a09c357a69b68612f653380d60816f5176c2` | `7492f445ef68d02f952328a1508d54ed8cd0dc91a68917d80f5c3fbb2dc90621` | `9d047f142bc72e2ad7da961f1307fb95dda889537b856b1e82f5dbfb9b9e631a` | `rag/retrieval/formal/riscv-simulator-parser/context.txt` |
| `riscv-simulator-register` | `8989a09c357a69b68612f653380d60816f5176c2` | `6767ac7ca169c9ca749b96ceca123ea2ed87b5cf30f28c2c063c922c6dae6ad1` | `9d047f142bc72e2ad7da961f1307fb95dda889537b856b1e82f5dbfb9b9e631a` | `rag/retrieval/formal/riscv-simulator-register/context.txt` |
| `riscv-simulator-registerfile` | `8989a09c357a69b68612f653380d60816f5176c2` | `6ce9e5c6bb0dc07104d1afe6f45eb5763906a9a47382ca81cea0ef0457be0244` | `9d047f142bc72e2ad7da961f1307fb95dda889537b856b1e82f5dbfb9b9e631a` | `rag/retrieval/formal/riscv-simulator-registerfile/context.txt` |

All canonical outputs are absent. Formal execution has not started; remote audit is required before context generation.
