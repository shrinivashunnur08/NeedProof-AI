
# Stage 1: Build the React application.
FROM node:22-alpine AS frontend-build

WORKDIR /web

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# Stage 2: Run FastAPI and serve the React build.
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /srv/backend

COPY backend/requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt
# Google Cloud clients used by the google_full profile (BigQuery analytics, Cloud Storage photos).
RUN pip install --no-cache-dir "google-cloud-bigquery>=3.25,<4" "google-cloud-storage>=2.18,<4"

COPY backend/ ./

# Compiled frontend; no Node.js runtime is needed.
COPY --from=frontend-build /web/dist /srv/frontend_dist

EXPOSE 8080

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
