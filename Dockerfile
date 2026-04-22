FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl wget ca-certificates build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir matrix-nio pytest

RUN useradd -m -s /bin/bash plato
RUN mkdir -p /data && chown plato:plato /data
WORKDIR /app

COPY server.py agent.py .
COPY start.sh .
RUN chmod +x start.sh

USER plato
EXPOSE 8847
VOLUME ["/data"]

CMD ["./start.sh"]
