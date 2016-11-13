#!/usr/bin/python
#service_customer_support.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (service_customer_support.py) is part of BitDust Software.
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
.. module:: service_customer_support

"""

from services.local_service import LocalService

def create_service():
    return CustomerSupportService()
    
class CustomerSupportService(LocalService):
    
    service_name = 'service_customer_support'
    config_path = 'services/customer-support/enabled'
    _jobs = {}
    _PING_INTERVAL = 120

    def dependent_on(self):
        return ['service_customer_patrol',
                ]
    
    def start(self):
        for starter in self._support_methods().values():
            starter()
        return True
    
    def stop(self):
        for job in self._jobs.values():
            job.stop()
        self._jobs.clear()
        return True
    
    def _support_methods(self):
        return {
            'ping': self._run_ping,
        }

    def _ping(self):
        from services import driver
        if driver.is_started('service_identity_propagate'):
            from p2p import contact_status
            from p2p import propagate
            for customer_idurl in contact_status.listOfflineCustomers():
                propagate.SendToID(customer_idurl, wide=True)

    def _run_ping(self):
        from twisted.internet.task import LoopingCall
        self._jobs['ping'] = LoopingCall(self._ping)
        self._jobs['ping'].start(self._PING_INTERVAL, now=False)
        return 'ping'
    
