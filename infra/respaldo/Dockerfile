# Respaldo automático de MongoDB: volcado diario comprimido, rotación y copia externa opcional.
FROM mongo:8.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends rclone tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY respaldar.sh restaurar.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/respaldar.sh /usr/local/bin/restaurar.sh

VOLUME /respaldos
ENTRYPOINT ["/usr/local/bin/respaldar.sh"]
