FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY telematics/requirements.txt ./telematics/requirements.txt
RUN pip install --no-cache-dir -r telematics/requirements.txt

COPY telematics ./telematics

RUN useradd --create-home --shell /usr/sbin/nologin telematics
USER telematics

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import socket; s=socket.create_connection(('127.0.0.1', 8002), 3); s.close()"

CMD ["python", "-m", "telematics.listener"]