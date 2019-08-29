#!/usr/bin/env python3

"""This is a module for Rights storage API.

This module allows:
    * adding rights to person.
    * revoking right
    * searching for rights
    * updating/creating person
    * updating/creating organization
"""

# TODO: validate inputs!
# TODO: no get_time

import json
import logging
import psycopg2
from flask import request, jsonify
from flask_restful import Resource

LOGGER = logging.getLogger('rights')


def get_db_connection(conf):
    """Get connection object for Central Server database"""
    return psycopg2.connect(
        'host={} port={} dbname={} user={} password={}'.format(
            conf['db_host'], conf['db_port'], conf['db_db'], conf['db_user'], conf['db_pass']))


def get_person(cur, code):
    """Get person data from db"""
    cur.execute("""
        select id, first_name, last_name
        from rights.person
        where code=%(str)s""", {'str': code})
    rec = cur.fetchone()
    if rec:
        return rec[0], rec[1], rec[2]
    return None, None, None


def set_person(cur, code, first_name, last_name):
    """Get person data from db and update or insert if necessary"""
    current_id, current_first_name, current_last_name = get_person(cur, code)
    if current_id is None:
        cur.execute(
            """
                insert into rights.person(code, first_name, last_name)
                values(%(code)s, %(first_name)s, %(last_name)s)
                returning id""",
            {'code': code, 'first_name': first_name, 'last_name': last_name})
        return cur.fetchone()[0]
    if current_first_name != first_name or current_last_name != last_name:
        cur.execute(
            """
                update rights.person
                set first_name=%(first_name)s, last_name=%(last_name)s,
                    last_modified=current_timestamp
                where id=%(id)s""",
            {'first_name': first_name, 'last_name': last_name, 'id': current_id})
    return current_id


def get_organization(cur, code):
    """Get organization data from db"""
    cur.execute("""
        select id, name
        from rights.organization
        where code=%(str)s""", {'str': code})
    rec = cur.fetchone()
    if rec:
        return rec[0], rec[1]
    return None, None


def set_organization(cur, code, name):
    """Get organization data from db and update or insert if necessary"""
    current_id, current_name = get_organization(cur, code)
    if current_id is None:
        cur.execute(
            """
                insert into rights.organization(code, name)
                values(%(code)s, %(name)s)
                returning id""",
            {'code': code, 'name': name})
        return cur.fetchone()[0]
    if current_name != name:
        cur.execute(
            """
                update rights.organization
                set name=%(name)s, last_modified=current_timestamp
                where id=%(id)s""",
            {'name': name, 'id': current_id})
    return current_id


def revoke_right(cur, person_id, organization_id, right_type):
    """Revoke person right in db"""
    cur.execute(
        """
            update rights.right set valid_to=current_timestamp, last_modified=current_timestamp
            where person_id=%(person_id)s and organization_id=%(organization_id)s
                and right_type=%(right_type)s and valid_from<=current_timestamp
                and COALESCE(valid_to, current_timestamp + interval '1 day')>current_timestamp""",
        {'person_id': person_id, 'organization_id': organization_id, 'right_type': right_type})
    return cur.rowcount


def add_right(cur, **kwargs):
    """Add new person right to db

    Required keyword arguments:
    person_id, organization_id, right_type, valid_from, valid_to
    """
    cur.execute(
        """
            insert into rights.right (person_id, organization_id, right_type, valid_from, valid_to)
            values (%(person_id)s, %(organization_id)s, %(right_type)s, %(valid_from)s,
                %(valid_to)s)""",
        {
            'person_id': kwargs['person_id'], 'organization_id': kwargs['organization_id'],
            'right_type': kwargs['right_type'], 'valid_from': kwargs['valid_from'],
            'valid_to': kwargs['valid_to']})


