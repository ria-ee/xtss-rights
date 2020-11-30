#!/usr/bin/env python3

"""This is a module for Rights storage API.

This module allows:
    * adding rights to person.
    * revoking right
    * searching for rights
    * updating/creating person
    * updating/creating organization
    * checking API status
"""

from datetime import datetime
import json
import logging
import uuid
import psycopg2
from flask import request, jsonify
from flask_restful import Resource

LOGGER = logging.getLogger('rights')
DEFAULT_ONLY_VALID = True
DEFAULT_LIMIT = 100
DEFAULT_OFFSET = 0
DEFAULT_CONNECT_TIMEOUT = 5
TIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%f'
TIME_FORMAT_SEC = '%Y-%m-%dT%H:%M:%S'
TIME_FORMAT_DB = '%Y-%m-%d %H:%M:%S'


def get_db_connection(conf):
    """Get connection object for Central Server database"""
    connect_timeout = DEFAULT_CONNECT_TIMEOUT
    if 'db_connect_timeout' in conf:
        connect_timeout = conf['db_connect_timeout']
    return psycopg2.connect(
        'host={} port={} dbname={} user={} password={} connect_timeout={}'.format(
            conf['db_host'], conf['db_port'], conf['db_db'],
            conf['db_user'], conf['db_pass'], connect_timeout))


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
    if (first_name is not None and current_first_name != first_name) \
            or (last_name is not None and current_last_name != last_name):
        cur.execute(
            """
                update rights.person
                set first_name=COALESCE(%(first_name)s, first_name),
                    last_name=COALESCE(%(last_name)s, last_name)
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
    if name is not None and current_name != name:
        cur.execute(
            """
                update rights.organization
                set name=%(name)s
                where id=%(id)s""",
            {'name': name, 'id': current_id})
    return current_id


def revoke_right(cur, person_id, organization_id, right_type):
    """Revoke person right in db"""
    cur.execute(
        """
            update rights.right
            set
                revoked=true
            where person_id=%(person_id)s and organization_id=%(organization_id)s
                and right_type=%(right_type)s
                and not revoked""",
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
            values (%(person_id)s, %(organization_id)s, %(right_type)s,
                COALESCE(%(valid_from)s, current_timestamp),
                %(valid_to)s)""",
        {
            'person_id': kwargs['person_id'], 'organization_id': kwargs['organization_id'],
            'right_type': kwargs['right_type'], 'valid_from': kwargs['valid_from'],
            'valid_to': kwargs['valid_to']})


def get_search_rights_sql(only_valid, persons, organizations, rights):
    """Get SQL string for search right query"""
    sql_what = """
        select p.code, p.first_name, p.last_name, o.code, o.name,
            r.right_type, r.valid_from, r.valid_to, r.revoked"""
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
            and not r.revoked
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
        valid_from = rec[6]
        if isinstance(valid_from, datetime):
            valid_from = valid_from.strftime(TIME_FORMAT)
        valid_to = rec[7]
        if isinstance(valid_to, datetime):
            valid_to = valid_to.strftime(TIME_FORMAT)
        rights.append({
            'person': {'code': rec[0], 'first_name': rec[1], 'last_name': rec[2]},
            'organization': {'code': rec[3], 'name': rec[4]},
            'right': {
                'right_type': rec[5], 'valid_from': valid_from, 'valid_to': valid_to,
                'revoked': rec[8]}})

    LOGGER.debug('SQL total: %s', cur.mogrify(sql_total, params).decode('utf-8'))
    cur.execute(sql_total, params)
    total = cur.fetchone()[0]

    return {'rights': rights, 'limit': kwargs['limit'], 'offset': kwargs['offset'], 'total': total}


def make_response(data, log_header, log_level='info'):
    """Create JSON response object"""
    response = jsonify({'code': data['code'], 'msg': data['msg']})
    if 'response' in data:
        response = jsonify(
            {'code': data['code'], 'msg': data['msg'], 'response': data['response']})
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


def validate_config(conf, log_header):
    """Validate configuration values"""
    if not conf.get('db_host') or not conf.get('db_port') or not conf.get('db_db') \
            or not conf.get('db_user') or not conf.get('db_pass'):
        LOGGER.error('%sDB_CONF_ERROR: Cannot access database configuration', log_header)
        return {
            'http_status': 500, 'code': 'DB_CONF_ERROR',
            'msg': 'Cannot access database configuration'}
    return None


