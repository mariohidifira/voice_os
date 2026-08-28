"""Start the local VoiceOS stack with secrets from Windows Credential Manager."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

try:
    import keyring
except ImportError:
    print(
        "Python package 'keyring' is required. Install it with: py -m pip install keyring",
        file=sys.stderr,
    )
    raise SystemExit(2) from None


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "docker-compose.yml"
DEFAULT_SERVICES = ("db", "redis", "api", "mock", "web", "worker", "agent-worker")

# New canonical names come first. Existing VoiceOS aliases remain supported so
# other local systems can keep using the credentials they already reference.
CREDENTIALS: dict[str, tuple[tuple[str, str], ...]] = {
    "LIVEKIT_URL": (("VOICEOS.LIVEKIT_URL", "URL"),),
    "LIVEKIT_API_KEY": (("VOICEOS.LIVEKIT_API_KEY", "API_KEY"),),
    "LIVEKIT_API_SECRET": (("VOICEOS.LIVEKIT_API_SECRET", "API_SECRET"),),
    "OPENAI_API_KEY": (
        ("VOICEOS.OPENAI_API_KEY", "API_KEY"),
        ("VOICEOS.OPENAI", "API_KEY"),
    ),
    "ANTHROPIC_API_KEY": (
        ("VOICEOS.ANTHROPIC_API_KEY", "API_KEY"),
        ("VOICEOS.ANTHROPIC.CLAUDE", "API_KEY"),
    ),
    "ELEVENLABS_API_KEY": (
        ("VOICEOS.ELEVENLABS_API_KEY", "API_KEY"),
        ("VOICEOS.ELEVENLABS_MUSIC", "API_KEY"),
    ),
    "GOOGLE_API_KEY": (
        ("VOICEOS.GOOGLE_API_KEY", "API_KEY"),
        ("VOICEOS.GOOGLE.GEMINI", "API_KEY"),
    ),
    "CARTESIA_API_KEY": (
        ("VOICEOS.CARTESIA_API_KEY", "API_KEY"),
        ("VOICEOS.CARTESIA", "API_KEY"),
    ),
    "CEREBRAS_API_KEY": (
        ("VOICEOS.CEREBRAS_API_KEY", "API_KEY"),
        ("VOICEOS.CEREBRAS", "API_KEY"),
    ),
    "OPENROUTER_API_KEY": (
        ("VOICEOS.OPENROUTER_API_KEY", "API_KEY"),
        ("VOICEOS.OPENROUTER", "API_KEY"),
    ),
}


def load_credentials() -> tuple[dict[str, str], list[str]]:
    values: dict[str, str] = {}
    missing: list[str] = []
    for environment_name, candidates in CREDENTIALS.items():
        value = next(
            (
                password
                for service, username in candidates
                if (password := keyring.get_password(service, username))
            ),
            None,
        )
        if value:
            values[environment_name] = value
        else:
            missing.append(environment_name)
    return values, missing


def validate_voice_credentials(values: dict[str, str]) -> list[str]:
    missing = [
        name
        for name in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")
        if name not in values
    ]
    if "OPENAI_API_KEY" not in values:
        missing.append("OPENAI_API_KEY (STT)")
    if not {"ANTHROPIC_API_KEY", "OPENAI_API_KEY"} & values.keys():
        missing.append("ANTHROPIC_API_KEY or OPENAI_API_KEY (LLM)")
    if not {"ELEVENLABS_API_KEY", "CARTESIA_API_KEY"} & values.keys():
        missing.append("ELEVENLABS_API_KEY or CARTESIA_API_KEY (TTS)")
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Start VoiceOS without writing provider secrets to .env."
    )
    parser.add_argument(
        "services",
        nargs="*",
        help="Compose services to start (default: the complete local stack).",
    )
    parser.add_argument("--build", action="store_true", help="Rebuild images before starting.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only report which environment names are available; never print values.",
    )
    args = parser.parse_args()

    values, missing = load_credentials()
    for name in CREDENTIALS:
        status = "available" if name in values else "missing"
        print(f"{name}: {status}")

    services = tuple(args.services) or DEFAULT_SERVICES
    if args.check:
        return 0 if not missing else 1

    if "agent-worker" in services:
        voice_missing = validate_voice_credentials(values)
        if voice_missing:
            print(
                "Cannot start agent-worker; missing: " + ", ".join(voice_missing),
                file=sys.stderr,
            )
            return 2

    command = [
        "docker",
        "compose",
        "--project-directory",
        str(ROOT),
        "-f",
        str(COMPOSE_FILE),
        "up",
        "-d",
    ]
    if args.build:
        command.append("--build")
    command.extend(services)

    child_environment = os.environ.copy()
    child_environment.update(values)
    completed = subprocess.run(command, cwd=ROOT, env=child_environment, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
