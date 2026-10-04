FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 nodejs npm ca-certificates \
    && npm install --global @openai/codex@0.160.0 \
    && npm cache clean --force \
    && rm -rf /var/lib/apt/lists/* \
    && userdel ubuntu && useradd --uid 1000 --create-home --shell /bin/bash agent \
    && mkdir -p /home/agent/input /home/agent/work/scratch \
    && ln -s /usr/bin/python3 /usr/local/bin/python
COPY src/cre_brain/sandbox/files.py /opt/cre-transfer.py
RUN chmod 0644 /opt/cre-transfer.py
ENV HOME=/home/agent TMPDIR=/home/agent/work/scratch \
    CODEX_HOME=/home/agent/work/scratch/codex PYTHONDONTWRITEBYTECODE=1
WORKDIR /home/agent/work
USER 1000:1000
CMD ["sleep", "infinity"]
