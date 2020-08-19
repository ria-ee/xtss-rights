# Docker container for local testing

## Prerequisites
You will need a `docker` and `docker-compose` installed in order to use run service locally

## Running on Linux
Start service by navigating to `local` directory and running:
```
./up.sh
```

Remove service by running:
```
./down.sh
```

## Running on other platforms
Create a directory `local/files`.

Copy files `db.sql requirements.txt rights.py server.py` to `local/files` directory.

Build and run service:
```
docker-compose build
docker-compose up -d
```

Remove service by running:
```
docker-compose down
```

## Testing service
Add sample data:
```
curl -XPOST -d '{"organization":{"code":"00000000","name":"Org 0"},"person":{"code":"12345678901","first_name":"Firstname","last_name":"Lastname"},"right":{"right_type":"RIGHT1"}}' localhost:5080/set-right
```

Read sample data:
```
curl -XPOST -d '{}' localhost:5080/rights
```
