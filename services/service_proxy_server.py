#!/usr/bin/python
#service_proxy_server.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (service_proxy_server.py) is part of BitDust Software.
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
.. module:: service_proxy_server

"""

from services.local_service import LocalService

def create_service():
    return ProxyServerService()
    
class ProxyServerService(LocalService):
    
    service_name = 'service_proxy_server'
    config_path = 'services/proxy-server/enabled'
    
    def init(self):
        # self.debug_level = 2
        self.log_events = True
    
    def dependent_on(self):
        return ['service_p2p_hookups',
                ]
        
    def enabled(self):
        from main import settings
        return settings.enableProxyServer()
    
    def start(self):
        from transport.proxy import proxy_router
        proxy_router.A('init')
        proxy_router.A('start')
        return True
    
    def stop(self):
        from transport.proxy import proxy_router 
        proxy_router.A('stop')
        proxy_router.Destroy()
        return True
    
    def request(self, request, info):
        from transport.proxy import proxy_router 
        proxy_router.A('request-route', (request, info))
        return None
    
    def cancel(self, request, info):
        from transport.proxy import proxy_router 
        proxy_router.A('cancel-route', (request, info))
        return None

    