FROM node:22-slim AS frontend-build

WORKDIR /app/frontend
RUN corepack enable && corepack prepare pnpm@11.9.0 --activate

COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
RUN pnpm run build


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY scripts/ scripts/
COPY application.py ./
COPY --from=frontend-build /app/frontend/dist frontend/dist

EXPOSE 10000

CMD ["sh", "-c", "gunicorn application:application --bind 0.0.0.0:${PORT:-10000} --workers 2 --threads 2"]
