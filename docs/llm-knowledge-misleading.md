分析结论：问题确认
你的观察完全正确。三份 PRD 的"LLM 理解摘要"确实与"实现证据"、"差异与缺口"、"修改建议"、"验证建议"等后续章节完全重复，不是真正的"理解摘要"。
根因定位
document_generator.py:58-82 的 _build_llm_summary() 函数将 AnalysisResult 的所有结构化字段拼接为"摘要"：
# _build_llm_summary 当前做法：
parts = []
parts.append(f"结论：{analysis.conclusion}")          # ← 重复"实现完成度"
parts.append(f"证据：\n{...analysis.evidence}")        # ← 重复"实现证据"
parts.append(f"未实现：{...analysis.gaps}")            # ← 重复"差异与缺口"
parts.append(f"可能根因：{...analysis.suspected_causes}")  # ← 重复"可能根因"
parts.append(f"影响范围：{...analysis.affected_scope}")    # ← 重复"影响范围"
parts.append(f"建议：{...analysis.recommendations}")  # ← 重复"修改建议"
parts.append(f"验证：{...analysis.verification}")      # ← 重复"验证建议"
同时，LLM prompt (prompts/5930.txt) 没有请求 LLM 生成对需求的自然语言理解摘要——只请求了 conclusion、evidence、gaps、recommendations 等结构化分析字段。
因此 _build_llm_summary 没有任何"理解"数据可写，只能把分析结果重新拼装，结果与下方各章节 100% 重复。
三份 PRD 重复验证
PRD	LLM 理解摘要内容	与后续章节的关系
5930 (Ecall回拨模式)	24条证据 + 3条缺口 + 2条根因 + 6条范围 + 4条建议 + 5条验证	与"实现证据"、"差异与缺口"、"修改建议"、"验证建议"逐字重复
5923 (Service Request Criteria)	14条证据 + 3条缺口 + 3条根因 + 3条范围 + 4条建议 + 5条验证	同上，完全重复
5929 (Ending service EA/AA)	证据不足标记	特殊：因 confidence=低 走了 is_insufficient_evidence() 分支，输出"证据不足"，但实际"实现证据"章节仍有18条证据——逻辑矛盾
"LLM 理解摘要"应当是什么
应是：LLM 对需求本身的理解/释义，例如：
本需求要求 TCAM 在语音通话因用户取消或呼叫中心挂断结束后进入 25 分钟回拨模式；回拨期间周期性向 DHU 上报 CallBackMode 和剩余时间；来电自动应答；收到新 EA/AA 触发时发送 MSD 并续时；忽略 ICall/BCall 请求；无 EA/AA 服务时拒绝来电；回拨模式下拒绝 BCall 来电。
不应是：把分析结论、证据列表、缺口、建议等结构化数据再罗列一遍（这些都已各有专节）。
修复方向
需在两层同时修改：
1. LLM prompt（agent_prompt.py 或对应模板）：新增 understanding_summary 字段，要求 LLM 用自然语言概述它对需求的理解
2. AnalysisResult + _build_llm_summary()：新增 understanding_summary 字段，_build_llm_summary 优先使用该字段；当该字段为空时（向后兼容），生成简要综合而非全文复制
