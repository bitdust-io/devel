#!/usr/bin/python
# service_coins_accountant.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return CoinsAccountantService()


class CoinsAccountantService(LocalService):

    service_name = 'service_accountant'
    config_path = 'services/accountant/enabled'

    def dependent_on(self):
        return [
            'service_broadcasting',
            'service_blockchain',
        ]

    def installed(self):
        # TODO: to be continue...
        return False

    def start(self):
        from coins import coins_db
        from coins import accountant_node
        from coins import accountants_finder
        coins_db.init()
        accountants_finder.A('init')
        accountant_node.A('init')
        accountant_node.A('start')
        accountant_node.A().addStateChangedCallback(
            self._on_accountant_node_switched)
        return True

    def stop(self):
        from coins import coins_db
        from coins import accountant_node
        accountant_node.A().removeStateChangedCallback(
            self._on_accountant_node_switched)
        accountant_node.A('stop')
        accountant_node.A('shutdown')
        coins_db.shutdown()
        return True

    def request(self, json_payload, newpacket, info):
        from logs import lg
        from p2p import p2p_service
        # words = newpacket.Payload.split(' ')
        try:
            # mode = words[1][:10]
            mode = json_payload['action']
        except:
            lg.exc()
            return p2p_service.SendFail(newpacket, "invalid json payload")
        if mode != 'join' and mode != 'write' and mode != 'read':
            lg.out(8, "service_accountant.request DENIED, wrong mode provided : %s" % mode)
            return p2p_service.SendFail(newpacket, "invalid request")
        from coins import accountant_node
        if not accountant_node.A():
            lg.out(8, "service_accountant.request DENIED, accountant_node() state machine not exist")
            return p2p_service.SendFail(newpacket, "accountant_node service not started")
        # if accountant_node.A().state not in ['ACCOUNTANTS?', "READY", "VALID_COIN?", "WRITE_COIN!", ]:
        #     lg.out(8, "service_accountant.request DENIED, accountant_node() state is : %s" % accountant_node.A().state)
        # return p2p_service.SendFail(request, "accountant_node service
        # currently unavailable")
        if mode == 'join':
            accountant_node.A('accountant-connected', newpacket.OwnerID)
#             if accountant_node.A().state == 'OFFLINE':
#                 accountant_node.A('start')
            return p2p_service.SendAck(newpacket, 'accepted')
        return p2p_service.SendFail(newpacket, 'bad request')

    def health_check(self):
        from coins import accountant_node
        return accountant_node.A().state in [
            'READY', 'READ_COINS', 'VALID_COIN?', 'WRITE_COIN!', ]

    def _on_accountant_node_switched(self, oldstate, newstate, evt, *args, **kwargs):
        from logs import lg
        from twisted.internet import reactor  # @UnresolvedImport
        from coins import accountant_node
        if newstate == 'OFFLINE' and oldstate != 'AT_STARTUP':
            reactor.callLater(10 * 60, accountant_node.A, 'start')  # @UndefinedVariable
            lg.out(8, 'service_broadcasting._on_accountant_node_switched will try to reconnect again after 10 minutes')
