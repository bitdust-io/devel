#!/usr/bin/python
#local_site.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: local_site

"""

import os
import sys

from twisted.web import wsgi
from twisted.internet import reactor
from twisted.application import service, strports
from twisted.web import server 
from twisted.web import http

root_pth = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
if not ( len(sys.path) > 0 and sys.path[0] == root_pth ):
    sys.path.insert(0, os.path.join(root_pth))
sys.path.insert(1, os.path.join(root_pth, 'dj'))
sys.path.insert(2, os.path.join(root_pth, 'dj', 'asite'))
# sys.path.insert(3, os.path.join(root_pth, 'dj', 'asite', 'asite'))
print '\n'.join(sys.path)

from logs import lg

#------------------------------------------------------------------------------ 
    
def init():
    lg.out(4, 'local_site.init')
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "asite.settings") 
    from dj.django.core.handlers.wsgi import WSGIHandler
    wsgi_resource = wsgi.WSGIResource(reactor, reactor.getThreadPool(), WSGIHandler())
    site = server.Site(wsgi_resource)
    reactor.listenTCP(8080, site)
    import webbrowser
    webbrowser.open_new('http://localhost:8080')
        
    
def shutdown():
    lg.out(4, 'local_site.shutdown')


if __name__ == "__main__":
    init()
    reactor.run()
