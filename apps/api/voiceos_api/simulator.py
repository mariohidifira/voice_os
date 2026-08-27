from typing import Any, cast


def run_simulation(persona: str, objective: str, count: int, greeting: str = "Olá! Como posso ajudar?") -> dict[str, Any]:
    conversations: list[dict[str, Any]] = []
    for index in range(count):
        resolved = index % 10 != 9
        score = 95 if resolved else 70
        conversations.append(
            {
                "index": index + 1,
                "transcript": [
                    {"role": "agent", "text": greeting},
                    {"role": "user", "text": f"Persona: {persona}. Objetivo: {objective}. Caso {index + 1}."},
                    {"role": "agent", "text": "Entendi. Vou ajudar de forma objetiva."},
                ],
                "tool_calls": [],
                "qa": {"score": score, "resolved": resolved, "issues": [] if resolved else ["objective_not_resolved"]},
            }
        )
    average = sum(item["qa"]["score"] for item in conversations) / count
    return {"conversation_count": count, "average_score": average, "pass_rate": sum(item["qa"]["score"] >= 80 for item in conversations) / count, "conversations": conversations}


def simulation_yaml(report: dict[str, Any]) -> str:
    lines = ["version: 1", "cases:"]
    conversations = cast(list[dict[str, Any]], report.get("conversations", []))
    for conversation in conversations:
        lines.extend(
            [
                f"  - name: simulation-{conversation['index']}",
                "    channel: whatsapp",
                f"    expected_score_min: {conversation['qa']['score']}",
                "    turns:",
            ]
        )
        for turn in cast(list[dict[str, Any]], conversation["transcript"]):
            text = str(turn["text"]).replace('"', '\\"')
            lines.append(f"      - {{role: {turn['role']}, text: \"{text}\"}}")
    return "\n".join(lines) + "\n"
