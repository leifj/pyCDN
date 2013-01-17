"""
A simple CDN manager
"""
import cgitb
import hashlib
import os

import sys
import getopt
import json
import subprocess
import logging
from StringIO import StringIO
import time
import urllib
import workerpool

def _p(args,env=dict()):
    logging.debug(" ".join(args))
    proc = subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
    out,err = proc.communicate()
    if err is not None and len(err) > 0:
        logging.error(err)
    rv = proc.wait()
    if rv:
        raise RuntimeError("command exited with code != 0: %d" % rv)
    return StringIO(out)

def _opstatus():
    res = dict()
    for l in _p(['moncmd','list','opstatus']).readlines():
        def _d(i,e):
            s = i.split('=')
            if len(s) == 1:
                e[s] = None
            else:
                e[s[0]] = s[1]

        if "group=" in l:
            e = dict()
            for item in l.split():
                _d(item,e)
            res["%s#%s" % (e['group'],e['service'])] = e
    return res

def _up(status,host):
    def _ok(s):
        return s.get('opstatus',"0") != "0"

    ping = status.get('%s#%s' % (host,'ping'),None)
    if ping is None:
        return False
    http = status.get('%s#%s' % (host,'http'),None)
    if http is None:
        return False
    return _ok(ping) and _ok(http)

def _dump(o,fn):
    with open(fn,"w") as fd:
        fd.write(json.dumps(o))

def _pushto(hn,domain,mirror,res):
    try:
        return _p(['rsync',
                   '-avz',
                   '--delete',
                   '-e','ssh -oStrictHostKeyChecking=no -i/opt/cdn/keys/cdn',
                   "%s/" % mirror,'cdn@%s.%s:/var/www/' % (hn,domain)])
    except RuntimeError,ex:
        logging.error(ex)
        res[hn] = ex

def merkle_tree(dir,d=dict()):
    for path, dirnames, filenames in os.walk(dir,followlinks=False):
        dd = hashlib.sha256()
        for dir in dirnames.sort():
            subdir = os.path.join(path,dir)
            merkle_tree(subdir,d)
            logging.warn("%s -> %s" % (subdir,d[subdir]))
            dd.update(d[subdir])

        for fn in filenames.sort():
            subfile = os.path.join(path,fn)
            md = hashlib.sha256()
            try:
                with open(subfile,'rb') as fd:
                    buf = fd.read(8196)
                    while buf:
                        md.update(buf)
                        buf = fd.read(8196)
                d[subfile] = md.hexdigest()
                dd.update(d[subfile])
            except IOError,ex:
                logging.warn(ex)
        d[path] = dd.hexdigest()
    return d

def _verify(cn,domain,dir,res):
    try:
        r = urllib.urlopen("http://%s.%s/.host-meta/mt.json" % (cn,domain))
        mt_s = json.load(r); _dump(mt_s,"/tmp/mt_s.json");
        mt_l = merkle_tree(dir); _dump(mt_l,"/tmp/mt_l.json");
        if not mt_s['/var/www'] == mt_l[dir]:
            logging.debug("%s != %s" % (mt_s['/var/www'],mt_l[dir]))
            res[cn] = False
    except Exception,ex:
        res[cn] = ex

def _zone(contact,nameservers,aliases,cdn,ok):
    zone = dict()
    zone['ttl'] = 120
    zone['serial'] = int(time.strftime("%Y%M%d00"))
    zone['contact'] = contact
    zone['max_hosts'] = 2
    ns = dict()
    for n in nameservers:
        ns[n] = None
    zone['data'] = {'':{'ns':ns}}
    a = dict(a=[],aaaa=[])

    for v in aliases:
        zone['data'][v] = dict(alias="")

    for v in cdn:
        cn = v[1]
        zone['data'].setdefault(v[1],{})
        ar = [v[0],"100"]
        if '.' in v[0]:
            at = 'a'
        elif ':' in v[0]:
            at = 'aaaa'
        else:
            logging.error("Unknown address format %s" % v[0])

        zone['data'][cn][at] = [ar]
        if ok(cn):
            a[at].append(ar)
            for vn in v[2:]:
                zone['data'].setdefault(vn,dict())
                zone['data'][vn].setdefault('a',[])
                zone['data'][vn].setdefault('aaaa',[])
                zone['data'][vn][at].append(ar)

    if len(a['a']) > 0:
        zone['data']['']['a'] = a['a']
    if len(a['aaaa']) > 0:
        zone['data']['']['aaaa'] = a['aaaa']
    return json.dumps(zone)

