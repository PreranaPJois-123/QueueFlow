-- One-off upgrade for a database created by QueueFlow 1.x (everything owned by
-- the superuser). Run as the superuser AFTER creating queueflow_app:
--   docker compose exec -T -e APP_DB_PASSWORD postgres sh /docker-entrypoint-initdb.d/01-app-role.sh
--   docker compose exec -T postgres psql -U queueflow -d queueflow < docker/postgres/upgrade-existing-volume.sql
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('ALTER TABLE public.%I OWNER TO queueflow_app', r.tablename);
  END LOOP;
  FOR r IN SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = 'public' LOOP
    EXECUTE format('ALTER SEQUENCE public.%I OWNER TO queueflow_app', r.sequence_name);
  END LOOP;
  FOR r IN SELECT t.typname FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
           WHERE n.nspname = 'public' AND t.typtype = 'e' LOOP
    EXECUTE format('ALTER TYPE public.%I OWNER TO queueflow_app', r.typname);
  END LOOP;
END $$;
