import pytest
from pydantic import ValidationError
from voiceos_api.schemas import ToolCreate


def test_tool_name_contract() -> None:
    tool = ToolCreate(name="consultar_pedido", description="Use quando consultar pedido", type="webhook", parameters_schema={"type": "object"})
    assert tool.name == "consultar_pedido"
    with pytest.raises(ValidationError):
        ToolCreate(name="Invalid Name", description="x", type="webhook", parameters_schema={})

