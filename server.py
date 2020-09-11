#!/usr/bin/env python3

"""This is a Flask server configuration for Rights service."""

__version__ = '1.0'

import logging
from flask import Flask
from flask_restful import Api
from rights import SetRightApi, RevokeRightApi, RightsApi, PersonApi, OrganizationApi, StatusApi,\
    load_config

handler = logging.FileHandler('/var/log/xtss-rights/rights.log')
handler.setFormatter(logging.Formatter('%(asctime)s - %(process)d - %(levelname)s: %(message)s'))

# Rights module logger
logger_m = logging.getLogger('rights')
logger_m.setLevel(logging.INFO)
logger_m.addHandler(handler)

# Application logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)

config = load_config('config.json')

app = Flask(__name__)
api = Api(app)
api.add_resource(SetRightApi, '/set-right', resource_class_kwargs={'config': config})
api.add_resource(RevokeRightApi, '/revoke-right', resource_class_kwargs={'config': config})
api.add_resource(RightsApi, '/rights', resource_class_kwargs={'config': config})
api.add_resource(PersonApi, '/person', resource_class_kwargs={'config': config})
api.add_resource(OrganizationApi, '/organization', resource_class_kwargs={'config': config})
api.add_resource(StatusApi, '/status', resource_class_kwargs={'config': config})

logger.info('Starting Rights API v{}'.format(__version__))
