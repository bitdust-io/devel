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

from twisted.internet.defer import Deferred, DeferredList, succeed

#------------------------------------------------------------------------------

from logs import lg

from p2p import commands
from p2p import p2p_service

from coins import coins_io
from coins import contract_chain_consumer

#------------------------------------------------------------------------------

def reconnect():
    """
    """
    contract_chain_consumer.A('start')


def is_connected():
    """
    """
    if contract_chain_consumer.A() is None:
        lg.warn('contract_chain_consumer() not exist')
        return False
    if contract_chain_consumer.A().state != 'CONNECTED':
        if _Debug:
            lg.out(_DebugLevel, 'contract_chain_node._connected OFFLINE, nodes connection is not ready: %s' % contract_chain_consumer.A())
        return False
    return True


def send_query_to_accountants(query_dict):
    """
    """
    result = Deferred()
    defer_list = []
    for idurl in contract_chain_consumer.A().connected_accountants:
        single_accountant = Deferred()
        p2p_service.SendRetreiveCoin(idurl, query_dict, callbacks={
            commands.Coin(): lambda response_packet, info:
                single_accountant.callback((idurl, response_packet, )) if not single_accountant.called else None,
            commands.Fail(): lambda response_packet, info:
                single_accountant.callback((idurl, None, )) if not single_accountant.called else None,
        })
        defer_list.append(single_accountant)
    DeferredList(defer_list).addBoth(result.callback)
    return result


def collect_query_responses(accountant_results):
    """
    """
    fails = {}
    unique_coins = {}
    for success, result_tuple in accountant_results:
        accountant_idurl, response_packet = result_tuple
        if not success:
            fails[accountant_idurl] = fails.get(accountant_idurl, 0) + 1
            continue
        if not response_packet:
            fails[accountant_idurl] = fails.get(accountant_idurl, 0) + 1
            continue
        coins_list = coins_io.read_coins_from_packet(response_packet)
        if not coins_list:
            fails[accountant_idurl] = fails.get(accountant_idurl, 0) + 1
            continue
        for coin in coins_list:
            coin_hash = coin['miner']['hash']
            if coin_hash not in unique_coins:
                unique_coins[coin_hash] = coin
            if coins_io.coin_to_string(unique_coins[coin_hash]) != coins_io.coin_to_string(coin):
                fails[accountant_idurl] = fails.get(accountant_idurl, 0) + 1
    if fails:
        lg.warn('got failed or conflicting results from accountants: %s' % fails)
        # TODO: find some simple way to compare results and rich consensus between accountants
    return unique_coins.values()


def get_coin_by_hash(hash_id):
    """
    """
    if not is_connected():
        return succeed(None)
    query = dict(
        method='get',
        index='hash',
        key=hash_id,
    )
    result = Deferred()
    send_query_to_accountants(query).addBoth(
        lambda accountant_responses: result.callback(
            collect_query_responses(accountant_responses),
        )
    )
    return result


def get_coins_by_chain(provider_idurl, consumer_idurl):
    """
    """
    if not is_connected():
        return succeed(None)
    query = dict(
        method='get_many',
        index='chain_id',
        key='%s_%s' % (provider_idurl, consumer_idurl, ),
    )
    result = Deferred()
    send_query_to_accountants(query).addBoth(
        lambda accountant_responses: result.callback(
            collect_query_responses(accountant_responses),
        )
    )
    return result


def walk_coins():
    """
    """


def mine_coin():
    """
    """
    if not is_connected():
        return None
    contract_chain_consumer.A().connected_miner
