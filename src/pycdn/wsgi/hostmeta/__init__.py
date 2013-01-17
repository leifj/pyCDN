__author__ = 'leifj'

from pycdn.mt import MerkleTree
import os
import json
from pycdn.wsgi import not_found, dispatcher

def _mt(environ,start_response):
    dir = os.environ.get("MT_DIR","/var/www")
    start_response("200 OK",[('Content-Type','application/json')])
    mt = MerkleTree(dir)
    return [json.dumps(mt)]

urls = [
    (r'^$', not_found),
    (r'mt.json$', _mt),
    ]

def application(environ,start_response):
    return dispatcher(environ,start_response,urls)