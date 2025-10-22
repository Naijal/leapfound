
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates tini \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && pip install -r /app/requirements.txt
COPY . /app

ENV PORT=8000
EXPOSE 8000
ENTRYPOINT ["/usr/bin/tini","--"]
CMD ["python","-m","uvicorn","main:app","--host","0.0.0.0","--port","8000"]
