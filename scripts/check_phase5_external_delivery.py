from __future__ import annotations

import argparse
import json
import os
import ssl
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPORT = REPO_ROOT / "reports" / "phase5-external-delivery.json"
DEFAULT_HOSTED_ASSET = REPO_ROOT / "apps" / "web" / "public" / "voiceos.js"
DEFAULT_SIZE_ARTIFACT = REPO_ROOT / "packages" / "widget" / "dist" / "size.json"
MAX_GZIP_BYTES = 60 * 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the externally reachable hosted widget asset for Phase 5."
    )
    parser.add_argument("--base-url", default=None, help="Base URL where /voiceos.js is served")
    parser.add_argument("--asset-path", default="/voiceos.js", help="Hosted asset path")
    parser.add_argument("--expected-host", default=None, help="Expected hostname for the base URL")
    parser.add_argument(
        "--lighthouse-report",
        default=None,
        help="Optional path to a Lighthouse JSON report to retain as closeout evidence",
    )
    parser.add_argument(
        "--report",
        default=str(DEFAULT_REPORT),
        help="Output report path",
    )
    return parser.parse_args()


def step(name: str, ok: bool, detail: str, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {"name": name, "ok": ok, "detail": detail}
    payload.update(extra)
    return payload


def get_base_url(cli_value: str | None) -> str:
    if cli_value:
        return cli_value
    env_value = os.environ.get("VOICEOS_HOST_BASE_URL") or os.environ.get(
        "VOICEOS_PUBLIC_BASE_URL"
    )
    if env_value:
        return env_value
    raise SystemExit("Provide --base-url or set VOICEOS_HOST_BASE_URL / VOICEOS_PUBLIC_BASE_URL.")


def fetch_asset(url: str) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "voiceos-phase5-external-delivery-check/1.0"},
    )
    context = ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=20, context=context) as response:
        body = response.read()
        return {
            "url": url,
            "status": getattr(response, "status", response.getcode()),
            "content_type": response.headers.get("Content-Type"),
            "content_length_header": response.headers.get("Content-Length"),
            "bytes": len(body),
            "sample_prefix": body[:32].decode("utf-8", errors="replace"),
        }


def main() -> int:
    args = parse_args()
    base_url = get_base_url(args.base_url).rstrip("/")
    asset_url = urljoin(base_url + "/", args.asset_path.lstrip("/"))
    parsed = urlparse(base_url)

    steps: list[dict[str, object]] = [
        step(
            "base_url_uses_https",
            parsed.scheme == "https",
            "base URL should use HTTPS so custom-domain TLS is exercised",
            base_url=base_url,
        ),
        step(
            "base_url_has_hostname",
            bool(parsed.hostname),
            "base URL should contain a hostname",
            hostname=parsed.hostname,
        ),
    ]

    if args.expected_host:
        steps.append(
            step(
                "expected_hostname_match",
                parsed.hostname == args.expected_host,
                "base URL hostname should match the expected custom/staging domain",
                expected_host=args.expected_host,
                actual_host=parsed.hostname,
            )
        )

    hosted_asset_exists = DEFAULT_HOSTED_ASSET.is_file()
    size_artifact_exists = DEFAULT_SIZE_ARTIFACT.is_file()
    steps.append(
        step(
            "local_hosted_asset_present",
            hosted_asset_exists,
            "apps/web/public/voiceos.js should exist before claiming external delivery",
            path=str(DEFAULT_HOSTED_ASSET),
        )
    )
    steps.append(
        step(
            "local_size_artifact_present",
            size_artifact_exists,
            "packages/widget/dist/size.json should exist before claiming external delivery",
            path=str(DEFAULT_SIZE_ARTIFACT),
        )
    )

    size_payload: dict[str, object] | None = None
    if size_artifact_exists:
        size_payload = json.loads(DEFAULT_SIZE_ARTIFACT.read_text(encoding="utf-8"))
        browser_bundle = (
            size_payload.get("browser_bundle", {})
            if isinstance(size_payload.get("browser_bundle"), dict)
            else {}
        )
        gzip_bytes = browser_bundle.get("gzip_bytes")
        gzip_budget_bytes = browser_bundle.get("gzip_budget_bytes")
        within_budget = isinstance(gzip_bytes, int) and gzip_bytes <= MAX_GZIP_BYTES
        steps.append(
            step(
                "bundle_within_budget",
                within_budget,
                "browser bundle should stay within the <= 60 KB gzip budget",
                gzip_bytes=gzip_bytes,
                gzip_budget_bytes=gzip_budget_bytes,
            )
        )

    fetch_result: dict[str, object] | None = None
    fetch_error: str | None = None
    try:
        fetch_result = fetch_asset(asset_url)
        steps.extend(
            [
                step(
                    "hosted_asset_http_200",
                    int(fetch_result["status"]) == 200,
                    "hosted /voiceos.js should return HTTP 200",
                    **fetch_result,
                ),
                step(
                    "hosted_asset_non_empty",
                    int(fetch_result["bytes"]) > 0,
                    "hosted /voiceos.js should return a non-empty response body",
                    **fetch_result,
                ),
                step(
                    "hosted_asset_content_type_js",
                    "javascript" in str(fetch_result.get("content_type") or "").lower()
                    or "ecmascript" in str(fetch_result.get("content_type") or "").lower()
                    or "text/plain" in str(fetch_result.get("content_type") or "").lower(),
                    "hosted /voiceos.js should expose a JavaScript-compatible content type",
                    **fetch_result,
                ),
            ]
        )
    except (urllib.error.URLError, TimeoutError, ssl.SSLError) as exc:
        fetch_error = str(exc)
        steps.append(
            step(
                "hosted_asset_fetchable",
                False,
                "hosted /voiceos.js should be externally reachable over HTTPS",
                url=asset_url,
                error=fetch_error,
            )
        )

    lighthouse_summary: dict[str, object] | None = None
    if args.lighthouse_report:
        lighthouse_path = Path(args.lighthouse_report).expanduser().resolve()
        lighthouse_exists = lighthouse_path.is_file()
        steps.append(
            step(
                "lighthouse_report_present",
                lighthouse_exists,
                "optional Lighthouse JSON report should exist when provided",
                path=str(lighthouse_path),
            )
        )
        if lighthouse_exists:
            lighthouse_payload = json.loads(lighthouse_path.read_text(encoding="utf-8"))
            categories = lighthouse_payload.get("categories", {})
            performance = (
                categories.get("performance", {}).get("score")
                if isinstance(categories, dict)
                else None
            )
            lighthouse_summary = {
                "path": str(lighthouse_path),
                "performance_score": performance,
            }

    passed = all(item["ok"] for item in steps)
    report = {
        "scope": "phase5_external_delivery",
        "status_date": "2026-08-25",
        "base_url": base_url,
        "asset_url": asset_url,
        "passed": passed,
        "steps": steps,
        "size_artifact": size_payload,
        "fetch_result": fetch_result,
        "fetch_error": fetch_error,
        "lighthouse_summary": lighthouse_summary,
    }

    report_path = Path(args.report).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
