#!/usr/bin/python
# contract_chain_node.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (contract_chain_node.py) is part of BitDust Software.
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

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

from twisted.internet.defer import Deferred, DeferredList

#------------------------------------------------------------------------------ 

from logs import lg

from p2p import commands
from p2p import p2p_service

from coins import contract_chain_consumer

#------------------------------------------------------------------------------

def reconnect():
    contract_chain_consumer.A('start')


def is_connected():
    if contract_chain_consumer.A() is None:
        lg.warn('contract_chain_consumer() not exist')
        return False
    if contract_chain_consumer.A().state != 'CONNECTED':
        if _Debug:
            lg.out(_DebugLevel, 'contract_chain_node._connected OFFLINE, nodes connection is not ready: %s' % contract_chain_consumer.A())
        return False
    return True

def get_coin(hash_id):
    result = Deferred()
    if not is_connected():
        result.callback(None)
        return result
    query = dict(method='get', index='hash_id', key='hash_id')
    defer_list = []
    for idurl in contract_chain_consumer.A().connected_accountants:
        single_accountant = Deferred()
        p2p_service.SendRetreiveCoin(idurl, query, callbacks={
            commands.Coin(): single_accountant.callback(lambda response_packet, info: (idurl, response_packet)),
            commands.Fail(): single_accountant.callback(lambda response_packet, info: (idurl, None)),
        })
        defer_list.append(single_accountant)
    DeferredList(defer_list).addBoth(result.callback)
    return result

def get_coins():
    pass


def walk_coins():
    pass


def mine_coin():
    if not is_connected():
        return None
    contract_chain_consumer.A().connected_miner
