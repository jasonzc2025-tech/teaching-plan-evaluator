FROM registry.cn-hangzhou.aliyuncs.com/acs/python:3.11

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ \
    && pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt \
    && pip install "gunicorn>=21.2" "gevent>=23.9"

COPY . .

RUN mkdir -p /app/instance /app/data/uploads

RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

CMD ["gunicorn", \
     "-w", "2", \
     "-k", "gevent", \
     "--worker-connections", "50", \
     "-b", "0.0.0.0:5000", \
     "--timeout", "300", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "wsgi:application"]
