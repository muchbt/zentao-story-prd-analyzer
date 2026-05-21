import json
import os
from typing import Any, Dict

try:
    import openai
except ImportError:
    openai = None


def call_llm(prompt: str, agent: str = "codex") -> Dict[str, Any]:
    """
    调用 LLM，返回原始 JSON 字典。
    若失败，返回 {"error": "错误描述", "raw": "原始响应文本"}。
    """
    agent_lower = agent.lower()

    if agent_lower == "codex":
        try:
            if openai is None:
                return {"error": "openai 模块未安装", "raw": ""}
            openai.api_key = os.environ.get("OPENAI_API_KEY")
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            text = response.choices[0].message.content
        except Exception as exc:
            return {"error": f"LLM 调用失败: {exc}", "raw": ""}
    elif agent_lower == "claude":
        return {"error": "Claude 适配尚未实现，请配置 OPENAI_API_KEY 使用 Codex", "raw": ""}
    elif agent_lower == "opencode":
        return {"error": "OpenCode 适配尚未实现，请配置 OPENAI_API_KEY 使用 Codex", "raw": ""}
    else:
        return {"error": f"未识别 agent: {agent}", "raw": ""}

    # Try to extract JSON from Markdown code block if wrapped
    cleaned = text.strip()
    if cleaned.startswith("```json") and "```" in cleaned:
        cleaned = cleaned[len("```json"):].strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    elif cleaned.startswith("```") and "```" in cleaned:
        cleaned = cleaned[len("```"):].strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"error": "LLM 返回非 JSON", "raw": text}
