# Migration to liquibase

If you have existing Rights database and you want to start using liquibase then you need to perform the following steps:

1) Create backup for your data!

2) Run migration_to_lb.sql in your database.

3) Create liquibase configurations file `liquibase.properties` using example file `example_liquibase.properties`.

4) Mark all liquibase changes as applied (using liquibase docker image) by running the following command in project folder:
   ```
   docker run --rm -v $(pwd)/liquibase:/liquibase/changelog liquibase/liquibase --defaultsFile=/liquibase/changelog/liquibase.properties changelogSync
   ```
