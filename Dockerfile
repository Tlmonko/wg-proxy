FROM python:3.12-slim

ARG BOT_REPO=https://github.com/WoodieDudy/wg-vpn-tg-bot.git
ARG BOT_REF=main

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    wireguard-tools \
    iptables \
    iproute2 \
    procps \
    socat \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN git clone --depth 1 --branch "${BOT_REF}" "${BOT_REPO}" /app

RUN if [ -f requirements.txt ]; then \
      pip install --no-cache-dir -r requirements.txt; \
    elif [ -f pyproject.toml ]; then \
      pip install --no-cache-dir .; \
    fi

CMD ["python", "main.py"]
