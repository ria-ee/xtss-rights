-- Making schema liquibase compatible and using "identity" instead of sequences.

ALTER TABLE rights.change_log
    ALTER COLUMN id DROP DEFAULT;
DROP SEQUENCE rights.change_log_id_seq;
ALTER TABLE rights.change_log
    ALTER COLUMN id SET DATA TYPE INT8;
ALTER TABLE rights.change_log
    ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY;
ALTER TABLE rights.change_log
    ALTER COLUMN created SET default now();

ALTER TABLE rights.organization
    ALTER COLUMN id DROP DEFAULT;
DROP SEQUENCE rights.organization_id_seq;
ALTER TABLE rights.organization
    ALTER COLUMN id SET DATA TYPE INT8;
ALTER TABLE rights.organization
    ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY;
ALTER TABLE rights.organization
    ALTER COLUMN created SET default now();
ALTER TABLE rights.organization
    ALTER COLUMN last_modified SET default now();

ALTER TABLE rights.person
    ALTER COLUMN id DROP DEFAULT;
DROP SEQUENCE rights.person_id_seq;
ALTER TABLE rights.person
    ALTER COLUMN id SET DATA TYPE INT8;
ALTER TABLE rights.person
    ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY;
ALTER TABLE rights.person
    ALTER COLUMN created SET default now();
ALTER TABLE rights.person
    ALTER COLUMN last_modified SET default now();

ALTER TABLE rights."right"
    ALTER COLUMN id DROP DEFAULT;
DROP SEQUENCE rights.right_id_seq;
ALTER TABLE rights."right"
    ALTER COLUMN id SET DATA TYPE INT8;
ALTER TABLE rights."right"
    ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY;
ALTER TABLE rights."right"
    ALTER COLUMN created SET default now();
ALTER TABLE rights."right"
    ALTER COLUMN last_modified SET default now();
ALTER TABLE rights."right"
    ALTER COLUMN valid_from SET default now();