def get_search_rights_sql(only_valid, persons, organizations, rights):
    """Get SQL string for search right query"""
    sql_what = """
        select p.code, p.first_name, p.last_name, o.code, o.name,
            r.right_type, r.valid_from, r.valid_to"""
    sql_cnt = """
        select count(1)"""
    sql_from = """
        from rights.right r
        join rights.person p on (p.id=r.person_id)
        join rights.organization o on (o.id=r.organization_id)"""
    sql_where = """
        where true"""
    if only_valid:
        sql_where += """
            and r.valid_from<=current_timestamp
            and COALESCE(valid_to, current_timestamp + interval '1 day')>current_timestamp"""
    if persons:
        sql_where += """
            and p.code=ANY(%(persons)s)"""
    if organizations:
        sql_where += """
            and o.code=ANY(%(organizations)s)"""
    if rights:
        sql_where += """
            and r.right_type=ANY(%(rights)s)"""
    sql_limit = """
        limit %(limit)s offset %(offset)s"""

    sql_query = sql_what + sql_from + sql_where + sql_limit
    sql_total = sql_cnt + sql_from + sql_where

    return sql_query, sql_total


def search_rights(cur, **kwargs):
    """Search for rights in db
    Required keyword arguments:
    persons, organizations, rights, only_valid, limit, offset
    """

    sql_query, sql_total = get_search_rights_sql(
        kwargs['only_valid'], kwargs['persons'], kwargs['organizations'], kwargs['rights'])

    params = {
        'persons': kwargs['persons'], 'organizations': kwargs['organizations'],
        'rights': kwargs['rights'], 'limit': kwargs['limit'], 'offset': kwargs['offset']}
    rights = []

    LOGGER.debug('SQL: %s', cur.mogrify(sql_query, params).decode('utf-8'))
    cur.execute(sql_query, params)
    for rec in cur:
        rights.append({
            'person': {'code': rec[0], 'first_name': rec[1], 'last_name': rec[2]},
            'organization': {'code': rec[3], 'name': rec[4]},
            'right': {'right_type': rec[5], 'valid_from': rec[6], 'valid_to': rec[7]}})

    LOGGER.debug('SQL total: %s', cur.mogrify(sql_total, params).decode('utf-8'))
    cur.execute(sql_total, params)
    total = cur.fetchone()[0]

    return {'rights': rights, 'limit': kwargs['limit'], 'offset': kwargs['offset'], 'total': total}


def get_time(cur):
    """Get current time from db"""
    cur.execute("""select current_timestamp""")
    return cur.fetchone()[0]


def make_response(data, log_header, log_level='info'):
    """Create JSON response object"""
    response = jsonify({'code': data['code'], 'msg': data['msg']})
    response.status_code = data['http_status']
    if log_level == 'debug':
        LOGGER.debug('%sResponse: %s', log_header, data)
    else:
        LOGGER.info('%sResponse: %s', log_header, data)
    return response


def load_config(config_file):
    """Load configuration from JSON file"""
    try:
        with open(config_file, 'r') as conf:
            LOGGER.info('Configuration loaded from file "%s"', config_file)
            return json.load(conf)
    except IOError as err:
        LOGGER.error('Cannot load configuration file "%s": %s', config_file, str(err))
        return None
    except json.JSONDecodeError as err:
        LOGGER.error('Invalid JSON configuration file "%s": %s', config_file, str(err))
        return None


