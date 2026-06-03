from typing import Any, Dict, Optional

from .agent_client import AgentClient, AgentConfig


def call_llm(prompt: str, agent: str = "codex", agent_config: Optional[AgentConfig] = None) -> Dict[str, Any]:
    config = agent_config or AgentConfig(agent=agent)
    result = AgentClient(config).call(prompt)
    if not result.ok:
        error_data = {
            "error": result.error,
            "error_kind": result.error_kind,
            "raw": result.raw_response,
        }
        if result.gateway_error_code:
            error_data["gateway_error_code"] = result.gateway_error_code
        if result.gateway_session_ref:
            error_data["gateway_session_ref"] = result.gateway_session_ref
        if result.gateway_events:
            error_data["gateway_events"] = result.gateway_events
        if result.gateway_transport_error:
            error_data["gateway_transport_error"] = result.gateway_transport_error
        return error_data
    data = dict(result.json_data)
    data["raw"] = result.raw_response
    if result.gateway_session_ref:
        data["gateway_session_ref"] = result.gateway_session_ref
    if result.gateway_events:
        data["gateway_events"] = result.gateway_events
    return data
