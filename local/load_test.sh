#!/usr/bin/env bash

for thread in {1..20}; do
  for repeat in {1..100}; do
    # Get status
    curl -s localhost:5080/status > /dev/null
    # Set right
    curl -s -XPOST -d '{"organization":{"code":"'"${thread}"'","name":"Org 0"},"person":{"code":"'"${repeat}"'","first_name":"Firstname","last_name":"Lastname"},"right":{"right_type":"RIGHT1"}}' -H 'X-Ssl-Client-S-Dn: OU=XTSS,O=RIA,C=EE' localhost:5080/set-right > /dev/null
    # Get rights
    curl -s -XPOST -d '{"organizations": ["'"${thread}"'"],"persons": ["'"${repeat}"'"],"only_valid": false,"limit": 2}' -H 'X-Ssl-Client-S-Dn: OU=XTSS,O=RIA,C=EE' localhost:5080/rights > /dev/null
  done &
done
wait
