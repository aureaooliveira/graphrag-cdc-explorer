FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    GRAPHRAG_ROOT=/data \
    STORAGE_DIR=/storage

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
