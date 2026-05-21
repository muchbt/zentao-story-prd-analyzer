from typing import Any, Dict, Optional

from agent_client import AgentClient, AgentConfig


def call_llm(prompt: str, agent: str = "codex", agent_config: Optional[AgentConfig] = None) -> Dict[str, Any]:
    config = agent_config or AgentConfig(agent=agent)
    result = AgentClient(config).call(prompt)
    if not result.ok:
        return {
            "error": result.error,
            "error_kind": result.error_kind,
            "raw": result.raw_response,
        }
    data = dict(result.json_data)
    data["raw"] = result.raw_response
    return data
