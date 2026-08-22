import pytest

from scripts.conversation_suite import load_cases, run_suite


def test_conversation_case_minimums_and_unique_ids() -> None:
    for mode, minimum in (("text", 25), ("audio", 10)):
        cases = load_cases(mode)
        assert len(cases) >= minimum
        assert len({case["id"] for case in cases}) == len(cases)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["text", "audio"])
async def test_conversation_acceptance_suite(mode: str) -> None:
    report = await run_suite(mode)
    assert report["pass_rate"] >= 0.95, report["failures"]
    assert report["ttfb_p95_ms"] < 1500

