#!/bin/sh
# Runs once, when the PostgreSQL volume is first initialised (docker-entrypoint-initdb.d).
# Creates the extensions as the superuser, then a least-privilege application
# role that owns the database schema but cannot create roles or databases.
set -eu
psql -v ON_ERROR_STOP=1 -v app_password="$APP_DB_PASSWORD" --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'EOSQL'
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS btree_gist;
SELECT format('CREATE ROLE queueflow_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %L', :'app_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'queueflow_app') \gexec
GRANT CONNECT, TEMPORARY ON DATABASE queueflow TO queueflow_app;
ALTER SCHEMA public OWNER TO queueflow_app;
EOSQL
