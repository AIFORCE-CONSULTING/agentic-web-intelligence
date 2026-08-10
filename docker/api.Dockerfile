FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN useradd --create-home --uid 10001 platform

COPY apps/api/requirements.lock ./requirements.lock
COPY apps/api/app ./app

RUN pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements.lock

USER platform

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