def get_required_parameter(name, json_data, log_header):
    """Get required parameter from request

    Returns tuple of: valid parameter, error message
    """
    if json_data.get(name):
        return json_data.get(name), None

    LOGGER.warning(
        '%sMISSING_PARAMETER: Missing parameter "%s" '
        '(Request: %s)', log_header, name, json_data)
    return None, {
        'http_status': 400, 'code': 'MISSING_PARAMETER',
        'msg': 'Missing parameter "{}"'.format(name)}


def check_required_dict_item(dict_name, item_name, json_data, log_header):
    """Checks if required dict item is present in request

    Returns error message or None
    """
    if not json_data.get(dict_name) or not json_data.get(dict_name).get(item_name):
        LOGGER.warning(
            '%sMISSING_PARAMETER: Missing parameter "%s->%s" '
            '(Request: %s)', log_header, dict_name, item_name, json_data)
        return {
            'http_status': 400, 'code': 'MISSING_PARAMETER',
            'msg': 'Missing parameter "{}->{}"'.format(dict_name, item_name)}

    return None


def get_dict_parameter(name, values, json_data):
    """Get dictionary parameter from request

    Automatically fills missing values with None
    """
    result = {}
    for key in values:
        result[key] = None
    if isinstance(json_data.get(name), dict):
        item = json_data.get(name)
        for key in values:
            if key in item:
                result[key] = item[key]
    return result


def get_list_of_strings_parameter(name, json_data):
    """Get list of strings parameter from request"""
    result = []
    if isinstance(json_data.get(name), list):
        for item in json_data.get(name):
            if isinstance(item, str):
                result.append(item)
    return result


def get_int_parameter(name, json_data):
    """Get integer parameter from request"""
    if isinstance(json_data.get(name), int):
        return json_data.get(name)
    return None


def get_bool_parameter(name, json_data):
    """Get boolean parameter from request"""
    if isinstance(json_data.get(name), bool):
        return json_data.get(name)
    return None


def parse_timestamp(timestamp, json_data, log_header):
    """Parse timestamp

    Returns tuple of datetime, error message
    """
    # Parsing timestamps. Example: "2019-08-29T14:00:00.000000" or "2019-08-29T14:00:00"
    if not timestamp:
        return None, None
    try:
        return datetime.strptime(timestamp, TIME_FORMAT), None
    except (TypeError, ValueError):
        try:
            return datetime.strptime(timestamp, TIME_FORMAT_SEC), None
        except (TypeError, ValueError):
            LOGGER.warning(
                '%sINVALID_PARAMETER: Unrecognized timestamp "%s" '
                '(Request: %s)', log_header, timestamp, json_data)
            return None, {
                'http_status': 400, 'code': 'INVALID_PARAMETER',
                'msg': 'Unrecognized timestamp: "{}"'.format(timestamp)}


def check_timestamp(timestamp, json_data, log_header):
    """Checks if timestamp is valid (in the future)

    Returns error message or None
    """
    if isinstance(timestamp, datetime) and timestamp < datetime.now():
        LOGGER.warning(
            '%sINVALID_PARAMETER: timestamps must be in the future '
            '(Request: %s)', log_header, json_data)
        return {
            'http_status': 400, 'code': 'INVALID_PARAMETER',
            'msg': 'Timestamps must be in the future'}

    return None


def check_interval(valid_from, valid_to, json_data, log_header):
    """Checks if time interval is valid

    Returns error message or None
    """
    if isinstance(valid_from, datetime) and isinstance(valid_to, datetime) \
            and valid_from > valid_to:
        LOGGER.warning(
            '%sINVALID_PARAMETER: "valid_from" must be smaller then "valid_to" '
            '(Request: %s)', log_header, json_data)
        return {
            'http_status': 400, 'code': 'INVALID_PARAMETER',
            'msg': '"valid_from" must be smaller then "valid_to"'}

    request_error = check_timestamp(valid_from, json_data, log_header)
    if request_error:
        return request_error

    request_error = check_timestamp(valid_to, json_data, log_header)
    if request_error:
        return request_error

    return None


