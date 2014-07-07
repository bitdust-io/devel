# memdebug.py

"""
.. module:: memdebug

This is to test memory usage.
It was useful when I looked for memory leaks.
Can start a local HTTP server to keep track of all python objects in the memory.
"""

import cherrypy
import dowser

def start(port):
    cherrypy.config.update({
        'environment': 'embedded',
        'server.socket_port': port,
        'server.socket_host': '0.0.0.0',
    })
    cherrypy.tree.mount(dowser.Root())

    #cherrypy.server.quickstart()
    cherrypy.engine.start()

def stop():
    cherrypy.engine.exit()


#from twisted.web.wsgi import WSGIResource
#from twisted.internet import reactor
#
#from dozer import Dozer
#
#def application(environ, start_response):
#    start_response('200 OK', [('Content-type', 'text/plain')])
#    return ['Hello, world!']
#
#def start():
#    resource = WSGIResource(reactor, reactor.getThreadPool(), application)
#    wsgi_app = Dozer(application)


