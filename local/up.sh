#!/bin/bash

set -e
set -x

bash prepare.sh
docker-compose build
docker-compose up -d
