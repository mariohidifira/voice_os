"""Run the local Phase 4 acceptance flow and write a machine-readable report."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "apps" / "web"
API_DIR = ROOT / "apps" / "api"
TESTS_DIR = ROOT / "tests"
SCRIPTS_DIR = ROOT / "scripts"
REPORT_PATH = ROOT / "reports" / "phase4-local-acceptance.json"
TODAY = "2026-08-25"


@dataclass
class StepResult:
    name: str
    ok: bool
    command: str
    exit_code: int
    output: str

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "ok": self.ok,
            "command": self.command,
            "exit_code": self.exit_code,
            "output": _summarize_output(self.name, self.ok, self.output),
        }
        if self.name == "phase4_dashboard_e2e" and not self.ok:
            blocker = _diagnose_playwright_failure(self.output)
            if blocker is not None:
                payload["environment_blocker"] = blocker
        return payload


def _summarize_output(name: str, ok: bool, output: str) -> str:
    if not output:
        return ""
    if ok and name in {
        "whatsapp_gateway_stub",
        "whatsapp_handoff_api",
        "phase4_handoff_reproducer",
        "phase4_dashboard_e2e",
    }:
        return "[step output omitted on success]"
    return output


def _diagnose_playwright_failure(output: str) -> dict[str, object] | None:
    text = output or ""
    if "EPERM" in text and "lstat 'G:\\" in text:
        return {
            "type": "node_g_drive_eperm",
            "detail": "Node/Playwright cannot resolve G:\\ in this executor",
            "current_gap": "phase4_playwright_executor_blocked",
        }
    return None


def _healthcheck(url: str, attempts: int = 45, sleep_s: float = 1.0) -> bool:
    for _ in range(attempts):
        try:
            with urlopen(url, timeout=5) as response:  # noqa: S310
                if response.status == 200:
                    return True
        # A dev server can accept the TCP connection before it is ready to
        # return an HTTP response.  Treat that transient timeout like any
        # other readiness failure and keep polling until the deadline.
        except (TimeoutError, URLError):
            pass
        time.sleep(sleep_s)
    return False


def _run_step(name: str, command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> StepResult:
    completed = subprocess.run(  # noqa: S603
        command,
        cwd=str(cwd or ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    return StepResult(
        name=name,
        ok=completed.returncode == 0,
        command=" ".join(command),
        exit_code=completed.returncode,
        output=output.strip(),
    )


def _run_playwright_step(playwright_bin: str, env: dict[str, str]) -> StepResult:
    command = [playwright_bin, "test", "e2e/phase4-whatsapp-simulator.spec.ts", "--reporter=line"]
    direct = _run_step("phase4_dashboard_e2e", command, cwd=WEB_DIR, env=env)
    if direct.ok:
        return direct
    if os.name != "nt":
        return direct
    outputs = [("direct", direct)]
    fallback_command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / "run_phase4_playwright.ps1")]
    fallback = _run_step("phase4_dashboard_e2e", fallback_command, cwd=ROOT, env=env)
    outputs.append(("powershell_fallback", fallback))
    if fallback.ok:
        return fallback
    fallback.output = "\n\n".join(
        f"--- {label} ---\n{result.output}".strip()
        for label, result in outputs
        if result.output
    ).strip()
    return fallback


def _node_bin(name: str) -> str:
    if os.name == "nt":
        candidate = shutil.which(f"{name}.cmd")
        if candidate:
            return candidate
    candidate = shutil.which(name)
    if candidate:
        return candidate
    raise FileNotFoundError(f"Unable to resolve executable for {name!r}")


def _web_bin(name: str) -> str:
    candidates = []
    if os.name == "nt":
        candidates.extend(
            [
                WEB_DIR / "node_modules" / ".bin" / f"{name}.cmd",
                ROOT / "node_modules" / ".bin" / f"{name}.cmd",
            ]
        )
    else:
        candidates.extend(
            [
                WEB_DIR / "node_modules" / ".bin" / name,
                ROOT / "node_modules" / ".bin" / name,
            ]
        )
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return _node_bin(name)


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        process.terminate()
    else:
        process.send_signal(signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main() -> int:
    next_bin = _web_bin("next")
    playwright_bin = _web_bin("playwright")
    report_env = os.environ.copy()
    report_env.update(
        {
            "APP_ENV": "dev",
            "APP_BASE_URL": "http://localhost:3100",
            "AUTH_URL": "http://localhost:3100",
            "AUTH_TRUST_HOST": "true",
            "AUTH_SECRET": "dev-secret-change-me-at-least-32-bytes",
            "DATABASE_URL": "postgresql+asyncpg://voiceos:voiceos@127.0.0.1:5432/voiceos",
            "EMAIL_MOCK_URL": "http://localhost:9000/email",
            "API_INTERNAL_URL": "http://localhost:8005",
            "JWT_ISSUER": "voiceos",
            "JWT_AUDIENCE": "voiceos-api",
            "INTERNAL_API_TOKEN": "dev-internal-token",
            "LIVEKIT_URL": "wss://example.invalid",
            "LIVEKIT_API_KEY": "dev",
            "LIVEKIT_API_SECRET": "dev",
            "PLAYWRIGHT_EXTERNAL_SERVER": "1",
            "PLAYWRIGHT_BASE_URL": "http://localhost:3100",
        }
    )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    steps: list[StepResult] = []
    server_readiness: dict[str, bool] = {}

    with ExitStack() as stack:
        api = subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                "-m",
                "uvicorn",
                "voiceos_api.main:app",
                "--app-dir",
                str(API_DIR),
                "--host",
                "127.0.0.1",
                "--port",
                "8005",
            ],
            cwd=str(ROOT),
            env=report_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        stack.callback(_terminate_process, api)

        mock = subprocess.Popen(  # noqa: S603
            [sys.executable, "-m", "uvicorn", "apps.mock.main:app", "--host", "127.0.0.1", "--port", "9000"],
            cwd=str(ROOT),
            env=report_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        stack.callback(_terminate_process, mock)

        web = subprocess.Popen(  # noqa: S603
            [next_bin, "dev", "--port", "3100"],
            cwd=str(WEB_DIR),
            env=report_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        stack.callback(_terminate_process, web)

        server_readiness = {
            "web_login": _healthcheck("http://localhost:3100/login"),
            "api_health": _healthcheck("http://localhost:8005/health"),
            "mock_health": _healthcheck("http://localhost:9000/health"),
        }

        if not all(server_readiness.values()):
            report = {
                "date": TODAY,
                "scope": "phase4_local_acceptance",
                "passed": False,
                "server_readiness": server_readiness,
                "steps": [],
            }
            REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(report, indent=2))
            return 1

        steps.append(
            _run_step(
                "whatsapp_gateway_stub",
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    str(TESTS_DIR / "test_whatsapp_gateway.py"),
                ],
                env=report_env,
            )
        )
        steps.append(
            _run_step(
                "whatsapp_handoff_api",
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    str(TESTS_DIR / "test_api.py"),
                    "-k",
                    "whatsapp_handoff_route_sends_operator_message or whatsapp_handoff_route_accepts_string_secret_id",
                ],
                env=report_env,
            )
        )
        steps.append(
            _run_step(
                "phase4_handoff_reproducer",
                [sys.executable, str(SCRIPTS_DIR / "repro_phase4_handoff.py")],
                env=report_env,
            )
        )
        steps.append(
            _run_playwright_step(playwright_bin, report_env)
        )

    passed = all(step.ok for step in steps) and all(server_readiness.values())
    report = {
        "date": TODAY,
        "scope": "phase4_local_acceptance",
        "passed": passed,
        "server_readiness": server_readiness,
        "steps": [step.to_dict() for step in steps],
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
