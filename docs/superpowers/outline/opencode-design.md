实现计划：opencode --format json 调用功能
修改文件
1. zentao_analyzer/agent_client.py
- 新增 _parse_opencode_events(stdout: str) -> tuple[str, str] 函数：
- 逐行解析 NDJSON 事件流
- 提取所有 type == "text" 事件的 part.text，拼接为完整文本
- 提取所有 type == "error" 事件的 error.data.message 作为错误信息
- 跳过非 JSON 行（空行、step_start/step_finish/tool_use/reasoning 等旁路事件）
- 返回 (text_content, error_message)；均在无对应事件时返回空字符串
- 重写 _call_opencode(prompt) 方法：
- 命令从 [command, "run", prompt] 改为 [command, "run", "--format", "json", "--dir", cwd, prompt]
- 移除 input=None（位置参数不需 stdin）
- 成功时：先 _parse_opencode_events(stdout) 提取文本，再用 _parse_text() 解析 JSON 对象
- NDJSON 解析无 text 事件时回退到直接 _parse_text(stdout.strip())（兼容旧版）
- 无 text 事件但发现 error 事件时返回 AgentResult(ok=False, error_kind="runtime")
2. tests/test_agent_client.py
- 新增 TestOpenCodeEventParsing 类：
- test_single_text_event：单条 text 事件提取文本
- test_multiple_text_events_concatenated：多条 text 事件拼接
- test_error_event_detected：error 事件返回错误信息
- test_mixed_events_skip_non_text：step_start/step_finish/tool_use 等被跳过
- test_empty_output_falls_through：空/非 JSON 输出回退处理
- test_no_text_events_fallback_to_raw_parse：无 text 事件时回退到原始文本解析
- 更新 TestAgentClientOpenCode.test_opencode_success_passes_model：
- 验证命令包含 --format json
- 验证命令包含 --dir
- 模拟 NDJSON 输出格式
不修改的文件
- app_config.py：已有 opencode_command 配置，无需变动
- main.py：已有 --opencode-command 参数，无需变动
- SKILL.yaml/SKILL.md：已声明 opencode 支持
验证
python3 -m pytest tests/test_agent_client.py -v
python3 -m pytest tests/test_app_config.py -v
python3 -m pytest tests/test_llm_client.py -v
