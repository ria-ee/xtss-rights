CREATE ROLE rights_app WITH LOGIN;
ALTER USER rights_app WITH PASSWORD 'password';
GRANT CONNECT ON DATABASE db_rights TO rights_app;
