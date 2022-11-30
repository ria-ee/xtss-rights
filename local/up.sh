#!/bin/bash

set -e
set -x

bash prepare.sh
docker compose build
docker compose up -d

# Giving DB some time to start before liquibase step
for i in {1..30}; do
  # NB! Checking when db start listening on non-loopback IP - "db"
  docker exec local-db-1 pg_isready -h db && break
  sleep 1
done

docker run --rm --net local_default -v $(pwd)/../liquibase:/liquibase/changelog liquibase/liquibase --defaultsFile=/liquibase/changelog/liquibase.local.properties update
