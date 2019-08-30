CREATE SCHEMA IF NOT EXISTS rights;

DROP TABLE IF EXISTS rights.change_log;
DROP TABLE IF EXISTS rights.right;
DROP TABLE IF EXISTS rights.organization;
DROP TABLE IF EXISTS rights.person;

CREATE TABLE rights.change_log
(
    id bigserial PRIMARY KEY,
    table_name character varying NOT NULL,
    record_id bigint NOT NULL,
    operation character varying NOT NULL,
    old_value text,
    new_value text,
    created timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE rights.organization
(
    id bigserial PRIMARY KEY,
    code character varying NOT NULL UNIQUE,
    name character varying,
    created timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_modified timestamp without time zone DEFAULT CURRENT_TIMESTAMP

);

CREATE TABLE rights.person
(
    id bigserial PRIMARY KEY,
    code character varying NOT NULL UNIQUE,
    first_name character varying,
    last_name character varying,
    created timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_modified timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE rights.right
(
    id bigserial PRIMARY KEY,
    person_id bigint NOT NULL,
    organization_id bigint NOT NULL,
    right_type character varying NOT NULL,
    valid_from timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_to timestamp without time zone,
    created timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_modified timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT rights_organization_id_fkey FOREIGN KEY (organization_id)
        REFERENCES rights.organization (id) MATCH SIMPLE
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    CONSTRAINT rights_person_id_fkey FOREIGN KEY (person_id)
        REFERENCES rights.person (id) MATCH SIMPLE
        ON UPDATE CASCADE
        ON DELETE CASCADE
);



CREATE OR REPLACE FUNCTION rights.logger() RETURNS TRIGGER AS $body$
DECLARE
    v_old_data TEXT;
    v_new_data TEXT;
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        v_old_data := ROW(OLD.*);
        v_new_data := ROW(NEW.*);
        INSERT INTO rights.change_log (table_name, record_id, operation, old_value, new_value)
        VALUES (TG_TABLE_SCHEMA::TEXT||'.'||TG_TABLE_NAME::TEXT, OLD.id, TG_OP, v_old_data, v_new_data);
        RETURN NEW;
    ELSIF (TG_OP = 'DELETE') THEN
        v_old_data := ROW(OLD.*);
        INSERT INTO rights.change_log (table_name, record_id, operation, old_value, new_value)
        VALUES (TG_TABLE_SCHEMA::TEXT||'.'||TG_TABLE_NAME::TEXT, OLD.id, TG_OP, v_old_data, NULL);
        RETURN OLD;
    ELSIF (TG_OP = 'INSERT') THEN
        v_new_data := ROW(NEW.*);
        INSERT INTO rights.change_log (table_name, record_id, operation, old_value, new_value)
        VALUES (TG_TABLE_SCHEMA::TEXT||'.'||TG_TABLE_NAME::TEXT, NEW.id, TG_OP, NULL, v_new_data);
        RETURN NEW;
    ELSE
        RAISE WARNING '[rights.logger] - Other action occurred: %, at %',TG_OP,now();
        RETURN NULL;
    END IF;

EXCEPTION
    WHEN OTHERS THEN
        RAISE WARNING '[rights.logger] - Other error occurred - SQLSTATE: %, SQLERRM: %',SQLSTATE,SQLERRM;
        RETURN NULL;
END;
$body$
LANGUAGE plpgsql
SECURITY DEFINER;

DROP TRIGGER IF EXISTS logger on rights.organization;
CREATE TRIGGER logger
AFTER INSERT OR UPDATE OR DELETE ON rights.organization
FOR EACH ROW EXECUTE PROCEDURE rights.logger();

DROP TRIGGER IF EXISTS logger on rights.person;
CREATE TRIGGER logger
AFTER INSERT OR UPDATE OR DELETE ON rights.person
FOR EACH ROW EXECUTE PROCEDURE rights.logger();

DROP TRIGGER IF EXISTS logger on rights.right;
CREATE TRIGGER logger
AFTER INSERT OR UPDATE OR DELETE ON rights.right
FOR EACH ROW EXECUTE PROCEDURE rights.logger();

CREATE ROLE rights_app WITH LOGIN;
GRANT CONNECT ON DATABASE rights TO rights_app;
GRANT USAGE ON SCHEMA rights TO rights_app;
GRANT INSERT ON rights.change_log TO rights_app;
GRANT SELECT, INSERT, UPDATE ON rights.organization TO rights_app;
GRANT SELECT, INSERT, UPDATE ON rights.person TO rights_app;
GRANT SELECT, INSERT, UPDATE ON rights."right" TO rights_app;
GRANT USAGE ON SEQUENCE rights.organization_id_seq TO rights_app;
GRANT USAGE ON SEQUENCE rights.person_id_seq TO rights_app;
GRANT USAGE ON SEQUENCE rights.right_id_seq TO rights_app;
