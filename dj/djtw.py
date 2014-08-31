import os.path, os

from twisted.web2 import log, wsgi
from twisted.internet import reactor


# This part gets run when you run this file via: "twistd -noy demo.py"
if __name__ == '__builtin__':
    from twisted.application import service, strports
    from twisted.web2 import server, vhost, channel
    #from twisted.internet.ssl import DefaultOpenSSLContextFactory
    from twisted.python import util

    # Create the resource we will be serving
    from django.core.handlers.wsgi import AdminMediaHandler, WSGIHandler
    os.environ['DJANGO_SETTINGS_MODULE'] = 'myproject.settings.admin'
    test = wsgi.WSGIResource(AdminMediaHandler(WSGIHandler()))

    # Setup default common access logging
    res = log.LogWrapperResource(test)
    log.DefaultCommonAccessLoggingObserver().start()

    # Create the site and application objects
    site = server.Site(res)
    application = service.Application("demo")

    # Serve it via standard HTTP on port 8080
    s = strports.service('tcp:8080', channel.HTTPFactory(site))
    s.setServiceParent(application)

    # Serve it via HTTPs on port 8081
    #s = strports.service('ssl:8081:privateKey=doc/core/examples/server.pem', channel.HTTPFactory(site))
    #s.setServiceParent(application)