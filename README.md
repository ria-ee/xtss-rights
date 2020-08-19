# Rights service for X-tee self service portal

This simple service is used by X-tee self service portal to store user rights. You can use Docker to [test service locally](local/README.md).

## Install dependencies

Python virtual environment is an easy way to manage application dependencies. You will need to install support for python venv:
```bash
sudo apt-get install python3-venv
```

Application uses PostgreSQL as a database and Nginx for securing connections with TLS. Install them with a command:
```bash
sudo apt-get install postgresql nginx
```

## Create application user

```bash
sudo useradd xtss-rights
```

## Prepare application files

Create an application directory `/opt/xtss-rights`:
```bash
sudo mkdir -p /opt/xtss-rights
sudo chown -R xtss-rights:xtss-rights /opt/xtss-rights
```

Copy application files `rights.py`, `server.py`, `db.sql`, `db_user.sql` to directory `/opt/xtss-rights`.

Create a directory for logs:
```bash
sudo mkdir -p /var/log/xtss-rights
sudo chown -R xtss-rights:xtss-rights /var/log/xtss-rights
```

## Installing python venv

Install required python modules into venv using user `xtss-rights`:
```bash
sudo su - xtss-rights
cd /opt/xtss-rights
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Create a configuration file `/opt/xtss-rights/config.json` using an example configuration file: [example-config.json](example-config.json).

Configuration parameters:
* `db_host` - database address;
* `db_port` - database port;
* `db_db` - database name;
* `db_user` - database user name;
* `db_pass` - database user password;
* `allow_all` - if "true" then disable certificate DN check, default value: "false";
* `allowed` - list of allowed certificate DN's.

## DB initialization

Create database:
```bash
sudo -u postgres createdb rights
```

Run DB initialization SQL:
```bash
sudo -u postgres psql -f db.sql rights
sudo -u postgres psql -f db_user.sql rights
```

Create a password for "rights_app"
```bash
sudo -u postgres psql -c "ALTER USER rights_app WITH PASSWORD '<PASSWORD>'" rights
```

## Configuring Systemd

Add service description `systemd/xtss-rights.service` to `/lib/systemd/system/xtss-rights.service`.

Then start service and enable automatic startup:
```bash
sudo systemctl daemon-reload
sudo systemctl start xtss-rights
sudo systemctl enable xtss-rights
```

## Configuring Nginx

Copy `nginx/xtss-rights.conf` under `/etc/nginx/sites-available/`

Create a certificate for Nginx:
```bash
sudo mkdir -p /etc/nginx/xtss-rights
cd /etc/nginx/xtss-rights
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout rights.key -out rights.crt
```

Make sure key is accessible to nginx:
```bash
sudo chmod 640 /etc/nginx/xtss-rights/rights.key
sudo chgrp www-data /etc/nginx/xtss-rights/rights.key
```

On client side (XTSS app):
```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout client.key -out client.crt 
```

Note that client DN should be added to the list of `allowed` DN's in the `/opt/xtss-rights/config.json` configuration file.

Copy client.crt to Rights service machine: `/etc/nginx/xtss-rights/client.crt`

Note that you can allow multiple clients (or nodes) by creating certificate bundle. That can be done by concatenating multiple client certificates into single `client.crt` file.

And restart Nginx:
```bash
sudo systemctl start
```

## Testing service

Copy nginx `rights.crt` to client machine. Then issue command to add sample data:
```
curl --cert client.crt --key client.key --cacert rights.crt -i -XPOST -d '{"organization":{"code":"00000000","name":"Org 0"},"person":{"code":"12345678901","first_name":"Firstname","last_name":"Lastname"},"right":{"right_type":"RIGHT1"}}' https://<xtss-rights.hostname>:5443/set-right
```

And then to read sample data:
```
curl --cert client.crt --key client.key --cacert rights.crt -i -XPOST -d '{}' https://<xtss-rights.hostname>:5443/rights
```

## API Status

API Status is available on `/status` endpoint. You can test that with curl:
```bash
curl -k https://<xtss-rights.hostname>:5443/status
```