def parse_interval(valid_from, valid_to, json_data, log_header):
    """Parse timestamp interval and check its validity

    Returns tuple of valid_from, valid_to, error message
    """
    # Parse timestamps
    valid_from, request_error = parse_timestamp(
        valid_from, json_data, log_header)
    if request_error:
        return None, None, request_error
    valid_to, request_error = parse_timestamp(
        valid_to, json_data, log_header)
    if request_error:
        return None, None, request_error

    request_error = check_interval(valid_from, valid_to, json_data, log_header)
    if request_error:
        return None, None, request_error

    return valid_from, valid_to, None


def validate_set_right_request(json_data, log_header):
    """Check request parameters of set_right

    Returns tuple of: kwargs, error message
    """
    # Check required parameters
    request_error = check_required_dict_item('person', 'code', json_data, log_header)
    if request_error:
        return None, request_error
    request_error = check_required_dict_item('organization', 'code', json_data, log_header)
    if request_error:
        return None, request_error
    request_error = check_required_dict_item('right', 'right_type', json_data, log_header)
    if request_error:
        return None, request_error

    kwargs = {
        'person': get_dict_parameter('person', ['code', 'first_name', 'last_name'], json_data),
        'organization': get_dict_parameter('organization', ['code', 'name'], json_data),
        'right': get_dict_parameter('right', ['right_type', 'valid_from', 'valid_to'], json_data)
    }

    # Parse timestamps
    kwargs['right']['valid_from'], kwargs['right']['valid_to'], request_error = parse_interval(
        kwargs['right']['valid_from'], kwargs['right']['valid_to'], json_data, log_header)
    if request_error:
        return None, request_error

    return kwargs, None


def process_set_right(conf, json_data, log_header):
    """Process incoming set_right query"""
    conf_error = validate_config(conf, log_header)
    if conf_error:
        return conf_error

    kwargs, request_error = validate_set_right_request(json_data, log_header)
    if request_error:
        return request_error

    with get_db_connection(conf) as conn:
        with conn.cursor() as cur:
            # Update person
            person_id = set_person(
                cur, kwargs['person']['code'], kwargs['person']['first_name'],
                kwargs['person']['last_name'])

            # Update organization
            organization_id = set_organization(
                cur, kwargs['organization']['code'], kwargs['organization']['name'])

            # Revoke existing right if it exists
            revoke_right(cur, person_id, organization_id, kwargs['right']['right_type'])

            # Add new right
            add_right(
                cur, person_id=person_id, organization_id=organization_id,
                right_type=kwargs['right']['right_type'],
                valid_from=kwargs['right']['valid_from'],
                valid_to=kwargs['right']['valid_to'])
        conn.commit()

    LOGGER.info(
        '%sAdded new Right: person_code=%s, organization_code=%s, right_type=%s', log_header,
        kwargs['person']['code'], kwargs['organization']['code'],
        kwargs['right']['right_type'])

    return {'http_status': 201, 'code': 'CREATED', 'msg': 'New right added'}


def validate_revoke_right_request(json_data, log_header):
    """Check request parameters of revoke_right

    Returns tuple of: kwargs, error message
    """
    kwargs = {}

    # Required parameters:
    kwargs['person_code'], param_error = get_required_parameter(
        'person_code', json_data, log_header)
    if param_error:
        return None, param_error
    kwargs['organization_code'], param_error = get_required_parameter(
        'organization_code', json_data, log_header)
    if param_error:
        return None, param_error
    kwargs['right_type'], param_error = get_required_parameter(
        'right_type', json_data, log_header)
    if param_error:
        return None, param_error

    return kwargs, None


def process_revoke_right(conf, json_data, log_header):
    """Process incoming revoke_right query"""
    conf_error = validate_config(conf, log_header)
    if conf_error:
        return conf_error

    kwargs, request_error = validate_revoke_right_request(json_data, log_header)
    if request_error:
        return request_error

    with get_db_connection(conf) as conn:
        with conn.cursor() as cur:
            person_id = get_person(cur, kwargs['person_code'])[0]
            organization_id = get_organization(cur, kwargs['organization_code'])[0]

            # Revoke existing right if it exists
            if not revoke_right(cur, person_id, organization_id, kwargs['right_type']):
                return {'http_status': 200, 'code': 'RIGHT_NOT_FOUND', 'msg': 'No right was found'}
        conn.commit()

    LOGGER.info(
        '%sRevoked Right: person_code=%s, organization_code=%s, right_type=%s', log_header,
        kwargs['person_code'], kwargs['organization_code'],
        kwargs['right_type'])

    return {'http_status': 200, 'code': 'OK', 'msg': 'Right revoked'}


