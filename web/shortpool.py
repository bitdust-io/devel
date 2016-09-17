#!/usr/bin/python
# shortpool.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (shortpool.py) is part of BitDust Software.
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
.. module:: shortpool

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

_ShortPoolListener = None

#------------------------------------------------------------------------------ 

def init(get_data_callback, clear_data_callback, portnum):
    """
    """
    # global _ShortPoolListener
    # resource = ShortPoolServer(get_data_callback, clear_data_callback)
    # factory = Site(resource)
    # _ShortPoolListener = reactor.listenTCP(portnum, factory)
    
def shutdown():
    """
    """
#    global _ShortPoolListener
#    if _ShortPoolListener:
#        result = _ShortPoolListener.stopListening()
#        _ShortPoolListener.connectionLost("Closing ShortPoolListener as requested")
#        del _ShortPoolListener
#    else: 
#        result = Deferred()
#        result.callback(1)
#    _ShortPoolListener = None
#    return result

#------------------------------------------------------------------------------ 

class ShortPoolServer(Resource):
    isLeaf = True
    def __init__(self, get_data_callback, clear_data_callback):
        """
        """
        self.get_data_callback = get_data_callback
        self.clear_data_callback = clear_data_callback
        Resource.__init__(self)

    def destroy(self):
        """
        """
        self.get_data_callback = None
        self.clear_data_callback = None
        
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
        return self.__format_response(request, 1, data)
       
    def getData(self, request):
        """
        """
        data = self.get_data_callback()
        if len(data) > 0:
            self.clear_data_callback()
        return data
               
    def __format_response(self, request, status, data):
        response = json.dumps({'status':status,
                               'timestamp': int(time.time()), 
                               'data':data})
        if hasattr(request, 'jsonpcallback'):
            return request.jsonpcallback+'('+response+')'
        else:
            return response

#------------------------------------------------------------------------------ 
      
if __name__ == '__main__':
    resource = ShortPoolServer(lambda : {True: time.time(),}, lambda : True)
    factory = Site(resource)
    reactor.listenTCP(8000, factory)
    reactor.run()
    
    
    
