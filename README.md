# Rights service for X-tee self service portal

## DB initialization

Create database:
```bash
sudo -u postgres createdb rights
```

Run DB initialization SQL:
```bash
sudo -u postgres psql -f db.sql rights
```

Create a password for "rights_app"
```bash
sudo -u postgres psql -c "ALTER USER rights_app WITH PASSWORD '<PASSWORD>'" rights
```
