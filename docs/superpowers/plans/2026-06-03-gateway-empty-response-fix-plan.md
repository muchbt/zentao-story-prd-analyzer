# Gateway empty_response 修复计划

## 背景

运行 `requirement/5904 (FC_1053613_(1)_Send mute/unmute)` 分析时，返回 `"Agent 返回内容不含 JSON"` 错误（`error_kind: "parse_empty"`）。

### 根因诊断

根因链路：

```
analyzer → acp-agent-gateway start-session --agent opencode
  → spawn: opencode acp (ACP adapter v1.15.13)
  → opencode 实际搜索并生成文本，但 ACP adapter 不发送 agent_message_chunk 通知
  → gateway session.#text 始终为空
  → gateway stdout: {"status":"completed","text":"","stopReason":"empty_response"}
  → GatewayResult(ok=True, text="")  ← 忽略 stopReason
  → "Agent 返回内容不含 JSON"  ← 误导性错误消息
```

关键发现：

1. **opencode acp adapter (v1.15.13) 有 bug**：不通过 `agent_message_chunk` 通知回传文本。直接 `opencode run --format json` 可正常输出，但 ACP 协议路径不行。
2. **Gateway 行为符合其契约**：`end_turn + text==""` 映射为 `stopReason:"empty_response"`，`status` 仍为 `"completed"`。这是 Gateway README/ADR 明确记录的公共契约。
3. **analyzer 客户端丢弃了关键信号**：`GatewayResult` 没有 `stop_reason` 字段，也不检查 `stopReason`。Gateway 明确告知了 `empty_response`，但 analyzer 当成普通空文本交给了 JSON parser。

### 影响范围

所有通过 Gateway (`--agent gateway --gateway-agent opencode`) 调用的分析请求。`opencode acp` 适配器的 `agent_message_chunk` 缺失是个系统性 bug，因此当前 **所有** 通过该路径的请求都无法获取文本。

## 修复方案

修复点在 **analyzer 客户端**。不修改 Gateway 的公共契约（`empty_response` 保持 `status:"completed"`）。

### 变更文件

| 文件 | 变更 |
|------|------|
| `zentao_analyzer/gateway_client.py` | `GatewayResult` 新增 `stop_reason` 字段；`status=="completed"` 时检查 `stopReason` 与 `text` 是否为空，若为空返回 `ok=False`；新增 `agent_empty_response` 到 `GATEWAY_ERROR_MAP` 映射为 `gateway_empty_response` |
| `zentao_analyzer/agent_client.py` | `AgentResult` 新增 `gateway_stop_reason` 字段；`_parse_gateway_success` 和 `_parse_gateway_failure` 传播该字段 |
| `zentao_analyzer/llm_client.py` | `call_llm` 在 error data 和 success data 中传播 `gateway_stop_reason` |
| `zentao_analyzer/analysis_result.py` | `AnalysisResult` 新增 `gateway_stop_reason` 字段 |
| `zentao_analyzer/analyzer.py` | 错误和成功路径均从 `llm_data` 传播 `gateway_stop_reason` |
| `zentao_analyzer/main.py` | `gateway_empty_response` 加入可重试错误列表；debug bundle diagnostics 包含 `gateway_stop_reason` |
| `README.md` | 新增 `gateway_empty_response` 错误类型说明 |

### 核心逻辑变更

`gateway_client.py` 中 `call_gateway_start_session()`:

```python
if status == "completed":
    text = result_json.get("text", "")
    stop_reason = result_json.get("stopReason", "") or result_json.get("stop_reason", "")
    if stop_reason == "empty_response" or not text:
        return GatewayResult(
            ok=False,
            text="",
            stop_reason=stop_reason or "empty_response",
            error_code="agent_empty_response",
            error="Agent completed but returned no final text via ACP",
            error_kind="runtime",
            ...
        )
    return GatewayResult(ok=True, text=text, stop_reason=stop_reason, ...)
```

### 不做什么

- **不修改 Gateway 公共契约**：`empty_response` 不改为 `status:"failed"`。
- **不新增 Gateway 严格模式**（如 `--fail-on-empty-response`）：当前范围仅修复 analyzer 对该信号的接收。
- **不修复 opencode acp adapter**：属于 opencode v1.15.13 外部依赖。

## 验证

### 反馈回路

```bash
# 1. 用修改后的 gateway_client 跑 Gateway 空响应测试
python3 -c "
from zentao_analyzer.gateway_client import GatewayConfig, call_gateway_start_session
gw = call_gateway_start_session('Say hello', '/tmp', GatewayConfig(gateway_agent='opencode'))
assert gw.ok == False, f'expected ok=False, got {gw.ok}'
assert gw.stop_reason == 'empty_response', f'expected empty_response, got {gw.stop_reason}'
assert gw.error_code == 'agent_empty_response', f'expected agent_empty_response, got {gw.error_code}'
print('PASS: gateway empty_response properly detected')
"
```

### 单元测试

```bash
python3 -m pytest tests/test_gateway_client.py -x -q
```

### 文档

`README.md` 中 Agent 响应解析失败表格已更新，增加 `gateway_empty_response` 行。
