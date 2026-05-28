  作为“让 opencode run --format json 返回的事件流能提取最终分析文本”的计划，方向可行；作为此前讨论的“实时展示工具状态 + --agent-idle-timeout”功能计划，不可行，缺少流式读取与超时控制主链路。

  问题

  1. [P1] 该计划不能实现真实进度展示或 idle timeout

     当前 zentao_analyzer/agent_client.py:332 仍使用 subprocess.run(..., capture_output=True)，进程结束后才拿到 stdout。仅增加 --format json 和事后解析 NDJSON，用户仍无法在执行期间看到 tool_use，也无法基于事件
     实现 300 秒空闲终止。

     若目标包含前次确认的功能，必须增加 Popen/流式读取、--agent-progress、--agent-idle-timeout、事件日志转发及总超时/空闲超时并行控制。
  2. [P1] 不能把所有非 text 事件一律跳过

     tool_use 对“仅提取最终文本”的模式可以不参与最终 JSON 组装，但它正是未来真实进度功能的输入。解析层应区分：
      - 最终文本提取事件；
      - 可标准化的工具事件；
      - error 事件；
      - 未识别旁路事件。

     否则本次新增解析器随后还要被重构一次。
  3. [P1] error 与 text 同时出现时的成功规则未定义

     计划仅规定“无 text 但有 error 时失败”。如果事件流先产生部分 text，随后出现终止性 error，当前规则可能把不完整文本当成成功结果。需要先以实际事件 schema 确认 error 是否终止事件；在未确认前，检测到 error 应优
     先返回失败，且错误文本必须经过脱敏。
  4. [P1] raw event stream 不应进入既有响应/debug 路径

     OpenCode 原始事件可能包含工具参数、路径或输出。现有 _parse_text() 会把传入文本保存为 raw_response，随后可能写入 Debug Bundle。回退逻辑不能在“识别到事件流但没有 text”时直接 _parse_text(stdout.strip())，否
     则会把事件对象误作最终结果或保存原始事件载荷。

     推荐规则：只有 stdout 完全不是可识别的 OpenCode 事件流时，才回退旧文本解析；识别到事件流但未得到最终文本时返回解析失败。
  5. [P2] 事件字段结构尚未获得可靠验证

     本机 OpenCode 1.15.11 与官方文档确认了 opencode run --format json 和 --dir 有效，但未在帮助或官方 CLI 文档中定义 type == "text"、part.text、error.data.message 的具体 schema。实现前应取得一份真实脱敏事件样
     例或官方源代码/fixture，并据此编写测试，不能仅按猜测冻结解析协议。
  6. [P2] 命令改写遗漏现有参数保留规则

     当前实现会传入 --model 与 extra_args，见 zentao_analyzer/agent_client.py:324。新命令构造必须保留这些行为，并规定用户额外传入 --format / --dir 时如何避免重复冲突。
  7. [P2] “不修改文档”不成立

     README.md:247 与 SKILL.md:39 已将 OpenCode 描述为可调用后端；但旧 docs/superpowers/specs/2026-05-21-phase4-agent-ux-design.md:13 仍声明 OpenCode 仅为占位、不真实调用。新增 OpenCode JSON 协议时，应至少修正
     或废弃该历史冲突说明。

     若本计划并入进度流功能，还必须更新 docs/superpowers/specs/2026-05-27-agent-progress-streaming-design.md:20，因为其中当前明确写着 OpenCode 事件能力尚未确认。
  8. [P2] 验证范围不足且命令风格不一致

     仓库当前使用 unittest 主测试路径。除了所列单测，还需覆盖：
      - OpenCode error 事件与敏感信息脱敏；
      - 已识别事件流但缺最终文本的失败行为；
      - --model / extra_args / cwd 保持不回退；
      - 非零退出码结合事件输出；
      - 完整测试套件回归。

  建议拆分

  - 阶段 A：OpenCode 最终结果适配

    使用 --format json，安全提取最终文本并保持现有非流式调用；不声称支持实时工具展示或 idle timeout。
  - 阶段 B：Agent Progress Streaming

    按已保存规格统一实现 Claude、Codex，以及经验证后的 OpenCode 流式事件消费、日志输出和 --agent-idle-timeout。

  阶段 A 可先实施，但需先补齐事件 schema 证据、安全失败规则和文档一致性；当前计划原样执行存在误判成功与泄露原始事件内容的风险。

  来源：

  - OpenCode CLI 官方文档：https://opencode.ai/docs/cli/
  - 本机 opencode run --help：已确认 --format json 与 --dir 可用。
