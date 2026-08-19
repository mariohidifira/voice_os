FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY apps/api/voiceos_api apps/api/voiceos_api
COPY packages/shared-py/voiceos_shared packages/shared-py/voiceos_shared
RUN pip install --no-cache-dir .
COPY . .
ENV PYTHONPATH=/app/apps/api:/app/packages/shared-py
