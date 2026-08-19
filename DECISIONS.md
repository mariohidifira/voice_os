# Decisions

- 2026-08-17: External providers are accessed through typed adapters so local development and CI use deterministic fakes without credentials.
- 2026-08-17: The first migration uses SQL for exhaustive schema/RLS coverage; application models are added per endpoint to keep runtime code small.
- 2026-08-17: The embeddable widget uses a framework-free TypeScript build to stay below the 60 KB gzip target.

