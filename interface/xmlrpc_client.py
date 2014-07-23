

from twisted.internet import reactor
from twisted.web import xmlrpc

def output(result):
    print result
    reactor.stop()

proxy = xmlrpc.Proxy('http://localhost:5001', allowNone=True)
proxy.callRemote('ls').addBoth(output)
reactor.run()
