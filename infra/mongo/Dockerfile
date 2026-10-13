# MongoDB con replica set de un nodo (requisito para transacciones) y autenticación.
# Se usa igual en local (docker compose) y en el VPS (Easypanel).
FROM mongo:8.0

COPY iniciar.sh /usr/local/bin/iniciar-geifem.sh
RUN chmod +x /usr/local/bin/iniciar-geifem.sh

HEALTHCHECK --interval=10s --timeout=5s --start-period=40s --retries=10 \
  CMD mongosh --quiet --host 127.0.0.1 -u "$MONGO_INITDB_ROOT_USERNAME" -p "$MONGO_INITDB_ROOT_PASSWORD" \
      --authenticationDatabase admin --eval "rs.status().ok" | grep -q '^1$'

ENTRYPOINT ["/usr/local/bin/iniciar-geifem.sh"]
