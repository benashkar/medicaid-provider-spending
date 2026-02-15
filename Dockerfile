FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY db/ ./db/

EXPOSE 10000

CMD ["gunicorn", "app:create_app()", "--bind", "0.0.0.0:10000", "--workers", "2"]