def main():
    """
The main entrypoint of pyCDN
    """
    try:
        opts,args = getopt.getopt(sys.argv[1:],'hf:c:n:d:a:v:m:F',
            ['help','hosts=','contact=','name-server=','domain=','alert=','vhosts=','mirror=','force'])
    except getopt.error,msg:
        print msg
        sys.exit(2)

    hosts = "hosts.txt"
    contact = None
    domain = None
    alert = "root@localhost"
    vhosts = "vhosts.txt"
    mirror = "/opt/cdn/mirror"
    nameservers = []
    force = False
    for o,a in opts:
        if o in ('-h','--help'):
            print __doc__
            sys.exit(0)
        elif o in ('-f','--hosts'):
            hosts = a
        elif o in ('-c','--contact'):
            contact = a
        elif o in ('-n','--name-server'):
            nameservers.append(a)
        elif o in ('-d','--domain'):
            domain = a
        elif o in ('-a','--alert'):
            alert = a
        elif o in ('-m','--mirror'):
            mirror = a
        elif o in ('-F','--force'):
            force = True

    cdn = []
    with open(hosts) as fd:
        for l in fd.readlines():
            cdn.append(l.split())

    aliases = []
    with open(vhosts) as fd:
        for l in fd.readlines():
            e = l.split()
            aliases.append(e[0])

    cmd = args[0]
    if cmd == 'update':
        push_list = []
        if not force:
            pool = workerpool.WorkerPool(size=5)
            res = dict()
            pool.map(lambda cn: _verify(cn,domain,mirror,res),[v[1] for v in cdn])
            pool.shutdown()
            pool.wait()
            push_list = res.keys()
        else:
            push_list = [v[1] for v in cdn]

        pool = workerpool.WorkerPool(size=5)
        pres = dict()
        pool.map(lambda cn: _pushto(cn,domain,mirror,pres),push_list)
        pool.shutdown()
        pool.wait()

        pool = workerpool.WorkerPool(size=5)
        vres = dict()
        pool.map(lambda cn: _verify(cn,domain,mirror,vres),[v[1] for v in cdn])
        pool.shutdown()
        pool.wait()

        status = _opstatus()
        def ok(cn):
            return _up(status,cn) and not pres.has_key(cn) and not vres.has_key(cn)

        print _zone(contact,nameservers,aliases,cdn,ok)

    if cmd == 'geodns':
        status = _opstatus()
        def ok(cn):
            return _up(status,cn)

        print _zone(contact,nameservers,aliases,cdn,ok)

    elif cmd == 'moncfg':
        print """
alertdir                = /usr/lib/mon/alert.d
mondir                  = /usr/lib/mon/mon.d
logdir                  = /var/log/mon
historicfile            = /var/log/mon/history.log
maxprocs                = 20
histlength              = 100
randstart               = 60s
dtlogging               = yes
dtlogfile               = dtlog
"""

        for v in cdn:
            print "hostgroup %(host)s %(host)s.%(domain)s" % {'host': v[1],'domain':domain}

        for v in cdn:
            print """
watch %(hostgroup)s
      service http
              description "HTTP service"
              interval 2m
              monitor http.monitor
              period 
                      numalerts 10
                      alert mail.alert %(alert)s
                      upalert mail.alert %(alert)s
      service ping
                description "Responses to ping"
                interval 1m
                monitor fping.monitor
                period
                      numalerts 10
                      alert mail.alert %(alert)s
                      upalert mail.alert %(alert)s""" % {'hostgroup': v[1],'alert':alert}

