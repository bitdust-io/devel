#!/usr/bin/python
# coins_io.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (coins_io.py) is part of BitDust Software.
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

module:: coins_io

Every "contract" store a list of "coins", they form a single "chain" in the global DB
This is similar to well-known "blockchain" technology where every block is linked to another by hash.

"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True

#------------------------------------------------------------------------------

import os
import json
from collections import OrderedDict
from hashlib import md5

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import sys
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from lib import utime

from crypt import key

from userid import my_id


#------------------------------------------------------------------------------

def storage_contract_open(customer_idurl, duration, amount, price=1.0, trustee=None):
    """
    + type of resources: storage space (can be also : cpu, traffic, etc.)
    + amount: in megabytes
    + duration: seconds
    + customer: idurl of consumer
    + supplier: idurl of provider
    + trustee: idurl of trusted supporter
    + started: seconds since epoch
    + price: 1.0 by default
    """
    return {
        "miner": {
            "prev": "",
        },
        "payload": {
            "type": "storage",
            "amount": amount,
            "duration": duration,
            "customer": customer_idurl,
            "supplier": my_id.getLocalID(),
            "trustee": trustee,
            "started": utime.utcnow_to_sec1970(),
            "price": price,
        },
    }


def storage_contract_accept(prev_coin_json):
    """
    """
    return {
        "miner": {
            # populate previous hash from existing coin
            "prev": prev_coin_json['miner']['hash'],
        },
        "payload": {
            "accepted": utime.utcnow_to_sec1970(),
        },
    }


def storage_contract_continue(prev_coin_json, duration):
    """
    """
    return {
        "miner": {
            # populate previous hash from existing coin
            "prev": prev_coin_json['miner']['hash'],
        },
        "payload": {
            "extended": utime.utcnow_to_sec1970(),
            "duration": duration,
        },
    }


def add_signature(coin_json, role):
    """
    """
    _coin = coin_json.copy()
    _coin[role] = {
        'idurl': my_id.getLocalID(),
        'pubkey': key.MyPublicKey(),
    }
    coin_hash = get_coin_hash(_coin)
    _coin[role]['signature'] = key.Sign(coin_hash)
    return _coin


def verify_signature(coin_json, role):
    """
    """
    signature = coin_json[role]['signature']
    coin_json[role]['signature'] = ''
    # role_data = coin_json[role].copy()
    # signature = role_data.pop('signature')
    # _coin = dict(coin_json).c
    coin_hash = get_coin_hash(coin_json)
    coin_json[role]['signature'] = signature
    return key.VerifySignature(coin_json[role]['pubkey'], coin_hash, signature)


def set_prev_hash(coin_json, prev_hash):
    """
    """
    if 'miner' not in coin_json:
        coin_json['miner'] = {}
    coin_json['miner']['prev'] = prev_hash
    return coin_json



# def signed_coin(coin_json):
#     scoin = {
#         "creator": my_id.getLocalID(),
#         "pubkey": key.MyPublicKey(),
#     }
#     scoin.update(coin_json)
#     chash = get_coin_hash(scoin)
#     signature = key.Sign(chash)
#     scoin['signature'] = signature
#     return scoin


def coin_to_string(coin_json):
    return json.dumps(coin_json, sort_keys=True)

def coins_to_string(coins_list):
    return json.dumps(coins_list, sort_keys=True)


def string_to_coin(s):
    return json.loads(s)


def get_coin_hash(coin_json):
    coin_hashbase = coin_to_string(coin_json)
    return key.Hash(coin_hashbase, hexdigest=True)


def get_coin_base(coin_json):
    return coin_json
#     bcoin = coin_json.copy()
#     bcoin.pop('creator')
#     bcoin.pop('signature')
#     bcoin.pop('pubkey')
#     return bcoin


def bought_storage(partner, ):
    pass


#------------------------------------------------------------------------------

def read_query_from_packet(newpacket):
    try:
        query_j = json.loads(newpacket.Payload)
    except:
        lg.exc()
        return None
    # TODO: verify input query fields
    return query_j


def read_coins_from_packet(newpacket):
    try:
        coins_list = json.loads(newpacket.Payload)
    except:
        lg.exc()
        return None
    # TODO: verify all input coins here
    return coins_list

#------------------------------------------------------------------------------

def validate_coin(coin_json):
    # TODO: validate sub-fields, hashes, query on DB, etc.
    # if 'miner' not in coin_json:
    #     return False
    if 'creator' not in coin_json:
        return False
    if 'signature' not in coin_json['creator']:
        return False
    # if 'signer' not in coin_json:
    #     return False
    if 'payload' not in coin_json:
        return False
    return True


def verify_coin(coin_json, role):
    # TODO: check coin was really mined
    # if coin_json['hash'] != calculated_hash:
    #     return False
    return True

#------------------------------------------------------------------------------

#------------------------------------------------------------------------------


def _test():
    pass


if __name__ == "__main__":
    lg.set_debug_level(20)
    _test()
