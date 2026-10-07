FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 iptables util-linux ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1001 egress && useradd --uid 1001 --gid 1001 egress
COPY src/cre_brain/sandbox/proxy.py /opt/proxy.py
COPY docker/egress/start.sh /opt/start.sh
RUN chmod 0644 /opt/proxy.py /opt/start.sh
ENV PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["/bin/sh", "/opt/start.sh"]
