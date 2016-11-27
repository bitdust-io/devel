#!/usr/bin/python
# service_coins_accountant.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (service_accountant.py) is part of BitDust Software.
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

module:: service_coins_accountant
"""

from services.local_service import LocalService


def create_service():
    return CoinsAccountantService()


class CoinsAccountantService(LocalService):

    service_name = 'service_accountant'
    config_path = 'services/accountant/enabled'

    def dependent_on(self):
        return ['service_p2p_hookups',
                ]

    def start(self):
        from coins import accountant_node
        from coins import accountants_finder
        accountants_finder.A('init')
        accountant_node.A('init')
        accountant_node.A('start')
        accountant_node.A().addStateChangedCallback(
            self._on_accountant_node_switched)
        return True

    def stop(self):
        from coins import accountant_node
        accountant_node.A().removeStateChangedCallback(
            self._on_accountant_node_switched)
        accountant_node.A('stop')
        accountant_node.A('shutdown')
        return True

    def request(self, request, info):
        from logs import lg
        from p2p import p2p_service
        words = request.Payload.split(' ')
        try:
            mode = words[1][:10]
        except:
            lg.exc()
            return None
        if mode != 'join' and mode != 'write' and mode != 'read':
            lg.out(8, "service_accountant.request DENIED, wrong mode provided : %s" % mode)
            return None
        from coins import accountant_node
        if not accountant_node.A():
            lg.out(8, "service_accountant.request DENIED, accountant_node() state machine not exist")
            return p2p_service.SendFail(request, "accountant_node service not started")
        # if accountant_node.A().state not in ['ACCOUNTANTS?', "READY", "VALID_COIN?", "WRITE_COIN!", ]:
        #     lg.out(8, "service_accountant.request DENIED, accountant_node() state is : %s" % accountant_node.A().state)
        #     return p2p_service.SendFail(request, "accountant_node service currently unavailable")
        if mode == 'join':
            accountant_node.A('accountant-connected', request.OwnerID)
        return p2p_service.SendAck(request, 'accepted')

    def _on_accountant_node_switched(self, oldstate, newstate, evt, args):
        from logs import lg
        from twisted.internet import reactor
        from coins import accountant_node
        if newstate == 'OFFLINE' and oldstate != 'AT_STARTUP':
            # reactor.callLater(60, accountant_node.A, 'start')
            lg.out(8, 'service_broadcasting._on_accountant_node_switched will try to reconnect again after 1 minute')
