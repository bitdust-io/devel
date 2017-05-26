#!/usr/bin/python
# coins_index.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (coins_index.py) is part of BitDust Software.
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

module:: coins_index
"""

#------------------------------------------------------------------------------

_Debug = True

#------------------------------------------------------------------------------

import os

from hashlib import md5

from CodernityDB.hash_index import HashIndex
from CodernityDB.tree_index import TreeBasedIndex

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import sys
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

#------------------------------------------------------------------------------

_orig_read_index_single = None
_orig_add_single_index = None
_orig_write_index = None

def _fake_read_index_single(slf, p, ind, ind_kwargs={}):
    global _orig_read_index_single
    p = os.path.join(bpio.getExecutableDir(), 'coins', '_indexes')
    return _orig_read_index_single(slf, p, ind, ind_kwargs)

def _fake_add_single_index(slf, p, i, index):
    return True

def _fake_write_index(slf, new_index, number=0, edit=False, ind_kwargs=None):
    p = os.path.join(bpio.getExecutableDir(), 'coins', '_indexes')
    return _fake_read_index_single(slf, p, ), _fake_read_index_single.name

def patch_CodernityDB():
    global _orig_read_index_single
    global _orig_add_single_index
    global _orig_write_index
    from CodernityDB import database
    _orig_read_index_single = database.Database._read_index_single
    database.Database._read_index_single = _fake_read_index_single
    # _orig_add_single_index = database.Database._add_single_index
    # database.Database._add_single_index = _fake_add_single_index
    # _orig_write_index = getattr(database.Database, '__write_index')
    # setattr(database.Database, '__write_index', _fake_write_index)

#------------------------------------------------------------------------------

def definitions():
    return [
        ('creator', Creator, ),
        ('signer', Signer, ),
        ('miner', Miner, ),
        ('hash', HashID, ),
        ('prev', PrevHashID, ),
        ('supplier_customer', SupplierCustomer, ),
        ('time_created', TimeCreated, ),
        ('time_signed', TimeSigned, ),
        ('time_mined', TimeMined, ),
    ]

#------------------------------------------------------------------------------

def make_customer_header():
    src = '\n'
    src += 'from CodernityDB.hash_index import HashIndex\n'
    src += 'from CodernityDB.tree_index import TreeBasedIndex\n'
    src += 'from coins.coins_index import AbstractHashIndexByRole\n'
    src += 'from coins.coins_index import AbstractMD5IndexByRole\n'
    src += 'from coins.coins_index import AbstractMD5IndexByChain\n'
    src += 'from coins.coins_index import AbstractTimeIndex\n'
    src += 'from coins.coins_index import make_customer_header\n\n'
    return src

#------------------------------------------------------------------------------

class AbstractHashIndexByRole(HashIndex):
    role = None
    field = None
    key_format = '16s'

    def __init__(self, *args, **kwargs):
        kwargs['key_format'] = self.key_format
        super(AbstractHashIndexByRole, self).__init__(*args, **kwargs)

    def transform_key(self, key):
        return key

    def make_key_value(self, data):
        try:
            return self.transform_key(data[self.role][self.field]), None
        except (AttributeError, ValueError, KeyError, IndexError, ):
            return None
        except Exception:
            lg.exc()

    def make_key(self, key):
        return self.transform_key(key)

#------------------------------------------------------------------------------

class AbstractMD5IndexByRole(AbstractHashIndexByRole):

    def transform_key(self, key):
        return md5(key).digest()

#------------------------------------------------------------------------------

class AbstractMD5IndexByChain(HashIndex):
    producer_role = None
    consumer_role = None

    def __init__(self, *args, **kwargs):
        kwargs['key_format'] = '16s'
        super(AbstractMD5IndexByChain, self).__init__(*args, **kwargs)

    def make_key_value(self, data):
        try:
            chain_id = '%s_%s' % (
                data['payload'][self.producer_role],
                data['payload'][self.consumer_role],
            )
            return md5(chain_id).digest(), None
        except (AttributeError, ValueError, KeyError, IndexError, ):
            return None
        except Exception:
            lg.exc()

    def make_key(self, key):
        return md5(key).digest()

#------------------------------------------------------------------------------

class AbstractTimeIndex(TreeBasedIndex):
    role = None

    def __init__(self, *args, **kwargs):
        kwargs['key_format'] = 'I'
        kwargs['node_capacity'] = 128
        super(AbstractTimeIndex, self).__init__(*args, **kwargs)

    def make_key(self, key):
        return key

    def make_key_value(self, data):
        try:
            return data[self.role]['time'], None
        except (ValueError, KeyError, IndexError, ):
            return None
        except Exception:
            lg.exc()

#------------------------------------------------------------------------------

class Creator(AbstractMD5IndexByRole):
    custom_header = make_customer_header()
    role = 'creator'
    field = 'idurl'

#------------------------------------------------------------------------------

class Signer(AbstractMD5IndexByRole):
    custom_header = make_customer_header()
    role = 'signer'
    field = 'idurl'

#------------------------------------------------------------------------------

class Miner(AbstractMD5IndexByRole):
    custom_header = make_customer_header()
    role = 'miner'
    field = 'idurl'

#------------------------------------------------------------------------------

class HashID(AbstractHashIndexByRole):
    custom_header = make_customer_header()
    role = 'miner'
    field = 'hash'
    key_format = '40s'

#------------------------------------------------------------------------------

class PrevHashID(AbstractHashIndexByRole):
    custom_header = make_customer_header()
    role = 'miner'
    field = 'prev'
    key_format = '40s'

#------------------------------------------------------------------------------

class SupplierCustomer(AbstractMD5IndexByChain):
    custom_header = make_customer_header()
    producer_role = 'supplier'
    consumer_role = 'customer'

#------------------------------------------------------------------------------

class TimeCreated(AbstractTimeIndex):
    custom_header = make_customer_header()
    role = 'creator'

#------------------------------------------------------------------------------

class TimeSigned(AbstractTimeIndex):
    custom_header = make_customer_header()
    role = 'signer'

#------------------------------------------------------------------------------

class TimeMined(AbstractTimeIndex):
    custom_header = make_customer_header()
    role = 'miner'
