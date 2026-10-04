FROM ubuntu:24.04 AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends python3.12 python3.12-venv ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY pyproject.toml uv.lock ./
COPY src ./src
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_LINK_MODE=copy
RUN uv sync --locked --no-dev --no-editable --extra runtime --extra data

FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 python3.12-venv python3-uno libreoffice-calc libreoffice-writer \
    nodejs npm curl ca-certificates fonts-liberation fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /opt/venv /opt/venv
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /usr/local/bin/uv
ENV PATH=/opt/venv/bin:$PATH PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
RUN uv pip install --python /usr/bin/python3 --system --break-system-packages unoserver==3.4 \
    && npm install --global @openai/codex@0.160.0 \
    && python -m playwright install --with-deps chromium \
    && npm cache clean --force \
    && userdel ubuntu && useradd --uid 1000 --create-home --shell /bin/bash agent \
    && mkdir -p /home/agent/work/firms /home/agent/work/.agents /home/agent/work/.codex \
        /home/agent/work/deals /home/agent/work/memory /home/agent/work/outbox /home/agent/work/scratch
COPY src/cre_brain/sandbox/files.py /opt/cre-transfer.py
RUN chmod 0644 /opt/cre-transfer.py
ENV HOME=/home/agent TMPDIR=/home/agent/work/scratch \
    CODEX_HOME=/home/agent/work/scratch/codex PYTHONDONTWRITEBYTECODE=1
WORKDIR /home/agent/work
USER 1000:1000
CMD ["sleep", "infinity"]
