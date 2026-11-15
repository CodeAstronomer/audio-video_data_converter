FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WORK_DIR=/tmp/avdc \
    MAX_UPLOAD_MB=2048

WORKDIR /srv
COPY requirements.txt requirements-dev.txt ./
ARG WITH_TESTS=0
RUN pip install --no-cache-dir -r requirements.txt \
 && if [ "$WITH_TESTS" = "1" ]; then pip install --no-cache-dir -r requirements-dev.txt; fi

COPY app ./app
COPY tests ./tests

RUN useradd --system --uid 10001 --home /srv avdc
USER avdc

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/api/config')" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-server-header"]
