import hashlib
import logging

__author__ = 'leifj'

import os
import json
from pycdn.wsgi import not_found, dispatcher

def _digest(dir,d=dict()):
    for path, dirnames, filenames in os.walk(dir):
        dd = hashlib.sha256()
        for dir in dirnames:
            subdir = os.path.join(path,dir)
            _digest(subdir,d)
            dd.update(d[subdir])
        for fn in filenames:
            subfile = os.path.join(path,fn)
            md = hashlib.sha256()
            try:
                with open(subfile) as fd:
                    md.update(fd.read())
                d[subfile] = md.hexdigest()
            except IOError,ex:
                logging.warn(ex)
            dd.update(d[subfile])
        d[path] = dd.hexdigest()

def _mt(environ,start_response):
    dir = os.environ.get("MT_DIR","/var/www")
    start_response("200 OK",[('Content-Type','application/json')])
    mt = _digest(dir)
    return [json.dumps(mt)]

urls = [
    (r'^$', not_found),
    (r'mt.json$', _mt),
    ]

def application(environ,start_response):
    return dispatcher(environ,start_response,urls)