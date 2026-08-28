"""Configuration-driven conversation flow engine.

This module is deliberately independent of LiveKit and providers so flows can
be validated and simulated in the API/UI before a call is published.
"""

from dataclasses import dataclass
from typing import Any


class FlowConfigError(ValueError):
    """Raised when a process configuration cannot be executed safely."""


@dataclass(frozen=True)
class FlowResult:
    state: str
    response: str | None = None
    next_state: str | None = None
    terminal: bool = False
    action: dict[str, Any] | None = None


def validate_flow(config: dict[str, Any] | None) -> dict[str, Any]:
    """Validate and normalize the process portion of an agent runtime."""
    value = dict(config or {})
    states = value.get("states")
    if not isinstance(states, list) or not states:
        raise FlowConfigError("process.states must contain at least one state")
    state_ids = {str(item.get("id")) for item in states if isinstance(item, dict)}
    if len(state_ids) != len(states) or "None" in state_ids:
        raise FlowConfigError("process.states must have unique non-empty ids")
    initial = str(value.get("initial_state") or states[0]["id"])
    if initial not in state_ids:
        raise FlowConfigError("process.initial_state does not reference a state")
    for state in states:
        if not isinstance(state, dict):
            raise FlowConfigError("each process state must be an object")
        for transition in state.get("transitions", []):
            if not isinstance(transition, dict) or not transition.get("intent"):
                raise FlowConfigError("each transition requires an intent")
            target = transition.get("next")
            if target not in state_ids:
                raise FlowConfigError(f"transition target does not exist: {target}")
    value["initial_state"] = initial
    value["states"] = states
    return value


class FlowEngine:
    """Small per-call state machine; it never stores global call state."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = validate_flow(config)
        self.states = {str(item["id"]): item for item in self.config["states"]}
        self.state = self.config["initial_state"]
        self.ended = False

    def greeting(self) -> FlowResult:
        current = self.states[self.state]
        return FlowResult(self.state, str(current.get("prompt") or ""))

    def handle(self, intent: str) -> FlowResult:
        if self.ended:
            return FlowResult(self.state, terminal=True)
        current = self.states[self.state]
        transition = next(
            (item for item in current.get("transitions", []) if item.get("intent") == intent),
            None,
        )
        if transition is None:
            return FlowResult(self.state, str(current.get("fallback") or "Não entendi. Pode repetir?"))
        target = str(transition["next"])
        self.state = target
        destination = self.states[target]
        terminal = bool(destination.get("terminal"))
        self.ended = terminal
        return FlowResult(
            target,
            str(destination.get("prompt") or ""),
            target,
            terminal,
            dict(destination.get("action") or {}) or None,
        )


def match_intent(config: dict[str, Any], text: str) -> str | None:
    """Match a short utterance against configured examples without an LLM."""
    normalized = " ".join(text.lower().split())
    for item in config.get("intents", []):
        intent_id = str(item.get("id") or "")
        examples = item.get("examples") or []
        if intent_id and any(str(example).lower() in normalized for example in examples):
            return intent_id
    return None
