#!/usr/bin/python
# coins_io.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
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
.. module:: coins_io

"""

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
    sys.path.insert(
        0, _p.abspath(
            _p.join(
                _p.dirname(
                    _p.abspath(
                        sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from lib import utime

from crypt import key

from userid import my_id


#------------------------------------------------------------------------------

def storage_contract_open(customer_idurl, duration, amount, price=1.0):
    """
    + signer: idurl of this node
    + partner: idurl of given customer
    + type: sold_storage (can be also : buy_cpu, sell_traffic, buy_hosting, etc.)
    + duration: seconds
    + amount: in megabytes
    + price: 1.0 by default
    """
    coin = {
        "payload": {
            "type": "storage",
            "amount": amount,
            "price": price,
            "duration": duration,
            "customer": customer_idurl,
            "supplier": my_id.getLocalID(),
            "started": utime.utcnow_to_sec1970(),
        },
    }
    return signed_coin(coin)


def signed_coin(acoin):
    scoin = {
        "creator": my_id.getLocalID(),
        "pubkey": key.MyPublicKey(),
    }
    scoin.update(acoin)
    chash = get_coin_hash(scoin)
    signature = key.Sign(chash)
    scoin['signature'] = signature
    return scoin


def verify_coin_signature(scoin):
    acoin = scoin.copy()
    signature = acoin.pop('signature')
    chash = get_coin_hash(acoin)
    return key.VerifySignature(acoin.get('pubkey'), chash, signature)


def coin_to_string(acoin):
    return json.dumps(acoin, sort_keys=True)


def string_to_coin(s):
    return json.loads(s)


def get_coin_hash(acoin):
    coin_hashbase = coin_to_string(acoin)
    return key.Hash(coin_hashbase, hexdigest=True)


def get_coin_base(acoin):
    bcoin = acoin.copy()
    bcoin.pop('creator')
    bcoin.pop('signature')
    bcoin.pop('pubkey')
    return bcoin


def bought_storage(partner, ):
    pass


#------------------------------------------------------------------------------

def read_query_from_packet(newpacket):
    try:
        query_j = json.loads(newpacket.Payload)
    except:
        lg.exc()
        return None
    # TODO: verify query fields
    return query_j


def read_coins_from_packet(newpacket):
    try:
        coins_list = json.loads(newpacket.Payload)
    except:
        lg.exc()
        return None
    # TODO: verify coins
    return coins_list

#------------------------------------------------------------------------------


def validate_coin(acoin):
    # TODO: validate fields, hashes, query on DB, etc.
    if 'hash' not in acoin.keys():
        return False
    if 'tm' not in acoin.keys():
        return False
    if 'starter' not in acoin.keys():
        return False
    return True


def verify_coin(acoin):
    # TODO: check coin was really mined
    # if acoin['hash'] != calculated_hash:
    #     return False
    return True

#------------------------------------------------------------------------------

#------------------------------------------------------------------------------


def _test():
    pass


if __name__ == "__main__":
    lg.set_debug_level(20)
    _test()
