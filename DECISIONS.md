# Decisions

- 2026-08-17: External providers are accessed through typed adapters so local development and CI use deterministic fakes without credentials.
- 2026-08-17: The first migration uses SQL for exhaustive schema/RLS coverage; application models are added per endpoint to keep runtime code small.
- 2026-08-17: The embeddable widget uses a framework-free TypeScript build to stay below the 60 KB gzip target.
- 2026-08-22: Voice catalog and greeting previews use `GET /v1/voices` and `POST /v1/voices/{voice_id}/preview`; the API proxies ElevenLabs so provider credentials never reach the browser and returns an explicit unconfigured state in local/CI environments.
