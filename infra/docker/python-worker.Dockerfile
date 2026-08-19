FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY apps/api/voiceos_api apps/api/voiceos_api
COPY apps/agent-worker/voiceos_voice apps/agent-worker/voiceos_voice
COPY packages/shared-py/voiceos_shared packages/shared-py/voiceos_shared
RUN pip install --no-cache-dir .
COPY . .
ENV PYTHONPATH=/app/apps/api:/app/apps/agent-worker:/app/packages/shared-py
