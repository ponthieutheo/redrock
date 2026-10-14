# Une machine Linux neuve : Ubuntu 24.04 + Docker (paquets de la distribution), comme chez un utilisateur
FROM ubuntu:24.04
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      docker.io docker-compose-v2 git curl ca-certificates python3 cron qrencode openssl iptables sudo bsdutils \
    && rm -rf /var/lib/apt/lists/* && usermod -aG docker ubuntu
COPY start.sh /start.sh
CMD ["sh", "/start.sh"]