def process_set_right(conf, json_data, log_header):
    """Process incoming set_right query"""
    if not conf['db_host'] or not conf['db_port'] or not conf['db_db'] or not conf['db_user']\
            or not conf['db_pass']:
        LOGGER.error('%sDB_CONF_ERROR: Cannot access database configuration', log_header)
        return {
            'http_status': 500, 'code': 'DB_CONF_ERROR',
            'msg': 'Cannot access database configuration'}

    with get_db_connection(conf) as conn:
        with conn.cursor() as cur:
            # Setting optional parameters if they were empty
            if 'valid_from' not in json_data['right']:
                json_data['right']['valid_from'] = get_time(cur)
            if 'valid_to' not in json_data['right']:
                json_data['right']['valid_to'] = None

            # Update person
            person_id = set_person(
                cur, json_data['person']['code'], json_data['person']['first_name'],
                json_data['person']['last_name'])

            # Update organization
            organization_id = set_organization(
                cur, json_data['organization']['code'], json_data['organization']['name'])

            # Revoke existing right if it exists
            revoke_right(cur, person_id, organization_id, json_data['right']['right_type'])

            # Add new right
            add_right(
                cur, person_id=person_id, organization_id=organization_id,
                right_type=json_data['right']['right_type'],
                valid_from=json_data['right']['valid_from'],
                valid_to=json_data['right']['valid_to'])
        conn.commit()

    LOGGER.info(
        '%sAdded new Right: person_code=%s, organization_code=%s, right_type=%s', log_header,
        json_data['person']['code'], json_data['organization']['code'],
        json_data['right']['right_type'])

    return {'http_status': 201, 'code': 'CREATED', 'msg': 'New right added'}


def process_revoke_right(conf, json_data, log_header):
    """Process incoming revoke_right query"""
    if not conf['db_host'] or not conf['db_port'] or not conf['db_db'] or not conf['db_user']\
            or not conf['db_pass']:
        LOGGER.error('%sDB_CONF_ERROR: Cannot access database configuration', log_header)
        return {
            'http_status': 500, 'code': 'DB_CONF_ERROR',
            'msg': 'Cannot access database configuration'}

    with get_db_connection(conf) as conn:
        with conn.cursor() as cur:
            person_id = get_person(cur, json_data['person_code'])[0]
            organization_id = get_organization(cur, json_data['organization_code'])[0]

            # Revoke existing right if it exists
            if not revoke_right(cur, person_id, organization_id, json_data['right_type']):
                return {'http_status': 200, 'code': 'RIGHT_NOT_FOUND', 'msg': 'No right was found'}
        conn.commit()

    LOGGER.info(
        '%sRevoked Right: person_code=%s, organization_code=%s, right_type=%s', log_header,
        json_data['person_code'], json_data['organization_code'],
        json_data['right_type'])

    return {'http_status': 200, 'code': 'OK', 'msg': 'Right revoked'}


def process_search_rights(conf, json_data, log_header):
    """Process incoming search_rights query"""
    if not conf['db_host'] or not conf['db_port'] or not conf['db_db'] or not conf['db_user']\
            or not conf['db_pass']:
        LOGGER.error('%sDB_CONF_ERROR: Cannot access database configuration', log_header)
        return {
            'http_status': 500, 'code': 'DB_CONF_ERROR',
            'msg': 'Cannot access database configuration'}

    with get_db_connection(conf) as conn:
        with conn.cursor() as cur:
            result = search_rights(
                cur, persons=json_data['persons'], organizations=json_data['organizations'],
                rights=json_data['rights'], only_valid=json_data['only_valid'],
                limit=json_data['limit'], offset=json_data['offset'])
        conn.commit()

    LOGGER.info(
        '%sFound %s rights, returning %s rights with offset %s',
        log_header, result['total'], len(result['rights']), result['offset'])

    return {'http_status': 200, 'code': 'OK', 'msg': result}


def process_set_person(conf, json_data, log_header):
    """Process incoming set_person query"""
    if not conf['db_host'] or not conf['db_port'] or not conf['db_db'] or not conf['db_user']\
            or not conf['db_pass']:
        LOGGER.error('%sDB_CONF_ERROR: Cannot access database configuration', log_header)
        return {
            'http_status': 500, 'code': 'DB_CONF_ERROR',
            'msg': 'Cannot access database configuration'}

    with get_db_connection(conf) as conn:
        with conn.cursor() as cur:
            set_person(cur, json_data['code'], json_data['first_name'], json_data['last_name'])
        conn.commit()

    LOGGER.info('%sPerson updated: code=%s', log_header, json_data['code'])

    return {'http_status': 200, 'code': 'OK', 'msg': 'Person updated'}


