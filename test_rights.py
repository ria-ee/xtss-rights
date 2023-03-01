# Disable pylint errors that are not as relevant for tests:
# pylint: disable=missing-function-docstring missing-module-docstring missing-class-docstring
# pylint: disable=too-many-lines too-many-public-methods invalid-name too-many-arguments

import json
from datetime import datetime
import unittest
from unittest.mock import patch, MagicMock, mock_open, call
from flask import Flask, jsonify
from flask_restful import Api
import psycopg2
import rights


class MainTestCase(unittest.TestCase):
    def setUp(self):
        self.config = {
            "db_host": "localhost",
            "db_port": "5432",
            "db_db": "postgres",
            "db_user": "postgres",
            "db_pass": "password",
            "db_connect_timeout": 10,
            "allow_all": False,
            "allowed": [
                "OU=xtss,O=RIA,C=EE"
            ]}
        self.app = Flask(__name__)
        self.client = self.app.test_client()
        self.api = Api(self.app)
        self.api.add_resource(rights.SetRightApi, '/set-right', resource_class_kwargs={
            'config': self.config})
        self.api.add_resource(rights.RevokeRightApi, '/revoke-right', resource_class_kwargs={
            'config': self.config})
        self.api.add_resource(rights.RightsApi, '/rights', resource_class_kwargs={
            'config': self.config})
        self.api.add_resource(rights.PersonApi, '/person', resource_class_kwargs={
            'config': self.config})
        self.api.add_resource(rights.OrganizationApi, '/organization', resource_class_kwargs={
            'config': self.config})
        self.api.add_resource(rights.StatusApi, '/status', resource_class_kwargs={
            'config': self.config})

    def test_load_config(self):
        # Valid json
        with patch('builtins.open', mock_open(read_data=json.dumps({'allow_all': True}))) as m:
            self.assertEqual({'allow_all': True}, rights.load_config('FILENAME'))
            m.assert_called_once_with('FILENAME', 'r', encoding='utf-8')
        # Invalid json
        with patch('builtins.open', mock_open(read_data='INVALID_YAML: {}x')) as m:
            with self.assertLogs(rights.LOGGER, level='INFO') as cm:
                self.assertEqual({}, rights.load_config('FILENAME'))
                m.assert_called_once_with('FILENAME', 'r', encoding='utf-8')
                self.assertIn(
                    'INFO:rights:Loading configuration from file "FILENAME"', cm.output)
                self.assertIn(
                    'ERROR:rights:Invalid YAML configuration file "FILENAME"', cm.output[1])
        # Invalid file
        with patch('builtins.open', mock_open()) as m:
            m.side_effect = IOError
            with self.assertLogs(rights.LOGGER, level='INFO') as cm:
                self.assertEqual({}, rights.load_config('FILENAME'))
                m.assert_called_once_with('FILENAME', 'r', encoding='utf-8')
                self.assertEqual([
                    'ERROR:rights:Cannot open configuration file "FILENAME": '], cm.output)

    @patch('rights.load_config', return_value={'log_file': 'LOG_FILE'})
    @patch('os.umask')
    @patch('rights.LOGGER')
    @patch('logging.FileHandler')
    def test_configure_app(
            self, mock_log_file_handler, mock_logger, mock_os_umask, mock_load_config):
        config = rights.configure_app('CONFIG_FILE')
        mock_log_file_handler.assert_called_with('LOG_FILE')
        mock_logger.addHandler.assert_has_calls(mock_log_file_handler)
        mock_os_umask.assert_called_with(0o137)
        mock_load_config.assert_called_with('CONFIG_FILE')
        self.assertEqual({'log_file': 'LOG_FILE'}, config)

    @patch('rights.load_config', return_value={'a': 'b'})
    @patch('os.umask')
    @patch('rights.LOGGER')
    @patch('logging.StreamHandler')
    def test_configure_app_no_log_file(
            self, mock_console_log_handler, mock_logger, mock_os_umask, mock_load_config):
        config = rights.configure_app('CONFIG_FILE')
        mock_console_log_handler.assert_called_with()
        mock_logger.addHandler.assert_has_calls(mock_console_log_handler)
        mock_os_umask.assert_called_with(0o137)
        mock_load_config.assert_called_with('CONFIG_FILE')
        self.assertEqual({'a': 'b'}, config)

    @patch('psycopg2.connect')
    def test_get_db_connection(self, mock_pg_connect):
        rights.get_db_connection(self.config)
        mock_pg_connect.assert_called_with(
            'host=localhost port=5432 dbname=postgres user=postgres password=password '
            'connect_timeout=10 target_session_attrs=read-write')

    @patch('psycopg2.connect')
    def test_get_db_connection_default_timeout(self, mock_pg_connect):
        my_config = self.config.copy()
        del my_config['db_connect_timeout']
        rights.get_db_connection(my_config)
        mock_pg_connect.assert_called_with(
            'host=localhost port=5432 dbname=postgres user=postgres password=password '
            'connect_timeout=5 target_session_attrs=read-write')

    def test_get_person(self):
        cur = MagicMock()
        cur.execute = MagicMock()
        cur.fetchone = MagicMock(return_value=[1234, 'F_NAME', 'L_NAME'])
        self.assertEqual((1234, 'F_NAME', 'L_NAME'), rights.get_person(cur, '12345678901'))
        cur.execute.assert_called_with(
            '\n        select id, first_name, last_name'
            '\n        from rights.person'
            '\n        where code=%(str)s', {'str': '12345678901'})
        cur.fetchone.assert_called_once()

    def test_get_person_no_data(self):
        cur = MagicMock()
        cur.execute = MagicMock()
        cur.fetchone = MagicMock(return_value=None)
        self.assertEqual((None, None, None), rights.get_person(cur, '12345678901'))
        cur.execute.assert_called_with(
            '\n        select id, first_name, last_name'
            '\n        from rights.person'
            '\n        where code=%(str)s', {'str': '12345678901'})
        cur.fetchone.assert_called_once()

    @patch('rights.get_person', return_value=(1234, 'F_NAME', 'L_NAME'))
    def test_set_person_no_update(self, mock_get_person):
        cur = MagicMock()
        cur.execute = MagicMock()
        cur.fetchone = MagicMock(return_value=[1234])
        self.assertEqual(1234, rights.set_person(cur, '12345678901', 'F_NAME', 'L_NAME'))
        cur.execute.assert_not_called()
        cur.fetchone.assert_not_called()
        mock_get_person.assert_called_with(cur, '12345678901')

    @patch('rights.get_person', return_value=(1234, 'F_NAME', 'L_NAME'))
    def test_set_person_update(self, mock_get_person):
        cur = MagicMock()
        cur.execute = MagicMock()
        cur.fetchone = MagicMock(return_value=[1234])
        self.assertEqual(1234, rights.set_person(cur, '12345678901', 'F_NAME2', 'L_NAME2'))
        cur.execute.assert_called_with(
            '\n                update rights.person'
            '\n                set first_name=COALESCE(%(first_name)s, first_name),'
            '\n                    last_name=COALESCE(%(last_name)s, last_name)'
            '\n                where id=%(id)s', {
                'first_name': 'F_NAME2', 'last_name': 'L_NAME2', 'id': 1234})
        cur.fetchone.assert_not_called()
        mock_get_person.assert_called_with(cur, '12345678901')

    @patch('rights.get_person', return_value=(None, None, None))
    def test_set_person_insert(self, mock_get_person):
        cur = MagicMock()
        cur.execute = MagicMock()
        cur.fetchone = MagicMock(return_value=[1234])
        self.assertEqual(1234, rights.set_person(cur, '12345678901', 'F_NAME', 'L_NAME'))
        cur.execute.assert_called_with(
            '\n                insert into rights.person(code, first_name, last_name)'
            '\n                values(%(code)s, %(first_name)s, %(last_name)s)'
            '\n                returning id', {
                'code': '12345678901', 'first_name': 'F_NAME', 'last_name': 'L_NAME'})
        cur.fetchone.assert_called_once()
        mock_get_person.assert_called_with(cur, '12345678901')

    def test_get_organization(self):
        cur = MagicMock()
        cur.execute = MagicMock()
        cur.fetchone = MagicMock(return_value=[1234, 'ORG_NAME'])
        self.assertEqual((1234, 'ORG_NAME'), rights.get_organization(cur, '12345678'))
        cur.execute.assert_called_with(
            '\n        select id, name'
            '\n        from rights.organization'
            '\n        where code=%(str)s', {'str': '12345678'})
        cur.fetchone.assert_called_once()

    def test_get_organization_no_data(self):
        cur = MagicMock()
        cur.execute = MagicMock()
        cur.fetchone = MagicMock(return_value=None)
        self.assertEqual((None, None), rights.get_organization(cur, '12345678'))
        cur.execute.assert_called_with(
            '\n        select id, name'
            '\n        from rights.organization'
            '\n        where code=%(str)s', {'str': '12345678'})
        cur.fetchone.assert_called_once()

    @patch('rights.get_organization', return_value=(123, 'ORG_NAME'))
    def test_set_organization_no_update(self, mock_get_person):
        cur = MagicMock()
        cur.execute = MagicMock()
        cur.fetchone = MagicMock(return_value=[123])
        self.assertEqual(123, rights.set_organization(cur, '12345678', 'ORG_NAME'))
        cur.execute.assert_not_called()
        cur.fetchone.assert_not_called()
        mock_get_person.assert_called_with(cur, '12345678')

    @patch('rights.get_organization', return_value=(123, 'ORG_NAME'))
    def test_set_organization_update(self, mock_get_person):
        cur = MagicMock()
        cur.execute = MagicMock()
        cur.fetchone = MagicMock(return_value=[123])
        self.assertEqual(123, rights.set_organization(cur, '12345678', 'ORG_NAME2'))
        cur.execute.assert_called_with(
            '\n                update rights.organization'
            '\n                set name=%(name)s'
            '\n                where id=%(id)s', {'name': 'ORG_NAME2', 'id': 123})
        cur.fetchone.assert_not_called()
        mock_get_person.assert_called_with(cur, '12345678')

    @patch('rights.get_organization', return_value=(None, None))
    def test_set_organization_insert(self, mock_get_person):
        cur = MagicMock()
        cur.execute = MagicMock()
        cur.fetchone = MagicMock(return_value=[123])
        self.assertEqual(123, rights.set_organization(cur, '12345678', 'ORG_NAME'))
        cur.execute.assert_called_with(
            '\n                insert into rights.organization(code, name)'
            '\n                values(%(code)s, %(name)s)'
            '\n                returning id', {'code': '12345678', 'name': 'ORG_NAME'})
        cur.fetchone.assert_called_once()
        mock_get_person.assert_called_with(cur, '12345678')

    def test_revoke_right(self):
        cur = MagicMock()
        cur.execute = MagicMock()
        cur.rowcount = 1
        self.assertEqual(1, rights.revoke_right(cur, 1234, 123, 'RIGHT1'))
        cur.execute.assert_called_with(
            '\n            update rights.right'
            '\n            set'
            '\n                revoked=true'
            '\n            where person_id=%(person_id)s and organization_id=%(organization_id)s'
            '\n                and right_type=%(right_type)s'
            '\n                and not revoked', {
                'person_id': 1234, 'organization_id': 123, 'right_type': 'RIGHT1'})

    def test_add_right(self):
        cur = MagicMock()
        cur.execute = MagicMock()
        kwargs = {
            'person_id': 1234, 'organization_id': 123,
            'right_type': 'RIGHT1', 'valid_from': '2020-01-01',
            'valid_to': '2020-11-01'}
        self.assertEqual(None, rights.add_right(cur, **kwargs))
        cur.execute.assert_called_with(
            '\n            insert into rights.right (person_id, organization_id, '
            'right_type, valid_from, valid_to)'
            '\n            values (%(person_id)s, %(organization_id)s, %(right_type)s,'
            '\n                COALESCE(%(valid_from)s, current_timestamp),'
            '\n                %(valid_to)s)', {
                'person_id': 1234, 'organization_id': 123, 'right_type': 'RIGHT1',
                'valid_from': '2020-01-01', 'valid_to': '2020-11-01'})

    def test_get_search_rights_sql(self):
        self.assertEqual(
            ('\n        select p.code, p.first_name, p.last_name, o.code, o.name,\n'
             '            r.right_type, r.valid_from, r.valid_to, r.revoked\n'
             '        from rights.right r\n'
             '        join rights.person p on (p.id=r.person_id)\n'
             '        join rights.organization o on (o.id=r.organization_id)\n'
             '        where true\n'
             '            and not r.revoked\n'
             '            and r.valid_from<=current_timestamp\n'
             "            and COALESCE(valid_to, current_timestamp + interval '1 "
             "day')>current_timestamp\n"
             '            and p.code=ANY(%(persons)s)\n'
             '            and o.code=ANY(%(organizations)s)\n'
             '            and r.right_type=ANY(%(rights)s)\n'
             '        limit %(limit)s offset %(offset)s',
             '\n        select count(1)\n'
             '        from rights.right r\n'
             '        join rights.person p on (p.id=r.person_id)\n'
             '        join rights.organization o on (o.id=r.organization_id)\n'
             '        where true\n'
             '            and not r.revoked\n'
             '            and r.valid_from<=current_timestamp\n'
             "            and COALESCE(valid_to, current_timestamp + interval '1 "
             "day')>current_timestamp\n"
             '            and p.code=ANY(%(persons)s)\n'
             '            and o.code=ANY(%(organizations)s)\n'
             '            and r.right_type=ANY(%(rights)s)'),
            rights.get_search_rights_sql(
                True, ['12345678901', '12345678902'], ['12345678', '12345679'],
                ['RIGHTS1', 'RIGHTS2']))

    @patch('rights.get_search_rights_sql', return_value=('SQL1', 'SQL2'))
    def test_search_rights(self, mock_get_search_rights_sql):
        cur = MagicMock()
        cur.__iter__.return_value = [
            [
                '12345678901', 'F_NAME', 'L_NAME', '12345678', 'ORG_NAME', 'RIGHT1',
                datetime(2020, 1, 1, 10, 35, 45, 555),
                datetime(2020, 2, 10, 10, 35, 45, 555), False],
            [
                '12345678901', 'F_NAME', 'L_NAME', '12345678', 'ORG_NAME', 'RIGHT2',
                datetime(2020, 1, 1, 10, 35, 45, 555),
                datetime(2020, 2, 10, 10, 35, 45, 555), False]]
        cur.execute = MagicMock()
        cur.fetchone = MagicMock(return_value=[1])
        kwargs = {
            'persons': ['12345678901', '12345678902'],
            'organizations': ['12345678', '12345679'],
            'rights': ['RIGHTS1', 'RIGHTS2'],
            'only_valid': True, 'limit': 10, 'offset': 0}
        expected = {
            'limit': 10, 'offset': 0, 'rights': [
                {
                    'organization': {'code': '12345678', 'name': 'ORG_NAME'},
                    'person': {
                        'code': '12345678901', 'first_name': 'F_NAME', 'last_name': 'L_NAME'},
                    'right': {
                        'revoked': False, 'right_type': 'RIGHT1',
                        'valid_from': '2020-01-01T10:35:45.000555',
                        'valid_to': '2020-02-10T10:35:45.000555'}},
                {
                    'organization': {'code': '12345678', 'name': 'ORG_NAME'},
                    'person': {
                        'code': '12345678901', 'first_name': 'F_NAME', 'last_name': 'L_NAME'},
                    'right': {
                        'revoked': False, 'right_type': 'RIGHT2',
                        'valid_from': '2020-01-01T10:35:45.000555',
                        'valid_to': '2020-02-10T10:35:45.000555'}}],
            'total': 1}
        self.assertEqual(expected, rights.search_rights(cur, **kwargs))
        cur.execute.assert_has_calls([
            call('SQL1', {
                'persons': ['12345678901', '12345678902'],
                'organizations': ['12345678', '12345679'], 'rights': ['RIGHTS1', 'RIGHTS2'],
                'limit': 10, 'offset': 0}),
            call('SQL2', {
                'persons': ['12345678901', '12345678902'],
                'organizations': ['12345678', '12345679'], 'rights': ['RIGHTS1', 'RIGHTS2'],
                'limit': 10, 'offset': 0})])
        mock_get_search_rights_sql.assert_called_with(
            True, ['12345678901', '12345678902'], ['12345678', '12345679'], ['RIGHTS1', 'RIGHTS2'])

    def test_make_response(self):
        with self.app.app_context():
            with self.assertLogs(rights.LOGGER, level='INFO') as cm:
                expected_json = {'code': 'CODE', 'msg': 'MSG', 'response': 'RESPONSE'}
                response = rights.make_response(
                    {'code': 'CODE', 'msg': 'MSG', 'response': 'RESPONSE', 'http_status': 200},
                    'HEADER: ')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(expected_json, response.get_json())
                self.assertEqual([
                    "INFO:rights:HEADER: Response: {'code': 'CODE', 'msg': 'MSG', 'response': "
                    "'RESPONSE', 'http_status': 200}"], cm.output)

    def test_make_response_no_response(self):
        with self.app.app_context():
            with self.assertLogs(rights.LOGGER, level='INFO') as cm:
                expected_json = {'code': 'CODE', 'msg': 'MSG'}
                response = rights.make_response(
                    {'code': 'CODE', 'msg': 'MSG', 'http_status': 200},
                    'HEADER: ')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(expected_json, response.get_json())
                self.assertEqual([
                    "INFO:rights:HEADER: Response: {'code': 'CODE', 'msg': 'MSG', "
                    "'http_status': 200}"], cm.output)

    def test_make_response_debug(self):
        with self.app.app_context():
            with self.assertLogs(rights.LOGGER, level='DEBUG') as cm:
                expected_json = {'code': 'CODE', 'msg': 'MSG', 'response': 'RESPONSE'}
                response = rights.make_response(
                    {'code': 'CODE', 'msg': 'MSG', 'response': 'RESPONSE', 'http_status': 200},
                    'HEADER: ', log_level='debug')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(expected_json, response.get_json())
                self.assertEqual([
                    "DEBUG:rights:HEADER: Response: {'code': 'CODE', 'msg': 'MSG', 'response': "
                    "'RESPONSE', 'http_status': 200}"], cm.output)

    def test_validate_config(self):
        self.assertEqual(None, rights.validate_config(self.config, 'HEADER: '))

    def test_validate_config_no_field(self):
        field_list = ['db_host', 'db_port', 'db_db', 'db_user', 'db_pass']
        for field in field_list:
            my_config = self.config.copy()
            del my_config[field]
            with self.assertLogs(rights.LOGGER, level='INFO') as cm:
                expected = {
                    'code': 'DB_CONF_ERROR', 'http_status': 500,
                    'msg': 'Cannot access database configuration'}
                self.assertEqual(expected, rights.validate_config(my_config, 'HEADER: '))
                self.assertEqual(
                    ['ERROR:rights:HEADER: DB_CONF_ERROR: Cannot access database configuration'],
                    cm.output)

    def test_get_required_parameter(self):
        self.assertEqual(
            ('y', None),
            rights.get_required_parameter('x', {'x': 'y', 'a': 'b'}, 'HEADER: '))

    def test_get_required_parameter_missing(self):
        with self.assertLogs(rights.LOGGER, level='INFO') as cm:
            self.assertEqual(
                (None, {
                    'code': 'MISSING_PARAMETER', 'http_status': 400,
                    'msg': 'Missing parameter "z"'}),
                rights.get_required_parameter('z', {'x': 'y', 'a': 'b'}, 'HEADER: '))
            self.assertEqual(
                [
                    'WARNING:rights:HEADER: MISSING_PARAMETER: Missing parameter "z" (Request: '
                    "{'x': 'y', 'a': 'b'})"],
                cm.output)

    def test_check_required_dict_item(self):
        self.assertEqual(
            None,
            rights.check_required_dict_item('x', 'a', {'x': {'a': 'b'}}, 'HEADER: '))

    def test_check_required_dict_item_missing(self):
        with self.assertLogs(rights.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'MISSING_PARAMETER', 'http_status': 400,
                    'msg': 'Missing parameter "x->z"'},
                rights.check_required_dict_item('x', 'z', {'x': {'a': 'b'}}, 'HEADER: '))
            self.assertEqual(
                [
                    'WARNING:rights:HEADER: MISSING_PARAMETER: Missing parameter "x->z" (Request: '
                    "{'x': {'a': 'b'}})"],
                cm.output)

    def test_get_dict_parameter(self):
        self.assertEqual(
            {'a1': 'b1', 'a3': 'b3'},
            rights.get_dict_parameter('x', ['a1', 'a3'], {
                'x': {'a1': 'b1', 'a2': 'b2', 'a3': 'b3'}}))

    def test_get_dict_parameter_missing(self):
        self.assertEqual(
            {'a3': 'b3', 'a4': None},
            rights.get_dict_parameter('x', ['a3', 'a4'], {
                'x': {'a1': 'b1', 'a2': 'b2', 'a3': 'b3'}}))

    def test_get_list_of_strings_parameter(self):
        self.assertEqual(
            ['y1', 'y2', 'y3'],
            rights.get_list_of_strings_parameter('x', {'x': ['y1', 'y2', 'y3']}))

    def test_get_list_of_strings_missing(self):
        self.assertEqual(
            [],
            rights.get_list_of_strings_parameter('y', {'x': ['y1', 'y2', 'y3']}))

    def test_get_int_parameter(self):
        self.assertEqual(
            123,
            rights.get_int_parameter('x', {'x': 123}))

    def test_get_int_parameter_missing(self):
        self.assertEqual(
            None,
            rights.get_int_parameter('z', {'x': 123}))

    def test_get_bool_parameter(self):
        self.assertEqual(
            True,
            rights.get_bool_parameter('x', {'x': True}))

    def test_get_bool_parameter_missing(self):
        self.assertEqual(
            None,
            rights.get_bool_parameter('z', {'x': True}))

    def test_parse_timestamp(self):
        self.assertEqual(
            (datetime(2019, 8, 29, 14, 0), None),
            rights.parse_timestamp('2019-08-29T14:00:00.000000', {'x': 'y'}, 'HEADER: '))

    def test_parse_timestamp_second_format(self):
        self.assertEqual(
            (datetime(2019, 8, 29, 14, 0), None),
            rights.parse_timestamp('2019-08-29T14:00:00', {'x': 'y'}, 'HEADER: '))

    def test_parse_timestamp_none(self):
        self.assertEqual(
            (None, None),
            rights.parse_timestamp(None, {'x': 'y'}, 'HEADER: '))

    def test_parse_timestamp_invalid(self):
        with self.assertLogs(rights.LOGGER, level='INFO') as cm:
            self.assertEqual(
                (None, {
                    'code': 'INVALID_PARAMETER', 'http_status': 400,
                    'msg': 'Unrecognized timestamp: "invalid_timestamp"'}),
                rights.parse_timestamp('invalid_timestamp', {'x': 'y'}, 'HEADER: '))
            self.assertEqual(
                [
                    'WARNING:rights:HEADER: INVALID_PARAMETER: Unrecognized timestamp '
                    '"invalid_timestamp" (Request: {\'x\': \'y\'})'],
                cm.output)

    def test_get_datetime_now(self):
        self.assertIsInstance(rights.get_datetime_now(), datetime)

    @patch('rights.get_datetime_now', return_value=datetime(2019, 8, 1, 0, 0))
    def test_check_timestamp(self, datetime_mock):
        self.assertEqual(
            None,
            rights.check_timestamp(datetime(2019, 8, 29, 14, 0), {'x': 'y'}, 'HEADER: '))
        datetime_mock.assert_called_once()

    @patch('rights.get_datetime_now', return_value=datetime(2019, 9, 1, 0, 0))
    def test_check_timestamp_invalid(self, datetime_mock):
        with self.assertLogs(rights.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'INVALID_PARAMETER', 'http_status': 400,
                    'msg': 'Timestamps must be in the future'},
                rights.check_timestamp(datetime(2019, 8, 29, 14, 0), {'x': 'y'}, 'HEADER: '))
            self.assertEqual(
                [
                    'WARNING:rights:HEADER: INVALID_PARAMETER: timestamps must be in the future '
                    "(Request: {'x': 'y'})"],
                cm.output)
            datetime_mock.assert_called_once()

    @patch('rights.get_datetime_now', return_value=datetime(2019, 8, 1, 0, 0))
    def test_check_interval(self, _):
        self.assertEqual(
            None,
            rights.check_interval(
                datetime(2019, 8, 20, 14, 0), datetime(2019, 8, 29, 14, 0), {'x': 'y'}, 'HEADER: '))

    # Empty timestamps are accepted
    @patch('rights.get_datetime_now', return_value=datetime(2019, 8, 1, 0, 0))
    def test_check_interval_empty(self, _):
        self.assertEqual(
            None,
            rights.check_interval(
                None, None, {'x': 'y'}, 'HEADER: '))

    @patch('rights.get_datetime_now', return_value=datetime(2019, 8, 1, 0, 0))
    def test_check_interval_from_bigger(self, _):
        with self.assertLogs(rights.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'INVALID_PARAMETER',
                    'http_status': 400,
                    'msg': '"valid_from" must be smaller then "valid_to"'},
                rights.check_interval(
                    datetime(2019, 8, 29, 14, 0),
                    datetime(2019, 8, 20, 14, 0), {'x': 'y'}, 'HEADER: '))
            self.assertEqual(
                [
                    'WARNING:rights:HEADER: INVALID_PARAMETER: "valid_from" must be smaller then '
                    '"valid_to" (Request: {\'x\': \'y\'})'],
                cm.output)

    @patch('rights.get_datetime_now', return_value=datetime(2019, 8, 25, 0, 0))
    def test_check_interval_from_invalid(self, _):
        with self.assertLogs(rights.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'INVALID_PARAMETER',
                    'http_status': 400,
                    'msg': 'Timestamps must be in the future'},
                rights.check_interval(
                    datetime(2019, 8, 20, 14, 0),
                    datetime(2019, 8, 29, 14, 0), {'x': 'y'}, 'HEADER: '))
            self.assertEqual(
                [
                    'WARNING:rights:HEADER: INVALID_PARAMETER: timestamps must be in the future '
                    "(Request: {'x': 'y'})"],
                cm.output)

    @patch('rights.get_datetime_now', return_value=datetime(2019, 9, 1, 0, 0))
    def test_check_interval_to_invalid(self, _):
        with self.assertLogs(rights.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'INVALID_PARAMETER',
                    'http_status': 400,
                    'msg': 'Timestamps must be in the future'},
                rights.check_interval(
                    None,
                    datetime(2019, 8, 29, 14, 0), {'x': 'y'}, 'HEADER: '))
            self.assertEqual(
                [
                    'WARNING:rights:HEADER: INVALID_PARAMETER: timestamps must be in the future '
                    "(Request: {'x': 'y'})"],
                cm.output)

    @patch('rights.parse_timestamp', return_value=(None, None))
    def test_parse_interval(self, _):
        self.assertEqual(
            (None, None, None),
            rights.parse_interval(
                None, None, {'x': 'y'}, 'HEADER: '))

    @patch('rights.parse_timestamp', return_value=(None, 'ERR'))
    def test_parse_interval_from_invalid(self, _):
        self.assertEqual(
            (None, None, 'ERR'),
            rights.parse_interval(
                'X', None, {'x': 'y'}, 'HEADER: '))

    @patch('rights.parse_timestamp', side_effect=[(None, None), (None, 'ERR')])
    def test_parse_interval_to_invalid(self, _):
        # Should return 'ERR' after second call to parse_timestamp
        self.assertEqual(
            (None, None, 'ERR'),
            rights.parse_interval(
                'X', None, {'x': 'y'}, 'HEADER: '))

    @patch('rights.parse_timestamp', return_value=(None, None))
    @patch('rights.check_interval', return_value='ERR')
    def test_parse_interval_interval_invalid(self, *_):
        # Should return 'ERR' after call to check_interval
        self.assertEqual(
            (None, None, 'ERR'),
            rights.parse_interval(
                'X', 'Y', {'x': 'y'}, 'HEADER: '))

    @patch('rights.check_required_dict_item', return_value=None)
    def test_validate_set_right_request(self, check_required_dict_item_mock):
        json_data = {
            'organization': {'code': '00000000'},
            'person': {'code': '12345678901'},
            'right': {'right_type': 'RIGHT1'}}
        self.assertEqual(
            (
                {
                    'organization': {'code': '00000000', 'name': None},
                    'person': {'code': '12345678901', 'first_name': None, 'last_name': None},
                    'right': {'right_type': 'RIGHT1', 'valid_from': None, 'valid_to': None}},
                None),
            rights.validate_set_right_request(json_data, 'HEADER: '))
        check_required_dict_item_mock.assert_has_calls([
            call('person', 'code', json_data, 'HEADER: '),
            call('organization', 'code', json_data, 'HEADER: '),
            call('right', 'right_type', json_data, 'HEADER: ')
        ])

    @patch('rights.check_required_dict_item', return_value='ERR')
    def test_validate_set_right_request_invalid(self, check_required_dict_item_mock):
        json_data = {}
        self.assertEqual(
            (None, 'ERR'),
            rights.validate_set_right_request(json_data, 'HEADER: '))
        check_required_dict_item_mock.assert_has_calls([
            call('person', 'code', json_data, 'HEADER: ')
        ])

    @patch('rights.get_datetime_now', return_value=datetime(2019, 9, 1, 0, 0))
    @patch('rights.check_required_dict_item', return_value=None)
    def test_validate_set_right_request_invalid_ts(self, *_):
        json_data = {
            'organization': {'code': '00000000'},
            'person': {'code': '12345678901'},
            'right': {'right_type': 'RIGHT1', 'valid_from': '2019-08-29T14:00:00'}}
        with self.assertLogs(rights.LOGGER, level='INFO') as cm:
            self.assertEqual(
                (
                    None,
                    {
                        'code': 'INVALID_PARAMETER', 'http_status': 400,
                        'msg': 'Timestamps must be in the future'}),
                rights.validate_set_right_request(json_data, 'HEADER: '))
            self.assertEqual(
                [
                    'WARNING:rights:HEADER: INVALID_PARAMETER: timestamps must be in the future '
                    "(Request: {'organization': {'code': '00000000'}, 'person': {'code': "
                    "'12345678901'}, 'right': {'right_type': 'RIGHT1', 'valid_from': "
                    "'2019-08-29T14:00:00'}})"],
                cm.output)

    @patch('rights.add_right')
    @patch('rights.revoke_right')
    @patch('rights.set_organization', return_value=123)
    @patch('rights.set_person', return_value=12345)
    @patch('rights.get_db_connection')
    @patch('rights.validate_set_right_request', return_value=({
        'organization': {'code': '00000000', 'name': None},
        'person': {'code': '12345678901', 'first_name': None, 'last_name': None},
        'right': {'right_type': 'RIGHT1', 'valid_from': None, 'valid_to': None}}, None))
    @patch('rights.validate_config', return_value=None)
    def test_process_set_right(
            self, validate_config_mock, validate_set_right_request_mock, get_db_connection_mock,
            set_person_mock, set_organization_mock, revoke_right_mock, add_right_mock):
        with self.assertLogs(rights.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {'code': 'CREATED', 'http_status': 201, 'msg': 'New right added'},
                rights.process_set_right(
                    {'CONF': 'data'}, {'x': 'y'}, 'HEADER: '))
            validate_config_mock.assert_called_once()
            validate_set_right_request_mock.assert_called_once()
            get_db_connection_mock.assert_called_once()
            cursor_mock = get_db_connection_mock.return_value.__enter__.return_value.cursor
            cursor_mock.assert_called_once()
            cursor_return_mock = cursor_mock.return_value.__enter__.return_value
            set_person_mock.assert_called_with(cursor_return_mock, '12345678901', None, None)
            set_organization_mock.assert_called_with(cursor_return_mock, '00000000', None)
            revoke_right_mock.assert_called_with(cursor_return_mock, 12345, 123, 'RIGHT1')
            add_right_mock.assert_called_with(
                cursor_return_mock, organization_id=123, person_id=12345,
                right_type='RIGHT1', valid_from=None, valid_to=None)
            commit_mock = get_db_connection_mock.return_value.__enter__.return_value.commit
            commit_mock.assert_called_once()
            self.assertEqual(
                [
                    'INFO:rights:HEADER: Added new Right: person_code=12345678901, '
                    'organization_code=00000000, right_type=RIGHT1'],
                cm.output)

    @patch('rights.validate_config', return_value='ERR')
    def test_process_set_right_config_err(self, _):
        self.assertEqual(
            'ERR',
            rights.process_set_right(
                {'CONF': 'ERR'}, {'x': 'y'}, 'HEADER: '))

    @patch('rights.validate_set_right_request', return_value=(None, 'ERR'))
    @patch('rights.validate_config', return_value=None)
    def test_process_set_right_request_err(self, validate_config_mock, _):
        self.assertEqual(
            'ERR',
            rights.process_set_right(
                {'CONF': 'data'}, {'x': 'y'}, 'HEADER: '))
        validate_config_mock.assert_called_once()

    def test_validate_revoke_right_request(self):
        json_data = {
            'organization_code': '00000000',
            'person_code': '12345678901',
            'right_type': 'RIGHT1'}
        self.assertEqual(
            (
                {
                    'organization_code': '00000000',
                    'person_code': '12345678901',
                    'right_type': 'RIGHT1'},
                None),
            rights.validate_revoke_right_request(json_data, 'HEADER: '))

    @patch('rights.get_required_parameter', return_value=(None, 'ERR'))
    def test_validate_revoke_right_request_invalid(self, get_required_parameter_mock):
        json_data = {}
        self.assertEqual(
            (None, 'ERR'),
            rights.validate_revoke_right_request(json_data, 'HEADER: '))
        get_required_parameter_mock.assert_has_calls([
            call('person_code', json_data, 'HEADER: ')
        ])

    @patch('rights.revoke_right')
    @patch('rights.get_organization', return_value=(123, 'ON'))
    @patch('rights.get_person', return_value=(12345, 'FN', 'LN'))
    @patch('rights.get_db_connection')
    @patch('rights.validate_revoke_right_request', return_value=({
        'organization_code': '00000000',
        'person_code': '12345678901',
        'right_type': 'RIGHT1'}, None))
    @patch('rights.validate_config', return_value=None)
    def test_process_revoke_right(
            self, validate_config_mock, validate_revoke_right_request_mock, get_db_connection_mock,
            get_person_mock, get_organization_mock, revoke_right_mock):
        with self.assertLogs(rights.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {'code': 'OK', 'http_status': 200, 'msg': 'Right revoked'},
                rights.process_revoke_right(
                    {'CONF': 'data'}, {'x': 'y'}, 'HEADER: '))
            validate_config_mock.assert_called_once()
            validate_revoke_right_request_mock.assert_called_once()
            get_db_connection_mock.assert_called_once()
            cursor_mock = get_db_connection_mock.return_value.__enter__.return_value.cursor
            cursor_mock.assert_called_once()
            cursor_return_mock = cursor_mock.return_value.__enter__.return_value
            get_person_mock.assert_called_with(cursor_return_mock, '12345678901')
            get_organization_mock.assert_called_with(cursor_return_mock, '00000000')
            revoke_right_mock.assert_called_with(cursor_return_mock, 12345, 123, 'RIGHT1')
            commit_mock = get_db_connection_mock.return_value.__enter__.return_value.commit
            commit_mock.assert_called_once()
            self.assertEqual(
                [
                    'INFO:rights:HEADER: Revoked Right: person_code=12345678901, '
                    'organization_code=00000000, right_type=RIGHT1'],
                cm.output)

    @patch('rights.validate_config', return_value='ERR')
    def test_process_revoke_right_config_err(self, _):
        self.assertEqual(
            'ERR',
            rights.process_revoke_right(
                {'CONF': 'ERR'}, {'x': 'y'}, 'HEADER: '))

    @patch('rights.validate_revoke_right_request', return_value=(None, 'ERR'))
    @patch('rights.validate_config', return_value=None)
    def test_process_revoke_right_request_err(self, validate_revoke_right_request_mock, _):
        self.assertEqual(
            'ERR',
            rights.process_revoke_right(
                {'CONF': 'data'}, {'x': 'y'}, 'HEADER: '))
        validate_revoke_right_request_mock.assert_called_once()

    @patch('rights.revoke_right', return_value=0)
    @patch('rights.get_organization', return_value=(123, 'ON'))
    @patch('rights.get_person', return_value=(12345, 'FN', 'LN'))
    @patch('rights.get_db_connection')
    @patch('rights.validate_revoke_right_request', return_value=({
        'organization_code': '00000000',
        'person_code': '12345678901',
        'right_type': 'RIGHT1'}, None))
    @patch('rights.validate_config', return_value=None)
    def test_process_revoke_right_not_found(
            self, validate_config_mock, validate_revoke_right_request_mock, get_db_connection_mock,
            get_person_mock, get_organization_mock, revoke_right_mock):
        self.assertEqual(
            {'code': 'RIGHT_NOT_FOUND', 'http_status': 200, 'msg': 'No right was found'},
            rights.process_revoke_right(
                {'CONF': 'data'}, {'x': 'y'}, 'HEADER: '))
        validate_config_mock.assert_called_once()
        validate_revoke_right_request_mock.assert_called_once()
        get_db_connection_mock.assert_called_once()
        cursor_mock = get_db_connection_mock.return_value.__enter__.return_value.cursor
        cursor_mock.assert_called_once()
        cursor_return_mock = cursor_mock.return_value.__enter__.return_value
        get_person_mock.assert_called_with(cursor_return_mock, '12345678901')
        get_organization_mock.assert_called_with(cursor_return_mock, '00000000')
        revoke_right_mock.assert_called_with(cursor_return_mock, 12345, 123, 'RIGHT1')
        commit_mock = get_db_connection_mock.return_value.__enter__.return_value.commit
        commit_mock.assert_not_called()

    def test_validate_search_rights_request(self):
        json_data = {
            'organizations': ['00000000', '00000001'],
            'persons': ['12345678901', '12345'],
            'rights': ['RIGHT1', 'XXX'],
            'only_valid': False,
            'limit': 5,
            'offset': 3}
        self.assertEqual(
            {
                'limit': 5,
                'offset': 3,
                'only_valid': False,
                'organizations': ['00000000', '00000001'],
                'persons': ['12345678901', '12345'],
                'rights': ['RIGHT1', 'XXX']},
            rights.validate_search_rights_request(json_data))

    def test_validate_search_rights_request_defaults(self):
        json_data = {
            'organizations': ['00000000', '00000001'],
            'persons': ['12345678901', '12345'],
            'rights': ['RIGHT1', 'XXX']}
        self.assertEqual(
            {
                'limit': 100,
                'offset': 0,
                'only_valid': True,
                'organizations': ['00000000', '00000001'],
                'persons': ['12345678901', '12345'],
                'rights': ['RIGHT1', 'XXX']},
            rights.validate_search_rights_request(json_data))

    @patch('rights.search_rights', return_value={
        'total': 150,
        'offset': 0,
        'rights': [1, 2, 3]
    })
    @patch('rights.get_db_connection')
    @patch('rights.validate_search_rights_request', return_value={
        'limit': 100,
        'offset': 0,
        'only_valid': True,
        'organizations': ['00000000', '00000001'],
        'persons': ['12345678901', '12345'],
        'rights': ['RIGHT1', 'XXX']})
    @patch('rights.validate_config', return_value=None)
    def test_process_search_rights(
            self, validate_config_mock, validate_search_rights_request_mock,
            get_db_connection_mock, search_rights_mock):
        with self.assertLogs(rights.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'OK', 'http_status': 200, 'msg': 'Found 150 rights',
                    'response': {'offset': 0, 'rights': [1, 2, 3], 'total': 150}},
                rights.process_search_rights(
                    {'CONF': 'data'}, {'x': 'y'}, 'HEADER: '))
            validate_config_mock.assert_called_once()
            validate_search_rights_request_mock.assert_called_once()
            get_db_connection_mock.assert_called_once()
            cursor_mock = get_db_connection_mock.return_value.__enter__.return_value.cursor
            cursor_mock.assert_called_once()
            cursor_return_mock = cursor_mock.return_value.__enter__.return_value
            search_rights_mock.assert_called_with(
                cursor_return_mock, limit=100, offset=0, only_valid=True,
                organizations=['00000000', '00000001'], persons=['12345678901', '12345'],
                rights=['RIGHT1', 'XXX'])
            self.assertEqual(
                ['INFO:rights:HEADER: Found 150 rights, returning 3 rights with offset 0'],
                cm.output)

    @patch('rights.validate_config', return_value='ERR')
    def test_process_search_rights_config_err(self, _):
        self.assertEqual(
            'ERR',
            rights.process_search_rights(
                {'CONF': 'ERR'}, {'x': 'y'}, 'HEADER: '))

    def test_validate_set_person_request(self):
        json_data = {
            "code": "12345678901",
            "first_name": "First-name",
            "last_name": "Last-name"}
        self.assertEqual(
            (
                {'code': '12345678901', 'first_name': 'First-name', 'last_name': 'Last-name'},
                None),
            rights.validate_set_person_request(json_data, 'HEADER: '))

    @patch('rights.get_required_parameter', return_value=(None, 'ERR'))
    def test_validate_set_person_request_no_code(self, get_required_parameter_mock):
        json_data = {
            "first_name": "First-name",
            "last_name": "Last-name"}
        self.assertEqual(
            (None, 'ERR'),
            rights.validate_set_person_request(json_data, 'HEADER: '))
        get_required_parameter_mock.assert_called_once()

    @patch('rights.set_person')
    @patch('rights.get_db_connection')
    @patch('rights.validate_set_person_request', return_value=(
        {'code': '12345678901', 'first_name': 'First-name', 'last_name': 'Last-name'},
        None))
    @patch('rights.validate_config', return_value=None)
    def test_process_set_person(
            self, validate_config_mock, validate_set_person_request_mock,
            get_db_connection_mock, set_person_mock):
        with self.assertLogs(rights.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {'code': 'OK', 'http_status': 200, 'msg': 'Person updated'},
                rights.process_set_person(
                    {'CONF': 'data'}, {'x': 'y'}, 'HEADER: '))
            validate_config_mock.assert_called_once()
            validate_set_person_request_mock.assert_called_once()
            get_db_connection_mock.assert_called_once()
            cursor_mock = get_db_connection_mock.return_value.__enter__.return_value.cursor
            cursor_mock.assert_called_once()
            cursor_return_mock = cursor_mock.return_value.__enter__.return_value
            set_person_mock.assert_called_with(
                cursor_return_mock, '12345678901', 'First-name', 'Last-name')
            self.assertEqual(
                ['INFO:rights:HEADER: Person updated: code=12345678901'],
                cm.output)

    @patch('rights.validate_config', return_value='ERR')
    def test_process_set_person_config_err(self, _):
        self.assertEqual(
            'ERR',
            rights.process_set_person(
                {'CONF': 'ERR'}, {'x': 'y'}, 'HEADER: '))

    @patch('rights.validate_set_person_request', return_value=(None, 'REQ_ERR'))
    @patch('rights.validate_config', return_value=None)
    def test_process_set_person_req_err(self, *_):
        self.assertEqual(
            'REQ_ERR',
            rights.process_set_person(
                {'CONF': 'data'}, {'x': 'y'}, 'HEADER: '))

    def test_validate_set_organization_request(self):
        json_data = {
            'code': '00000000',
            'name': 'Org name'}
        self.assertEqual(
            ({'code': '00000000', 'name': 'Org name'}, None),
            rights.validate_set_organization_request(json_data, 'HEADER: '))

    @patch('rights.get_required_parameter', return_value=(None, 'ERR'))
    def test_validate_set_organization_request_no_code(self, get_required_parameter_mock):
        json_data = {'name': 'Org name'}
        self.assertEqual(
            (None, 'ERR'),
            rights.validate_set_organization_request(json_data, 'HEADER: '))
        get_required_parameter_mock.assert_called_once()

    @patch('rights.set_organization')
    @patch('rights.get_db_connection')
    @patch('rights.validate_set_organization_request', return_value=(
        {'code': '00000000', 'name': 'Org name'},
        None))
    @patch('rights.validate_config', return_value=None)
    def test_process_set_organization(
            self, validate_config_mock, validate_set_organization_request_mock,
            get_db_connection_mock, set_person_mock):
        with self.assertLogs(rights.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {'code': 'OK', 'http_status': 200, 'msg': 'Organization updated'},
                rights.process_set_organization(
                    {'CONF': 'data'}, {'x': 'y'}, 'HEADER: '))
            validate_config_mock.assert_called_once()
            validate_set_organization_request_mock.assert_called_once()
            get_db_connection_mock.assert_called_once()
            cursor_mock = get_db_connection_mock.return_value.__enter__.return_value.cursor
            cursor_mock.assert_called_once()
            cursor_return_mock = cursor_mock.return_value.__enter__.return_value
            set_person_mock.assert_called_with(
                cursor_return_mock, '00000000', 'Org name')
            self.assertEqual(
                ['INFO:rights:HEADER: Organization updated: code=00000000'],
                cm.output)

    @patch('rights.validate_config', return_value='ERR')
    def test_process_set_organization_config_err(self, _):
        self.assertEqual(
            'ERR',
            rights.process_set_organization(
                {'CONF': 'ERR'}, {'x': 'y'}, 'HEADER: '))

    @patch('rights.validate_set_organization_request', return_value=(None, 'REQ_ERR'))
    @patch('rights.validate_config', return_value=None)
    def test_process_set_organization_req_err(self, *_):
        self.assertEqual(
            'REQ_ERR',
            rights.process_set_organization(
                {'CONF': 'data'}, {'x': 'y'}, 'HEADER: '))

    def test_check_client(self):
        # Client allowed
        self.assertEqual(
            True,
            rights.check_client(self.config, 'OU=xtss,O=RIA,C=EE'))
        # Client not allowed
        self.assertEqual(
            False,
            rights.check_client(self.config, 'OU=xtss2,O=RIA,C=EE'))
        # No client
        self.assertEqual(
            False,
            rights.check_client(self.config, None))
        # Invalid config ('allowed' is not 'list')
        self.assertEqual(
            False,
            rights.check_client(
                {
                    'allow_all': False,
                    'allowed': 'OU=xtss,O=RIA,C=EE'},
                'OU=xtss,O=RIA,C=EE'))
        # All clients allowed
        self.assertEqual(
            True,
            rights.check_client({'allow_all': True}, 'OU=xtss,O=RIA,C=EE'))
        # No configuration
        self.assertEqual(
            False,
            rights.check_client({}, 'OU=xtss,O=RIA,C=EE'))

    @patch('rights.make_response', return_value='ERR')
    def test_incorrect_client(self, _):
        with self.assertLogs(rights.LOGGER, level='INFO') as cm:
            self.assertEqual(
                'ERR',
                rights.incorrect_client('CLIENT_DN', 'HEADER: '))
            self.assertEqual(
                ['ERROR:rights:HEADER: FORBIDDEN: Client certificate is not allowed: CLIENT_DN'],
                cm.output)

    @patch('rights.get_db_connection')
    @patch('rights.validate_config', return_value=None)
    def test_test_db(self, _, get_db_connection_mock):
        self.assertEqual(
            {'code': 'OK', 'http_status': 200, 'msg': 'API is ready'},
            rights.test_db(self.config, 'HEADER: '))
        cursor_mock = get_db_connection_mock.return_value.__enter__.return_value.cursor
        cursor_mock.assert_called_once()
        cursor_return_mock = cursor_mock.return_value.__enter__.return_value
        cursor_return_mock.execute.assert_called_with('select count(1) from rights."right";')

    @patch('rights.validate_config', return_value='ERR')
    def test_test_db_no_conf(self, _):
        self.assertEqual('ERR', rights.test_db(self.config, 'HEADER: '))

    @patch('uuid.uuid4', return_value='UUID4')
    def test_get_log_header(self, _):
        with self.app.test_request_context('url'):
            self.assertEqual('[METHOD] ', rights.get_log_header('METHOD'))
        with self.app.test_request_context('url', headers={'X-B3-TraceId': 'TRACE_ID'}):
            self.assertEqual('[METHOD TRACE_ID,UUID4] ', rights.get_log_header('METHOD'))

    @patch('rights.check_client', return_value=False)
    def test_set_right_incorrect_client(self, mock_check_client):
        with self.app.app_context():
            with self.assertLogs(rights.LOGGER, level='INFO') as cm:
                json_data = {
                    'organization': {'code': '00000000'},
                    'person': {'code': '12345678901'},
                    'right': {'right_type': 'RIGHT1'}}
                response = self.client.post('/set-right', json=json_data)
                self.assertEqual(403, response.status_code)
                self.assertEqual(
                    jsonify({
                        'code': 'FORBIDDEN',
                        'msg': 'Client certificate is not allowed: None'}).json,
                    response.json
                )
                self.assertEqual([
                    f"INFO:rights:[SetRight:post] {rights.INCOMING_REQUEST_MSG}: "
                    "{'organization': {'code': '00000000'}, 'person': {'code': '12345678901'}, "
                    "'right': {'right_type': 'RIGHT1'}}",
                    'INFO:rights:[SetRight:post] Client DN: None',
                    'ERROR:rights:[SetRight:post] FORBIDDEN: Client certificate is not allowed: '
                    'None',
                    "INFO:rights:[SetRight:post] Response: {'http_status': 403, 'code': "
                    "'FORBIDDEN', 'msg': 'Client certificate is not allowed: None'}"], cm.output)
                mock_check_client.assert_called_with({
                    'db_host': 'localhost', 'db_port': '5432',
                    'db_db': 'postgres', 'db_user': 'postgres',
                    'db_pass': 'password', 'db_connect_timeout': 10, 'allow_all': False,
                    'allowed': ['OU=xtss,O=RIA,C=EE']}, None)

    @patch('rights.process_set_right', side_effect=psycopg2.Error('DB_ERROR_MSG'))
    @patch('rights.check_client', return_value=True)
    def test_set_right_db_error_handled(self, mock_check_client, mock_process_set_right):
        with self.app.app_context():
            with self.assertLogs(rights.LOGGER, level='INFO') as cm:
                json_data = {
                    'organization': {'code': '00000000'},
                    'person': {'code': '12345678901'},
                    'right': {'right_type': 'RIGHT1'}}
                response = self.client.post('/set-right', json=json_data)
                self.assertEqual(500, response.status_code)
                self.assertEqual(
                    jsonify({
                        'code': 'DB_ERROR',
                        'msg': rights.DB_ERROR_MSG}).json,
                    response.json
                )
                self.assertEqual([
                    f"INFO:rights:[SetRight:post] {rights.INCOMING_REQUEST_MSG}: "
                    "{'organization': {'code': '00000000'}, 'person': {'code': '12345678901'}, "
                    "'right': {'right_type': 'RIGHT1'}}",
                    'INFO:rights:[SetRight:post] Client DN: None',
                    f'ERROR:rights:[SetRight:post] DB_ERROR: {rights.DB_ERROR_MSG}: '
                    'DB_ERROR_MSG',
                    "INFO:rights:[SetRight:post] Response: {'http_status': 500, 'code': "
                    f"'DB_ERROR', 'msg': '{rights.DB_ERROR_MSG}'"
                    "}"], cm.output)
                mock_check_client.assert_called_with({
                    'db_host': 'localhost', 'db_port': '5432',
                    'db_db': 'postgres', 'db_user': 'postgres',
                    'db_pass': 'password', 'db_connect_timeout': 10, 'allow_all': False,
                    'allowed': ['OU=xtss,O=RIA,C=EE']}, None)
                mock_process_set_right.assert_called_with({
                    'db_host': 'localhost', 'db_port': '5432', 'db_db': 'postgres',
                    'db_user': 'postgres', 'db_pass': 'password', 'db_connect_timeout': 10,
                    'allow_all': False, 'allowed': ['OU=xtss,O=RIA,C=EE']}, {
                        'organization': {'code': '00000000'}, 'person': {'code': '12345678901'},
                        'right': {'right_type': 'RIGHT1'}},
                    '[SetRight:post] ')

    @patch('rights.process_set_right', return_value={
        'http_status': 200, 'code': 'OK', 'msg': 'SET_RIGHT_OK'})
    @patch('rights.check_client', return_value=True)
    def test_set_right_ok(self, mock_check_client, mock_process_set_right):
        with self.app.app_context():
            with self.assertLogs(rights.LOGGER, level='INFO') as cm:
                json_data = {
                    'organization': {'code': '00000000'},
                    'person': {'code': '12345678901'},
                    'right': {'right_type': 'RIGHT1'}}
                response = self.client.post('/set-right', json=json_data)
                self.assertEqual(200, response.status_code)
                self.assertEqual(
                    jsonify({'code': 'OK', 'msg': 'SET_RIGHT_OK'}).json,
                    response.json
                )
                self.assertEqual([
                    f"INFO:rights:[SetRight:post] {rights.INCOMING_REQUEST_MSG}: "
                    "{'organization': {'code': '00000000'}, 'person': {'code': '12345678901'}, "
                    "'right': {'right_type': 'RIGHT1'}}",
                    'INFO:rights:[SetRight:post] Client DN: None',
                    "INFO:rights:[SetRight:post] Response: {'http_status': 200, 'code': 'OK', "
                    "'msg': 'SET_RIGHT_OK'}"], cm.output)
                mock_check_client.assert_called_with({
                    'db_host': 'localhost', 'db_port': '5432',
                    'db_db': 'postgres', 'db_user': 'postgres',
                    'db_pass': 'password', 'db_connect_timeout': 10, 'allow_all': False,
                    'allowed': ['OU=xtss,O=RIA,C=EE']}, None)
                mock_process_set_right.assert_called_with({
                    'db_host': 'localhost', 'db_port': '5432', 'db_db': 'postgres',
                    'db_user': 'postgres', 'db_pass': 'password', 'db_connect_timeout': 10,
                    'allow_all': False, 'allowed': ['OU=xtss,O=RIA,C=EE']}, {
                        'organization': {'code': '00000000'}, 'person': {'code': '12345678901'},
                        'right': {'right_type': 'RIGHT1'}},
                    '[SetRight:post] ')

    @patch('rights.check_client', return_value=False)
    def test_revoke_right_incorrect_client(self, mock_check_client):
        with self.app.app_context():
            with self.assertLogs(rights.LOGGER, level='INFO') as cm:
                json_data = {
                    'organization_code': '00000000',
                    'person_code': '12345678901',
                    'right_type': 'RIGHT1'}
                response = self.client.post('/revoke-right', json=json_data)
                self.assertEqual(403, response.status_code)
                self.assertEqual(
                    jsonify({
                        'code': 'FORBIDDEN',
                        'msg': 'Client certificate is not allowed: None'}).json,
                    response.json
                )
                self.assertEqual([
                    f"INFO:rights:[RevokeRight:post] {rights.INCOMING_REQUEST_MSG}: "
                    "{'organization_code': "
                    "'00000000', 'person_code': '12345678901', 'right_type': 'RIGHT1'}",
                    'INFO:rights:[RevokeRight:post] Client DN: None',
                    'ERROR:rights:[RevokeRight:post] FORBIDDEN: Client certificate is not '
                    'allowed: None',
                    "INFO:rights:[RevokeRight:post] Response: {'http_status': 403, 'code': "
                    "'FORBIDDEN', 'msg': 'Client certificate is not allowed: None'}"], cm.output)
                mock_check_client.assert_called_with({
                    'db_host': 'localhost', 'db_port': '5432',
                    'db_db': 'postgres', 'db_user': 'postgres',
                    'db_pass': 'password', 'db_connect_timeout': 10, 'allow_all': False,
                    'allowed': ['OU=xtss,O=RIA,C=EE']}, None)

    @patch('rights.process_revoke_right', side_effect=psycopg2.Error('DB_ERROR_MSG'))
    @patch('rights.check_client', return_value=True)
    def test_revoke_right_db_error_handled(self, mock_check_client, mock_process_revoke_right):
        with self.app.app_context():
            with self.assertLogs(rights.LOGGER, level='INFO') as cm:
                json_data = {
                    'organization_code': '00000000',
                    'person_code': '12345678901',
                    'right_type': 'RIGHT1'}
                response = self.client.post('/revoke-right', json=json_data)
                self.assertEqual(500, response.status_code)
                self.assertEqual(
                    jsonify({
                        'code': 'DB_ERROR',
                        'msg': rights.DB_ERROR_MSG}).json,
                    response.json
                )
                self.assertEqual([
                    f"INFO:rights:[RevokeRight:post] {rights.INCOMING_REQUEST_MSG}: "
                    "{'organization_code': "
                    "'00000000', 'person_code': '12345678901', 'right_type': 'RIGHT1'}",
                    'INFO:rights:[RevokeRight:post] Client DN: None',
                    f'ERROR:rights:[RevokeRight:post] DB_ERROR: {rights.DB_ERROR_MSG}: '
                    'DB_ERROR_MSG',
                    "INFO:rights:[RevokeRight:post] Response: {'http_status': 500, 'code': "
                    f"'DB_ERROR', 'msg': '{rights.DB_ERROR_MSG}'"
                    "}"], cm.output)
                mock_check_client.assert_called_with({
                    'db_host': 'localhost', 'db_port': '5432',
                    'db_db': 'postgres', 'db_user': 'postgres',
                    'db_pass': 'password', 'db_connect_timeout': 10, 'allow_all': False,
                    'allowed': ['OU=xtss,O=RIA,C=EE']}, None)
                mock_process_revoke_right.assert_called_with(
                    {
                        'db_host': 'localhost', 'db_port': '5432', 'db_db': 'postgres',
                        'db_user': 'postgres', 'db_pass': 'password', 'db_connect_timeout': 10,
                        'allow_all': False, 'allowed': ['OU=xtss,O=RIA,C=EE']
                    }, {
                        'organization_code': '00000000', 'person_code': '12345678901',
                        'right_type': 'RIGHT1'
                    }, '[RevokeRight:post] ')

    @patch('rights.process_revoke_right', return_value={
        'http_status': 200, 'code': 'OK', 'msg': 'REVOKE_RIGHT_OK'})
    @patch('rights.check_client', return_value=True)
    def test_revoke_right_ok(self, mock_check_client, mock_process_revoke_right):
        with self.app.app_context():
            with self.assertLogs(rights.LOGGER, level='INFO') as cm:
                json_data = {
                    'organization_code': '00000000',
                    'person_code': '12345678901',
                    'right_type': 'RIGHT1'}
                response = self.client.post('/revoke-right', json=json_data)
                self.assertEqual(200, response.status_code)
                self.assertEqual(
                    jsonify({'code': 'OK', 'msg': 'REVOKE_RIGHT_OK'}).json,
                    response.json
                )
                self.assertEqual([
                    f"INFO:rights:[RevokeRight:post] {rights.INCOMING_REQUEST_MSG}: "
                    "{'organization_code': "
                    "'00000000', 'person_code': '12345678901', 'right_type': 'RIGHT1'}",
                    'INFO:rights:[RevokeRight:post] Client DN: None',
                    "INFO:rights:[RevokeRight:post] Response: {'http_status': 200, 'code': 'OK', "
                    "'msg': 'REVOKE_RIGHT_OK'}"], cm.output)
                mock_check_client.assert_called_with({
                    'db_host': 'localhost', 'db_port': '5432',
                    'db_db': 'postgres', 'db_user': 'postgres',
                    'db_pass': 'password', 'db_connect_timeout': 10, 'allow_all': False,
                    'allowed': ['OU=xtss,O=RIA,C=EE']}, None)
                mock_process_revoke_right.assert_called_with(
                    {
                        'db_host': 'localhost', 'db_port': '5432', 'db_db': 'postgres',
                        'db_user': 'postgres', 'db_pass': 'password', 'db_connect_timeout': 10,
                        'allow_all': False, 'allowed': ['OU=xtss,O=RIA,C=EE']
                    }, {
                        'organization_code': '00000000', 'person_code': '12345678901',
                        'right_type': 'RIGHT1'}, '[RevokeRight:post] ')

    @patch('rights.check_client', return_value=False)
    def test_rights_incorrect_client(self, mock_check_client):
        with self.app.app_context():
            with self.assertLogs(rights.LOGGER, level='INFO') as cm:
                json_data = {
                    'organizations': ['00000000', '00000001'],
                    'persons': ['12345678901', '12345'],
                    'rights': ['RIGHT1', 'XXX'],
                    'only_valid': False,
                    'limit': 5,
                    'offset': 3}
                response = self.client.post('/rights', json=json_data)
                self.assertEqual(403, response.status_code)
                self.assertEqual(
                    jsonify({
                        'code': 'FORBIDDEN',
                        'msg': 'Client certificate is not allowed: None'}).json,
                    response.json
                )
                self.assertEqual([
                    f"INFO:rights:[Rights:post] {rights.INCOMING_REQUEST_MSG}: "
                    "{'limit': 5, 'offset': 3, "
                    "'only_valid': False, 'organizations': ['00000000', '00000001'], 'persons': "
                    "['12345678901', '12345'], 'rights': ['RIGHT1', 'XXX']}",
                    'INFO:rights:[Rights:post] Client DN: None',
                    'ERROR:rights:[Rights:post] FORBIDDEN: Client certificate is not allowed: '
                    'None',
                    "INFO:rights:[Rights:post] Response: {'http_status': 403, 'code': "
                    "'FORBIDDEN', 'msg': 'Client certificate is not allowed: None'}"], cm.output)
                mock_check_client.assert_called_with({
                    'db_host': 'localhost', 'db_port': '5432',
                    'db_db': 'postgres', 'db_user': 'postgres',
                    'db_pass': 'password', 'db_connect_timeout': 10, 'allow_all': False,
                    'allowed': ['OU=xtss,O=RIA,C=EE']}, None)

    @patch('rights.process_search_rights', side_effect=psycopg2.Error('DB_ERROR_MSG'))
    @patch('rights.check_client', return_value=True)
    def test_rights_db_error_handled(self, mock_check_client, mock_process_search_rights):
        with self.app.app_context():
            with self.assertLogs(rights.LOGGER, level='INFO') as cm:
                json_data = {
                    'organizations': ['00000000', '00000001'],
                    'persons': ['12345678901', '12345'],
                    'rights': ['RIGHT1', 'XXX'],
                    'only_valid': False,
                    'limit': 5,
                    'offset': 3}
                response = self.client.post('/rights', json=json_data)
                self.assertEqual(500, response.status_code)
                self.assertEqual(
                    jsonify({
                        'code': 'DB_ERROR',
                        'msg': rights.DB_ERROR_MSG}).json,
                    response.json
                )
                self.assertEqual([
                    f"INFO:rights:[Rights:post] {rights.INCOMING_REQUEST_MSG}: "
                    "{'limit': 5, 'offset': 3, "
                    "'only_valid': False, 'organizations': ['00000000', '00000001'], 'persons': "
                    "['12345678901', '12345'], 'rights': ['RIGHT1', 'XXX']}",
                    'INFO:rights:[Rights:post] Client DN: None',
                    f'ERROR:rights:[Rights:post] DB_ERROR: {rights.DB_ERROR_MSG}: '
                    'DB_ERROR_MSG'], cm.output)
                mock_check_client.assert_called_with({
                    'db_host': 'localhost', 'db_port': '5432',
                    'db_db': 'postgres', 'db_user': 'postgres',
                    'db_pass': 'password', 'db_connect_timeout': 10, 'allow_all': False,
                    'allowed': ['OU=xtss,O=RIA,C=EE']}, None)
                mock_process_search_rights.assert_called_with(
                    {
                        'db_host': 'localhost', 'db_port': '5432', 'db_db': 'postgres',
                        'db_user': 'postgres', 'db_pass': 'password', 'db_connect_timeout': 10,
                        'allow_all': False, 'allowed': ['OU=xtss,O=RIA,C=EE']
                    }, {
                        'limit': 5, 'offset': 3, 'only_valid': False,
                        'organizations': ['00000000', '00000001'],
                        'persons': ['12345678901', '12345'], 'rights': ['RIGHT1', 'XXX']
                    }, '[Rights:post] ')

    @patch('rights.process_search_rights', return_value={
        'http_status': 200, 'code': 'OK', 'msg': 'SEARCH_RIGHTS_OK'})
    @patch('rights.check_client', return_value=True)
    def test_rights_ok(self, mock_check_client, mock_process_search_rights):
        with self.app.app_context():
            with self.assertLogs(rights.LOGGER, level='INFO') as cm:
                json_data = {
                    'organizations': ['00000000', '00000001'],
                    'persons': ['12345678901', '12345'],
                    'rights': ['RIGHT1', 'XXX'],
                    'only_valid': False,
                    'limit': 5,
                    'offset': 3}
                response = self.client.post('/rights', json=json_data)
                self.assertEqual(200, response.status_code)
                self.assertEqual(
                    jsonify({'code': 'OK', 'msg': 'SEARCH_RIGHTS_OK'}).json,
                    response.json
                )
                self.assertEqual([
                    f"INFO:rights:[Rights:post] {rights.INCOMING_REQUEST_MSG}: "
                    "{'limit': 5, 'offset': 3, "
                    "'only_valid': False, 'organizations': ['00000000', '00000001'], 'persons': "
                    "['12345678901', '12345'], 'rights': ['RIGHT1', 'XXX']}",
                    'INFO:rights:[Rights:post] Client DN: None'], cm.output)
                mock_check_client.assert_called_with({
                    'db_host': 'localhost', 'db_port': '5432',
                    'db_db': 'postgres', 'db_user': 'postgres',
                    'db_pass': 'password', 'db_connect_timeout': 10, 'allow_all': False,
                    'allowed': ['OU=xtss,O=RIA,C=EE']}, None)
                mock_process_search_rights.assert_called_with(
                    {
                        'db_host': 'localhost', 'db_port': '5432', 'db_db': 'postgres',
                        'db_user': 'postgres', 'db_pass': 'password', 'db_connect_timeout': 10,
                        'allow_all': False, 'allowed': ['OU=xtss,O=RIA,C=EE']
                    }, {
                        'limit': 5, 'offset': 3, 'only_valid': False,
                        'organizations': ['00000000', '00000001'],
                        'persons': ['12345678901', '12345'], 'rights': ['RIGHT1', 'XXX']
                    }, '[Rights:post] ')

    @patch('rights.check_client', return_value=False)
    def test_person_incorrect_client(self, mock_check_client):
        with self.app.app_context():
            with self.assertLogs(rights.LOGGER, level='INFO') as cm:
                json_data = {
                    'code': '12345678901',
                    'first_name': 'First-name',
                    'last_name': 'Last-name'}
                response = self.client.post('/person', json=json_data)
                self.assertEqual(403, response.status_code)
                self.assertEqual(
                    jsonify({
                        'code': 'FORBIDDEN',
                        'msg': 'Client certificate is not allowed: None'}).json,
                    response.json
                )
                self.assertEqual([
                    f"INFO:rights:[Person:post] {rights.INCOMING_REQUEST_MSG}: "
                    "{'code': '12345678901', "
                    "'first_name': 'First-name', 'last_name': 'Last-name'}",
                    'INFO:rights:[Person:post] Client DN: None',
                    'ERROR:rights:[Person:post] FORBIDDEN: Client certificate is not allowed: '
                    'None',
                    "INFO:rights:[Person:post] Response: {'http_status': 403, 'code': "
                    "'FORBIDDEN', 'msg': 'Client certificate is not allowed: None'}"], cm.output)
                mock_check_client.assert_called_with({
                    'db_host': 'localhost', 'db_port': '5432',
                    'db_db': 'postgres', 'db_user': 'postgres',
                    'db_pass': 'password', 'db_connect_timeout': 10, 'allow_all': False,
                    'allowed': ['OU=xtss,O=RIA,C=EE']}, None)

    @patch('rights.process_set_person', side_effect=psycopg2.Error('DB_ERROR_MSG'))
    @patch('rights.check_client', return_value=True)
    def test_person_db_error_handled(self, mock_check_client, mock_process_set_person):
        with self.app.app_context():
            with self.assertLogs(rights.LOGGER, level='INFO') as cm:
                json_data = {
                    'code': '12345678901',
                    'first_name': 'First-name',
                    'last_name': 'Last-name'}
                response = self.client.post('/person', json=json_data)
                self.assertEqual(500, response.status_code)
                self.assertEqual(
                    jsonify({
                        'code': 'DB_ERROR',
                        'msg': rights.DB_ERROR_MSG}).json,
                    response.json
                )
                self.assertEqual([
                    f"INFO:rights:[Person:post] {rights.INCOMING_REQUEST_MSG}: "
                    "{'code': '12345678901', "
                    "'first_name': 'First-name', 'last_name': 'Last-name'}",
                    'INFO:rights:[Person:post] Client DN: None',
                    f'ERROR:rights:[Person:post] DB_ERROR: {rights.DB_ERROR_MSG}: '
                    'DB_ERROR_MSG',
                    "INFO:rights:[Person:post] Response: {'http_status': 500, 'code': 'DB_ERROR', "
                    f"'msg': '{rights.DB_ERROR_MSG}'"
                    "}"], cm.output)
                mock_check_client.assert_called_with({
                    'db_host': 'localhost', 'db_port': '5432',
                    'db_db': 'postgres', 'db_user': 'postgres',
                    'db_pass': 'password', 'db_connect_timeout': 10, 'allow_all': False,
                    'allowed': ['OU=xtss,O=RIA,C=EE']}, None)
                mock_process_set_person.assert_called_with(
                    {
                        'db_host': 'localhost', 'db_port': '5432', 'db_db': 'postgres',
                        'db_user': 'postgres', 'db_pass': 'password', 'db_connect_timeout': 10,
                        'allow_all': False, 'allowed': ['OU=xtss,O=RIA,C=EE']
                    }, {
                        'code': '12345678901', 'first_name': 'First-name', 'last_name': 'Last-name'
                    }, '[Person:post] ')

    @patch('rights.process_set_person', return_value={
        'http_status': 200, 'code': 'OK', 'msg': 'SET_PERSON_OK'})
    @patch('rights.check_client', return_value=True)
    def test_person_ok(self, mock_check_client, mock_process_set_person):
        with self.app.app_context():
            with self.assertLogs(rights.LOGGER, level='INFO') as cm:
                json_data = {
                    'code': '12345678901',
                    'first_name': 'First-name',
                    'last_name': 'Last-name'}
                response = self.client.post('/person', json=json_data)
                self.assertEqual(200, response.status_code)
                self.assertEqual(
                    jsonify({'code': 'OK', 'msg': 'SET_PERSON_OK'}).json,
                    response.json
                )
                self.assertEqual([
                    f"INFO:rights:[Person:post] {rights.INCOMING_REQUEST_MSG}: "
                    "{'code': '12345678901', "
                    "'first_name': 'First-name', 'last_name': 'Last-name'}",
                    'INFO:rights:[Person:post] Client DN: None',
                    "INFO:rights:[Person:post] Response: {'http_status': 200, 'code': 'OK', "
                    "'msg': 'SET_PERSON_OK'}"], cm.output)
                mock_check_client.assert_called_with({
                    'db_host': 'localhost', 'db_port': '5432',
                    'db_db': 'postgres', 'db_user': 'postgres',
                    'db_pass': 'password', 'db_connect_timeout': 10, 'allow_all': False,
                    'allowed': ['OU=xtss,O=RIA,C=EE']}, None)
                mock_process_set_person.assert_called_with(
                    {
                        'db_host': 'localhost', 'db_port': '5432', 'db_db': 'postgres',
                        'db_user': 'postgres', 'db_pass': 'password', 'db_connect_timeout': 10,
                        'allow_all': False, 'allowed': ['OU=xtss,O=RIA,C=EE']
                    }, {
                        'code': '12345678901', 'first_name': 'First-name', 'last_name': 'Last-name'
                    }, '[Person:post] ')

    @patch('rights.check_client', return_value=False)
    def test_organization_incorrect_client(self, mock_check_client):
        with self.app.app_context():
            with self.assertLogs(rights.LOGGER, level='INFO') as cm:
                json_data = {
                    'code': '00000000',
                    'name': 'Org name'}
                response = self.client.post('/organization', json=json_data)
                self.assertEqual(403, response.status_code)
                self.assertEqual(
                    jsonify({
                        'code': 'FORBIDDEN',
                        'msg': 'Client certificate is not allowed: None'}).json,
                    response.json
                )
                self.assertEqual([
                    f"INFO:rights:[Organization:post] {rights.INCOMING_REQUEST_MSG}: "
                    "{'code': '00000000', "
                    "'name': 'Org name'}",
                    'INFO:rights:[Organization:post] Client DN: None',
                    'ERROR:rights:[Organization:post] FORBIDDEN: Client certificate is not '
                    'allowed: None',
                    "INFO:rights:[Organization:post] Response: {'http_status': 403, 'code': "
                    "'FORBIDDEN', 'msg': 'Client certificate is not allowed: None'}"], cm.output)
                mock_check_client.assert_called_with({
                    'db_host': 'localhost', 'db_port': '5432',
                    'db_db': 'postgres', 'db_user': 'postgres',
                    'db_pass': 'password', 'db_connect_timeout': 10, 'allow_all': False,
                    'allowed': ['OU=xtss,O=RIA,C=EE']}, None)

    @patch('rights.process_set_organization', side_effect=psycopg2.Error('DB_ERROR_MSG'))
    @patch('rights.check_client', return_value=True)
    def test_organization_db_error_handled(self, mock_check_client, mock_process_set_organization):
        with self.app.app_context():
            with self.assertLogs(rights.LOGGER, level='INFO') as cm:
                json_data = {
                    'code': '00000000',
                    'name': 'Org name'}
                response = self.client.post('/organization', json=json_data)
                self.assertEqual(500, response.status_code)
                self.assertEqual(
                    jsonify({
                        'code': 'DB_ERROR',
                        'msg': rights.DB_ERROR_MSG}).json,
                    response.json
                )
                self.assertEqual([
                    f"INFO:rights:[Organization:post] {rights.INCOMING_REQUEST_MSG}: "
                    "{'code': '00000000', "
                    "'name': 'Org name'}",
                    'INFO:rights:[Organization:post] Client DN: None',
                    f'ERROR:rights:[Organization:post] DB_ERROR: {rights.DB_ERROR_MSG}: '
                    'DB_ERROR_MSG',
                    "INFO:rights:[Organization:post] Response: {'http_status': 500, 'code': "
                    f"'DB_ERROR', 'msg': '{rights.DB_ERROR_MSG}'"
                    "}"], cm.output)
                mock_check_client.assert_called_with({
                    'db_host': 'localhost', 'db_port': '5432',
                    'db_db': 'postgres', 'db_user': 'postgres',
                    'db_pass': 'password', 'db_connect_timeout': 10, 'allow_all': False,
                    'allowed': ['OU=xtss,O=RIA,C=EE']}, None)
                mock_process_set_organization.assert_called_with({
                    'db_host': 'localhost', 'db_port': '5432', 'db_db': 'postgres',
                    'db_user': 'postgres', 'db_pass': 'password', 'db_connect_timeout': 10,
                    'allow_all': False, 'allowed': ['OU=xtss,O=RIA,C=EE']},
                    {'code': '00000000', 'name': 'Org name'}, '[Organization:post] ')

    @patch('rights.process_set_organization', return_value={
        'http_status': 200, 'code': 'OK', 'msg': 'SET_ORGANIZATION_OK'})
    @patch('rights.check_client', return_value=True)
    def test_organization_ok(self, mock_check_client, mock_process_set_organization):
        with self.app.app_context():
            with self.assertLogs(rights.LOGGER, level='INFO') as cm:
                json_data = {
                    'code': '00000000',
                    'name': 'Org name'}
                response = self.client.post('/organization', json=json_data)
                self.assertEqual(200, response.status_code)
                self.assertEqual(
                    jsonify({'code': 'OK', 'msg': 'SET_ORGANIZATION_OK'}).json,
                    response.json
                )
                self.assertEqual([
                    f"INFO:rights:[Organization:post] {rights.INCOMING_REQUEST_MSG}: "
                    "{'code': '00000000', "
                    "'name': 'Org name'}",
                    'INFO:rights:[Organization:post] Client DN: None',
                    "INFO:rights:[Organization:post] Response: {'http_status': 200, 'code': 'OK', "
                    "'msg': 'SET_ORGANIZATION_OK'}"], cm.output)
                mock_check_client.assert_called_with({
                    'db_host': 'localhost', 'db_port': '5432',
                    'db_db': 'postgres', 'db_user': 'postgres',
                    'db_pass': 'password', 'db_connect_timeout': 10, 'allow_all': False,
                    'allowed': ['OU=xtss,O=RIA,C=EE']}, None)
                mock_process_set_organization.assert_called_with({
                    'db_host': 'localhost', 'db_port': '5432', 'db_db': 'postgres',
                    'db_user': 'postgres', 'db_pass': 'password', 'db_connect_timeout': 10,
                    'allow_all': False, 'allowed': ['OU=xtss,O=RIA,C=EE']},
                    {'code': '00000000', 'name': 'Org name'}, '[Organization:post] ')

    @patch('rights.test_db', side_effect=psycopg2.Error('DB_ERROR_MSG'))
    def test_status_db_error_handled(self, mock_test_db):
        with self.app.app_context():
            with self.assertLogs(rights.LOGGER, level='INFO') as cm:
                response = self.client.get('/status')
                self.assertEqual(500, response.status_code)
                self.assertEqual(
                    jsonify({
                        'code': 'DB_ERROR',
                        'msg': rights.DB_ERROR_MSG}).json,
                    response.json
                )
                self.assertEqual([
                    'INFO:rights:[Status:get] Incoming status request',
                    f'ERROR:rights:[Status:get] DB_ERROR: {rights.DB_ERROR_MSG}: '
                    'DB_ERROR_MSG',
                    "INFO:rights:[Status:get] Response: {'http_status': 500, 'code': 'DB_ERROR', "
                    f"'msg': '{rights.DB_ERROR_MSG}'"
                    "}"], cm.output)
                mock_test_db.assert_called_with({
                    'db_host': 'localhost', 'db_port': '5432', 'db_db': 'postgres',
                    'db_user': 'postgres', 'db_pass': 'password', 'db_connect_timeout': 10,
                    'allow_all': False, 'allowed': ['OU=xtss,O=RIA,C=EE']}, '[Status:get] ')

    @patch('rights.test_db', return_value={
        'http_status': 200, 'code': 'OK', 'msg': 'All Correct'})
    def test_status_ok(self, mock_test_db):
        with self.app.app_context():
            with self.assertLogs(rights.LOGGER, level='INFO') as cm:
                response = self.client.get('/status')
                self.assertEqual(200, response.status_code)
                self.assertEqual(
                    jsonify({'code': 'OK', 'msg': 'All Correct'}).json,
                    response.json
                )
                self.assertEqual([
                    'INFO:rights:[Status:get] Incoming status request',
                    "INFO:rights:[Status:get] Response: {'http_status': 200, 'code': 'OK', 'msg': "
                    "'All Correct'}"], cm.output)
                mock_test_db.assert_called_with({
                    'db_host': 'localhost', 'db_port': '5432', 'db_db': 'postgres',
                    'db_user': 'postgres', 'db_pass': 'password', 'db_connect_timeout': 10,
                    'allow_all': False, 'allowed': ['OU=xtss,O=RIA,C=EE']}, '[Status:get] ')

    @patch('rights.configure_app', return_value={'log_file': 'LOG_FILE'})
    @patch('rights.Api')
    def test_create_app(self, mock_api, mock_configure_app):
        mock_api_value = MagicMock()
        mock_api.return_value = mock_api_value
        app = rights.create_app('CONFIG_FILE')
        mock_configure_app.assert_called_with('CONFIG_FILE')
        self.assertIsInstance(app, rights.Flask)
        mock_api_value.add_resource.assert_has_calls([
            call(rights.SetRightApi, '/set-right', resource_class_kwargs={
                'config': {'log_file': 'LOG_FILE'}}),
            call(rights.RevokeRightApi, '/revoke-right', resource_class_kwargs={
                'config': {'log_file': 'LOG_FILE'}}),
            call(rights.RightsApi, '/rights', resource_class_kwargs={
                'config': {'log_file': 'LOG_FILE'}}),
            call(rights.PersonApi, '/person', resource_class_kwargs={
                'config': {'log_file': 'LOG_FILE'}}),
            call(rights.OrganizationApi, '/organization', resource_class_kwargs={
                'config': {'log_file': 'LOG_FILE'}}),
            call(rights.StatusApi, '/status', resource_class_kwargs={
                'config': {'log_file': 'LOG_FILE'}})
        ])


if __name__ == '__main__':
    unittest.main()