def validate_search_rights_request(json_data):
    """Check request parameters of search_rights

    Validation never fails (no required parameters)
    Returns: kwargs
    """
    kwargs = {
        'persons': get_list_of_strings_parameter('persons', json_data),
        'organizations': get_list_of_strings_parameter('organizations', json_data),
        'rights': get_list_of_strings_parameter('rights', json_data),
        'only_valid': get_bool_parameter('only_valid', json_data),
        'limit': get_int_parameter('limit', json_data),
        'offset': get_int_parameter('offset', json_data)}

    # Setting default values
    if kwargs['only_valid'] is None:
        kwargs['only_valid'] = DEFAULT_ONLY_VALID
    if kwargs['limit'] is None:
        kwargs['limit'] = DEFAULT_LIMIT
    if kwargs['offset'] is None:
        kwargs['offset'] = DEFAULT_OFFSET

    return kwargs


def process_search_rights(conf, json_data, log_header):
    """Process incoming search_rights query"""
    conf_error = validate_config(conf, log_header)
    if conf_error:
        return conf_error

    kwargs = validate_search_rights_request(json_data)

    with get_db_connection(conf) as conn:
        with conn.cursor() as cur:
            result = search_rights(
                cur, **kwargs)
        conn.commit()

    LOGGER.info(
        '%sFound %s rights, returning %s rights with offset %s',
        log_header, result['total'], len(result['rights']), result['offset'])

    return {
        'http_status': 200, 'code': 'OK',
        'msg': 'Found {} rights'.format(result['total']),
        'response': result}


def validate_set_person_request(json_data, log_header):
    """Check request parameters of set_person

    Returns tuple of: kwargs, error message
    """
    kwargs = {}

    # Required parameters:
    kwargs['code'], param_error = get_required_parameter('code', json_data, log_header)
    if param_error:
        return None, param_error

    # Optional parameters
    kwargs['first_name'] = json_data.get('first_name')
    kwargs['last_name'] = json_data.get('last_name')

    return kwargs, None


def process_set_person(conf, json_data, log_header):
    """Process incoming set_person query"""
    conf_error = validate_config(conf, log_header)
    if conf_error:
        return conf_error

    kwargs, request_error = validate_set_person_request(json_data, log_header)
    if request_error:
        return request_error

    with get_db_connection(conf) as conn:
        with conn.cursor() as cur:
            set_person(cur, kwargs['code'], kwargs['first_name'], kwargs['last_name'])
        conn.commit()

    LOGGER.info('%sPerson updated: code=%s', log_header, kwargs['code'])

    return {'http_status': 200, 'code': 'OK', 'msg': 'Person updated'}


def validate_set_organization_request(json_data, log_header):
    """Check request parameters of set_organization

    Returns tuple of: kwargs, error message
    """
    kwargs = {}

    # Required parameters:
    kwargs['code'], param_error = get_required_parameter('code', json_data, log_header)
    if param_error:
        return None, param_error

    # Optional parameters
    kwargs['name'] = json_data.get('name')

    return kwargs, None


def process_set_organization(conf, json_data, log_header):
    """Process incoming set_organization query"""
    conf_error = validate_config(conf, log_header)
    if conf_error:
        return conf_error

    kwargs, request_error = validate_set_organization_request(json_data, log_header)
    if request_error:
        return request_error

    with get_db_connection(conf) as conn:
        with conn.cursor() as cur:
            set_organization(cur, kwargs['code'], kwargs['name'])
        conn.commit()

    LOGGER.info('%sOrganization updated: code=%s', log_header, kwargs['code'])
    return {'http_status': 200, 'code': 'OK', 'msg': 'Organization updated'}


def check_client(config, client_dn):
    """Check if client dn is in whitelist"""
    # If config is None then all clients are not allowed
    if config is None:
        return False
    if config.get('allow_all', False) is True:
        return True

    allowed = config.get('allowed')
    if client_dn is None or not isinstance(allowed, list):
        return False

    if client_dn in allowed:
        return True

    return False


def incorrect_client(client_dn, log_header):
    """Return error response when client is not allowed"""
    LOGGER.error('%sFORBIDDEN: Client certificate is not allowed: %s', log_header, client_dn)
    return make_response({
        'http_status': 403, 'code': 'FORBIDDEN',
        'msg': 'Client certificate is not allowed: {}'.format(client_dn)}, log_header)


