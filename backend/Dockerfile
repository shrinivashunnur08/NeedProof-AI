FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-cloud.txt ./requirements-cloud.txt
RUN pip install --no-cache-dir -r requirements-cloud.txt
COPY app/ ./app/
ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn app.cloud_decision_api:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]
