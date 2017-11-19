#!/usr/bin/python
# rest_http_server.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (rest_http_server.py) is part of BitDust Software.
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
#
#
#
#

"""
..

module:: rest_http_server
"""

#------------------------------------------------------------------------------

import cgi
import json

#------------------------------------------------------------------------------

from twisted.internet import reactor
from twisted.web.server import Site

#------------------------------------------------------------------------------

from logs import lg

from interface import api

from lib.txrestapi.txrestapi.resource import APIResource
from lib.txrestapi.txrestapi.methods import GET, POST, PUT, ALL

#------------------------------------------------------------------------------

_APIListener = None

#------------------------------------------------------------------------------

def init(port=None):
    global _APIListener
    if _APIListener is not None:
        lg.warn('_APIListener already initialized')
        return
    if not port:
        port = 8180
    try:
        api_resource = BitDustRESTHTTPServer()
        site = Site(api_resource, timeout=None)
        _APIListener = reactor.listenTCP(port, site)
    except:
        lg.exc()
    lg.out(4, 'rest_http_server.init')


def shutdown():
    global _APIListener
    if _APIListener is None:
        lg.warn('_APIListener is None')
        return
    lg.out(4, 'rest_http_server.shutdown calling _APIListener.stopListening()')
    _APIListener.stopListening()
    del _APIListener
    _APIListener = None
    lg.out(4, '    _APIListener destroyed')

#------------------------------------------------------------------------------

class BitDustRESTHTTPServer(APIResource):

    @GET('^/process/stop/?$')
    def process_stop(self, request):
        return api.stop()

    @GET('^/process/restart/?$')
    def process_restart(self, request):
        return api.restart(showgui=bool(request.args.get('showgui')))

    @GET('^/process/show/?$')
    def process_show(self, request):
        return api.show()

    @GET('^/config/list/?$')
    def config_list(self, request):
        return api.config_list(sort=True)

    @GET('^/config/get/?$')
    def config_get(self, request):
        import pdb; pdb.set_trace()
        return api.config_get(key=cgi.escape(request.args.get('key')[0]))

    @POST('^/config/set/?$')
    def config_set(self, request):
        data = json.loads(request.content.getvalue())
        return api.config_set(key=data['key'], value=data['value'])

    @GET('^/network/stun/?$')
    def network_stun(self, request):
        return api.network_stun()

#------------------------------------------------------------------------------
