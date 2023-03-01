# Docker container for local testing

## Prerequisites
You will need a `docker` with docker compose plugin installed in order to use run service locally

## Running on Linux
Start service by navigating to `local` directory and running:
```
docker compose up --build
```

Remove service by running:
```
docker compose down
```

## Testing service
Add sample data:
```
curl -XPOST -d '{"organization":{"code":"00000000","name":"Org 0"},"person":{"code":"12345678901","first_name":"Firstname","last_name":"Lastname"},"right":{"right_type":"RIGHT1"}}' -H 'X-Ssl-Client-S-Dn: OU=XTSS,O=RIA,C=EE' localhost:5080/set-right
```

Read sample data:
```
curl -XPOST -d '{}' -H 'X-Ssl-Client-S-Dn: OU=XTSS,O=RIA,C=EE' localhost:5080/rights
```