def test_db(conf, log_header):
    """Add new X-Road subsystem to Central Server"""
    conf_error = validate_config(conf, log_header)
    if conf_error:
        return conf_error

    with get_db_connection(conf) as conn:
        with conn.cursor() as cur:
            cur.execute("""select count(1) from rights."right";""")
            return {
                'http_status': 200, 'code': 'OK',
                'msg': 'API is ready'}


def get_log_header(method):
    """Get log header string"""
    trace_id = request.headers.get('X-B3-TraceId')
    if trace_id:
        return '[{} {},{}] '.format(method, trace_id, uuid.uuid4())

    return '[{}] '.format(method)


class SetRightApi(Resource):
    """SetRight API class for Flask"""
    def __init__(self, config):
        self.config = config

    def post(self):
        """POST method for changing or adding right"""
        log_header = get_log_header('SetRight:post')
        json_data = request.get_json(force=True)
        client_dn = request.headers.get('X-Ssl-Client-S-Dn')

        LOGGER.info('%sIncoming request: %s', log_header, json_data)
        LOGGER.info('%sClient DN: %s', log_header, client_dn)

        if not check_client(self.config, client_dn):
            return incorrect_client(client_dn, log_header)

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
        log_header = get_log_header('RevokeRight:post')
        json_data = request.get_json(force=True)
        client_dn = request.headers.get('X-Ssl-Client-S-Dn')

        LOGGER.info('%sIncoming request: %s', log_header, json_data)
        LOGGER.info('%sClient DN: %s', log_header, client_dn)

        if not check_client(self.config, client_dn):
            return incorrect_client(client_dn, log_header)

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
        log_header = get_log_header('Rights:post')
        json_data = request.get_json(force=True)
        client_dn = request.headers.get('X-Ssl-Client-S-Dn')

        LOGGER.info('%sIncoming request: %s', log_header, json_data)
        LOGGER.info('%sClient DN: %s', log_header, client_dn)

        if not check_client(self.config, client_dn):
            return incorrect_client(client_dn, log_header)

        try:
            response = process_search_rights(self.config, json_data, log_header)
        except psycopg2.Error as err:
            LOGGER.error('%sDB_ERROR: Unclassified database error: %s', log_header, err)
            response = {
                'http_status': 500, 'code': 'DB_ERROR',
                'msg': 'Unclassified database error'}

        # Logging responses (that may be big) only on DEBUG level
        return make_response(response, log_header, log_level='debug')


class PersonApi(Resource):
    """Person API class for Flask"""
    def __init__(self, config):
        self.config = config

    def post(self):
        """POST method form changing or adding person"""
        log_header = get_log_header('Person:post')
        json_data = request.get_json(force=True)
        client_dn = request.headers.get('X-Ssl-Client-S-Dn')

        LOGGER.info('%sIncoming request: %s', log_header, json_data)
        LOGGER.info('%sClient DN: %s', log_header, client_dn)

        if not check_client(self.config, client_dn):
            return incorrect_client(client_dn, log_header)

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
        log_header = get_log_header('Organization:post')
        json_data = request.get_json(force=True)
        client_dn = request.headers.get('X-Ssl-Client-S-Dn')

        LOGGER.info('%sIncoming request: %s', log_header, json_data)
        LOGGER.info('%sClient DN: %s', log_header, client_dn)

        if not check_client(self.config, client_dn):
            return incorrect_client(client_dn, log_header)

        try:
            response = process_set_organization(self.config, json_data, log_header)
        except psycopg2.Error as err:
            LOGGER.error('%sDB_ERROR: Unclassified database error: %s', log_header, err)
            response = {
                'http_status': 500, 'code': 'DB_ERROR',
                'msg': 'Unclassified database error'}

        return make_response(response, log_header)


class StatusApi(Resource):
    """Status API class for Flask"""
    def __init__(self, config):
        self.config = config

    def get(self):
        """GET method"""
        log_header = get_log_header('Status:get')
        LOGGER.info('%sIncoming status request', log_header)

        try:
            response = test_db(self.config, log_header)
        except psycopg2.Error as err:
            LOGGER.error('%sDB_ERROR: Unclassified database error: %s', log_header, err)
            response = {
                'http_status': 500, 'code': 'DB_ERROR',
                'msg': 'Unclassified database error'}

        return make_response(response, log_header)
