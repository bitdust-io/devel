#!/usr/bin/python
# contract_chain_node.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

from twisted.internet.defer import Deferred, DeferredList, succeed, fail

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


def get_coin_by_hash(hash_id):
    """
    """
    if not is_connected():
        return succeed(None)
    return Query(dict(
        method='get',
        index='hash',
        key=hash_id,
    )).result


def get_coins_by_chain(chain, provider_idurl, consumer_idurl):
    """
    """
    if not is_connected():
        return succeed(None)
    return Query(dict(
        method='get_many',
        index=chain,
        key='%s_%s' % (provider_idurl, consumer_idurl, ),
    )).result


def send_to_miner(coins):
    """
    """
    if not is_connected():
        return succeed(None)
    result = Deferred()
    p2p_service.SendCoin(
        contract_chain_consumer.A().connected_miner,
        coins,
        callbacks={
            commands.Ack(): lambda response, info: result.callback(response),
            commands.Fail(): lambda response, info: result.errback(Exception(response)),
        }
    )
    return result

#------------------------------------------------------------------------------

class Query(object):

    def __init__(self, query_dict):
        """
        """
        self.result = Deferred()
        self.out_packets = {}
        for idurl in contract_chain_consumer.A().connected_accountants:
            single_accountant = Deferred()
            outpacket = p2p_service.SendRetrieveCoin(idurl, query_dict, callbacks={
                commands.Coin(): self._on_coin_received,
                commands.Fail(): self._on_coin_failed,
            })
            assert outpacket.PacketID not in self.out_packets
            self.out_packets[outpacket.PacketID] = single_accountant
        DeferredList(list(self.out_packets.values())).addBoth(self._on_results_collected)
        if _Debug:
            lg.out(_DebugLevel, 'contract_chain_node.Query created to request from %d accountants' % len(self.out_packets))

    def __del__(self):
        """
        """
        if _Debug:
            lg.out(_DebugLevel, 'contract_chain_node.Query object destoryed')

    def _close(self):
        """
        """
        self.result = None
        self.out_packets.clear()

    def _on_coin_received(self, response_packet, info):
        """
        """
        if _Debug:
            lg.out(_DebugLevel, 'contract_chain_node._on_coin_received %r' % response_packet)
        assert response_packet.PacketID in self.out_packets
        self.out_packets[response_packet.PacketID].callback((response_packet.CreatorID, response_packet, ))

    def _on_coin_failed(self, response_packet, info):
        """
        """
        if _Debug:
            lg.out(_DebugLevel, 'contract_chain_node._on_coin_failed %r' % response_packet)
        assert response_packet.PacketID in self.out_packets
        self.out_packets[response_packet.PacketID].callback((response_packet.CreatorID, None, ))

    def _on_results_collected(self, accountant_results):
        """
        """
        fails = {}
        unique_coins = {}
        for success, result_tuple in accountant_results:
            accountant_idurl, response_packet = result_tuple
            if not success:
                fails[accountant_idurl] = fails.get(accountant_idurl, 0) + 1
                continue
            if response_packet is None:
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
        if not unique_coins:
            if _Debug:
                lg.out(_DebugLevel, 'contract_chain_node._on_results_collected : NO COINS FOUND')
            self.result.callback([])
            self._close()
            return None
        if fails:
            lg.warn('conflicting results from accountants: %s' % fails)
            # TODO: find some simple way to establish consensus between accountants
            # if one accountant is cheating or failing, coins from his machine must be filtered out
            # probably here we can trigger a process to replace bad accountants
            self.result.errback(Exception(str(fails)))
            self._close()
            return None
        if _Debug:
            lg.out(_DebugLevel, 'contract_chain_node._on_results_collected : %d COINS FOUND' % len(unique_coins))
        self.result.callback(list(unique_coins.values()))
        return None
