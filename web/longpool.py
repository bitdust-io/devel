#!/usr/bin/python
# longpool.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (longpool.py) is part of BitDust Software.
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
.. module:: longpool

Got sample code from:

    http://coder1.com/articles/twisted-long-polling-jsonp

"""

import json
import time

#------------------------------------------------------------------------------

from twisted.web import server
from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.internet import reactor
from twisted.internet import task
from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

_LongPoolListener = None

#------------------------------------------------------------------------------


def init(get_data_callback, clear_data_callback, portnum):
    """
    """
    global _LongPoolListener
    resource = LongPoolServer(get_data_callback, clear_data_callback)
    factory = Site(resource)
    _LongPoolListener = reactor.listenTCP(portnum, factory)


def shutdown():
    """
    """
    global _LongPoolListener
    if _LongPoolListener:
        result = _LongPoolListener.stopListening()
        _LongPoolListener.connectionLost("Closing LongPoolListener as requested")
        del _LongPoolListener
    else:
        result = Deferred()
        result.callback(1)
    _LongPoolListener = None
    return result

#------------------------------------------------------------------------------


class LongPoolServer(Resource):
    isLeaf = True

    def __init__(self, get_data_callback, clear_data_callback):
        """
        """
        self.delayed_requests = []
        self.get_data_callback = get_data_callback
        self.clear_data_callback = clear_data_callback
        self.loop_requests = task.LoopingCall(self.processDelayedRequests)
        self.loop_requests.start(1, False)
        Resource.__init__(self)

    def destroy(self):
        """
        """
        self.get_data_callback = None
        self.clear_data_callback = None
        self.delayed_requests = []
        self.loop_requests.stop()

    def render(self, request):
        """
        """
        request.setHeader('Content-Type', 'application/json')
        args = request.args
        if 'callback' in args:
            request.jsonpcallback = args['callback'][0]
        if 'lastupdate' in args:
            request.lastupdate = args['lastupdate'][0]
        else:
            request.lastupdate = 0
        data = self.getData(request)
        if len(data) > 0:
            return self.__format_response(request, 1, data)
        self.delayed_requests.append(request)
        return server.NOT_DONE_YET

    def getData(self, request):
        """
        """
        data = self.get_data_callback()
        if len(data) > 0:
            self.clear_data_callback()
        return data

    def processDelayedRequests(self):
        global _LongPoolListener
        if _LongPoolListener is None:
            self.destroy()
            return
        for request in self.delayed_requests:
            data = self.getData(request)
            if len(data) > 0:
                try:
                    request.write(self.__format_response(request, 1, data))
                    request.finish()
                except:
                    print 'connection lost before complete.'
                finally:
                    self.delayed_requests.remove(request)

    def __format_response(self, request, status, data):
        response = json.dumps({'status': status,
                               'timestamp': int(time.time()),
                               'data': data})
        if hasattr(request, 'jsonpcallback'):
            return request.jsonpcallback + '(' + response + ')'
        else:
            return response

#------------------------------------------------------------------------------

if __name__ == '__main__':
    resource = LongPoolServer(lambda: {True: time.time(), }, lambda: True)
    factory = Site(resource)
    reactor.listenTCP(8000, factory)
    reactor.run()
