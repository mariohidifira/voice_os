import pytest
from pydantic import ValidationError
from voiceos_api.schemas import AgentDraftPatch, ToolCreate


def test_tool_name_contract() -> None:
    tool = ToolCreate(name="consultar_pedido", description="Use quando consultar pedido", type="webhook", parameters_schema={"type": "object"})
    assert tool.name == "consultar_pedido"
    with pytest.raises(ValidationError):
        ToolCreate(name="Invalid Name", description="x", type="webhook", parameters_schema={})


def test_agent_process_mode_requires_valid_flow() -> None:
    with pytest.raises(ValidationError, match="execution_mode"):
        AgentDraftPatch(behavior={"execution_mode": "unknown"})
    with pytest.raises(ValidationError, match="behavior.process"):
        AgentDraftPatch(behavior={"execution_mode": "deterministic"})


def test_agent_process_mode_accepts_states() -> None:
    draft = AgentDraftPatch(
        behavior={
            "execution_mode": "hybrid",
            "process": {"states": [{"id": "start"}]},
        }
    )
    assert draft.behavior["execution_mode"] == "hybrid"
