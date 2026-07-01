FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./bot/
COPY infrastructure/ ./infrastructure/
COPY alembic.ini .

RUN mkdir -p /app/media

CMD ["python", "-m", "bot.main"]
