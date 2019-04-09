#!/usr/bin/python
# miner.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (miner.py) is part of BitDust Software.
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
.. module:: miner.

Data to be store in global "coins" storage:

For example this should be written for a coin mined by supplier to declare storage sharing:

    + signer: idurl of this node
    + partner: idurl of given customer
    + type: storage (can be also : cpu, traffic, hosting, etc.)
    + start: time in UTC
    + end: time in UTC
    + amount: in megabytes
    + price: 1.0 by default


Customer in opposite will mine such "coins":

    + signer: idurl of this node
    + partner: idurl of supplier
    + type: storage
    + start: time in UTC
    + end: time in UTC
    + amount: in megabytes
    + quality: 1.0 if supplier passed all validation tests for this period


So we have a contract between customer and supplier and both sides declare periodically how it is going
by "mining" a safe "crypto-coins" and put some details into the coin.


We have also "status coins" or "ping coins". When a node get connected to other node it first sends a Identity
packet to "ping" remote side and waits for Ack packet in response. A correct Ack means that remote side is
online at the moment. So we want to declare that info to be able to keep track of how long this node
was online in the past and so how reliable he was.
So the first node will mine a "ping coin" and put such info into it:

    + signer: idurl of this node
    + partner: idurl of remote node
    + type: ack
    + start: time in UTC when he sent Identity packet to remote peer
    + end: time in UTC when he receives Ack packet from remote peer

And remote node should declare that as well to confirm this, this is sort of "pong coin":

    + signer: idurl of this node
    + partner: idurl of the first node who send a "ping" packet
    + type: identity
    + start: time in UTC when this node receives a packet
    + end: <empty>
"""

from __future__ import absolute_import
_Debug = False
_DebugLevel = 14

#------------------------------------------------------------------------------

import datetime

#------------------------------------------------------------------------------

from coins import mine

#------------------------------------------------------------------------------

_CoinsMinerNode = None
_MyStartedContracts = []
_MyFinishedContracts = []

#------------------------------------------------------------------------------


def node():
    global _CoinsMinerNode
    return _CoinsMinerNode


def started_contracts():
    global _MyStartedContracts
    return _MyStartedContracts


def finished_contracts():
    global _MyFinishedContracts
    return _MyFinishedContracts

#------------------------------------------------------------------------------


def init():
    global _CoinsMinerNode
    if _CoinsMinerNode:
        return
    _CoinsMinerNode = CoinsMinerNode()


def shutdown():
    global _CoinsMinerNode
    if _CoinsMinerNode is None:
        return
    del _CoinsMinerNode
    _CoinsMinerNode = None

#------------------------------------------------------------------------------


def inbox_packet(newpacket, info, status, error_message):
    if status != 'finished':
        return False
    if not node():
        return False
    return node().inbox_packet(newpacket, info)

#------------------------------------------------------------------------------


def start_contract(typ, partner):
    contract = Contract(
        type=typ,
        partner=partner,
        start=datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        end=None,
    )
    started_contracts(contract)


def finish_contract(typ, partner, **kwargs):
    found = None
    for contract in started_contracts():
        if contract.type == typ and contract.partner == partner:
            found = contract
            break
    if not found:
        return False
    started_contracts().remove(found)
    found.end = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    for key, value in kwargs.items():
        setattr(found, key, value)
    finished_contracts().append(found)

#------------------------------------------------------------------------------


class Contract(object):

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

#------------------------------------------------------------------------------


class CoinsMinerNode(object):

    def inbox_packet(self, newpacket, info):
        return False

    def mine_and_send(self, data):
        from transport import gateway
        outpacket = ''
        gateway.outbox(outpacket)
