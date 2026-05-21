FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . /app

RUN mkdir -p /app/out /workspace

EXPOSE 8765

CMD ["python", "-m", "code_study_notes", "web", "--host", "0.0.0.0", "--port", "8765", "--out", "/app/out"]
