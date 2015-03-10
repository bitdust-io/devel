#!/usr/bin/python
#xmlrpc_client.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: xmlrpc_client
"""


from twisted.internet import reactor
from twisted.web import xmlrpc

from main import settings

#------------------------------------------------------------------------------ 

def output(result):
    print result
    reactor.stop()

proxy = xmlrpc.Proxy('http://localhost:%d' % settings.DefaultXMLRPCPort(), allowNone=True)
proxy.callRemote('backups_list').addBoth(output)
reactor.run()


