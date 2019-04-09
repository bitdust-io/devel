#!/usr/bin/env python
# memdebug.py
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (memdebug.py) is part of BitDust Software.
#
# BitDust is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BitDust Software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with BitDust Software.  If not, see <http://www.gnu.org/licenses/>.
#
# Please contact us if you have any questions at bitdust.io@gmail.com

"""
.. module:: memdebug.

This is to test memory usage. It was useful when I looked for memory
leaks. Can start a local HTTP server to keep track of all python objects
in the memory.
"""

from __future__ import absolute_import
import cherrypy  # @UnresolvedImport
import dowser  # @UnresolvedImport


def start(port):
    cherrypy.config.update({
        'environment': 'embedded',
        'server.socket_port': port,
        'server.socket_host': '0.0.0.0',
    })
    cherrypy.tree.mount(dowser.Root())

    # cherrypy.server.quickstart()
    cherrypy.engine.start()


def stop():
    cherrypy.engine.exit()


#from twisted.web.wsgi import WSGIResource
#from twisted.internet import reactor  # @UnresolvedImport
#
#from dozer import Dozer
#
# def application(environ, start_response):
#    start_response('200 OK', [('Content-type', 'text/plain')])
#    return ['Hello, world!']
#
# def start():
#    resource = WSGIResource(reactor, reactor.getThreadPool(), application)
#    wsgi_app = Dozer(application)
