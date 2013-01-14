"""
A simple CDN manager
"""

import sys
import getopt
import json
import subprocess
import logging
from StringIO import StringIO
import time

def _p(args,env=dict()):
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
        if "group=" in l:
            e = [dict(item.split('=')) for item in l.split()]
            res["%s#%s" % (e['group'],e['service'])] = e
    return res

def _up(status,host):
    sinfo = status.get('%s#%s' % (host,'ping'),None)
    if sinfo is None:
        return False
    return sinfo.get('opstatus',"0") == "1"

def main():
    """
The main entrypoint of pyCDN
    """
    try:
        opts,args = getopt.getopt(sys.argv[1:],'hf:c:n:d:',['help','hosts=','contact=','name-server=','domain='])
    except getopt.error,msg:
        print msg
        sys.exit(2)

    hosts = "hosts.txt"
    contact = None
    domain = None
    nameservers = []
    for o,a in opts:
        if o in ('-h','--help'):
            print __doc__
            sys.exit(0)
        elif o in ('-f','--hosts'):
            hosts = a
        elif o in ('-c','--contact'):
            contact = a
        elif o in ('-n','--name-server'):
            nameservers.append(o)
        elif o in ('-d','--domain'):
            domain = o

    cdn = []
    with open(hosts) as h:
        for l in h.readlines():
            cdn.append(l.split())

    cmd = args[0]
    if cmd == 'geodns': 
        zone = dict()
        zone['ttl'] = 120
        zone['serial'] = int(time.strftime("%Y%M%d00"))
        zone['contact'] = contact
        zone['max_hosts'] = 2
        ns = [dict(n,None) for n in nameservers]
        zone['data'] = {'':{'ns':ns}}
        a = dict(a=[],aaaa=[])
        status = _opstatus()

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

            zone['data'][cn][at] = ar
            if _up(status,cn):
                a[at].append(ar)
                for vn in v[2:]:
                    zone['data'].setdefault(vn,dict())
                    zone['data'][vn].setdefault('a',[])
                    zone['data'][vn].setdefault('aaaa',[])
                    zone['data'][vn][at].append(ar)

        zone['data']['']['a'] = a['a']
        zone['data']['']['aaaa'] = a['aaaa']
        print json.dumps(zone)
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
            print "hostgroup %s %s.%s" % (v[1],v[1],domain)

        for v in cdn:
            print """
watch %s
      service http
              description "HTTP service"
              interval 2m
              monitor http.monitor
              period 
                      numalerts 10
                      alert mail.alert
                      upalert mail.alert""" % v[1]