def process_set_organization(conf, json_data, log_header):
    """Process incoming set_organization query"""
    if not conf['db_host'] or not conf['db_port'] or not conf['db_db'] or not conf['db_user']\
            or not conf['db_pass']:
        LOGGER.error('%sDB_CONF_ERROR: Cannot access database configuration', log_header)
        return {
            'http_status': 500, 'code': 'DB_CONF_ERROR',
            'msg': 'Cannot access database configuration'}

    with get_db_connection(conf) as conn:
        with conn.cursor() as cur:
            set_organization(cur, json_data['code'], json_data['name'])
        conn.commit()

    LOGGER.info('%sOrganization updated: code=%s', log_header, json_data['code'])

    return {'http_status': 200, 'code': 'OK', 'msg': 'Organization updated'}


class SetRightApi(Resource):
    """SetRight API class for Flask"""
    def __init__(self, config):
        self.config = config

    def post(self):
        """POST method for changing or adding right"""
        log_header = '[SetRight:post] '
        json_data = request.get_json(force=True)

        LOGGER.info('%sIncoming request: %s', log_header, json_data)

        try:
            response = process_set_right(self.config, json_data, log_header)
        except psycopg2.Error as err:
            LOGGER.error('%sDB_ERROR: Unclassified database error: %s', log_header, err)
            response = {
                'http_status': 500, 'code': 'DB_ERROR',
                'msg': 'Unclassified database error'}

        return make_response(response, log_header)


class RevokeRightApi(Resource):
    """RevokeRight API class for Flask"""
    def __init__(self, config):
        self.config = config

    def post(self):
        """POST method for revoking right"""
        log_header = '[RevokeRight:post] '
        json_data = request.get_json(force=True)

        LOGGER.info('%sIncoming request: %s', log_header, json_data)

        try:
            response = process_revoke_right(self.config, json_data, log_header)
        except psycopg2.Error as err:
            LOGGER.error('%sDB_ERROR: Unclassified database error: %s', log_header, err)
            response = {
                'http_status': 500, 'code': 'DB_ERROR',
                'msg': 'Unclassified database error'}

        return make_response(response, log_header)


class RightsApi(Resource):
    """Rights API class for Flask"""
    def __init__(self, config):
        self.config = config

    def post(self):
        """POST method for searching for rights"""
        log_header = '[Rights:post] '
        json_data = request.get_json(force=True)

        LOGGER.info('%sIncoming request: %s', log_header, json_data)

        try:
            response = process_search_rights(self.config, json_data, log_header)
        except psycopg2.Error as err:
            LOGGER.error('%sDB_ERROR: Unclassified database error: %s', log_header, err)
            response = {
                'http_status': 500, 'code': 'DB_ERROR',
                'msg': 'Unclassified database error'}

        return make_response(response, log_header, log_level='debug')


class PersonApi(Resource):
    """Person API class for Flask"""
    def __init__(self, config):
        self.config = config

    def post(self):
        """POST method form changing or adding person"""
        log_header = '[Person:post] '
        json_data = request.get_json(force=True)

        LOGGER.info('%sIncoming request: %s', log_header, json_data)

        try:
            response = process_set_person(self.config, json_data, log_header)
        except psycopg2.Error as err:
            LOGGER.error('%sDB_ERROR: Unclassified database error: %s', log_header, err)
            response = {
                'http_status': 500, 'code': 'DB_ERROR',
                'msg': 'Unclassified database error'}

        return make_response(response, log_header)


class OrganizationApi(Resource):
    """Organization API class for Flask"""
    def __init__(self, config):
        self.config = config

    def post(self):
        """POST method for changing or adding organization"""
        log_header = '[Organization:post] '
        json_data = request.get_json(force=True)

        LOGGER.info('%sIncoming request: %s', log_header, json_data)

        try:
            response = process_set_organization(self.config, json_data, log_header)
        except psycopg2.Error as err:
            LOGGER.error('%sDB_ERROR: Unclassified database error: %s', log_header, err)
            response = {
                'http_status': 500, 'code': 'DB_ERROR',
                'msg': 'Unclassified database error'}

        return make_response(response, log_header)
