import pytest
from voiceos_voice.flow import FlowConfigError, FlowEngine, validate_flow


def flow_config() -> dict:
    return {
        "initial_state": "start",
        "states": [
            {"id": "start", "prompt": "Posso ajudar?", "transitions": [{"intent": "yes", "next": "done"}]},
            {"id": "done", "prompt": "Até logo.", "terminal": True},
        ],
    }


def test_flow_transitions_and_terminal_state() -> None:
    engine = FlowEngine(flow_config())
    assert engine.greeting().response == "Posso ajudar?"
    result = engine.handle("yes")
    assert result.state == "done"
    assert result.terminal is True
    assert engine.handle("yes").terminal is True


def test_unknown_intent_stays_in_state() -> None:
    engine = FlowEngine(flow_config())
    result = engine.handle("nope")
    assert result.state == "start"
    assert result.next_state is None
    assert result.response


def test_invalid_target_is_rejected() -> None:
    with pytest.raises(FlowConfigError, match="target does not exist"):
        validate_flow({"states": [{"id": "start", "transitions": [{"intent": "x", "next": "missing"}]}]})
